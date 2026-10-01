# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from __future__ import annotations

import logging
import typing

from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.fields import Domain
from odoo.tools.misc import OrderedSet

_logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from odoo.addons.marketing_automation.models.marketing_trace import MarketingTrace


class MarketingActivity(models.Model):
    _inherit = 'marketing.activity'

    activity_type = fields.Selection(selection_add=[
        ('sms', 'SMS')
    ], ondelete={'sms': 'set structure'})
    mass_mailing_id_mailing_type = fields.Selection(selection_add=[('sms', 'SMS')])
    trigger_type = fields.Selection(selection_add=[
        ('sms_click', 'SMS: clicked'),
        ('sms_not_click', 'SMS: not clicked'),
        ('sms_bounce', 'SMS: bounced')
    ], ondelete={
        'sms_click': lambda recs: recs._set_default_trigger_type(),
        'sms_not_click': lambda recs: recs._set_default_trigger_type(),
        'sms_bounce': lambda recs: recs._set_default_trigger_type(),
    })
    trigger_category = fields.Selection(selection_add=[('sms', 'SMS')], compute='_compute_trigger_category')
    trigger_category_ui = fields.Selection(selection_add=[('sms', 'SMS')], compute='_compute_trigger_category_ui')

    def _get_allowed_triggering_activity_types(self):
        allowed_triggering_activity_types = super()._get_allowed_triggering_activity_types()
        allowed_triggering_activity_types.append('sms')
        return allowed_triggering_activity_types

    def _search_can_be_triggering_activity(self, operator, value):
        domain = Domain('activity_type', '=', 'sms')
        if (operator == '=' and False in value) or (operator == '!=' and True in value):
            domain = ~domain
        return domain | super()._search_can_be_triggering_activity(operator, value)

    @api.depends('activity_type', 'mass_mailing_id.subject')
    def _compute_name(self):
        sms_activities = self.filtered(
            lambda activity: activity.activity_type == 'sms')
        super(MarketingActivity, self - sms_activities)._compute_name()
        for activity in sms_activities:
            mailing_subject = activity.mass_mailing_id.subject
            activity.name = _("Send SMS: %(mailing_subject)s", mailing_subject=mailing_subject) \
                if mailing_subject else _("Send SMS")

    def _compute_allowed_trigger_type_ui(self):
        sms_activities = self.filtered_domain([('triggering_activity_id.activity_type', '=', 'sms')])
        sms_activities_grouped_by_is_split = sms_activities.grouped(lambda x: x.activity_type == 'split')
        if (True in sms_activities_grouped_by_is_split):
            sms_activities_grouped_by_is_split[True].allowed_trigger_type_ui = ['click', 'bounce']
        if (False in sms_activities_grouped_by_is_split):
            sms_activities_grouped_by_is_split[False].allowed_trigger_type_ui = ['click', 'not_click', 'bounce']
        super(MarketingActivity, self - sms_activities)._compute_allowed_trigger_type_ui()

    @api.depends('activity_type')
    def _compute_mass_mailing_id_mailing_type(self):
        sms_activities = self.filtered_domain([('activity_type', '=', 'sms')])
        for activity in sms_activities:
            if activity.activity_type == 'sms':
                activity.mass_mailing_id_mailing_type = 'sms'
        super(MarketingActivity, self - sms_activities)._compute_mass_mailing_id_mailing_type()

    @api.depends('trigger_type')
    def _compute_trigger_category(self):
        non_sms_trigger_category = self.env['marketing.activity']
        for activity in self:
            if activity.trigger_type in ['sms_click', 'sms_not_click', 'sms_bounce']:
                activity.trigger_category = 'sms'
            else:
                non_sms_trigger_category |= activity

        super(MarketingActivity, non_sms_trigger_category)._compute_trigger_category()

    def _get_implied_processed_events(self) -> dict[str, set]:
        events = super()._get_implied_processed_events()
        events.update({
            'sms_open': {'sms_open'},
            'sms_click': {'sms_open', 'sms_click'},
            'sms_bounce': {'sms_bounce'}
        })
        return events

    def _get_opposite_trigger_types(self):
        types = super()._get_opposite_trigger_types()
        sms_types = {
            'sms_bounce': (
                ['sms_click', 'activity'],
                self.env._('Parent activity SMS bounced'),
            ),
            'sms_click': (
                ['sms_not_click'],
                self.env._('Parent activity SMS clicked'),
            ),
            'sms_not_click': (
                ['sms_click'], '',
            ),
        }
        types.update(**sms_types)
        return types

    def _get_reschedule_trigger_types(self):
        trigger_types = super()._get_reschedule_trigger_types()
        trigger_types.add('sms_not_click')
        return trigger_types

    def _execute_sms(self, traces: MarketingTrace) -> MarketingTrace:
        """ SMS marketing based activity. Runs on 'res_ids' linked to traces.
        Launch activity's mailing.mailing on traces res_ids in batch.

        :return: correctly processed traces, subset of input 'traces' """
        if not self.env.is_superuser() and not self.env.user.has_group('marketing_automation.group_marketing_automation_user'):
            raise AccessError(_('To use this feature you should be an administrator or belong to the marketing automation group.'))

        res_ids = list(OrderedSet(traces.mapped('res_id')))
        processed_traces = self.env['marketing.trace']

        mailing = self.mass_mailing_id.sudo().with_context(default_marketing_activity_id=self.ids[0])
        try:
            mailing.action_send_sms(res_ids)
        except Exception as e:  # noqa: BLE001
            _logger.warning('Marketing Automation: activity <%s> encountered mass mailing issue %s', self.id, str(e), exc_info=True)
            traces.action_set_error(message=self.env._('Exception in SMS Marketing: %s', e))
        else:
            failed_stats = self.env['mailing.trace'].sudo().search([
                ('marketing_trace_id', 'in', traces.ids),
                ('trace_status', 'in', ['error', 'cancel'])
            ])
            cancel_doc_ids = [stat.res_id for stat in failed_stats if stat.trace_status == 'cancel']
            error_doc_ids = [stat.res_id for stat in failed_stats if stat.trace_status == 'error']

            processed_traces = traces
            canceled_traces = traces.filtered(lambda trace: trace.res_id in cancel_doc_ids)
            error_traces = traces.filtered(lambda trace: trace.res_id in error_doc_ids)

            if canceled_traces:
                canceled_traces.action_set_canceled(message=self.env._('SMS cancelled'), check_participant_completed=False)
                processed_traces = processed_traces - canceled_traces
            if error_traces:
                error_traces.action_set_error(message=self.env._('SMS failed'))
                processed_traces = processed_traces - error_traces
            if processed_traces:
                processed_traces.action_set_processed()
        return processed_traces
