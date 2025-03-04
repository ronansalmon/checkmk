#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# TODO: Rework connection management and multiplexing
from __future__ import annotations

import ast
import copy
import os
import shutil
import time
import traceback
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from logging import Logger
from pathlib import Path
from typing import Any, Literal, TypeVar

from six import ensure_str

import cmk.utils.paths
import cmk.utils.store as store
import cmk.utils.version as cmk_version
from cmk.utils.crypto import Password, password_hashing
from cmk.utils.type_defs import ContactgroupName, UserId

import cmk.gui.hooks as hooks
import cmk.gui.pages
import cmk.gui.utils as utils
from cmk.gui.background_job import (
    BackgroundJob,
    BackgroundJobAlreadyRunning,
    BackgroundProcessInterface,
    InitialStatusArgs,
    job_registry,
)
from cmk.gui.config import active_config
from cmk.gui.ctx_stack import request_local_attr
from cmk.gui.exceptions import MKAuthException, MKInternalError, MKUserError
from cmk.gui.hooks import request_memoize
from cmk.gui.htmllib.html import html
from cmk.gui.http import request, response
from cmk.gui.i18n import _
from cmk.gui.log import logger as gui_logger
from cmk.gui.logged_in import LoggedInUser
from cmk.gui.plugins.userdb.utils import (
    active_connections,
    add_internal_attributes,
    get_connection,
    get_user_attributes,
    load_cached_profile,
    new_user_template,
    release_users_lock,
    save_cached_profile,
    user_attribute_registry,
    user_sync_config,
    UserAttribute,
    UserConnector,
)
from cmk.gui.site_config import is_wato_slave_site
from cmk.gui.type_defs import SessionInfo, TwoFactorCredentials, Users, UserSpec
from cmk.gui.userdb import user_attributes
from cmk.gui.userdb.htpasswd import Htpasswd
from cmk.gui.userdb.ldap_connector import MKLDAPException
from cmk.gui.utils.roles import roles_of_user
from cmk.gui.utils.urls import makeuri_contextless
from cmk.gui.valuespec import (
    DEF_VALUE,
    DropdownChoice,
    TextInput,
    ValueSpec,
    ValueSpecDefault,
    ValueSpecHelp,
    ValueSpecText,
)

auth_logger = gui_logger.getChild("auth")


def load_plugins() -> None:
    """Plugin initialization hook (Called by cmk.gui.main_modules.load_plugins())"""
    utils.load_web_plugins("userdb", globals())


# The saved configuration for user connections is a bit inconsistent, let's fix
# this here once and for all.
def _fix_user_connections() -> None:
    for cfg in active_config.user_connections:
        # Although our current configuration always seems to have a 'disabled'
        # entry, this might not have always been the case.
        cfg.setdefault("disabled", False)
        # Only migrated configurations have a 'type' entry, all others are
        # implictly LDAP connections.
        cfg.setdefault("type", "ldap")


# When at least one LDAP connection is defined and active a sync is possible
def sync_possible() -> bool:
    return any(connection.type() == "ldap" for _connection_id, connection in active_connections())


def locked_attributes(connection_id: str | None) -> list[str]:
    """Returns a list of connection specific locked attributes"""
    return _get_attributes(connection_id, lambda c: c.locked_attributes())


def multisite_attributes(connection_id: str | None) -> list[str]:
    """Returns a list of connection specific multisite attributes"""
    return _get_attributes(connection_id, lambda c: c.multisite_attributes())


def non_contact_attributes(connection_id: str | None) -> list[str]:
    """Returns a list of connection specific non contact attributes"""
    return _get_attributes(connection_id, lambda c: c.non_contact_attributes())


def _get_attributes(
    connection_id: str | None, selector: Callable[[UserConnector], list[str]]
) -> list[str]:
    connection = get_connection(connection_id)
    return selector(connection) if connection else []


def create_non_existing_user(connection_id: str, username: UserId, now: datetime) -> None:
    # Since user_exists also looks into the htpasswd and treats all users that can be found there as
    # "existing users", we don't care about partially known users here and don't create them ad-hoc.
    # The load_users() method will handle this kind of users (TODO: Consolidate this!).
    # Which makes this function basically relevant for users that authenticate using an LDAP
    # connection and do not exist yet.
    if user_exists(username):
        return  # User exists. Nothing to do...

    users = load_users(lock=True)
    users[username] = new_user_template(connection_id)
    save_users(users, now)

    # Call the sync function for this new user
    connection = get_connection(connection_id)
    try:
        if connection is None:
            raise MKUserError(None, _("Invalid user connection: %s") % connection_id)

        connection.do_sync(
            add_to_changelog=False,
            only_username=username,
            load_users_func=load_users,
            save_users_func=save_users,
        )
    except MKLDAPException as e:
        show_exception(connection_id, _("Error during sync"), e, debug=active_config.debug)
    except Exception as e:
        show_exception(connection_id, _("Error during sync"), e)


def is_customer_user_allowed_to_login(user_id: UserId) -> bool:
    if not cmk_version.is_managed_edition():
        return True

    try:
        import cmk.gui.cme.managed as managed  # pylint: disable=no-name-in-module
    except ImportError:
        return True

    user = LoggedInUser(user_id)
    if managed.is_global(user.customer_id):
        return True

    return managed.is_current_customer(user.customer_id)


# This function is called very often during regular page loads so it has to be efficient
# even when having a lot of users.
#
# When using the multisite authentication with just by WATO created users it would be
# easy, but we also need to deal with users which are only existant in the htpasswd
# file and don't have a profile directory yet.
def user_exists(username: UserId) -> bool:
    if _user_exists_according_to_profile(username):
        return True

    return Htpasswd(Path(cmk.utils.paths.htpasswd_file)).exists(username)


def _user_exists_according_to_profile(username: UserId) -> bool:
    base_path = cmk.utils.paths.profile_dir / username
    return base_path.joinpath("transids.mk").exists() or base_path.joinpath("serial.mk").exists()


def _check_login_timeout(username: UserId, idle_time: float) -> None:
    idle_timeout = load_custom_attr(
        user_id=username, key="idle_timeout", parser=_convert_idle_timeout
    )
    if idle_timeout is None:
        idle_timeout = active_config.user_idle_timeout
    if idle_timeout is not None and idle_timeout is not False and idle_time > idle_timeout:
        raise MKAuthException(f"{username} login timed out (Inactivity exceeded {idle_timeout})")


