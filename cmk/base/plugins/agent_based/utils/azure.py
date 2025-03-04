#!/usr/bin/env python3
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import json
from typing import Any, Callable, Iterable, Mapping, NamedTuple, Sequence

from ..agent_based_api.v1 import check_levels, IgnoreResultsError, render, Service
from ..agent_based_api.v1.type_defs import CheckResult, DiscoveryResult, StringTable

AZURE_AGENT_SEPARATOR = "|"


class AzureMetric(NamedTuple):
    name: str
    aggregation: str
    value: float
    unit: str


class Resource(NamedTuple):
    id: str
    name: str
    type: str
    group: str
    kind: str | None = None
    location: str | None = None
    tags: Mapping[str, str] = {}
    properties: Mapping[str, str | int] = {}
    specific_info: Mapping[str, str | int] = {}
    metrics: Mapping[str, AzureMetric] = {}
    subscription: str | None = None


class MetricData(NamedTuple):
    azure_metric_name: str
    metric_name: str
    metric_label: str
    render_func: Callable[[float], str]
    upper_levels_param: str = ""
    lower_levels_param: str = ""
    boundaries: tuple[float | None, float | None] | None = None


Section = Mapping[str, Resource]


#   .--Parse---------------------------------------------------------------.
#   |                      ____                                            |
#   |                     |  _ \ __ _ _ __ ___  ___                        |
#   |                     | |_) / _` | '__/ __|/ _ \                       |
#   |                     |  __/ (_| | |  \__ \  __/                       |
#   |                     |_|   \__,_|_|  |___/\___|                       |
#   |                                                                      |
#   '----------------------------------------------------------------------'


def _get_metrics_number(row: Sequence[str]) -> int:
    if str(row[0]) != "metrics following":
        return 0
    try:
        return int(row[1])
    except ValueError:
        return 0


def _get_metrics(metrics_data: Sequence[Sequence[str]]) -> Iterable[tuple[str, AzureMetric]]:
    for metric_line in metrics_data:
        metric_dict = json.loads(AZURE_AGENT_SEPARATOR.join(metric_line))

        key = f"{metric_dict['aggregation']}_{metric_dict['name'].replace(' ', '_')}"
        yield key, AzureMetric(
            metric_dict["name"],
            metric_dict["aggregation"],
            metric_dict["value"],
            metric_dict["unit"],
        )


def _get_resource(resource: Mapping[str, Any], metrics=None):  # type:ignore[no-untyped-def]
    return Resource(
        resource["id"],
        resource["name"],
        resource["type"],
        resource["group"],
        resource.get("kind"),
        resource.get("location"),
        resource.get("tags", {}),
        resource.get("properties", {}),
        resource.get("specific_info", {}),
        metrics or {},
        resource.get("subscription"),
    )


def _parse_resource(resource_data: Sequence[Sequence[str]]) -> Resource | None:
    """read resource json and parse metric lines

    Metrics are stored in a dict. Key is name, prefixed by their aggregation,
    spaces become underscores:
      Disk Read Bytes|average|0.0|...
    is stored at
      resource.metrics["average_Disk_Read_Bytes"]
    """
    try:
        resource = json.loads(AZURE_AGENT_SEPARATOR.join(resource_data[0]))
    except (ValueError, IndexError):
        return None

    if len(resource_data) < 3:
        return _get_resource(resource)

    metrics_num = _get_metrics_number(resource_data[1])
    if metrics_num == 0:
        return _get_resource(resource)

    metrics = dict(_get_metrics(resource_data[2 : 2 + metrics_num]))
    return _get_resource(resource, metrics=metrics)


def parse_resources(string_table: StringTable) -> Mapping[str, Resource]:
    raw_resources: list[list[Sequence[str]]] = []

    # create list of lines per resource
    for row in string_table:
        if row == ["Resource"]:
            raw_resources.append([])
            continue
        if raw_resources:
            raw_resources[-1].append(row)

    parsed_resources = (_parse_resource(r) for r in raw_resources)

    return {r.name: r for r in parsed_resources if r}


#   .--Discovery-----------------------------------------------------------.
#   |              ____  _                                                 |
#   |             |  _ \(_)___  ___ _____   _____ _ __ _   _               |
#   |             | | | | / __|/ __/ _ \ \ / / _ \ '__| | | |              |
#   |             | |_| | \__ \ (_| (_) \ V /  __/ |  | |_| |              |
#   |             |____/|_|___/\___\___/ \_/ \___|_|   \__, |              |
#   |                                                  |___/               |
#   +----------------------------------------------------------------------+


