#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


# check_mk plugin to monitor Fujitsu storage systems supporting FJDARY-E60.MIB or FJDARY-E100.MIB
# Copyright (c) 2012 FuH Entwicklungsgesellschaft mbH, Umkirch, Germany. All rights reserved.
# Author: Philipp Hoefflin, 2012, hoefflin+cmk@fuh-e.de

# generic data structure widely used in the FJDARY-Mibs:
# <oid>
# <oid>.1: Index
# <oid>.3: Status
# the latter can be one of the following:

from .agent_based_api.v1 import any_of, equals, register, SNMPTree
from .utils.fjdarye import check_fjdarye_item, discover_fjdarye_item, parse_fjdarye_item

FJDARYE_SUPPORTED_DEVICES = [
    ".1.3.6.1.4.1.211.1.21.1.60",  # fjdarye60
    ".1.3.6.1.4.1.211.1.21.1.150",  # fjdarye500
    ".1.3.6.1.4.1.211.1.21.1.153",  # fjdarye600
]


register.snmp_section(
    name="fjdarye_controller_modules_flash",
    parse_function=parse_fjdarye_item,
    fetch=[
        SNMPTree(base=f"{device_oid}.2.4.2.1", oids=["1", "3"])
        for device_oid in FJDARYE_SUPPORTED_DEVICES
    ],
    detect=any_of(
        *[equals(".1.3.6.1.2.1.1.2.0", device_oid) for device_oid in FJDARYE_SUPPORTED_DEVICES]
    ),
)


register.check_plugin(
    name="fjdarye_controller_modules_flash",
    service_name="Controller Module Flash %s",
    discovery_function=discover_fjdarye_item,
    check_function=check_fjdarye_item,
)