def _reset_failed_logins(username: UserId) -> None:
    """Login succeeded: Set failed login counter to 0"""
    num_failed_logins = _load_failed_logins(username)
    if num_failed_logins != 0:
        _save_failed_logins(username, 0)


def _load_failed_logins(username: UserId) -> int:
    num = load_custom_attr(user_id=username, key="num_failed_logins", parser=utils.saveint)
    return 0 if num is None else num


def _save_failed_logins(username: UserId, count: int) -> None:
    save_custom_attr(username, "num_failed_logins", str(count))


# userdb.need_to_change_pw returns either None or the reason description why the
# password needs to be changed
def need_to_change_pw(username: UserId, now: datetime) -> str | None:
    if not _is_local_user(username):
        return None
    if load_custom_attr(user_id=username, key="enforce_pw_change", parser=utils.saveint) == 1:
        return "enforced"
    last_pw_change = load_custom_attr(user_id=username, key="last_pw_change", parser=utils.saveint)
    max_pw_age = active_config.password_policy.get("max_age")
    if not max_pw_age:
        return None
    if not last_pw_change:
        # The age of the password is unknown. Assume the user has just set
        # the password to have the first access after enabling password aging
        # as starting point for the password period. This bewares all users
        # from needing to set a new password after enabling aging.
        save_custom_attr(username, "last_pw_change", str(int(now.timestamp())))
        return None
    if now.timestamp() - last_pw_change > max_pw_age:
        return "expired"
    return None


def is_two_factor_login_enabled(user_id: UserId) -> bool:
    """Whether or not 2FA is enabled for the given user"""
    return bool(load_two_factor_credentials(user_id)["webauthn_credentials"])


def disable_two_factor_authentication(user_id: UserId) -> None:
    credentials = load_two_factor_credentials(user_id, lock=True)
    credentials["webauthn_credentials"].clear()
    save_two_factor_credentials(user_id, credentials)


def is_two_factor_completed() -> bool:
    """Whether or not the user has completed the 2FA challenge"""
    return session.session_info.two_factor_completed


def set_two_factor_completed() -> None:
    session.session_info.two_factor_completed = True


def load_two_factor_credentials(user_id: UserId, lock: bool = False) -> TwoFactorCredentials:
    cred = load_custom_attr(
        user_id=user_id, key="two_factor_credentials", parser=ast.literal_eval, lock=lock
    )
    return TwoFactorCredentials(webauthn_credentials={}, backup_codes=[]) if cred is None else cred


def save_two_factor_credentials(user_id: UserId, credentials: TwoFactorCredentials) -> None:
    save_custom_attr(user_id, "two_factor_credentials", repr(credentials))


def make_two_factor_backup_codes() -> list[tuple[str, str]]:
    """Creates a set of new two factor backup codes

    The codes are returned in plain form for displaying and in hashed+salted form for storage
    """
    return [
        (password, password_hashing.hash_password(Password(password)))
        for password in (utils.get_random_string(10) for i in range(10))
    ]


def is_two_factor_backup_code_valid(user_id: UserId, code: str) -> bool:
    """Verifies whether or not the given backup code is valid and invalidates the code"""
    credentials = load_two_factor_credentials(user_id)
    matched_code = ""

    for stored_code in credentials["backup_codes"]:
        try:
            password_hashing.verify(Password(code), stored_code)
            matched_code = stored_code
            break
        except (password_hashing.PasswordInvalidError, ValueError):
            continue

    if not matched_code:
        return False

    # Invalidate the just used code
    credentials = load_two_factor_credentials(user_id, lock=True)
    credentials["backup_codes"].remove(matched_code)
    save_two_factor_credentials(user_id, credentials)

    return True


def load_user(user_id: UserId) -> UserSpec:
    """Loads of a single user profile

    This is called during regular page processing. We must not load the whole user database, because
    that would take too much time. To optimize this, we have the "cached user profile" files which
    are read normally when working with a single user.
    """
    user = load_cached_profile(user_id)
    if user is None:
        # No cached profile present. Load all users to get the users data
        user = load_users(lock=False).get(user_id, {})
        assert user is not None  # help mypy
    return user


def _is_local_user(user_id: UserId) -> bool:
    return load_user(user_id).get("connector", "htpasswd") == "htpasswd"


def user_locked(user_id: UserId) -> bool:
    return bool(load_user(user_id).get("locked"))


def _root_dir() -> str:
    return cmk.utils.paths.check_mk_config_dir + "/wato/"


def _multisite_dir() -> str:
    return cmk.utils.paths.default_config_dir + "/multisite.d/wato/"


# TODO: Change to factory
class UserSelection(DropdownChoice[UserId]):
    """Dropdown for choosing a multisite user"""

    def __init__(  # pylint: disable=redefined-builtin
        self,
        only_contacts: bool = False,
        only_automation: bool = False,
        none: str | None = None,
        # ValueSpec
        title: str | None = None,
        help: ValueSpecHelp | None = None,
        default_value: ValueSpecDefault[UserId] = DEF_VALUE,
    ) -> None:
        super().__init__(
            choices=self._generate_wato_users_elements_function(
                none, only_contacts=only_contacts, only_automation=only_automation
            ),
            invalid_choice="complain",
            title=title,
            help=help,
            default_value=default_value,
        )

    def _generate_wato_users_elements_function(  # type:ignore[no-untyped-def]
        self, none_value: str | None, only_contacts: bool = False, only_automation: bool = False
    ):
        def get_wato_users(nv: str | None) -> list[tuple[UserId | None, str]]:
            users = load_users()
            elements: list[tuple[UserId | None, str]] = sorted(
                [
                    (name, "{} - {}".format(name, us.get("alias", name)))
                    for (name, us) in users.items()
                    if (not only_contacts or us.get("contactgroups"))
                    and (not only_automation or us.get("automation_secret"))
                ]
            )
            if nv is not None:
                elements.insert(0, (None, nv))
            return elements

        return lambda: get_wato_users(none_value)

    def value_to_html(self, value: Any) -> ValueSpecText:
        return str(super().value_to_html(value)).rsplit(" - ", 1)[-1]


