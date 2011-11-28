#!/usr/bin/python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2010             mk@mathias-kettner.de |
# +------------------------------------------------------------------+
#
# This file is part of Check_MK.
# The official homepage is at http://mathias-kettner.de/check_mk.
#
# check_mk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  check_mk is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# ails.  You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

#   .--Views---------------------------------------------------------------.
#   |                    __     ___                                        |
#   |                    \ \   / (_) _____      _____                      |
#   |                     \ \ / /| |/ _ \ \ /\ / / __|                     |
#   |                      \ V / | |  __/\ V  V /\__ \                     |
#   |                       \_/  |_|\___| \_/\_/ |___/                     |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | Views optimated for usage in the mobile UI                           |
#   '----------------------------------------------------------------------'

def mobile_view(d):
    x = {
        'mobile'          : True,
        'browser_reload'  : 0,
        'column_headers'  : 'off',
        'description'     : 'This view is used by the mobile GUI',
        'hidden'          : False,
        'hidebutton'      : False,
        'icon'            : None,
        'mobile'          : True,
        'public'          : True,
        'topic'           : _('Mobile'),
        'user_sortable'   : False,
        'play_sounds'     : False,
        'show_checkboxes' : False,
        'mustsearch'      : False,
    }
    x.update(d)
    return x


multisite_builtin_views.update({
    # View of all current service problems
    'mobile_svcproblems': mobile_view({
        'datasource': 'services',
        'group_painters': [],
        'hard_filters': ['summary_host', 'in_downtime'],
        'hard_filtervars': [
            ('is_service_in_notification_period', '-1'),
            ('hst0', 'on'),
            ('hst1', ''),
            ('hst2', ''),
            ('hstp', 'on'),
            ('is_service_acknowledged', '-1'),
            ('hdst0', 'on'),
            ('hdst1', 'on'),
            ('hdst2', 'on'),
            ('hdst3', 'on'),
            ('hdstp', 'on'),
            ('is_summary_host', '0'),
            ('st0', ''),
            ('st1', 'on'),
            ('st2', 'on'),
            ('st3', 'on'),
            ('stp', ''),
            ('is_in_downtime', '0'),
        ],
        'hide_filters': [],
        'layout': 'mobilelist',
        'name': 'mobile_svcproblems',
        'num_columns': 4,
        'painters': [('service_state_onechar', None, ''),
                     ('svc_state_age', None, ''),
                     ('host', 'mobile_hoststatus', ''),
                     ('service_description',
                      'mobile_service',
                      '')],
        'show_filters': ['service_in_notification_period',
                         'hoststate',
                         'service_acknowledged',
                         'svchardstate',
                         'svcstate'],
        'sorters': [('svcstate', True),
                    ('stateage', False),
                    ('svcdescr', False)],
        'title': _('Service problems (all)'),
    }),

    # View of unhandled service problems
    'mobile_svcproblems_unack': mobile_view({
        'datasource': 'services',
        'group_painters': [],
        'hard_filters': ['summary_host', 'in_downtime', 'service_acknowledged'],
        'hard_filtervars': [
            ('is_service_in_notification_period', '-1'),
            ('hst0', 'on'),
            ('hst1', ''),
            ('hst2', ''),
            ('hstp', 'on'),
            ('is_service_acknowledged', '0'),
            ('hdst0', 'on'),
            ('hdst1', 'on'),
            ('hdst2', 'on'),
            ('hdst3', 'on'),
            ('hdstp', 'on'),
            ('is_summary_host', '0'),
            ('st0', ''),
            ('st1', 'on'),
            ('st2', 'on'),
            ('st3', 'on'),
            ('stp', ''),
            ('is_in_downtime', '0'),
        ],
        'hide_filters': [],
        'layout': 'mobilelist',
        'name': 'mobile_svcproblems',
        'num_columns': 4,
        'painters': [('service_state_onechar', None, ''),
                     ('svc_state_age', None, ''),
                     ('host', 'mobile_hoststatus', ''),
                     ('service_description',
                      'mobile_service',
                      '')],
        'show_filters': ['service_in_notification_period',
                         'hoststate',
                         'service_acknowledged',
                         'svchardstate',
                         'svcstate'],
        'sorters': [('svcstate', True),
                    ('stateage', False),
                    ('svcdescr', False)],
        'title': _('Service problems (unhandled)'),
    }),

    # View showing the details of one service
    'mobile_service': mobile_view({
        'datasource': 'services',
        'group_painters': [],
        'hard_filters': [],
        'hard_filtervars': [],
        'hide_filters': ['site', 'service', 'host'],
        'hidden' : True,
        'layout': 'mobiledataset',
        'linktitle': 'Details',
        'name': 'mobile_service',
        'num_columns': 1,
        'painters': [
            ('sitealias', None, ''),
            ('host', 'hoststatus', ''),
            ('service_description', 'servicedesc', ''),
            ('service_icons', None, ''),
            ('service_state', None, ''),
            ('svc_group_memberlist', None, ''),
            ('svc_contact_groups', None, ''),
            ('svc_contacts', None, ''),
            ('svc_plugin_output', None, ''),
            ('svc_long_plugin_output', None, ''),
            ('svc_perf_data', None, ''),
            ('svc_check_command', None, ''),
            ('svc_attempt', None, ''),
            ('svc_check_type', None, ''),
            ('svc_state_age', None, ''),
            ('svc_check_age', None, ''),
            ('svc_next_check', None, ''),
            ('svc_next_notification', None, ''),
            ('svc_last_notification', None, ''),
            ('svc_check_latency', None, ''),
            ('svc_check_duration', None, ''),
            ('svc_in_downtime', None, ''),
            ('svc_in_notifper', None, ''),
            ('svc_notifper', None, ''),
            ('check_manpage', None, ''),
            ('svc_custom_notes', None, ''),
            ('svc_pnpgraph', None, ''),
        ],
        'show_filters': [],
        'sorters': [],
        'title': _('Service'),
    }),

    # All services of one host
    'mobile_host': mobile_view({
        'datasource': 'services',
        'group_painters': [],
        'hard_filters': [],
        'hard_filtervars': [
              ('st0', 'on'),
              ('st1', 'on'),
              ('st2', 'on'),
              ('st3', 'on'),
              ('stp', 'on'),
        ],
        'hidden': True,
        'hide_filters': ['site', 'host'],
        'layout': 'mobilelist',
        'name': 'mobile_svcproblems',
        'num_columns': 4,
        'painters': [
            ('service_state_onechar', None),
            ('service_description', 'service'),
            ('svc_state_age', None),
            ('perfometer', None),
        ],
        'show_filters': ['svcstate', 'serviceregex'],
        'sorters': [('svcstate', True),
                    ('stateage', False),
                    ('svcdescr', False)],
        'linktitle' : _('Services of this host'),
        'title': _('Services of host'),
    }),

    # View showing the details of one host
    'mobile_hoststatus': mobile_view({
        'datasource': 'hosts',
        'group_painters': [],
        'hard_filters': [],
        'hard_filtervars': [],
        'hide_filters': ['site', 'host'],
        'hidden' : True,
        'icon' : 'status',
        'layout': 'mobiledataset',
        'painters': [
            ('sitealias', None),
            ('host', 'host'),
            ('alias', None),
            ('host_icons', None),
            ('host_state', None),
            ('host_address', None),
            ('host_group_memberlist', None),
            ('host_parents', None),
            ('host_childs', None),
            ('host_contact_groups', None),
            ('host_contacts', None),
            ('host_plugin_output', None),
            ('host_perf_data', None),
            ('host_attempt', None),
            ('host_check_type', None),
            ('host_state_age', None),
            ('host_check_age', None),
            ('host_next_check', None),
            ('host_next_notification', None),
            ('host_last_notification', None),
            ('host_check_latency', None),
            ('host_check_duration', None),
            ('host_in_downtime', None),
            ('host_in_notifper', None),
            ('host_notifper', None),
            ('num_services', 'mobile_host'),
            ('host_pnpgraph', None),
        ],
        'show_filters': [],
        'sorters': [],
        'linktitle': _('Host status'),
        'title': _('Status of Host'),
    }),
})


