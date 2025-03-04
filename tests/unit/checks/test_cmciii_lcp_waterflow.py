#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Sequence
from typing import NamedTuple

import pytest

from tests.testlib import Check

from cmk.base.plugins.agent_based.agent_based_api.v1.type_defs import StringTable

pytestmark = pytest.mark.checks


class WaterflowReading(NamedTuple):
    name: str
    status: str
    unit: str
    flow: float
    minflow: float
    maxflow: float


@pytest.mark.parametrize(
    "string_table, section",
    [
        pytest.param(
            [
                [
                    "Waterflow",
                    "0.0 l/min",
                    "130.0 l/min",
                    "0.0 l/min",
                    "OK",
                    "2",
                    "Control-Valve",
                    "32 %",
                    "OK",
                    "2",
                    "Cooling-Capacity",
                    "0 W",
                    "OK",
                ],
            ],
            WaterflowReading(
                name="Waterflow", flow=0.0, unit="l/min", maxflow=130.0, minflow=0.0, status="OK"
            ),
            id="Waterflow measurements are parsed correctly",
        ),
    ],
)
def test_parse_cmciii_lcp_waterflow(string_table: StringTable, section: StringTable) -> None:
    check = Check("cmciii_lcp_waterflow")
    assert check.run_parse(string_table) == section


def test_parse_cmciii_lcp_waterflow_empty_section() -> None:
    check = Check("cmciii_lcp_waterflow")
    assert check.run_parse([]) is None


@pytest.mark.parametrize(
    "string_table, discovered_item",
    [
        pytest.param(
            WaterflowReading(
                name="Waterflow", flow=0.0, unit="l/min", maxflow=130.0, minflow=0.0, status="OK"
            ),
            [(None, {})],
            id="Waterflow sensor is discovered within OID range.",
        ),
        pytest.param(
            None,
            [],
            id="Waterflow sensor is not discovered when there are no measurements for it.",
        ),
    ],
)
def test_discover_cmciii_lcp_waterflow(  # type:ignore[no-untyped-def]
    string_table: StringTable, discovered_item
) -> None:
    check = Check("cmciii_lcp_waterflow")
    assert list(check.run_discovery(string_table)) == discovered_item


@pytest.mark.parametrize(
    "string_table, check_results",
    [
        pytest.param(
            WaterflowReading(
                name="Waterflow", flow=0.0, unit="l/min", maxflow=130.0, minflow=0.0, status="OK"
            ),
            [
                0,
                "Waterflow Status: OK Flow: 0.0, MinFlow: 0.0, MaxFLow: 130.0",
                [("flow", "0.0l/min", "0.0:130.0", 0, 0)],
            ],
            id="Check results of waterflow sensor measurements",
        ),
    ],
)
def test_check_cmciii_lcp_waterflow(string_table: StringTable, check_results: Sequence) -> None:
    check = Check("cmciii_lcp_waterflow")
    assert list(check.run_check("item not relevant", {}, string_table)) == check_results


def test_check_cmciii_lcp_waterflow_empty_section() -> None:
    check = Check("cmciii_lcp_waterflow")
    assert check.run_check("item not relevant", {}, None) is None