def on_succeeded_login(username: UserId, now: datetime) -> str:
    _ensure_user_can_init_session(username, now)
    _reset_failed_logins(username)
    return _initialize_session(username, now)


def on_failed_login(username: UserId, now: datetime) -> None:
    users = load_users(lock=True)
    if user := users.get(username):
        user["num_failed_logins"] = user.get("num_failed_logins", 0) + 1
        if active_config.lock_on_logon_failures:
            if user["num_failed_logins"] >= active_config.lock_on_logon_failures:
                user["locked"] = True
        save_users(users, now)

    if active_config.log_logon_failures:
        if user:
            existing = "Yes"
            log_msg_until_locked = str(
                bool(active_config.lock_on_logon_failures) - user["num_failed_logins"]
            )
            if not user.get("locked"):
                log_msg_locked = "No"
            elif log_msg_until_locked == "0":
                log_msg_locked = "Yes (now)"
            else:
                log_msg_locked = "Yes"
        else:
            existing = "No"
            log_msg_until_locked = "N/A"
            log_msg_locked = "N/A"
        auth_logger.warning(
            "Login failed for username: %s (existing: %s, locked: %s, failed logins until locked: %s), client: %s",
            username,
            existing,
            log_msg_locked,
            log_msg_until_locked,
            request.remote_ip,
        )


def on_logout(username: UserId, session_id: str) -> None:
    _invalidate_session(username, session_id)


def on_access(username: UserId, session_id: str, now: datetime) -> None:
    session_infos = _load_session_infos(username)
    if not _is_valid_user_session(username, session_infos, session_id):
        raise MKAuthException("Invalid user session")

    # Check whether or not there is an idle timeout configured, delete cookie and
    # require the user to renew the log when the timeout exceeded.
    session_info = session_infos[session_id]
    _check_login_timeout(username, now.timestamp() - session_info.last_activity)
    _set_session(username, session_info)


def on_end_of_request(user_id: UserId, now: datetime) -> None:
    if not session:
        return  # Nothing to be done in case there is no session

    assert user_id == session.user_id
    session_infos = _load_session_infos(user_id, lock=True)
    if session_infos:
        _refresh_session(session.session_info, now)
        session_infos[session.session_info.session_id] = session.session_info

    _save_session_infos(user_id, session_infos)


# .
#   .--User Session--------------------------------------------------------.
#   |       _   _                 ____                _                    |
#   |      | | | |___  ___ _ __  / ___|  ___  ___ ___(_) ___  _ __         |
#   |      | | | / __|/ _ \ '__| \___ \ / _ \/ __/ __| |/ _ \| '_ \        |
#   |      | |_| \__ \  __/ |     ___) |  __/\__ \__ \ | (_) | | | |       |
#   |       \___/|___/\___|_|    |____/ \___||___/___/_|\___/|_| |_|       |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | When single users sessions are activated, a user an only login once  |
#   | a time. In case a user tries to login a second time, an error is     |
#   | shown to the later login.                                            |
#   |                                                                      |
#   | To make this feature possible a session ID is computed during login, |
#   | saved in the users cookie and stored in the user profile together    |
#   | with the current time as "last activity" timestamp. This timestamp   |
#   | is updated during each user activity in the GUI.                     |
#   |                                                                      |
#   | Once a user logs out or the "last activity" is older than the        |
#   | configured session timeout, the session is invalidated. The user     |
#   | can then login again from the same client or another one.            |
#   '----------------------------------------------------------------------'


@dataclass
class Session:
    """Container object for encapsulating the session of the currently logged in user"""

    user_id: UserId
    session_info: SessionInfo


session: Session = request_local_attr("session")


def _is_valid_user_session(
    username: UserId, session_infos: dict[str, SessionInfo], session_id: str
) -> bool:
    """Return True in case this request is done with a currently valid user session"""
    if not session_infos:
        return False  # no session active

    if session_id not in session_infos:
        auth_logger.debug(
            "%s session_id %s not valid (logged out or timed out?)", username, session_id
        )
        return False

    return True


def _ensure_user_can_init_session(username: UserId, now: datetime) -> None:
    """When single user session mode is enabled, check that there is not another active session"""
    session_timeout = active_config.single_user_session
    if session_timeout is None:
        return  # No login session limitation enabled, no validation
    for session_info in _load_session_infos(username).values():
        idle_time = now.timestamp() - session_info.last_activity
        if idle_time <= session_timeout:
            auth_logger.debug(
                f"{username} another session is active (inactive for: {idle_time} seconds)"
            )
            raise MKUserError(None, _("Another session is active"))


def _initialize_session(username: UserId, now: datetime) -> str:
    """Creates a new user login session (if single user session mode is enabled) and
    returns the session_id of the new session."""
    session_infos = _cleanup_old_sessions(_load_session_infos(username, lock=True), now)

    session_id = _create_session_id()
    now_ts = int(now.timestamp())
    session_info = SessionInfo(
        session_id=session_id,
        started_at=now_ts,
        last_activity=now_ts,
        flashes=[],
    )

    _set_session(username, session_info)
    session_infos[session_id] = session_info

    # Save once right after initialization. It may be saved another time later, in case something
    # was modified during the request (e.g. flashes were added)
    _save_session_infos(username, session_infos)

    return session_id


def _set_session(user_id: UserId, session_info: SessionInfo) -> None:
    request_local_attr().session = Session(user_id=user_id, session_info=session_info)


def _cleanup_old_sessions(
    session_infos: Mapping[str, SessionInfo], now: datetime
) -> dict[str, SessionInfo]:
    """Remove invalid / outdated sessions

    In single user session mode all sessions are removed. In regular mode, the sessions are limited
    to 20 per user. Sessions with an inactivity > 7 days are also removed.
    """
    if active_config.single_user_session:
        # In single user session mode there is only one session allowed at a time. Once we
        # reach this place, we can be sure that we are allowed to remove all existing ones.
        return {}

    return {
        s.session_id: s
        for s in sorted(session_infos.values(), key=lambda s: s.last_activity, reverse=True)[:20]
        if now.timestamp() - s.last_activity < 86400 * 7
    }


def _create_session_id() -> str:
    """Creates a random session id for the user and returns it."""
    return utils.gen_id()


def _refresh_session(session_info: SessionInfo, now: datetime) -> None:
    """Updates the current session of the user"""
    session_info.last_activity = int(now.timestamp())


