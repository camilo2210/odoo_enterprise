# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ticket_count = fields.Integer("Tickets", compute='_compute_ticket_count')

    def _count_tickets_by_partner_id(self, extra_domain=[]):
        all_partners_subquery = self.with_context(active_test=False)._search([('id', 'child_of', self.ids)])
        domain = Domain.AND([[('partner_id', 'in', all_partners_subquery)], extra_domain])
        groups = self.env['helpdesk.ticket']._read_group(domain, groupby=['partner_id'], aggregates=['__count'])
        count_by_partner_id = defaultdict(int)
        for partner, count in groups:
            while partner:
                count_by_partner_id[partner.id] += count
                partner = partner.with_context(prefetch_fields=False).parent_id
        return count_by_partner_id

    def _compute_ticket_count(self):
        count_by_partner_id = self._count_tickets_by_partner_id()
        for partner in self:
            partner.ticket_count = count_by_partner_id.get(partner.id, 0)

    def action_open_helpdesk_ticket(self):
        self.ensure_one()
        action = {
            **self.env["ir.actions.actions"]._for_xml_id("helpdesk.helpdesk_ticket_action_main_tree"),
            'display_name': _("%(partner_name)s's Tickets", partner_name=self.name),
            'context': {},
        }
        all_child = self.with_context(active_test=False).search([('id', 'child_of', self.ids)])
        search_domain = [('partner_id', 'in', (self | all_child).ids)]
        if self.ticket_count <= 1:
            ticket_id = self.env['helpdesk.ticket'].search(search_domain, limit=1)
            action['res_id'] = ticket_id.id
            action['views'] = [(view_id, view_type) for view_id, view_type in action['views'] if view_type == "form"]
        else:
            action['domain'] = search_domain
            action['views'] = [
                (self.env['ir.model.data']._xmlid_to_res_id('helpdesk.helpdesk_tickets_view_tree_res_partner'), view_type) if view_type == 'list' else
                (view_id, view_type)
                for view_id, view_type in action['views']
            ]
        return action

    def write(self, vals):
        if vals.get('company_id'):
            tickets_other_company = self.env['helpdesk.ticket'].search_count([('partner_id', 'in', self.ids), ('company_id', '!=', vals['company_id'])], limit=1)
            if tickets_other_company:
                raise UserError(
                    _("You cannot update the company of this partner because it would lead to inconsistency with some of its tickets.")
                )
        return super().write(vals)
