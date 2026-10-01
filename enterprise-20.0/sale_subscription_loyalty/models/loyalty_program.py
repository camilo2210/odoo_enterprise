# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    def _get_recurring_rule_matches(self, product_ids_set):
        """ Get the recordsets of the recurring rules that match the order products.

        :param product_ids_set: set of all the products ids in the order.
        :return: rules recordsets matching the order products.
        """
        self.ensure_one()
        matching_rule_ids = self.env['loyalty.rule']
        # Directly check each rule if there is an intersection between the order products and the valid rule produts.
        for rule in self.rule_ids:
            if rule.recurring_invoice:
                # For each recurring rule, we check if the sub products match the rule domain.
                valid_product_ids_set = set(rule._get_valid_products().ids)
                # If no products are specified, the rule applies to all products.
                if not valid_product_ids_set or product_ids_set.intersection(valid_product_ids_set):
                    matching_rule_ids |= rule
        return matching_rule_ids