def _invalidate_session(username: UserId, session_id: str) -> None:
    session_infos = _load_session_infos(username, lock=True)
    with suppress(KeyError):
        del session_infos[session_id]
        _save_session_infos(username, session_infos)


def _save_session_infos(username: UserId, session_infos: dict[str, SessionInfo]) -> None:
    """Saves the sessions for the current user"""
    save_custom_attr(
        username, "session_info", repr({k: asdict(v) for k, v in session_infos.items()})
    )


def _load_session_infos(username: UserId, lock: bool = False) -> dict[str, SessionInfo]:
    """Returns the stored sessions of the given user"""
    return (
        load_custom_attr(
            user_id=username, key="session_info", parser=_convert_session_info, lock=lock
        )
        or {}
    )


def _convert_session_info(value: str) -> dict[str, SessionInfo]:
    if value == "":
        return {}

    if value.startswith("{"):
        return {k: SessionInfo(**v) for k, v in ast.literal_eval(value).items()}

    # Transform pre 2.0 values
    session_id, last_activity = value.split("|", 1)
    return {
        session_id: SessionInfo(
            session_id=session_id,
            # We don't have that information. The best guess is to use the last activitiy
            started_at=int(last_activity),
            last_activity=int(last_activity),
            flashes=[],
        ),
    }


def _convert_start_url(value: str) -> str:
    # TODO in Version 2.0.0 and 2.0.0p1 the value was written without repr(),
    # remove the if condition one day
    if value.startswith("'") and value.endswith("'"):
        return ast.literal_eval(value)
    return value


# .
#   .-Users----------------------------------------------------------------.
#   |                       _   _                                          |
#   |                      | | | |___  ___ _ __ ___                        |
#   |                      | | | / __|/ _ \ '__/ __|                       |
#   |                      | |_| \__ \  __/ |  \__ \                       |
#   |                       \___/|___/\___|_|  |___/                       |
#   |                                                                      |
#   +----------------------------------------------------------------------+


class GenericUserAttribute(UserAttribute):
    def __init__(
        self,
        user_editable: bool,
        show_in_table: bool,
        add_custom_macro: bool,
        domain: str,
        permission: str | None,
        from_config: bool,
    ) -> None:
        super().__init__()
        self._user_editable = user_editable
        self._show_in_table = show_in_table
        self._add_custom_macro = add_custom_macro
        self._domain = domain
        self._permission = permission
        self._from_config = from_config

    def from_config(self) -> bool:
        return self._from_config

    def user_editable(self) -> bool:
        return self._user_editable

    def permission(self) -> None | str:
        return self._permission

    def show_in_table(self) -> bool:
        return self._show_in_table

    def add_custom_macro(self) -> bool:
        return self._add_custom_macro

    def domain(self) -> str:
        return self._domain

    @classmethod
    def is_custom(cls) -> bool:
        return False


def load_contacts() -> dict[str, Any]:
    return store.load_from_mk_file(_contacts_filepath(), "contacts", {})


def _contacts_filepath() -> str:
    return _root_dir() + "contacts.mk"


@request_memoize()
def load_users(lock: bool = False) -> Users:  # pylint: disable=too-many-branches
    if lock:
        # Note: the lock will be released on next save_users() call or at
        #       end of page request automatically.
        store.aquire_lock(_contacts_filepath())

    # First load monitoring contacts from Checkmk's world. If this is
    # the first time, then the file will be empty, which is no problem.
    # Execfile will the simply leave contacts = {} unchanged.
    # ? exact type of keys and items returned from load_mk_file seems to be unclear
    contacts = load_contacts()

    # Now load information about users from the GUI config world
    # ? can users dict be modified in load_mk_file function call and the type of keys str be changed?
    users = store.load_from_mk_file(_multisite_dir() + "users.mk", "multisite_users", {})

    # Merge them together. Monitoring users not known to Multisite
    # will be added later as normal users.
    result = {}
    for uid, user in users.items():
        # Transform user IDs which were stored with a wrong type
        uid = ensure_str(uid)  # pylint: disable= six-ensure-str-bin-call

        profile = contacts.get(uid, {})
        profile.update(user)
        result[uid] = profile

        # Convert non unicode mail addresses
        if "email" in profile:
            profile["email"] = ensure_str(  # pylint: disable= six-ensure-str-bin-call
                profile["email"]
            )

    # This loop is only neccessary if someone has edited
    # contacts.mk manually. But we want to support that as
    # far as possible.
    for uid, contact in contacts.items():

        if uid not in result:
            result[uid] = contact
            result[uid]["roles"] = ["user"]
            result[uid]["locked"] = True
            result[uid]["password"] = ""

    # Passwords are read directly from the apache htpasswd-file.
    # That way heroes of the command line will still be able to
    # change passwords with htpasswd. Users *only* appearing
    # in htpasswd will also be loaded and assigned to the role
    # they are getting according to the multisite old-style
    # configuration variables.

    htpwd_entries = Htpasswd(Path(cmk.utils.paths.htpasswd_file)).load(allow_missing_file=True)
    for uid, password in htpwd_entries.items():
        if password.startswith("!"):
            locked = True
            password = password[1:]
        else:
            locked = False

        if uid in result:
            result[uid]["password"] = password
            result[uid]["locked"] = locked
        else:
            # Create entry if this is an admin user
            new_user = UserSpec(
                roles=roles_of_user(uid),
                password=password,
                locked=False,
                connector="htpasswd",
            )

            add_internal_attributes(new_user)

            result[uid] = new_user
        # Make sure that the user has an alias
        result[uid].setdefault("alias", uid)

    # Now read the serials, only process for existing users
    serials_file = Path(cmk.utils.paths.htpasswd_file).with_name("auth.serials")
    try:
        for line in serials_file.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                user_id, serial = line.split(":")[:2]
                if user_id in result:
                    result[user_id]["serial"] = utils.saveint(serial)
    except OSError:  # file not found
        pass

    attributes: list[tuple[str, Callable]] = [
        ("num_failed_logins", utils.saveint),
        ("last_pw_change", utils.saveint),
        ("enforce_pw_change", lambda x: bool(utils.saveint(x))),
        ("idle_timeout", _convert_idle_timeout),
        ("session_info", _convert_session_info),
        ("start_url", _convert_start_url),
        ("ui_theme", lambda x: x),
        ("two_factor_credentials", ast.literal_eval),
        ("ui_sidebar_position", lambda x: None if x == "None" else x),
    ]

    # Now read the user specific files
    directory = cmk.utils.paths.var_dir + "/web/"
    for uid in os.listdir(directory):
        if uid[0] != ".":

            # read special values from own files
            if uid in result:
                for attr, conv_func in attributes:
                    val = load_custom_attr(user_id=uid, key=attr, parser=conv_func)
                    if val is not None:
                        result[uid][attr] = val

            # read automation secrets and add them to existing
            # users or create new users automatically
            try:
                user_secret_path = Path(directory) / uid / "automation.secret"
                with user_secret_path.open(encoding="utf-8") as f:
                    secret: str | None = f.read().strip()
            except OSError:
                secret = None

            if secret:
                if uid in result:
                    result[uid]["automation_secret"] = secret
                else:
                    result[uid] = {
                        "roles": ["guest"],
                        "automation_secret": secret,
                    }

    return result


