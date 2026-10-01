# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval

from odoo.exceptions import UserError
from odoo.fields import Domain

from odoo import api, fields, models


class L10nSaNationalizationPercentage(models.Model):
    _name = "l10n.sa.nationalization.percentage"
    _description = "Nationalization Percentage Report"

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self: self.env.company)
    department_ids = fields.Many2many('hr.department', string="Departments")
    date = fields.Date(default=fields.Date.context_today)
    excluded_employee_domain = fields.Char("Exclude")
    saudization_rate = fields.Float()

    saudi_employee_ids = fields.Many2many('hr.employee', readonly=True)
    saudi_employees_count = fields.Integer(readonly=True)

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != 'SA':
            raise UserError(self.env._('You must be logged in a SA company to use this feature'))
        return super().default_get(fields)

    @api.depends('date', 'company_id.name')
    def _compute_name(self):
        for report in self:
            report_date = report.date or fields.Date.context_today(report)
            report.name = self.env._("Nationalization for %(company)s on %(date)s", company=report.company_id.name, date=report_date)

    def action_compute_rate(self):
        self.ensure_one()
        report_date = self.date or fields.Date.context_today(self)

        version_domain = Domain([
            ('company_id', '=', self.company_id.id),
            ('contract_date_start', '<=', report_date),
            '|',
                ('contract_date_end', '>=', report_date),
                ('contract_date_end', '=', False),
        ])

        if self.department_ids:
            version_domain &= Domain([('department_id', 'in', self.department_ids.ids)])

        total_employees_count = len(self.env['hr.version'].search(version_domain).mapped('employee_id'))

        if not total_employees_count:
            self.saudi_employee_ids = False
            self.saudi_employees_count = 0
            self.saudization_rate = 0.0
            return

        target_departments = self.department_ids or self.env['hr.department'].search([('company_id', '=', self.company_id.id)])
        wage_domain = Domain.FALSE
        for department in target_departments:
            wage_domain |= Domain([
                ('department_id', '=', department.id),
                ('wage', '>=', department.l10n_sa_saudization_minimum_wage)
            ])

        saudi_version_domain = version_domain & wage_domain & Domain([
            ('employee_id.country_id.code', '=', 'SA')
        ])

        saudi_employees = self.env['hr.version'].search(saudi_version_domain).mapped('employee_id')

        if self.excluded_employee_domain:
            exclude_domain = literal_eval(self.excluded_employee_domain)
            if exclude_domain:
                saudi_employees = self.env['hr.employee'].search(
                    Domain([('id', 'in', saudi_employees.ids)]) & ~Domain(exclude_domain)
                )

        self.saudi_employee_ids = saudi_employees
        self.saudi_employees_count = len(saudi_employees)
        self.saudization_rate = len(saudi_employees) / total_employees_count

    def action_open_employees(self):
        self.ensure_one()
        return {
            'name': self.env._('Saudi Employees'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.saudi_employee_ids.ids)],
            'context': {'create': False},
        }
