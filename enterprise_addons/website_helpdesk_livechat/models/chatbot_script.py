# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models, fields
from odoo.exceptions import ValidationError


class ChatbotScript(models.Model):
    _inherit = 'chatbot.script'

    ticket_count = fields.Integer(string='Generated Ticket Count', compute='_compute_ticket_count', export_string_translation=False)

    @api.constrains('script_step_ids')
    @api.onchange('script_step_ids')
    def _validate_script_steps(self):
        for step in self.script_step_ids.sorted('sequence'):
            if step.step_type == 'question_email':
                break
            if step.step_type == 'create_ticket':
                raise ValidationError(_('An "Email" step type must exist before the "Create Ticket" step for a ticket to be created.'))

    def _compute_ticket_count(self):
        tickets_data = self.env['helpdesk.ticket'].with_context(active_test=False).sudo()._read_group(
            [('utm_reference', 'in', [f'{script._name},{script.id}' for script in self])],
            ['utm_reference'], ['__count']
        )
        mapped_tickets = dict(tickets_data)
        for script in self:
            script.ticket_count = mapped_tickets.get(f'{script._name},{script.id}', 0)

    def action_view_tickets(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('helpdesk.helpdesk_ticket_action_main_tree')
        action['domain'] = [('utm_reference', '=', f'{self._name},{self.id}')]
        action['context'] = {'create': False}
        return action