def custom_attr_path(userid: UserId, key: str) -> str:
    return cmk.utils.paths.var_dir + "/web/" + userid + "/" + key + ".mk"


T = TypeVar("T")


def load_custom_attr(
    *,
    user_id: UserId,
    key: str,
    parser: Callable[[str], T],
    lock: bool = False,
) -> T | None:
    result = store.load_text_from_file(Path(custom_attr_path(user_id, key)), lock=lock)
    return None if result == "" else parser(result.strip())


def save_custom_attr(userid: UserId, key: str, val: Any) -> None:
    path = custom_attr_path(userid, key)
    store.mkdir(os.path.dirname(path))
    store.save_text_to_file(path, "%s\n" % val)


def remove_custom_attr(userid: UserId, key: str) -> None:
    try:
        os.unlink(custom_attr_path(userid, key))
    except OSError:
        pass  # Ignore non existing files


def get_online_user_ids(now: datetime) -> list[UserId]:
    online_threshold = now.timestamp() - active_config.user_online_maxage
    return [
        user_id
        for user_id, user in load_users(lock=False).items()
        if get_last_activity(user) >= online_threshold
    ]


def get_last_activity(user: UserSpec) -> int:
    return max([s.last_activity for s in user.get("session_info", {}).values()] + [0])


def split_dict(d: Mapping[str, Any], keylist: list[str], positive: bool) -> dict[str, Any]:
    return {k: v for k, v in d.items() if (k in keylist) == positive}


def save_users(profiles: Users, now: datetime) -> None:
    write_contacts_and_users_file(profiles)

    # Execute user connector save hooks
    hook_save(profiles)

    updated_profiles = _add_custom_macro_attributes(profiles)

    _save_auth_serials(updated_profiles)
    _save_user_profiles(updated_profiles, now)
    _cleanup_old_user_profiles(updated_profiles)

    # Release the lock to make other threads access possible again asap
    # This lock is set by load_users() only in the case something is expected
    # to be written (like during user syncs, wato, ...)
    release_users_lock()

    # Invalidate the users memoized data
    # The magic attribute has been added by the lru_cache decorator.
    load_users.cache_clear()  # type: ignore[attr-defined]

    # Call the users_saved hook
    hooks.call("users-saved", updated_profiles)


# TODO: Isn't this needed only while generating the contacts.mk?
#       Check this and move it to the right place
def _add_custom_macro_attributes(profiles: Users) -> Users:
    updated_profiles = copy.deepcopy(profiles)

    # Add custom macros
    core_custom_macros = {
        name for name, attr in get_user_attributes() if attr.add_custom_macro()  #
    }
    for user in updated_profiles.keys():
        for macro in core_custom_macros:
            if macro in updated_profiles[user]:
                # UserSpec is now a TypedDict, unfortunately not complete yet,
                # thanks to such constructs.
                updated_profiles[user]["_" + macro] = updated_profiles[user][macro]  # type: ignore[literal-required]

    return updated_profiles


# Write user specific files
def _save_user_profiles(  # pylint: disable=too-many-branches
    updated_profiles: Users,
    now: datetime,
) -> None:
    non_contact_keys = _non_contact_keys()
    multisite_keys = _multisite_keys()

    for user_id, user in updated_profiles.items():
        user_dir = cmk.utils.paths.var_dir + "/web/" + user_id
        store.mkdir(user_dir)

        # authentication secret for local processes
        auth_file = user_dir + "/automation.secret"
        if "automation_secret" in user:
            store.save_text_to_file(auth_file, "%s\n" % user["automation_secret"])
        elif os.path.exists(auth_file):
            os.unlink(auth_file)

        # Write out user attributes which are written to dedicated files in the user
        # profile directory. The primary reason to have separate files, is to reduce
        # the amount of data to be loaded during regular page processing
        save_custom_attr(user_id, "serial", str(user.get("serial", 0)))
        save_custom_attr(user_id, "num_failed_logins", str(user.get("num_failed_logins", 0)))
        save_custom_attr(
            user_id, "enforce_pw_change", str(int(bool(user.get("enforce_pw_change"))))
        )
        save_custom_attr(
            user_id, "last_pw_change", str(user.get("last_pw_change", int(now.timestamp())))
        )

        if "idle_timeout" in user:
            save_custom_attr(user_id, "idle_timeout", user["idle_timeout"])
        else:
            remove_custom_attr(user_id, "idle_timeout")

        if user.get("start_url") is not None:
            save_custom_attr(user_id, "start_url", repr(user["start_url"]))
        else:
            remove_custom_attr(user_id, "start_url")

        if user.get("two_factor_credentials") is not None:
            save_two_factor_credentials(user_id, user["two_factor_credentials"])
        else:
            remove_custom_attr(user_id, "two_factor_credentials")

        # Is None on first load
        if user.get("ui_theme") is not None:
            save_custom_attr(user_id, "ui_theme", user["ui_theme"])
        else:
            remove_custom_attr(user_id, "ui_theme")

        if "ui_sidebar_position" in user:
            save_custom_attr(user_id, "ui_sidebar_position", user["ui_sidebar_position"])
        else:
            remove_custom_attr(user_id, "ui_sidebar_position")

        _save_cached_profile(user_id, user, multisite_keys, non_contact_keys)


