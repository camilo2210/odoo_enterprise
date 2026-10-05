# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError


class HrSalaryRuleSection(models.Model):
    _name = 'hr.salary.rule.section'
    _description = 'Salary Input Section'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer()
    struct_ids = fields.Many2many('hr.payroll.structure', string="Available in Salary Structure")

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_used_in_salary_structure(self):
        if self.env['hr.salary.rule'].search_count([
            ('input_section', 'in', self.ids),
            ('input_used_in_definition', '=', True)
        ], limit=1):
            raise UserError(self.env._(
                "You cannot delete a section currently used in a salary structure."
            ))
