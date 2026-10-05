from __future__ import annotations

import logging
import typing

from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.fields import Domain
from odoo.tools import SQL
from odoo.tools.misc import OrderedSet

_logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from odoo.addons.marketing_automation.models.marketing_trace import MarketingTrace


class MarketingActivity(models.Model):
    _inherit = 'marketing.activity'

    activity_type = fields.Selection(selection_add=[
        ('whatsapp', 'Whatsapp Message')
    ], ondelete={'whatsapp': 'set structure'})

    whatsapp_template_id = fields.Many2one(
        "whatsapp.template",
        string="Whatsapp Template",
        compute="_compute_whatsapp_template_id",
        readonly=False,
        index=True,
        ondelete="restrict",
        store=True,
    )

    trigger_type = fields.Selection(selection_add=[
        ('whatsapp_click', 'Whatsapp: click'),
        ('whatsapp_not_click', 'Whatsapp: not click'),
        ('whatsapp_open', 'Whatsapp: opened'),
        ('whatsapp_not_open', 'Whatsapp: not opened'),
        ('whatsapp_reply', 'Whatsapp: replied'),
        ('whatsapp_not_reply', 'Whatsapp: not replied'),
        ('whatsapp_bounce', 'Whatsapp: message bounced'),
    ], ondelete={
        'whatsapp_click': lambda recs: recs._set_default_trigger_type(),
        'whatsapp_not_click': lambda recs: recs._set_default_trigger_type(),
        'whatsapp_open': lambda recs: recs._set_default_trigger_type(),
        'whatsapp_not_open': lambda recs: recs._set_default_trigger_type(),
        'whatsapp_reply': lambda recs: recs._set_default_trigger_type(),
        'whatsapp_not_reply': lambda recs: recs._set_default_trigger_type(),
        'whatsapp_bounce': lambda recs: recs._set_default_trigger_type(),
    })
    trigger_category = fields.Selection(selection_add=[('whatsapp', 'WhatsApp')], compute='_compute_trigger_category')
    trigger_category_ui = fields.Selection(selection_add=[('whatsapp', 'WhatsApp')], compute='_compute_trigger_category_ui')
    whatsapp_error = fields.Boolean('Whatsapp Error', compute="_compute_whatsapp_error", store=True)

    def _get_allowed_triggering_activity_types(self):
        allowed_triggering_activity_types = super()._get_allowed_triggering_activity_types()
        allowed_triggering_activity_types.append('whatsapp')
        return allowed_triggering_activity_types

    @api.depends('activity_type')
    def _compute_mass_mailing_id(self):
        whatsapp_activities = self.filtered(lambda activity: activity.activity_type == 'whatsapp')
        whatsapp_activities.mass_mailing_id = False
        super(MarketingActivity, self - whatsapp_activities)._compute_mass_mailing_id()

    @api.depends('triggering_activity_id', 'triggering_activity_id.activity_type')
    def _compute_trigger_category(self):
        whatsapp_types = ['whatsapp_click', 'whatsapp_not_click',
                          'whatsapp_open', 'whatsapp_not_open', 'whatsapp_reply',
                          'whatsapp_not_reply', 'whatsapp_bounce', 'message_cancel']
        whatsapp_activities = self.filtered(lambda activity: activity.trigger_type in whatsapp_types)
        whatsapp_activities.trigger_category = 'whatsapp'
        super(MarketingActivity, self - whatsapp_activities)._compute_trigger_category()

    @api.depends('activity_type', 'whatsapp_template_id')
    def _compute_name(self):
        whatsapp_activities = self.filtered(
            lambda activity: activity.activity_type == 'whatsapp')
        super(MarketingActivity, (self - whatsapp_activities))._compute_name()
        for record in whatsapp_activities:
            template_name = record.whatsapp_template_id.name
            record.name = _("Send Whatsapp: %(template_name)s", template_name=template_name) \
                if template_name else _("Send Whatsapp")

    def _inverse_trigger_type_ui(self):
        whatsapp_triggered = self.filtered_domain([('triggering_activity_id.activity_type', '=', 'whatsapp'), ('trigger_type_ui', 'not in', ['click', 'not_click'])])
        super(MarketingActivity, self - whatsapp_triggered)._inverse_trigger_type_ui()
        for record in whatsapp_triggered:
            trigger = record.trigger_type_ui.replace("open", "read").replace("reply", "replied").replace("bounce", "bounced")
            record.trigger_type = f"whatsapp_{trigger}"

    @api.onchange('whatsapp_template_id')
    def _compute_whatsapp_error(self):
        failing = self.filtered(
            lambda a: a.whatsapp_template_id and any(btn.url_type != 'tracked' for btn in a.whatsapp_template_id.button_ids)
        )
        (self - failing).whatsapp_error = False
        failing.whatsapp_error = True

    @api.depends('activity_type')
    def _compute_whatsapp_template_id(self):
        non_whatsapp_activities = self.filtered(lambda activity: activity.activity_type != 'whatsapp')
        non_whatsapp_activities.whatsapp_template_id = False

    def _search_can_be_triggering_activity(self, operator, value):
        domain = Domain('activity_type', '=', 'whatsapp')
        if (operator == '=' and False in value) or (operator == '!=' and True in value):
            domain = ~domain
        return domain | super()._search_can_be_triggering_activity(operator, value)

    def _get_full_statistics(self):
        whatsapp_activities = self.filtered(lambda activity: activity.activity_type == 'whatsapp')
        non_whatsapp_activities = self - whatsapp_activities

        non_whatsapp_stats = (
            super(MarketingActivity, non_whatsapp_activities)._get_full_statistics()
            if non_whatsapp_activities else []
        )

        if not whatsapp_activities:
            return non_whatsapp_stats

        self.env["marketing.trace"].flush_model(["activity_id", "whatsapp_message_id", "participant_id"])
        self.env["whatsapp.message"].flush_model(["state", "links_click_datetime"])
        self.env.cr.execute(SQL("""
            SELECT
                trace.activity_id,
                COUNT(wa_message.state) FILTER (WHERE wa_message.state in ('sent', 'delivered', 'read', 'replied')) AS total_sent,
                COUNT(wa_message.state) FILTER (WHERE wa_message.state in ('read', 'replied')) AS total_open,
                COUNT(wa_message.state) FILTER (WHERE wa_message.state in ('replied')) AS total_reply,
                COUNT(wa_message.state) FILTER (WHERE wa_message.state in ('error')) AS rejected,
                COUNT(wa_message.state) FILTER (WHERE wa_message.links_click_datetime is NOT NULL) AS total_click
            FROM
                marketing_trace AS trace
            LEFT JOIN
                whatsapp_message AS wa_message
            ON (wa_message.id = trace.whatsapp_message_id)
            JOIN
                marketing_participant AS part
            ON (trace.participant_id = part.id)
            WHERE
                (part.is_test = false or part.is_test IS NULL) AND
                trace.activity_id IN %s
            GROUP BY
            trace.activity_id;
        """, tuple(whatsapp_activities.ids)))

        return non_whatsapp_stats + self.env.cr.dictfetchall()

    def _get_implied_processed_events(self):
        events = super()._get_implied_processed_events()
        events.update({
            'whatsapp_open': {'whatsapp_open'},
            'whatsapp_click': {'whatsapp_open', 'whatsapp_click'},
            'whatsapp_reply': {'whatsapp_open', 'whatsapp_click', 'whatsapp_reply'},
            'whatsapp_bounce': {'whatsapp_bounce'}
        })
        return events

    def _get_opposite_trigger_types(self):
        types = super()._get_opposite_trigger_types()
        wa_types = {
            'whatsapp_bounce': (
                ['whatsapp_click', 'whatsapp_open', 'whatsapp_reply', 'activity'],
                self.env._('Parent whatsapp message bounced'),
            ),
            'whatsapp_click': (
                ['whatsapp_not_click'],
                self.env._('Parent whatsapp message clicked'),
            ),
            'whatsapp_not_click': (
                ['whatsapp_click'], '',
            ),
            'whatsapp_not_open': (
                ['whatsapp_open'], '',
            ),
            'whatsapp_not_reply': (
                ['whatsapp_reply'], '',
            ),
            'whatsapp_open': (
                ['whatsapp_not_open'],
                self.env._('Parent whatsapp message opened'),
            ),
            'whatsapp_reply': (
                ['whatsapp_not_reply'],
                self.env._('Parent whatsapp message replied to'),
            ),
        }
        types.update(**wa_types)
        return types

    def _get_reschedule_trigger_types(self):
        types = super()._get_reschedule_trigger_types()
        types |= {'whatsapp_not_open', 'whatsapp_not_reply', 'whatsapp_not_click'}
        return types

    @api.model
    def _is_a_reply_trigger_type(self, trigger_type):
        return super()._is_a_reply_trigger_type(trigger_type) or trigger_type == 'whatsapp_reply'

    def _execute_whatsapp(self, traces: MarketingTrace) -> MarketingTrace:
        """ WhatsApp sending based activity. Runs on 'res_ids' linked to traces.
        Launch a 'whatsapp.composer' in batch mode on traces res_ids.

        :return: correctly processed traces, subset of input 'traces' """
        if not self.env.is_superuser() and not self.env.user.has_group('marketing_automation.group_marketing_automation_user'):
            raise AccessError(_('To use this feature you should be an administrator or belong to the marketing automation group.'))

        res_ids = list(OrderedSet(traces.mapped('res_id')))
        processed_traces = self.env['marketing.trace']

        composer_vals = {
            'batch_mode': True,
            'res_ids': res_ids,
            'res_model': self.model_name,
            'wa_template_id': self.whatsapp_template_id.id,
        }
        try:
            composer = self.env['whatsapp.composer'].with_context(active_model=self.model_name).create(composer_vals)
            messages_values = composer._create_whatsapp_messages_values(skip_raise_number=True)
            trace_by_res_id = {t.res_id: t for t in traces}
            for res_id, message_values in zip(res_ids, messages_values):
                if trace := trace_by_res_id.get(res_id):
                    message_values['marketing_trace_ids'] = [(4, trace.id)]

            # at most 500 messages are sent at one go, so there is no reason to divide them further.
            messages = self.env['whatsapp.message'].create(messages_values)
            messages._send()

        except Exception as e:  # noqa: BLE001 we don't want to crash because if error occurs during sending, we should assign traces 'error' state
            _logger.warning('Marketing Automation: activity <%s> encountered WhatsApp message issue %s', self.id, str(e))
            traces.action_set_error(message=self.env._('Exception in Whatsapp Marketing: %s', e))
        else:
            cancelled_traces = traces.filtered(lambda trace: trace.whatsapp_message_id.state == 'cancel')
            error_traces = traces.filtered(lambda trace: trace.whatsapp_message_id.state == 'error')

            if cancelled_traces:
                cancelled_traces.action_set_canceled(message=self.env._('WhatsApp canceled'), check_participant_completed=False)
            if error_traces:
                error_traces.action_set_error(message=self.env._('WhatsApp failed'))
            processed_traces = traces - (cancelled_traces | error_traces)
            if processed_traces:
                processed_traces.action_set_processed()
        return processed_traces

    def action_view_sent_wa(self):
        return self._action_view_documents_filtered_wa('sent')

    def action_view_delivered_wa(self):
        return self._action_view_documents_filtered_wa('delivered')

    def action_view_read_wa(self):
        return self._action_view_documents_filtered_wa('read')

    def action_view_clicked_wa(self):
        return self._action_view_documents_filtered_wa('clicked')

    def action_view_replied_wa(self):
        return self._action_view_documents_filtered_wa('replied')

    def _action_view_documents_filtered_wa(self, view_filter: str) -> dict[str, str]:
        """Return an action with a domain tailored to the `view_filter` parameter.

        The domain dynamically includes WhatsApp message states based on `view_filter` values:
        - 'sent', 'delivered', 'read', 'replied': The filter builds on state progressions, where 'delivered' includes 'sent', etc.
        - 'clicked': Filters for messages with clicked links.
        Other values default to all traces.

        :param view_filter:  A filter condition ('sent', 'delivered', 'read', 'replied', 'clicked', etc.).
        :return: Updated action dictionary with domain and context set according to the filter.
        """
        action = self.env["ir.actions.actions"]._for_xml_id("marketing_automation.marketing_participants_action_mail")
        orders = ['sent', 'delivered', 'read', 'replied']
        if view_filter in orders:
            idx = orders.index(view_filter)
            found_traces = self.trace_ids.filtered(lambda trace: trace.whatsapp_message_id.state in orders[idx:])
        elif view_filter == 'clicked':
            found_traces = self.trace_ids.filtered(lambda trace: trace.whatsapp_message_id.links_click_datetime)
        else:
            found_traces = self.env['marketing.trace']

        action.update({
            'display_name': _('Participants of %(name)s (%(filter)s)', name=self.name, filter=view_filter),
            'domain': [('id', 'in', found_traces.participant_id.ids)],
            'context': dict(self.env.context, create=False)
        })
        return action