# During deletion of users we don't delete files which might contain user settings
# and e.g. customized views which are not easy to reproduce. We want to keep the
# files which are the result of a lot of work even when e.g. the LDAP sync deletes
# a user by accident. But for some internal files it is ok to delete them.
#
# Be aware: The user_exists() function relies on these files to be deleted.
def _cleanup_old_user_profiles(updated_profiles: Users) -> None:
    profile_files_to_delete = [
        "automation.secret",
        "transids.mk",
        "serial.mk",
    ]
    directory = cmk.utils.paths.var_dir + "/web"
    for user_dir in os.listdir(cmk.utils.paths.var_dir + "/web"):
        if user_dir not in [".", ".."] and user_dir not in updated_profiles:
            entry = directory + "/" + user_dir
            if not os.path.isdir(entry):
                continue

            for to_delete in profile_files_to_delete:
                if os.path.exists(entry + "/" + to_delete):
                    os.unlink(entry + "/" + to_delete)


def write_contacts_and_users_file(
    profiles: Users, custom_default_config_dir: str | None = None
) -> None:
    non_contact_keys = _non_contact_keys()
    multisite_keys = _multisite_keys()
    updated_profiles = _add_custom_macro_attributes(profiles)

    if custom_default_config_dir:
        check_mk_config_dir = "%s/conf.d/wato" % custom_default_config_dir
        multisite_config_dir = "%s/multisite.d/wato" % custom_default_config_dir
    else:
        check_mk_config_dir = "%s/conf.d/wato" % cmk.utils.paths.default_config_dir
        multisite_config_dir = "%s/multisite.d/wato" % cmk.utils.paths.default_config_dir

    non_contact_attributes_cache: dict[str | None, list[str]] = {}
    multisite_attributes_cache: dict[str | None, list[str]] = {}
    for user_settings in updated_profiles.values():
        connector = user_settings.get("connector")
        if connector not in non_contact_attributes_cache:
            non_contact_attributes_cache[connector] = non_contact_attributes(connector)
        if connector not in multisite_attributes_cache:
            multisite_attributes_cache[connector] = multisite_attributes(connector)

    # Remove multisite keys in contacts.
    # TODO: Clean this up. Just improved the performance, but still have no idea what its actually doing...
    contacts = dict(
        e
        for e in [
            (
                id,
                split_dict(
                    user,
                    non_contact_keys + non_contact_attributes_cache[user.get("connector")],
                    False,
                ),
            )
            for (id, user) in updated_profiles.items()
        ]
    )

    # Only allow explicitely defined attributes to be written to multisite config
    users = {}
    for uid, profile in updated_profiles.items():
        users[uid] = {
            p: val
            for p, val in profile.items()
            if p in multisite_keys + multisite_attributes_cache[profile.get("connector")]
        }

    # Checkmk's monitoring contacts
    store.save_to_mk_file(
        "{}/{}".format(check_mk_config_dir, "contacts.mk"),
        "contacts",
        contacts,
        pprint_value=active_config.wato_pprint_config,
    )

    # GUI specific user configuration
    store.save_to_mk_file(
        "{}/{}".format(multisite_config_dir, "users.mk"),
        "multisite_users",
        users,
        pprint_value=active_config.wato_pprint_config,
    )


def _non_contact_keys() -> list[str]:
    """User attributes not to put into contact definitions for Check_MK"""
    return [
        "automation_secret",
        "connector",
        "enforce_pw_change",
        "idle_timeout",
        "language",
        "last_pw_change",
        "locked",
        "num_failed_logins",
        "password",
        "roles",
        "serial",
        "session_info",
        "two_factor_credentials",
    ] + _get_multisite_custom_variable_names()


def _multisite_keys() -> list[str]:
    """User attributes to put into multisite configuration"""
    multisite_variables = [
        var
        for var in _get_multisite_custom_variable_names()
        if var not in ("start_url", "ui_theme", "ui_sidebar_position")
    ]
    return [
        "roles",
        "locked",
        "automation_secret",
        "alias",
        "language",
        "connector",
    ] + multisite_variables


def _get_multisite_custom_variable_names() -> list[str]:
    return [name for name, attr in get_user_attributes() if attr.domain() == "multisite"]  #


def _save_auth_serials(updated_profiles: Users) -> None:
    """Write out the users serials"""
    # Write out the users serials
    serials = ""
    for user_id, user in updated_profiles.items():
        serials += "%s:%d\n" % (user_id, user.get("serial", 0))
    store.save_text_to_file(
        "%s/auth.serials" % os.path.dirname(cmk.utils.paths.htpasswd_file), serials
    )


def rewrite_users(now: datetime) -> None:
    save_users(load_users(lock=True), now)


def create_cmk_automation_user(now: datetime) -> None:
    secret = utils.gen_id()
    users = load_users(lock=True)
    users[UserId("automation")] = {
        "alias": "Check_MK Automation - used for calling web services",
        "contactgroups": [],
        "automation_secret": secret,
        "password": password_hashing.hash_password(Password(secret)),
        "roles": ["admin"],
        "locked": False,
        "serial": 0,
        "email": "",
        "pager": "",
        "notifications_enabled": False,
        "language": "en",
        "connector": "htpasswd",
    }
    save_users(users, now)


def _save_cached_profile(
    user_id: UserId, user: UserSpec, multisite_keys: list[str], non_contact_keys: list[str]
) -> None:
    # Only save contact AND multisite attributes to the profile. Not the
    # infos that are stored in the custom attribute files.
    cache = UserSpec()
    for key in user.keys():
        if key in multisite_keys or key not in non_contact_keys:
            # UserSpec is now a TypedDict, unfortunately not complete yet, thanks to such constructs.
            cache[key] = user[key]  # type: ignore[literal-required]

    save_cached_profile(user_id, cache)


def contactgroups_of_user(user_id: UserId) -> list[ContactgroupName]:
    return load_user(user_id).get("contactgroups", [])


def _convert_idle_timeout(value: str) -> int | bool | None:
    try:
        return False if value == "False" else int(value)  # disabled or set
    except ValueError:
        return None  # Invalid value -> use global setting


