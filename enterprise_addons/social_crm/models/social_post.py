# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SocialPost(models.Model):
    _inherit = 'social.post'

    use_leads = fields.Boolean('Use Leads', compute='_compute_use_leads')
    leads_opportunities_count = fields.Integer('Leads / Opportunities count', groups='sales_team.group_sale_salesman',
                                               compute='_compute_leads_opportunities_count', compute_sudo=True)

    def _compute_use_leads(self):
        for post in self:
            post.use_leads = self.env.user.has_group('crm.group_use_lead')

    def _compute_leads_opportunities_count(self):
        lead_data = {}
        if self:
            lead_data = dict(
                self.env['crm.lead']._read_group(
                    [('utm_reference', 'in', [f'{post._name},{post.id}' for post in self])],
                    ['utm_reference'], ['__count'])
                )

        for post in self:
            post.leads_opportunities_count = lead_data.get(f'{post._name},{post.id}', 0)

    def action_redirect_to_leads_opportunities(self):
        view = 'crm.crm_lead_all_leads' if self.use_leads else 'crm.crm_lead_opportunities'
        action = self.env["ir.actions.actions"]._for_xml_id(view)
        action['view_mode'] = 'list,kanban,graph,pivot,form,calendar'
        action['domain'] = [('utm_reference', 'in', [f'{post._name},{post.id}' for post in self])]
        action['context'] = {'active_test': False, 'create': False}
        return action