def discover_azure_by_metrics(
    *desired_metrics: str,
    resource_type: str | None = None,
) -> Callable[[Section], DiscoveryResult]:
    """Return a discovery function, that will discover if any of the metrics are found"""

    def discovery_function(section: Section) -> DiscoveryResult:
        for item, resource in section.items():
            if (resource_type is None or resource_type == resource.type) and (
                set(desired_metrics) & set(resource.metrics)
            ):
                yield Service(item=item)

    return discovery_function


#   .--Checks--------------------------------------------------------------.
#   |                    ____ _               _                            |
#   |                   / ___| |__   ___  ___| | _____                     |
#   |                  | |   | '_ \ / _ \/ __| |/ / __|                    |
#   |                  | |___| | | |  __/ (__|   <\__ \                    |
#   |                   \____|_| |_|\___|\___|_|\_\___/                    |
#   |                                                                      |
#   +----------------------------------------------------------------------+


def iter_resource_attributes(
    resource: Resource, include_keys: tuple[str] = ("location",)
) -> Iterable[tuple[str, str | None]]:
    def capitalize(string):
        return string[0].upper() + string[1:]

    for key in include_keys:
        if (value := getattr(resource, key)) is not None:
            yield capitalize(key), value

    for key, value in sorted(resource.tags.items()):
        if not key.startswith("hidden-"):
            yield capitalize(key), value


def check_azure_metrics(
    metrics_data: Sequence[MetricData],
) -> Callable[[str, Mapping[str, Any], Section], CheckResult]:
    def check_metric(item: str, params: Mapping[str, Any], section: Section) -> CheckResult:
        resource = section.get(item)
        if not resource:
            raise IgnoreResultsError("Data not present at the moment")

        metrics = [resource.metrics.get(m.azure_metric_name) for m in metrics_data]
        if not any(metrics):
            raise IgnoreResultsError("Data not present at the moment")

        for metric, metric_data in zip(metrics, metrics_data):
            if not metric:
                continue

            yield from check_levels(
                metric.value,
                levels_upper=params.get(metric_data.upper_levels_param),
                levels_lower=params.get(metric_data.lower_levels_param),
                metric_name=metric_data.metric_name,
                label=metric_data.metric_label,
                render_func=metric_data.render_func,
                boundaries=metric_data.boundaries,
            )

    return check_metric


def check_memory() -> Callable[[str, Mapping[str, Any], Section], CheckResult]:
    return check_azure_metrics(
        [
            MetricData(
                "average_memory_percent",
                "mem_used_percent",
                "Memory utilization",
                render.percent,
                upper_levels_param="levels",
            )
        ]
    )


def check_cpu() -> Callable[[str, Mapping[str, Any], Section], CheckResult]:
    return check_azure_metrics(
        [
            MetricData(
                "average_cpu_percent",
                "util",
                "CPU utilization",
                render.percent,
                upper_levels_param="levels",
            )
        ]
    )


def check_connections() -> Callable[[str, Mapping[str, Any], Section], CheckResult]:
    return check_azure_metrics(
        [
            MetricData(
                "average_active_connections",
                "active_connections",
                "Active connections",
                lambda x: str(int(x)),
                upper_levels_param="active_connections",
            ),
            MetricData(
                "total_connections_failed",
                "failed_connections",
                "Failed connections",
                lambda x: str(int(x)),
                upper_levels_param="failed_connections",
            ),
        ]
    )


def check_network() -> Callable[[str, Mapping[str, Any], Section], CheckResult]:
    return check_azure_metrics(
        [
            MetricData(
                "total_network_bytes_ingress",
                "ingress",
                "Network in",
                render.bytes,
                upper_levels_param="ingress_levels",
            ),
            MetricData(
                "total_network_bytes_egress",
                "egress",
                "Network out",
                render.bytes,
                upper_levels_param="egress_levels",
            ),
        ]
    )


def check_storage() -> Callable[[str, Mapping[str, Any], Section], CheckResult]:
    return check_azure_metrics(
        [
            MetricData(
                "average_io_consumption_percent",
                "io_consumption_percent",
                "IO",
                render.percent,
                upper_levels_param="io_consumption",
            ),
            MetricData(
                "average_storage_percent",
                "storage_percent",
                "Storage",
                render.percent,
                upper_levels_param="storage",
            ),
            MetricData(
                "average_serverlog_storage_percent",
                "serverlog_storage_percent",
                "Server log storage",
                render.percent,
                upper_levels_param="serverlog_storage",
            ),
        ]
    )
