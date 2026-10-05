# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MailingTrace(models.Model):
    _inherit = 'mailing.trace'

    marketing_trace_id = fields.Many2one(
        'marketing.trace', string='Marketing Trace',
        index=True, ondelete='cascade')

    def set_failed(self, domain=None, failure_reason=False, failure_type=False):
        traces = super().set_failed(domain=domain, failure_reason=failure_reason, failure_type=failure_type)
        marketing_mail_traces = traces.filtered(lambda trace: trace.marketing_trace_id.activity_type == 'mail')
        marketing_mail_traces.marketing_trace_id.action_set_error(message=self.env._('Email failed'))
        return traces

    def set_clicked(self, domain=None):
        traces = super().set_clicked(domain=domain)
        marketing_mail_traces = traces.filtered(lambda trace: trace.marketing_trace_id.activity_type == 'mail')
        for marketing_trace in marketing_mail_traces.marketing_trace_id:
            marketing_trace.process_event('mail_click')
        return traces

    def set_opened(self, domain=None):
        traces = super().set_opened(domain=domain)
        marketing_mail_traces = traces.filtered(lambda trace: trace.marketing_trace_id.activity_type == 'mail')
        for marketing_trace in marketing_mail_traces.marketing_trace_id:
            marketing_trace.process_event('mail_open')
        return traces

    def set_replied(self, domain=None):
        traces = super().set_replied(domain=domain)
        marketing_mail_traces = traces.filtered(lambda trace: trace.marketing_trace_id.activity_type == 'mail')
        for marketing_trace in marketing_mail_traces.marketing_trace_id:
            marketing_trace.process_event('mail_reply')
        return traces

    def set_bounced(self, domain=None, failure_reason=False, failure_type=False):
        traces = super().set_bounced(domain=domain, failure_reason=failure_reason, failure_type=failure_type)
        marketing_mail_traces = traces.filtered(lambda trace: trace.marketing_trace_id.activity_type == 'mail')
        for marketing_trace in marketing_mail_traces.marketing_trace_id:
            marketing_trace.process_event('mail_bounce')
        return traces
