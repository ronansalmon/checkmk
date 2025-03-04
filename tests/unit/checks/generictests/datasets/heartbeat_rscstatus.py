#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# fmt: off
# type: ignore

checkname = 'heartbeat_rscstatus'

info = [['all']]

discovery = {'': [(None, {'discovered_state': 'all'})]}

checks = {
    '': [
        (None, {'discovered_state': 'all'}, [
            (0, 'Current state: all', []),
        ]),
        (None, {'discovered_state': 'local'}, [
            (2, 'Current state: all (Expected: local)', []),
        ]),
        (None, '"all"', [
            (0, 'Current state: all', []),
        ]),
        (None, '"local"', [
            (2, 'Current state: all (Expected: local)', []),
        ]),
    ],
}
