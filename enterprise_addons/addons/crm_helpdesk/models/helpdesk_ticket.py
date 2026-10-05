# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def _find_matching_partner(self, force_create=False):
        """ Try to find a matching partner with available information on the
        ticket, using notably customer's name, email, phone, ...

        # TODO : Move this + the one from crm into mail_thread

        :return: partner browse record
        """
        self.ensure_one()
        partner = self.partner_id
        if not partner and self.partner_email:
            partner = self._partner_find_from_emails_single([self.partner_email], no_create=not force_create)
        if not partner and self.partner_phone:
            partner = self.env['res.partner'].search([('phone_mobile_search', '=', self.partner_phone)], limit=1)

        if not partner and force_create:
            partner = self.env['res.partner'].create({
                'name': self.partner_name or self.name,
                'email': self.partner_email,
                'phone': self.partner_phone,
            })

        return partner

    def action_convert_ticket_to_lead_or_opportunity(self):
        return {
            'name': _('Convert to Lead') if self.env.user.has_group('crm.group_use_lead') else _('Convert to Opportunity'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket.to.lead',
            'view_mode': 'form',
            'view_id': self.env.ref('crm_helpdesk.helpdesk_ticket_to_lead_view_form').id,
            'target': 'new',
            'context': {
                'dialog_size': 'medium',
                'default_team_id': self.env['crm.team']._get_default_team_id(user_id=self.user_id.id, domain=None),
            },
        }
