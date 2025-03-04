#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from __future__ import annotations

import dataclasses
import enum
import re
import sys
from collections.abc import Container, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Generic, Literal, NamedTuple, NewType, TypeVar, Union

if sys.version_info < (3, 11):
    # Generic typed dict
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

T = TypeVar("T")

HostName = str
HostAddress = str
HostgroupName = str
ServiceName = str
ServicegroupName = str
ContactgroupName = str
TimeperiodName = str

# We still need "Union" because of https://github.com/python/mypy/issues/11098
AgentTargetVersion = Union[None, str, tuple[str, str], tuple[str, dict[str, str]]]

AgentRawData = NewType("AgentRawData", bytes)

RulesetName = str
RuleValue = Any  # TODO: Improve this type

# FIXME: A lot of signatures regarding rules and rule sets are simply lying:
# They claim to expect a RuleConditionsSpec or Ruleset (from cmk.utils.type_defs), but
# they are silently handling a very chaotic tuple-based structure, too. We
# really, really need to fix all those signatures! Some test cases for tuples are in
# test_tuple_rulesets.py. They contain some horrible hand-made types...


# TODO: Improve this type
class RuleConditionsSpec(TypedDict, total=False):
    host_tags: Any
    host_labels: Any
    host_name: HostOrServiceConditions | None
    service_description: HostOrServiceConditions | None
    service_labels: Any
    host_folder: Any


class _RuleSpecBase(TypedDict, Generic[T]):
    value: T
    condition: RuleConditionsSpec


class RuleSpec(Generic[T], _RuleSpecBase[T], total=False):
    id: str  # Should not be optional but nearly not test has that attribute set!
    options: RuleOptionsSpec


class RuleOptionsSpec(TypedDict, total=False):
    disabled: bool
    description: str
    comment: str
    docu_url: str
    predefined_condition_id: str


@dataclasses.dataclass()
class RuleOptions:
    disabled: bool | None
    description: str
    comment: str
    docu_url: str
    predefined_condition_id: str | None = None

    @classmethod
    def from_config(
        cls,
        rule_options_config: RuleOptionsSpec,
    ) -> RuleOptions:
        return cls(
            disabled=rule_options_config.get("disabled", None),
            description=rule_options_config.get("description", ""),
            comment=rule_options_config.get("comment", ""),
            docu_url=rule_options_config.get("docu_url", ""),
            predefined_condition_id=rule_options_config.get("predefined_condition_id"),
        )

    def to_config(self) -> RuleOptionsSpec:
        rule_options_config: RuleOptionsSpec = {}
        if self.disabled is not None:
            rule_options_config["disabled"] = self.disabled
        if self.description:
            rule_options_config["description"] = self.description
        if self.comment:
            rule_options_config["comment"] = self.comment
        if self.docu_url:
            rule_options_config["docu_url"] = self.docu_url
        if self.predefined_condition_id:
            rule_options_config["predefined_condition_id"] = self.predefined_condition_id
        return rule_options_config


HostOrServiceConditionRegex = TypedDict(
    "HostOrServiceConditionRegex",
    {"$regex": str},
)
HostOrServiceConditionsSimple = list[HostOrServiceConditionRegex | str]
HostOrServiceConditionsNegated = TypedDict(
    "HostOrServiceConditionsNegated",
    {"$nor": HostOrServiceConditionsSimple},
)

HostOrServiceConditions = (
    HostOrServiceConditionsSimple | HostOrServiceConditionsNegated
)  # TODO: refine type

Ruleset = list[RuleSpec[T]]
CheckPluginNameStr = str
ActiveCheckPluginName = str
Item = str | None
Labels = Mapping[str, str]
LabelSources = dict[str, str]

TagID = str
TaggroupID = str
TaggroupIDToTagID = Mapping[TaggroupID, TagID]
TagIDToTaggroupID = Mapping[TagID, TaggroupID]
TagIDs = set[TagID]
TagConditionNE = TypedDict(
    "TagConditionNE",
    {
        "$ne": TagID | None,
    },
)
TagConditionOR = TypedDict(
    "TagConditionOR",
    {
        "$or": Sequence[TagID | None],
    },
)
TagConditionNOR = TypedDict(
    "TagConditionNOR",
    {
        "$nor": Sequence[TagID | None],
    },
)
TagCondition = TagID | None | TagConditionNE | TagConditionOR | TagConditionNOR
# Here, we have data structures such as
# {'ip-v4': {'$ne': 'ip-v4'}, 'snmp_ds': {'$nor': ['no-snmp', 'snmp-v1']}, 'taggroup_02': None, 'aux_tag_01': 'aux_tag_01', 'address_family': 'ip-v4-only'}
TaggroupIDToTagCondition = Mapping[TaggroupID, TagCondition]
TagsOfHosts = dict[HostName, TaggroupIDToTagID]

LabelConditions = dict[str, str | TagConditionNE]


class GroupedTagSpec(TypedDict):
    id: TagID | None
    title: str
    aux_tags: list[TagID]


class _AuxTagSpecOpt(TypedDict, total=False):
    topic: str


class AuxTagSpec(_AuxTagSpecOpt):
    id: TagID
    title: str


class _TaggroupSpecOpt(TypedDict, total=False):
    topic: str
    help: str


class TaggroupSpec(_TaggroupSpecOpt):
    id: TaggroupID
    title: str
    tags: list[GroupedTagSpec]


