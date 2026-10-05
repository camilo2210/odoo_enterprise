# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import models, fields


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def _default_name(self):
        name = ''
        if helpdesk_ticket_id := self.env.context.get('default_helpdesk_ticket_id'):
            ticket = self.env['helpdesk.ticket'].browse(helpdesk_ticket_id)
            if ticket.has_access('read'):
                name = ticket.name
        return name

    name = fields.Text(default=_default_name)
    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket', string='Original Ticket', index='btree_not_null', readonly=True)

    def action_open_helpdesk_ticket(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('helpdesk.helpdesk_ticket_action_main_my')
        action.update({
            'res_id': self.helpdesk_ticket_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'context': {'create': False},
        })
        return action

    def write(self, vals):
        previous_states_state = None
        if 'state' in vals:
            previous_states_state = {slot: slot.state for slot in self}
        res = super().write(vals)
        if vals.get('state') == '4_completed':
            tracked_interventions = self.filtered(
                lambda t: t.helpdesk_ticket_id.use_fsm and previous_states_state[t] != t.state)
            for slot in tracked_interventions:
                subtype = self.env.ref('helpdesk_planning_field_service.mt_ticket_intervention_completed')
                slot.helpdesk_ticket_id.sudo().message_post(
                    body=slot._get_html_link(),
                    subtype_id=subtype.id,
                )
        return res

    def _reset_intervention_fields(self):
        self.helpdesk_ticket_id = False
        super()._reset_intervention_fields()