# .
#   .-Custom-Attrs.--------------------------------------------------------.
#   |   ____          _                          _   _   _                 |
#   |  / ___|   _ ___| |_ ___  _ __ ___         / \ | |_| |_ _ __ ___      |
#   | | |  | | | / __| __/ _ \| '_ ` _ \ _____ / _ \| __| __| '__/ __|     |
#   | | |__| |_| \__ \ || (_) | | | | | |_____/ ___ \ |_| |_| |  \__ \_    |
#   |  \____\__,_|___/\__\___/|_| |_| |_|    /_/   \_\__|\__|_|  |___(_)   |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | Mange custom attributes of users (in future hosts etc.)              |
#   '----------------------------------------------------------------------'
def register_custom_user_attributes(attributes: list[dict[str, Any]]) -> None:
    for attr in attributes:
        if attr["type"] != "TextAscii":
            raise NotImplementedError()

        @user_attribute_registry.register
        class _LegacyUserAttribute(GenericUserAttribute):
            # Play safe: Grab all necessary data at class construction time,
            # it's highly unclear if the attr dict is mutated later or not.
            _name = attr["name"]
            _valuespec = TextInput(title=attr["title"], help=attr["help"])
            _topic = attr.get("topic", "personal")
            _user_editable = attr["user_editable"]
            _show_in_table = attr.get("show_in_table", False)
            _add_custom_macro = attr.get("add_custom_macro", False)

            @classmethod
            def name(cls) -> str:
                return cls._name

            def valuespec(self) -> ValueSpec:
                return self._valuespec

            def topic(self) -> str:
                return self._topic

            def __init__(self) -> None:
                super().__init__(
                    user_editable=self._user_editable,
                    show_in_table=self._show_in_table,
                    add_custom_macro=self._add_custom_macro,
                    domain="multisite",
                    permission=None,
                    from_config=True,
                )

            @classmethod
            def is_custom(cls) -> bool:
                return True

    cmk.gui.userdb.ldap_connector.register_user_attribute_sync_plugins()


def update_config_based_user_attributes() -> None:
    _clear_config_based_user_attributes()
    register_custom_user_attributes(active_config.wato_user_attrs)


def _clear_config_based_user_attributes() -> None:
    for _name, attr in get_user_attributes():
        if attr.from_config():
            user_attribute_registry.unregister(attr.name())


# .
#   .-Hooks----------------------------------------------------------------.
#   |                     _   _             _                              |
#   |                    | | | | ___   ___ | | _____                       |
#   |                    | |_| |/ _ \ / _ \| |/ / __|                      |
#   |                    |  _  | (_) | (_) |   <\__ \                      |
#   |                    |_| |_|\___/ \___/|_|\_\___/                      |
#   |                                                                      |
#   +----------------------------------------------------------------------+


def check_credentials(
    username: UserId, password: Password[str], now: datetime
) -> UserId | Literal[False]:
    """Verify the credentials given by a user using all auth connections"""
    for connection_id, connection in active_connections():
        # None        -> User unknown, means continue with other connectors
        # '<user_id>' -> success
        # False       -> failed
        result = connection.check_credentials(username, password)

        if result is False:
            return False

        if result is None:
            continue

        user_id: UserId = result
        if not isinstance(user_id, str):
            raise MKInternalError(
                _("The username returned by the %s connector is not of type string (%r).")
                % (connection_id, user_id)
            )

        # Check whether or not the user exists (and maybe create it)
        #
        # We have the cases where users exist "partially"
        # a) The htpasswd file of the site may have a username:pwhash data set
        #    and Checkmk does not have a user entry yet
        # b) LDAP authenticates a user and Checkmk does not have a user entry yet
        #
        # In these situations a user account with the "default profile" should be created
        create_non_existing_user(connection_id, user_id, now)

        if not is_customer_user_allowed_to_login(user_id):
            # A CME not assigned with the current sites customer
            # is not allowed to login
            auth_logger.debug("User '%s' is not allowed to login: Invalid customer" % user_id)
            return False

        # Now, after successfull login (and optional user account creation), check whether or
        # not the user is locked.
        if user_locked(user_id):
            auth_logger.debug("User '%s' is not allowed to login: Account locked" % user_id)
            return False  # The account is locked

        return user_id

    return False


def show_exception(connection_id: str, title: str, e: Exception, debug: bool = True) -> None:
    html.show_error(
        "<b>" + connection_id + " - " + title + "</b>"
        "<pre>%s</pre>" % (debug and traceback.format_exc() or e)
    )


def hook_save(users: Users) -> None:
    """Hook function can be registered here to be executed during saving of the
    new user construct"""
    for connection_id, connection in active_connections():
        try:
            connection.save_users(users)
        except Exception as e:
            if active_config.debug:
                raise
            show_exception(connection_id, _("Error during saving"), e)


def general_userdb_job(now: datetime) -> None:
    """This function registers general stuff, which is independet of the single
    connectors to each page load. It is exectued AFTER all other connections jobs."""

    hooks.call("userdb-job")

    # Create initial auth.serials file, same issue as auth.php above
    serials_file = "%s/auth.serials" % os.path.dirname(cmk.utils.paths.htpasswd_file)
    if not os.path.exists(serials_file) or os.path.getsize(serials_file) == 0:
        rewrite_users(now)


def execute_userdb_job() -> None:
    """This function is called by the GUI cron job once a minute.

    Errors are logged to var/log/web.log."""
    if not userdb_sync_job_enabled():
        return

    job = UserSyncBackgroundJob()
    if job.is_active():
        gui_logger.debug("Another synchronization job is already running: Skipping this sync")
        return

    job.start(
        lambda job_interface: job.do_sync(
            job_interface=job_interface,
            add_to_changelog=False,
            enforce_sync=False,
            load_users_func=load_users,
            save_users_func=save_users,
        )
    )


def userdb_sync_job_enabled() -> bool:
    cfg = user_sync_config()

    if cfg is None:
        return False  # not enabled at all

    if cfg == "master" and is_wato_slave_site():
        return False

    return True


@cmk.gui.pages.register("ajax_userdb_sync")
def ajax_sync() -> None:
    try:
        job = UserSyncBackgroundJob()
        try:
            job.start(
                lambda job_interface: job.do_sync(
                    job_interface=job_interface,
                    add_to_changelog=False,
                    enforce_sync=True,
                    load_users_func=load_users,
                    save_users_func=save_users,
                )
            )
        except BackgroundJobAlreadyRunning as e:
            raise MKUserError(None, _("Another user synchronization is already running: %s") % e)
        response.set_data("OK Started synchronization\n")
    except Exception as e:
        gui_logger.exception("error synchronizing user DB")
        if active_config.debug:
            raise
        response.set_data("ERROR %s\n" % e)