class TagConfigSpec(TypedDict):
    tag_groups: list[TaggroupSpec]
    aux_tags: list[AuxTagSpec]


CheckVariables = dict[str, Any]
Seconds = int
Timestamp = int
TimeRange = tuple[int, int]

ServiceState = int
HostState = int
ServiceDetails = str
ServiceAdditionalDetails = str

MetricName = str
MetricTuple = tuple[
    MetricName,
    float,
    float | None,
    float | None,
    float | None,
    float | None,
]

ClusterMode = Literal["native", "failover", "worst", "best"]

LegacyCheckParameters = None | Mapping[Any, Any] | tuple[Any, ...] | list[Any] | str | int | bool
ParametersTypeAlias = Mapping[str, Any]  # Modification may result in an incompatible API change.

SetAutochecksTable = dict[
    tuple[str, Item], tuple[ServiceName, LegacyCheckParameters, Labels, list[HostName]]
]

SetAutochecksTablePre20 = dict[tuple[str, Item], tuple[dict[str, Any], Labels]]


@dataclass
class DiscoveryResult:
    self_new: int = 0
    self_removed: int = 0
    self_kept: int = 0
    self_total: int = 0
    self_new_host_labels: int = 0
    self_total_host_labels: int = 0
    clustered_new: int = 0
    clustered_old: int = 0
    clustered_vanished: int = 0
    clustered_ignored: int = 0

    # None  -> No error occured
    # ""    -> Not monitored (disabled host)
    # "..." -> An error message about the failed discovery
    error_text: str | None = None

    # An optional text to describe the services changed by the operation
    diff_text: str | None = None


class UserId(str):
    USER_ID_REGEX = re.compile(r"^[\w_$][-\w.@_$]*$")

    @classmethod
    def validate(cls, text: str) -> None:
        """Check if it is a valid UserId

        We use the userid to create file paths, so we we need to be strict...

        >>> UserId.validate("cmkadmin")
        >>> UserId.validate("")
        >>> UserId.validate("foo/../")
        Traceback (most recent call last):
        ...
        ValueError: Invalid username: 'foo/../'
        """
        if text == "":
            # For legacy reasons (e.g. cmk.gui.visuals)
            return

        if not cls.USER_ID_REGEX.match(text):
            raise ValueError(f"Invalid username: {text!r}")

    @classmethod
    def builtin(cls) -> UserId:
        """A special UserId signifying something is owned or created not by a real user but shipped
        as a built in functionality.

        This is mostly used in cmk.gui.visuals.

        Note that, unfortunately, the UserId "" will sometimes also be constructed via regular
        initialization, so this method is not the only source for them.
        Moreover, be aware that it is very possible that some parts of the code use the UserId ""
        with a different meaning.
        """
        return UserId("")

    def __new__(cls, text: str) -> UserId:
        cls.validate(text)
        return super().__new__(cls, text)


# This def is used to keep the API-exposed object in sync with our
# implementation.
SNMPDetectBaseType = list[list[tuple[str, str, bool]]]

# TODO: TimeperiodSpec should really be a class or at least a NamedTuple! We
# can easily transform back and forth for serialization.
TimeperiodSpec = dict[str, str | list[str] | list[tuple[str, str]]]
TimeperiodSpecs = dict[TimeperiodName, TimeperiodSpec]


class SourceType(enum.Enum):
    """Classification of management sources vs regular hosts"""

    HOST = enum.auto()
    MANAGEMENT = enum.auto()


class HostKey(NamedTuple):
    hostname: HostName
    source_type: SourceType


# TODO: We should really parse our configuration file and use a
# class/NamedTuple, see above.
def timeperiod_spec_alias(timeperiod_spec: TimeperiodSpec, default: str = "") -> str:
    alias = timeperiod_spec.get("alias", default)
    if isinstance(alias, str):
        return alias
    raise Exception(f"invalid timeperiod alias {alias!r}")


class EvalableFloat(float):
    """Extends the float representation for Infinities in such way that
    they can be parsed by eval"""

    def __str__(self) -> str:
        return super().__repr__()

    def __repr__(self) -> str:
        if self > sys.float_info.max:
            return "1e%d" % (sys.float_info.max_10_exp + 1)
        if self < -1 * sys.float_info.max:
            return "-1e%d" % (sys.float_info.max_10_exp + 1)
        return super().__repr__()


class _Everything(Container[Any]):
    def __contains__(self, other: object) -> bool:
        return True


EVERYTHING = _Everything()

# Symbolic representations of states in plugin output
# TODO(ml): Should probably be of type enum::int -> str
state_markers = ("", "(!)", "(!!)", "(?)")


class ExitSpec(TypedDict, total=False):
    empty_output: int
    connection: int
    timeout: int
    exception: int
    wrong_version: int
    missing_sections: int
    specific_missing_sections: list[tuple[str, int]]
    restricted_address_mismatch: int
    legacy_pull_mode: int


class HostLabelValueDict(TypedDict):
    value: str
    plugin_name: str | None


DiscoveredHostLabelsDict = dict[str, HostLabelValueDict]


InfluxDBConnectionSpec = dict[str, Any]

# TODO(ml): IPMICredentials belongs with IPMIFetcher but
#           we need to fix the layering problem with the
#           global config before this is safe.
IPMICredentials = Mapping[str, str]
