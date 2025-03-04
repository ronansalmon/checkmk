#!/usr/bin/env python3
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Sequence

import pytest

from tests.unit.conftest import FixRegister

from cmk.utils.type_defs import CheckPluginName, SectionName

from cmk.base.api.agent_based.checking_classes import CheckPlugin
from cmk.base.api.agent_based.type_defs import StringTable
from cmk.base.plugins.agent_based.agent_based_api.v1 import Metric, Result, Service, State
from cmk.base.plugins.agent_based.utils.df import FILESYSTEM_DEFAULT_PARAMS

STRING_TABLE = [
    [
        '{"total": 1,"members": [{"id": 0,"uuid": "b5611ec3-b459-4cfe-91d8-64b6c074e72b","name": "SSD_R6","numFPVVs": 1,"numTPVVs": 0,"numTDVVs": 15,"UsrUsage": {"totalMiB": 20261120,"rawTotalMiB": 24313343,"usedMiB": 20261120,"rawUsedMiB": 24313343},"SAUsage": {"totalMiB": 104448,"rawTotalMiB": 313344,"usedMiB": 94976,"rawUsedMiB": 284928},"SDUsage": {"totalMiB": 44800,"rawTotalMiB": 53760,"usedMiB": 25600,"rawUsedMiB": 30719},"state": 1}]}'
    ]
]


@pytest.fixture(name="check")
def _3par_cpgs_check_plugin(fix_register: FixRegister) -> CheckPlugin:
    return fix_register.check_plugins[CheckPluginName("3par_cpgs")]


@pytest.fixture(name="usage_check")
def _3par_cpgs_usage_check_plugin(fix_register: FixRegister) -> CheckPlugin:
    return fix_register.check_plugins[CheckPluginName("3par_cpgs_usage")]


@pytest.mark.parametrize(
    "section, expected_discovery_result",
    [
        pytest.param(
            STRING_TABLE,
            [Service(item="SSD_R6")],
            id="For every disk that a Service is created.",
        ),
        pytest.param(
            [],
            [],
            id="If there are no items in the input, nothing is discovered.",
        ),
    ],
)
def test_discover_3par_cpgs(
    check: CheckPlugin,
    fix_register: FixRegister,
    section: StringTable,
    expected_discovery_result: Sequence[Service],
) -> None:
    parse_3par_cpgs = fix_register.agent_sections[SectionName("3par_cpgs")].parse_function
    assert list(check.discovery_function(parse_3par_cpgs(section))) == expected_discovery_result


@pytest.mark.parametrize(
    "section, item, expected_check_result",
    [
        pytest.param(
            STRING_TABLE,
            "not_found",
            [],
            id="If the item is not found, there are no results.",
        ),
        pytest.param(
            STRING_TABLE,
            "SSD_R6",
            [Result(state=State.OK, summary="Normal, 16 VVs")],
            id="If the state of the disk is 1, the check result is OK (Normal) and information about how many VVs are available is displayed.",
        ),
        pytest.param(
            [
                [
                    '{"total": 1,"members": [{"id": 0,"uuid": "b5611ec3-b459-4cfe-91d8-64b6c074e72b","name": "SSD_R6","numFPVVs": 1,"numTPVVs": 0,"numTDVVs": 15,"UsrUsage": {"totalMiB": 20261120,"rawTotalMiB": 24313343,"usedMiB": 20261120,"rawUsedMiB": 24313343},"SAUsage": {"totalMiB": 104448,"rawTotalMiB": 313344,"usedMiB": 94976,"rawUsedMiB": 284928},"SDUsage": {"totalMiB": 44800,"rawTotalMiB": 53760,"usedMiB": 25600,"rawUsedMiB": 30719},"state": 2}]}'
                ]
            ],
            "SSD_R6",
            [Result(state=State.WARN, summary="Degraded, 16 VVs")],
            id="If the state of the disk is 2, the check result is WARN (Degraded) and information about how many VVs are available is displayed.",
        ),
        pytest.param(
            [
                [
                    '{"total": 1,"members": [{"id": 0,"uuid": "b5611ec3-b459-4cfe-91d8-64b6c074e72b","name": "SSD_R6","numFPVVs": 1,"numTPVVs": 0,"numTDVVs": 15,"UsrUsage": {"totalMiB": 20261120,"rawTotalMiB": 24313343,"usedMiB": 20261120,"rawUsedMiB": 24313343},"SAUsage": {"totalMiB": 104448,"rawTotalMiB": 313344,"usedMiB": 94976,"rawUsedMiB": 284928},"SDUsage": {"totalMiB": 44800,"rawTotalMiB": 53760,"usedMiB": 25600,"rawUsedMiB": 30719},"state": 3}]}'
                ]
            ],
            "SSD_R6",
            [Result(state=State.CRIT, summary="Failed, 16 VVs")],
            id="If the state of the disk is 3, the check result is CRIT (Failed) and information about how many VVs are available is displayed.",
        ),
    ],
)
def test_check_3par_cpgs(
    check: CheckPlugin,
    fix_register: FixRegister,
    section: StringTable,
    item: str,
    expected_check_result: Sequence[Result],
) -> None:
    parse_3par_cpgs = fix_register.agent_sections[SectionName("3par_cpgs")].parse_function
    assert (
        list(
            check.check_function(
                item=item,
                params={},
                section=parse_3par_cpgs(section),
            )
        )
        == expected_check_result
    )


