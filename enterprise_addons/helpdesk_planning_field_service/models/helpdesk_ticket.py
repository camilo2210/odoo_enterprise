# Part of Odoo. See LICENSE file for full copyright and licensing details
from ast import literal_eval
from collections import defaultdict
from odoo import fields, models
from odoo.fields import Domain


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    use_fsm = fields.Boolean(related='team_id.use_fsm', export_string_translation=False)
    planning_slot_count = fields.Integer(compute='_compute_planning_slot_count', export_string_translation=False)
    planning_slot_done_count = fields.Integer(compute='_compute_planning_slot_count', export_string_translation=False)
    scheduled_datetime = fields.Datetime('Scheduled Date', compute='_compute_scheduled_datetime', groups='planning.group_planning_user', export_string_translation=False)

    def _compute_planning_slot_count(self):
        planning_slot_count_per_ticket, planning_slot_done_count_per_ticket = defaultdict(int), defaultdict(int)
        for ticket, state, count in self.env['planning.slot']._read_group(
            [
                ('helpdesk_ticket_id', 'in', self.ids),
            ],
            ['helpdesk_ticket_id', 'state'],
            ['__count'],
        ):
            planning_slot_count_per_ticket[ticket.id] += count
            if state == '4_completed':
                planning_slot_done_count_per_ticket[ticket.id] += count

        for ticket in self:
            ticket.planning_slot_count = planning_slot_count_per_ticket.get(ticket.id, 0)
            ticket.planning_slot_done_count = planning_slot_done_count_per_ticket.get(ticket.id, 0)

    def _compute_scheduled_datetime(self):
        domain = Domain([('start_datetime', '!=', False)])
        scheduled_datetime_per_task = dict(
            self.env['planning.slot']._read_group(
                domain & Domain([('end_datetime', '>=', fields.Datetime.now()), ('helpdesk_ticket_id', 'in', self.ids)]),
                ['helpdesk_ticket_id'],
                ['start_datetime:min'],
            )
        )
        remaining_tickets = self.filtered(lambda t: t not in scheduled_datetime_per_task)
        if remaining_tickets:
            scheduled_datetime_per_task.update(dict(
                self.env['planning.slot']._read_group(
                    domain & Domain('helpdesk_ticket_id', 'in', remaining_tickets.ids),
                    ['helpdesk_ticket_id'],
                    ['start_datetime:max'],
                )
            ))

        for ticket in self:
            ticket.scheduled_datetime = scheduled_datetime_per_task.get(ticket, False)

    def _get_intervention_action(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('planning.planning_action_schedule_by_resource')
        context = dict(
            literal_eval(action.get('context', '{}')),
            default_helpdesk_ticket_id=self.id,
            default_partner_id=self.partner_id.address_get(['delivery']).get('delivery') or self.partner_id.id,
            default_company_id=self.company_id.id,
        )
        if self.scheduled_datetime:
            context['initialDate'] = self.scheduled_datetime
        if self.env.context.get('search_default_ticket'):
            context['search_default_helpdesk_ticket_id'] = self.id
        action['context'] = context
        return action

    def action_view_interventions(self):
        action = self.with_context(search_default_ticket=True)._get_intervention_action()
        action['display_name'] = self.env._('Interventions')
        return action

    def action_plan_intervention(self):
        return self._get_intervention_action()

    # ---------------------------------------------------
    # Mail gateway
    # ---------------------------------------------------

    def _mail_get_message_subtypes(self):
        res = super()._mail_get_message_subtypes()
        if len(self) == 1 and self.team_id:
            intervention_completed_subtype = self.env.ref('helpdesk_planning_field_service.mt_ticket_intervention_completed')
            if not self.team_id.use_fsm and intervention_completed_subtype in res:
                res -= intervention_completed_subtype
        return res