@job_registry.register
class UserSyncBackgroundJob(BackgroundJob):
    job_prefix = "user_sync"

    @classmethod
    def gui_title(cls) -> str:
        return _("User synchronization")

    def __init__(self) -> None:
        super().__init__(
            self.job_prefix,
            InitialStatusArgs(
                title=self.gui_title(),
                stoppable=False,
            ),
        )

    def _back_url(self) -> str:
        return makeuri_contextless(request, [("mode", "users")], filename="wato.py")

    def do_sync(
        self,
        job_interface: BackgroundProcessInterface,
        add_to_changelog: bool,
        enforce_sync: bool,
        load_users_func: Callable[[bool], Users],
        save_users_func: Callable[[Users, datetime], None],
    ) -> None:
        job_interface.send_progress_update(_("Synchronization started..."))
        if self._execute_sync_action(
            job_interface,
            add_to_changelog,
            enforce_sync,
            load_users_func,
            save_users_func,
            datetime.now(),
        ):
            job_interface.send_result_message(_("The user synchronization completed successfully."))
        else:
            job_interface.send_exception(_("The user synchronization failed."))

    def _execute_sync_action(
        self,
        job_interface: BackgroundProcessInterface,
        add_to_changelog: bool,
        enforce_sync: bool,
        load_users_func: Callable[[bool], Users],
        save_users_func: Callable[[Users, datetime], None],
        now: datetime,
    ) -> bool:
        for connection_id, connection in active_connections():
            try:
                if not enforce_sync and not connection.sync_is_needed():
                    continue

                job_interface.send_progress_update(
                    _("[%s] Starting sync for connection") % connection_id
                )
                connection.do_sync(
                    add_to_changelog=add_to_changelog,
                    only_username=None,
                    load_users_func=load_users,
                    save_users_func=save_users,
                )
                job_interface.send_progress_update(
                    _("[%s] Finished sync for connection") % connection_id
                )
            except Exception as e:
                job_interface.send_exception(_("[%s] Exception: %s") % (connection_id, e))
                gui_logger.error(
                    "Exception (%s, userdb_job): %s", connection_id, traceback.format_exc()
                )

        job_interface.send_progress_update(_("Finalizing synchronization"))
        general_userdb_job(now)
        return True


def execute_user_profile_cleanup_job() -> None:
    """This function is called by the GUI cron job once a minute.

    Errors are logged to var/log/web.log."""
    job = UserProfileCleanupBackgroundJob()
    if job.is_active():
        gui_logger.debug("Job is already running: Skipping this time")
        return

    interval = 3600
    with suppress(FileNotFoundError):
        if time.time() - UserProfileCleanupBackgroundJob.last_run_path().stat().st_mtime < interval:
            gui_logger.debug("Job was already executed within last %d seconds", interval)
            return

    job.start(job.do_execute)


@job_registry.register
class UserProfileCleanupBackgroundJob(BackgroundJob):
    job_prefix = "user_profile_cleanup"

    @staticmethod
    def last_run_path() -> Path:
        return Path(cmk.utils.paths.var_dir, "wato", "last_user_profile_cleanup.mk")

    @classmethod
    def gui_title(cls) -> str:
        return _("User profile cleanup")

    def __init__(self) -> None:
        super().__init__(
            self.job_prefix,
            InitialStatusArgs(
                title=self.gui_title(),
                lock_wato=False,
                stoppable=False,
            ),
        )

    def do_execute(self, job_interface: BackgroundProcessInterface) -> None:
        try:
            cleanup_abandoned_profiles(self._logger, datetime.now(), timedelta(days=30))
            job_interface.send_result_message(_("Job finished"))
        finally:
            UserProfileCleanupBackgroundJob.last_run_path().touch(exist_ok=True)


def cleanup_abandoned_profiles(logger: Logger, now: datetime, max_age: timedelta) -> None:
    """Cleanup abandoned profile directories

    The cleanup is done like this:

    - Load the userdb to get the list of locally existing users
    - Iterate over all use profile directories and find all directories that don't belong to an
      existing user
    - For each of these directories find the most recent written file
    - In case the most recent written file is older than max_age days delete the profile directory
    - Create an audit log entry for each removed directory
    """
    users = set(load_users().keys())
    if not users:
        logger.warning("Found no users. Be careful and not cleaning up anything.")
        return

    profile_base_dir = cmk.utils.paths.profile_dir
    # Some files like ldap_*_sync_time.mk can be placed in
    # ~/var/check_mk/web, causing error entries in web.log while trying to
    # delete a dir
    profiles = {
        profile_dir.name for profile_dir in profile_base_dir.iterdir() if profile_dir.is_dir()
    }

    abandoned_profiles = sorted(profiles - users)
    if not abandoned_profiles:
        logger.debug("Found no abandoned profile.")
        return

    logger.info("Found %d abandoned profiles", len(abandoned_profiles))
    logger.debug("Profiles: %s", ", ".join(abandoned_profiles))

    for profile_name in abandoned_profiles:
        profile_dir = profile_base_dir / profile_name
        last_mtime = datetime.fromtimestamp(
            max((p.stat().st_mtime for p in profile_dir.glob("*.mk")), default=0.0)
        )
        if now - last_mtime > max_age:
            try:
                logger.info("Removing abandoned profile directory: %s", profile_name)
                shutil.rmtree(profile_dir)
            except OSError:
                logger.debug("Could not delete %s", profile_dir, exc_info=True)


def _register_user_attributes() -> None:
    user_attribute_registry.register(user_attributes.ForceAuthUserUserAttribute)
    user_attribute_registry.register(user_attributes.DisableNotificationsUserAttribute)
    user_attribute_registry.register(user_attributes.StartURLUserAttribute)
    user_attribute_registry.register(user_attributes.UIThemeUserAttribute)
    user_attribute_registry.register(user_attributes.UISidebarPosition)
    user_attribute_registry.register(user_attributes.UIIconTitle)
    user_attribute_registry.register(user_attributes.UIIconPlacement)
    user_attribute_registry.register(user_attributes.UIBasicAdvancedToggle)


_register_user_attributes()
