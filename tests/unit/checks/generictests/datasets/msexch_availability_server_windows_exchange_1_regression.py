#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# fmt: off
# type: ignore

checkname = 'msexch_availability'

info = [[
    'AvailabilityRequestssec', 'AverageNumberofMailboxesProcessedperRequest',
    'AverageNumberofMailboxesProcessedperRequest_Base',
    'AverageTimetoMapExternalCallertoInternalIdentity',
    'AverageTimetoMapExternalCallertoInternalIdentity_Base',
    'AverageTimetoProcessaCrossForestFreeBusyRequest',
    'AverageTimetoProcessaCrossForestFreeBusyRequest_Base',
    'AverageTimetoProcessaCrossSiteFreeBusyRequest',
    'AverageTimetoProcessaCrossSiteFreeBusyRequest_Base',
    'AverageTimetoProcessaFederatedFreeBusyRequest',
    'AverageTimetoProcessaFederatedFreeBusyRequest_Base',
    'AverageTimetoProcessaFederatedFreeBusyRequestwithOAuth',
    'AverageTimetoProcessaFederatedFreeBusyRequestwithOAuth_Base',
    'AverageTimetoProcessaFreeBusyRequest', 'AverageTimetoProcessaFreeBusyRequest_Base',
    'AverageTimetoProcessaMeetingSuggestionsRequest',
    'AverageTimetoProcessaMeetingSuggestionsRequest_Base',
    'AverageTimetoProcessanIntraSiteFreeBusyRequest',
    'AverageTimetoProcessanIntraSiteFreeBusyRequest_Base', 'Caption',
    'ClientReportedFailuresAutodiscoverFailures', 'ClientReportedFailuresConnectionFailures',
    'ClientReportedFailuresPartialorOtherFailures', 'ClientReportedFailuresTimeoutFailures',
    'ClientReportedFailuresTotal', 'CrossForestCalendarFailuressec',
    'CrossForestCalendarQueriessec', 'CrossSiteCalendarFailuressec',
    'CrossSiteCalendarQueriessec', 'CurrentRequests', 'Description',
    'FederatedFreeBusyCalendarQueriesincludingOAuthsec', 'FederatedFreeBusyFailuressec',
    'FederatedFreeBusyFailureswithOAuthsec', 'ForeignConnectorQueriessec',
    'ForeignConnectorRequestFailureRate', 'Frequency_Object', 'Frequency_PerfTime',
    'Frequency_Sys100NS', 'IntraSiteCalendarFailuressec', 'IntraSiteCalendarQueriessec',
    'IntraSiteProxyFreeBusyCalendarQueriessec', 'IntraSiteProxyFreeBusyFailuressec', 'Name',
    'PublicFolderQueriessec', 'PublicFolderRequestFailuressec',
    'SuccessfulClientReportedRequestsLessthan10seconds',
    'SuccessfulClientReportedRequestsLessthan20seconds',
    'SuccessfulClientReportedRequestsLessthan5seconds',
    'SuccessfulClientReportedRequestsOver20seconds', 'SuccessfulClientReportedRequestsTotal',
    'SuggestionsRequestssec', 'Timestamp_Object', 'Timestamp_PerfTime', 'Timestamp_Sys100NS'
],
        [
            '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0',
            '0', '0', '0', '0', '0', '', '0', '0', '0', '0', '0', '0', '0', '0', '0',
            '0', '', '0', '0', '0', '0', '0', '0', '1953125', '10000000', '0', '0',
            '0', '0', '', '0', '0', '0', '0', '0', '0', '0', '0', '0', '6743176212200',
            '130951777565030000'
        ]]

discovery = {'': [(None, None)]}

checks = {
    '': [(None, {}, [(0, 'Requests/sec: 0.00', [('requests_per_sec', 0.0, None, None, None,
                                                None)])])]
}
