from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    salary_rule_ids = fields.Many2many(
        'hr.salary.rule',
        string="Salary Rules",
        copy=False,
        domain=[('condition_select', '=', 'property_input'), ('input_usage_payslip', '=', True)],
        groups="hr_payroll.group_hr_payroll_user",
    )

    @api.constrains('salary_rule_ids')
    def _check_salary_rule_ids(self):
        for product_template in self:
            rules_per_structure = product_template.salary_rule_ids.grouped('struct_ids')

            # Identify which structures have more than one rule
            duplicate_structures = [struct.display_name for struct, rules in rules_per_structure.items() if len(rules) > 1 and struct]
            if duplicate_structures:
                raise ValidationError(self.env._(
                    "You cannot assign multiple salary rules to the same structure for this product.\n"
                    "Please fix the following structure(s): %s",
                    ", ".join(duplicate_structures)
                ))

            wrong_account_rules = [
                rule.display_name for rule in product_template.salary_rule_ids
                if not rule.account_debit or rule.account_debit.account_type != 'liability_payable']
            if wrong_account_rules:
                raise ValidationError(self.env._(
                    "The salary rules linked to a product must have a debit account of type 'Liability Payable'.\n"
                    "Please fix the following salary rule(s): %s",
                    ", ".join(wrong_account_rules)
                ))
