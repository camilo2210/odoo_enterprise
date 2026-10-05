# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrSalaryRuleCategory(models.Model):
    _name = 'hr.salary.rule.category'
    _description = 'Salary Rule Category'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    parent_id = fields.Many2one('hr.salary.rule.category', string='Parent', index=True,
        help="Linking a salary category to its parent is used only for the reporting purpose.",
        domain="['|', ('country_id', '=', False), ('country_id', '=', country_id)]")
    children_ids = fields.One2many('hr.salary.rule.category', 'parent_id', string='Children')
    note = fields.Html(string='Description')
    country_id = fields.Many2one(
        'res.country',
        string="Country",
        default=lambda self: self.env.company.country_id,
        domain=lambda self: [('id', 'in', self.env.companies.country_id.ids)]
    )
    salary_rule_ids = fields.Many2many('hr.salary.rule', compute='_compute_salary_rule_ids', string='Salary Rules')
    optional_on_work_entry_type_ids = fields.Many2many('hr.work.entry.type',
        relation='hr_salary_rule_category_options_hr_work_entry_type_rel',
        string="Optional on", groups='hr_payroll.group_hr_payroll_user',
        domain="[('country_id', '=', country_id)]",
        help="Time Types on which this category can be added optionally on time off created by HR user")
    is_premium_pay = fields.Boolean(string="Premium Pay",
        help="Legal premium pay category. Custom premium pays can be created as children of this category to grant an extra amount on top of the legal rate.")
    parent_is_premium_pay = fields.Boolean(related='parent_id.is_premium_pay', string="Parent is a Premium Pay")
    premium_amount_per_hour = fields.Float(string="Amount per Hour",
        help="Extra amount granted per hour of worked time carrying this premium pay.")
    premium_amount_per_day = fields.Float(string="Amount per Day",
        help="Extra amount granted per day of worked time carrying this premium pay.")
    premium_percentage_hourly_rate = fields.Float(string="Percentage of Hourly Rate",
        help="Extra percentage of the worked time own hourly rate granted per hour of worked time carrying this premium pay.")
    active = fields.Boolean(string="Active", default=True)

    def _compute_salary_rule_ids(self):
        for category in self:
            rules = self.env['hr.salary.rule'].search([
                '|',
                    ('category_ids', 'child_of', category.id),
                    ('category_ids', 'parent_of', category.id),
            ])
            category.salary_rule_ids = rules

    def action_open_salary_rules(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Salary Rules'),
            'res_model': 'hr.salary.rule',
            'view_mode': 'list,form',
            'domain': ['|', ('category_ids', 'child_of', self.id), ('category_ids', 'parent_of', self.id)],
            'context': {'default_category_ids': [self.id]},
        }

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if self._has_cycle():
            raise ValidationError(_('Error! You cannot create recursive hierarchy of Salary Rule Category.'))

    @api.constrains('country_id')
    def _check_rule_category_country(self):
        for category in self:
            if category.country_id and self.env['hr.salary.rule'].sudo().search_count([('category_ids', 'in', category.id), ('country_id', '!=', category.country_id.id)], limit=1):
                raise UserError(_('You cannot change the country of category %s as it is used in existing Salary Rules', category.name))

    def _get_codes_with_ancestors(self):
        """Return the set of codes of these categories and all their ancestors."""
        codes = set()
        for category in self:
            while category:
                codes.add(category.code)
                category = category.parent_id
        return codes

    def _sum_salary_rule_category(self, localdict, amount):
        for category in self:
            if category.parent_id:
                localdict = category.parent_id._sum_salary_rule_category(localdict, amount)
            localdict['categories'][category.code] += amount
        return localdict

    def _get_seized_categories(self):
        return self.browse()
