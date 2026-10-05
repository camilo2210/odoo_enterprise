# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import models


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    def _l10n_ph_hr_payroll_get_rules_per_categories(self):
        """
        Maps category codes to their associated salary rules, recursively rolling rules up
        to all parent categories.

        Example:
            Rule `HP` belongs to `OT`.
            Hierarchy: OT -> TAX_CASH_EARNINGS -> CASH_EARNINGS

            Resulting map:
            {
                'OT':                {'HP'},
                'TAX_CASH_EARNINGS': {'HP', 'BASIC'},
                'CASH_EARNINGS':     {'HP', 'BASIC', ...},
            }

        :return: defaultdict mapping category codes to a set of rule codes
        """
        mapping = defaultdict(set)
        for rule in self.rule_ids:
            for category in rule.category_ids:
                mapping[category.code].add(rule.code)
                parent = category.parent_id
                while parent:
                    mapping[parent.code].add(rule.code)
                    parent = parent.parent_id
        return mapping
