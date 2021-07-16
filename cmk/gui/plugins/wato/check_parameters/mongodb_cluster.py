#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from cmk.gui.i18n import _
from cmk.gui.plugins.wato import (
    CheckParameterRulespecWithItem,
    RulespecGroupCheckParametersStorage,
    rulespec_registry,
)
from cmk.gui.valuespec import Dictionary, Integer, TextInput, Tuple


def _parameter_valuespec_mongodb_cluster() -> Dictionary:
    return Dictionary(elements=[
        (
            "levels_number_jumbo",
            Tuple(
                title=_("Number of jumbo chunks per shard per collection"),
                elements=[
                    Integer(title=_("Warning if above"), unit=_("count"), minvalue=0),
                    Integer(title=_("Critical if above"), unit=_("count"), minvalue=0),
                ],
            ),
        ),
    ])


rulespec_registry.register(
    CheckParameterRulespecWithItem(
        check_group_name="mongodb_cluster",
        group=RulespecGroupCheckParametersStorage,
        item_spec=lambda: TextInput(title=_(
            "Database/Collection name ('<DB name> <collection name>')"),),
        match_type="dict",
        parameter_valuespec=_parameter_valuespec_mongodb_cluster,
        title=lambda: _("MongoDB Cluster"),
    ))
