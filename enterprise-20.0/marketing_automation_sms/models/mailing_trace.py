# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class MailingTrace(models.Model):
    _inherit = 'mailing.trace'

    def set_failed(self, domain=None, failure_reason=False, failure_type=False):
        traces = super().set_failed(domain=domain, failure_reason=failure_reason, failure_type=failure_type)
        marketing_sms_traces = traces.filtered(lambda trace: trace.marketing_trace_id.activity_type == 'sms')
        marketing_sms_traces.marketing_trace_id.action_set_error(message=self.env._('SMS failed'))
        return traces

    def set_clicked(self, domain=None):
        traces = super().set_clicked(domain=domain)
        marketing_sms_traces = traces.filtered(lambda trace: trace.marketing_trace_id.activity_type == 'sms')
        for marketing_trace in marketing_sms_traces.marketing_trace_id:
            marketing_trace.process_event('sms_click')
        return traces

    def set_bounced(self, domain=None, failure_reason=False, failure_type=False):
        traces = super().set_bounced(domain=domain, failure_reason=failure_reason, failure_type=failure_type)
        marketing_sms_traces = traces.filtered(lambda trace: trace.marketing_trace_id.activity_type == 'sms')
        for marketing_trace in marketing_sms_traces.marketing_trace_id:
            marketing_trace.process_event('sms_bounce')
        return traces