#.
#   .--Layouts-------------------------------------------------------------.
#   |                _                            _                        |
#   |               | |    __ _ _   _  ___  _   _| |_ ___                  |
#   |               | |   / _` | | | |/ _ \| | | | __/ __|                 |
#   |               | |__| (_| | |_| | (_) | |_| | |_\__ \                 |
#   |               |_____\__,_|\__, |\___/ \__,_|\__|___/                 |
#   |                           |___/                                      |
#   +----------------------------------------------------------------------+
#   | Display-Layouts for the views used by mobile. There are two layouts: |
#   | one for a list of items, one for a single dataset.                   |
#   '----------------------------------------------------------------------'

def render_mobile_list(rows, view, group_painters, painters, num_columns, show_checkboxes):
    if not html.mobile:
        html.show_error(_("This view can only be used in mobile mode."))
        return

    # Force relative timestamp always. This saves space.
    multisite_painter_options["ts_format"]["value"] = "rel"

    odd = "odd"
    html.write('<table class="mobile data">')
    for row in rows:
        odd = odd == "odd" and "even" or "odd"
        html.write('<tr class="%s0">' % odd)
        for n, p in enumerate(painters):
            if n > 0 and n % num_columns == 0:
                html.write('</tr><tr class="%s0">' % odd)
            if n == len(painters) - 1 and n % num_columns != (num_columns - 1):
                tdattrs = 'colspan="%d"' % (num_columns - (n % num_columns))
            else:
                tdattrs = ""
            paint(p, row, tdattrs)
        html.write('</row>')
    html.write('</table>')
    html.javascript('$("table.mobile a").attr("data-ajax", "false");')

multisite_layouts["mobilelist"] = {
    "title"      : _("Mobile: List"),
    "render"     : render_mobile_list,
    "group"      : False,
    "checkboxes" : False,
}

def render_mobile_dataset(rows, view, group_painters, painters, num_columns, show_checkboxes):
    if not html.mobile:
        html.show_error(_("This view can only be used in mobile mode."))
        return

    multisite_painter_options["ts_format"]["value"] = "both"

    for row in rows:
        # html.write('<div data-role="collapsible" data-content-theme="d">')
        # html.write('<h3>Header</h3><p>')
        html.write('<table class=dataset>')
        for p in painters:
            tdclass, content = prepare_paint(p, row)
            # Omit empty cells
            if content:
                painter, link = p[0:2]
                if len(p) >= 5 and p[4]:
                    title = p[4] # Use custom title
                else:
                    title = painter["title"]
                html.write('<tr class=header>')
                html.write('<th>%s</th></tr>\n' % title)
                html.write('<tr class=data>')
                paint(p, row)
                html.write('</tr>\n')
        html.write('</table>')
        # html.write('</p></div>')


multisite_layouts["mobiledataset"] = {
    "title"      : _("Mobile: Dataset"),
    "render"     : render_mobile_dataset,
    "group"      : False,
    "checkboxes" : False,
}