@pytest.mark.parametrize(
    "section, expected_discovery_result",
    [
        pytest.param(
            STRING_TABLE,
            [
                Service(item="SSD_R6 SAUsage"),
                Service(item="SSD_R6 SDUsage"),
                Service(item="SSD_R6 UsrUsage"),
            ],
            id="For each disk a Service for SAUsage, SDUsage and UsrUsage is created if they are available.",
        ),
        pytest.param(
            [],
            [],
            id="If there are no items in the input, nothing is discovered.",
        ),
    ],
)
def test_discover_3par_cpgs_usage(
    usage_check: CheckPlugin,
    fix_register: FixRegister,
    section: StringTable,
    expected_discovery_result: Sequence[Service],
) -> None:
    parse_3par_cpgs = fix_register.agent_sections[SectionName("3par_cpgs")].parse_function

    assert (
        list(usage_check.discovery_function(parse_3par_cpgs(section))) == expected_discovery_result
    )


@pytest.mark.parametrize(
    "section, item, expected_check_result",
    [
        pytest.param(
            STRING_TABLE,
            "not_found",
            [],
            id="If the item is not found, there are no results.",
        ),
        pytest.param(
            [
                [
                    '{"total": 1,"members": [{"id": 0,"uuid": "b5611ec3-b459-4cfe-91d8-64b6c074e72b","name": "SSD_R6","numFPVVs": 1,"numTPVVs": 0,"numTDVVs": 15,"UsrUsage": {"totalMiB": 20261120,"rawTotalMiB": 24313343,"usedMiB": 0,"rawUsedMiB": 24313343},"SAUsage": {"totalMiB": 104448,"rawTotalMiB": 313344,"usedMiB": 0,"rawUsedMiB": 284928},"SDUsage": {"totalMiB": 44800,"rawTotalMiB": 53760,"usedMiB": 0,"rawUsedMiB": 30719},"state": 2}]}'
                ]
            ],
            "SSD_R6 SAUsage",
            [
                Result(state=State.OK, summary="Used: 0% - 0 B of 102 GiB"),
                Metric(
                    "fs_used",
                    0.0,
                    levels=(83558.39999961853, 94003.19999980927),
                    boundaries=(0.0, 104448.0),
                ),
                Metric("fs_free", 104448.0, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    0.0,
                    levels=(79.99999999963478, 89.99999999981739),
                    boundaries=(0.0, 100.0),
                ),
                Metric("fs_size", 104448.0, boundaries=(0.0, None)),
            ],
            id="If the used space is below the WARN/CRIT levels, the result is OK.",
        ),
        pytest.param(
            [
                [
                    '{"total": 1,"members": [{"id": 0,"uuid": "b5611ec3-b459-4cfe-91d8-64b6c074e72b","name": "SSD_R6","numFPVVs": 1,"numTPVVs": 0,"numTDVVs": 15,"UsrUsage": {"totalMiB": 20261120,"rawTotalMiB": 24313343,"usedMiB": 0,"rawUsedMiB": 24313343},"SAUsage": {"totalMiB": 104448,"rawTotalMiB": 313344,"usedMiB": 0,"rawUsedMiB": 284928},"SDUsage": {"totalMiB": 44800,"rawTotalMiB": 53760,"usedMiB": 37890,"rawUsedMiB": 30719},"state": 2}]}'
                ]
            ],
            "SSD_R6 SDUsage",
            [
                Result(
                    state=State.WARN,
                    summary="Used: 84.58% - 37.0 GiB of 43.8 GiB (warn/crit at 80.00%/90.00% used)",
                ),
                Metric("fs_used", 37890.0, levels=(35840.0, 40320.0), boundaries=(0.0, 44800.0)),
                Metric("fs_free", 6910.0, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    84.57589285714285,
                    levels=(80.0, 90.0),
                    boundaries=(0.0, 100.0),
                ),
                Metric("fs_size", 44800.0, boundaries=(0.0, None)),
            ],
            id="If the used space is above the WARN levels, the result is WARN.",
        ),
        pytest.param(
            [
                [
                    '{"total": 1,"members": [{"id": 0,"uuid": "b5611ec3-b459-4cfe-91d8-64b6c074e72b","name": "SSD_R6","numFPVVs": 1,"numTPVVs": 0,"numTDVVs": 15,"UsrUsage": {"totalMiB": 20261120,"rawTotalMiB": 24313343,"usedMiB": 20161120,"rawUsedMiB": 24313343},"SAUsage": {"totalMiB": 104448,"rawTotalMiB": 313344,"usedMiB": 0,"rawUsedMiB": 284928},"SDUsage": {"totalMiB": 44800,"rawTotalMiB": 53760,"usedMiB": 37890,"rawUsedMiB": 30719},"state": 2}]}'
                ]
            ],
            "SSD_R6 UsrUsage",
            [
                Result(
                    state=State.CRIT,
                    summary="Used: 99.51% - 19.2 TiB of 19.3 TiB (warn/crit at 80.00%/90.00% used)",
                ),
                Metric(
                    "fs_used",
                    20161120.0,
                    levels=(16208896.0, 18235008.0),
                    boundaries=(0.0, 20261120.0),
                ),
                Metric("fs_free", 100000.0, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    99.50644386884832,
                    levels=(80.0, 90.0),
                    boundaries=(0.0, 100.0),
                ),
                Metric("fs_size", 20261120.0, boundaries=(0.0, None)),
            ],
            id="If the used space is above the CRIT levels, the result is CRIT.",
        ),
    ],
)
def test_check_3par_cpgs_usage(
    usage_check: CheckPlugin,
    fix_register: FixRegister,
    section: StringTable,
    item: str,
    expected_check_result: Sequence[Result | Metric],
) -> None:
    parse_3par_cpgs = fix_register.agent_sections[SectionName("3par_cpgs")].parse_function
    assert (
        list(
            usage_check.check_function(
                item=item,
                params=FILESYSTEM_DEFAULT_PARAMS,
                section=parse_3par_cpgs(section),
            )
        )
        == expected_check_result
    )
