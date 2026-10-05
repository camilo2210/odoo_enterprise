# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'

    recurring_invoice = fields.Boolean(
        string="Recurring",
        help="New points will be granted for each renewed period.",
    )

    @api.constrains('recurring_invoice', 'program_id')
    def _check_recurring_invoice(self):
        for rule in self:
            if rule.recurring_invoice and rule.program_id.applies_on not in ('future', 'both'):
                raise ValidationError(_("The recurring option on a loyalty rule is only available for programs that apply to future orders."))

    def _get_rule_matches_with_subscription_program(self, order_id):
        """ Returns the loyalty.rule recordset matching the subscription products. """
        recurring_programs = self.env['loyalty.program'].search([
            ('active', '=', True),
            ('rule_ids.recurring_invoice', '=', True),
        ])
        order_product_ids_set = set(order_id.order_line.product_id.ids)
        rule_matches = self.env['loyalty.rule']
        for program in recurring_programs:
            rule_matches |= program._get_recurring_rule_matches(order_product_ids_set)
        return rule_matches
