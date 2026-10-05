# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    subscription_count = fields.Integer(string='Subscriptions', compute='_subscription_count')

    def write(self, vals):
        res = super().write(vals)
        if 'active' in vals and not vals.get('active'):
            Subscription = self.env['sale.order']
            order_ids = Subscription.sudo().search([
                ('subscription_state', '=', '3_progress'),
                '|',
                ('partner_shipping_id', 'in', self.ids),
                ('partner_invoice_id', 'in', self.ids)
            ])
            if order_ids:
                contract_str = ", ".join(order_ids.mapped('name'))
                raise ValidationError(_("You can't archive the partner as it is used in the following recurring orders: %s", contract_str))
        return res

    def _subscription_count(self):
        all_partners_subquery = self.with_context(active_test=False)._search([('id', 'child_of', self.ids)])

        subscription_data = self.env['sale.order']._read_group(
            domain=[('partner_id', 'in', all_partners_subquery), ('is_subscription', '=', True), ('subscription_state', 'in', ['3_progress', '6_churn', '4_paused'])],
            groupby=['partner_id'], aggregates=['__count'],
        )

        self.subscription_count = 0
        for partner, count in subscription_data:
            while partner:
                if partner in self:
                    partner.subscription_count += count
                partner = partner.with_context(prefetch_fields=False).parent_id

    def open_related_subscription(self):
        self.ensure_one()
        all_partners = self.with_context(active_test=False).search([('id', 'child_of', self.ids)])
        domain = [('partner_id', 'in', all_partners.ids), ('is_subscription', '=', True), ('subscription_state', 'in', ['3_progress', '6_churn', '4_paused'])]
        subscriptions = self.env['sale.order'].search(domain)

        action = {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "name": _("Partner Subscription"),
            "domain": [('id', 'in', subscriptions.ids)],
            "context": {
                'default_partner_id': self.id,
            }
        }

        if len(subscriptions) == 1:
            action['res_id'] = subscriptions.id
            action['views'] = [(self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]
        else:
            action['views'] = [(self.env.ref('sale_subscription.sale_subscription_view_tree').id, 'list'), (self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]
        return action
