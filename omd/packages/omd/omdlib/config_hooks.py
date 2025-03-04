#!/usr/bin/env python3
#
#       U  ___ u  __  __   ____
#        \/"_ \/U|' \/ '|u|  _"\
#        | | | |\| |\/| |/| | | |
#    .-,_| |_| | | |  | |U| |_| |\
#     \_)-\___/  |_|  |_| |____/ u
#          \\   <<,-,,-.   |||_
#         (__)   (./  \.) (__)_)
#
# This file is part of OMD - The Open Monitoring Distribution.
# The official homepage is at <http://omdistro.org>.
#
# OMD  is  free software;  you  can  redistribute it  and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the  Free Software  Foundation  in  version 2.  OMD  is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# ails.  You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.
"""Site configuration and config hooks

Hooks are scripts in lib/omd/hooks that are being called with one
of the following arguments:

default - return the default value of the hook. Mandatory
set     - implements a new setting for the hook
choices - available choices for enumeration hooks
depends - exists with 1, if this hook misses its dependent hook settings
"""

import logging
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from ipaddress import ip_network
from pathlib import Path
from re import Pattern
from typing import TYPE_CHECKING

from omdlib.type_defs import ConfigChoiceHasError

from cmk.utils.exceptions import MKTerminate
from cmk.utils.log import VERBOSE
from cmk.utils.type_defs import result

if TYPE_CHECKING:
    from omdlib.contexts import SiteContext

logger = logging.getLogger("cmk.omd")

ConfigHookChoiceItem = tuple[str, str]
ConfigHookChoices = Pattern | list[ConfigHookChoiceItem] | ConfigChoiceHasError | None
ConfigHook = dict[str, str | bool | ConfigHookChoices]
ConfigHooks = dict[str, ConfigHook]
ConfigHookResult = tuple[int, str]


class IpAddressListHasError(ConfigChoiceHasError):
    def __call__(self, value: str) -> result.Result[None, str]:
        ip_addresses = value.split()
        if not ip_addresses:
            return result.Error("Specify at least one IP address.")
        for ip_address in ip_addresses:
            try:
                ip_network(ip_address)
            except ValueError:
                return result.Error(f"The IP address {ip_address} does match the expected format.")
        return result.OK(None)


# Put all site configuration (explicit and defaults) into environment
# variables beginning with CONFIG_
def create_config_environment(site: "SiteContext") -> None:
    for varname, value in site.conf.items():
        os.environ["CONFIG_" + varname] = value


# TODO: RENAME
def save_site_conf(site: "SiteContext") -> None:
    confdir = Path(site.dir, "etc/omd")
    confdir.mkdir(exist_ok=True)
    with Path(site.dir, "etc/omd/site.conf").open(mode="w") as f:
        for hook_name, value in sorted(site.conf.items(), key=lambda x: x[0]):
            f.write(f"CONFIG_{hook_name}='{value}'\n")


# Get information about all hooks. Just needed for
# the "omd config" command.
def load_config_hooks(site: "SiteContext") -> ConfigHooks:
    config_hooks: ConfigHooks = {}

    hook_files = []
    if site.hook_dir:
        hook_files = os.listdir(site.hook_dir)

    for hook_name in hook_files:
        try:
            if hook_name[0] != ".":
                hook = _config_load_hook(site, hook_name)
                # only load configuration hooks
                if hook.get("choices", None) is not None:
                    config_hooks[hook_name] = hook
        except MKTerminate:
            raise
        except Exception:
            pass
    config_hooks = load_hook_dependencies(site, config_hooks)
    return config_hooks


def _config_load_hook(  # pylint: disable=too-many-branches
    site: "SiteContext",
    hook_name: str,
) -> ConfigHook:
    hook: ConfigHook = {
        "name": hook_name,
        "deprecated": False,
    }

    if not site.hook_dir:
        # IMHO this should be unreachable...
        raise MKTerminate("Site has no version and therefore no hooks")

    description = ""
    description_active = False
    with Path(site.hook_dir, hook_name).open() as hook_file:
        for line in hook_file:
            if line.startswith("# Alias:"):
                hook["alias"] = line[8:].strip()
            elif line.startswith("# Menu:"):
                hook["menu"] = line[7:].strip()
            elif line.startswith("# Deprecated: yes"):
                hook["deprecated"] = True
            elif line.startswith("# Description:"):
                description_active = True
            elif line.startswith("#  ") and description_active:
                description += line[3:].strip() + "\n"
            else:
                description_active = False
    hook["description"] = description

    hook_info = call_hook(site, hook_name, ["choices"])[1]
    hook["choices"] = _parse_hook_choices(hook_info)
    return hook


def _parse_hook_choices(hook_info: str) -> ConfigHookChoices:
    # The choices can either be a list of possible keys. Then
    # the hook outputs one live for each choice where the key and a
    # description are separated by a colon. Or it outputs one line
    # where that line is an extended regular expression matching the
    # possible values.

    match [choice.strip() for choice in hook_info.split("\n")]:
        case [""]:
            return None
        case ["@{IP_ADDRESS_LIST}"]:
            return IpAddressListHasError()
        case [regextext]:
            return re.compile(regextext + "$")
        case choices_list:
            try:
                choices: list[ConfigHookChoiceItem] = []
                for line in choices_list:
                    val, descr = line.split(":", 1)
                    choices.append((val.strip(), descr.strip()))
            except ValueError as excep:
                raise MKTerminate(f"Invalid output of hook: {choices_list}: {excep}") from excep
            return choices
    return None


def load_hook_dependencies(site: "SiteContext", config_hooks: ConfigHooks) -> ConfigHooks:
    for hook_name in sort_hooks(list(config_hooks.keys())):
        hook = config_hooks[hook_name]
        exitcode, _content = call_hook(site, hook_name, ["depends"])
        if exitcode:
            hook["active"] = False
        else:
            hook["active"] = True
    return config_hooks


# Always sort CORE hook to the end because it runs "cmk -U" which
# relies on files created by other hooks.
def sort_hooks(hook_names: list[str]) -> Iterable[str]:
    return sorted(hook_names, key=lambda n: (n == "CORE", n))


def hook_exists(site: "SiteContext", hook_name: str) -> bool:
    if not site.hook_dir:
        return False
    hook_file = site.hook_dir + hook_name
    return os.path.exists(hook_file)


def call_hook(site: "SiteContext", hook_name: str, args: list[str]) -> ConfigHookResult:

    if not site.hook_dir:
        # IMHO this should be unreachable...
        raise MKTerminate("Site has no version and therefore no hooks")

    cmd = [site.hook_dir + hook_name] + args
    hook_env = os.environ.copy()
    hook_env.update(
        {
            "OMD_ROOT": site.dir,
            "OMD_SITE": site.name,
        }
    )

    logger.log(VERBOSE, "Calling hook: %s", subprocess.list2cmdline(cmd))

    completed_process = subprocess.run(
        cmd,
        env=hook_env,
        close_fds=True,
        shell=False,
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )
    content = completed_process.stdout.strip()

    if completed_process.returncode and args[0] != "depends":
        sys.stderr.write(f"Error running {subprocess.list2cmdline(cmd)}: {content}\n")

    return completed_process.returncode, content
