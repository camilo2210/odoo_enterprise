# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import fields, models


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    country_code = fields.Char(related='country_id.code')
    l10n_hk_is_termination_pay = fields.Boolean(
        string='Is Termination',
        help="If checked, Payslips using this structure will be excluded from the ADW / 713 Ordinance calculations."
    )

    def _l10n_hk_get_rules_per_categories(self):
        """
        Maps category codes to their associated salary rules, recursively rolling rules up
        to all parent categories.

        Example:
            Rule `OVERSEAS_PAY` belongs to `OVERSEAS_INCOME`.
            Hierarchy: OVERSEAS_INCOME -> HK_BASIC -> GROSS_CASH

            Resulting map:
            {
                'OVERSEAS_INCOME': {'OVERSEAS_PAY': <rule>},
                'HK_BASIC':        {'OVERSEAS_PAY': <rule>, 'BASIC': <rule>},
                'GROSS_CASH':      {'OVERSEAS_PAY': <rule>, 'BASIC': <rule>, ...},
            }

        :return: defaultdict mapping category codes to a dict of {rule_code: rule_record}
        """
        mapping = defaultdict(dict)
        for rule in self.rule_ids:
            for category in rule.category_ids:
                mapping[category.code][rule.code] = rule
                while category.parent_id:
                    category = category.parent_id
                    mapping[category.code][rule.code] = rule
        return mapping
