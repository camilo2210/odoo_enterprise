# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nInGratuityCalculationReportWizard(models.TransientModel):
    _name = 'l10n.in.gratuity.calculation.report.wizard'
    _description = 'Gratuity Calculation Report'

    @api.model
    def default_get(self, field_list=None):
        if self.env.company.country_id.code != "IN":
            raise UserError(self.env._('You must be logged in a Indian company to use this feature'))
        return super().default_get(field_list)

    def _get_structure_domain(self):
        return ['|', ('country_id', '=', self.env.ref('base.in').id), ('country_id', '=', False)]

    def _get_employee_domain(self):
        employees = self.env['hr.payslip'].search(
            [('state', 'in', ['validated', 'paid'])]
        ).employee_id.filtered(lambda e: e.company_id.country_id.code == "IN").ids
        return [('id', 'in', employees)]

    selection_mode = fields.Selection([
        ('employee', 'By Employee'),
        ('department', 'By Department'),
        ('job_position', 'By Job Position'),
        ('salary_structure', 'By Salary Structure'),
        ('employee_tag', 'By Employee Tag')
        ], default="employee")
    department_id = fields.Many2one('hr.department')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    job_id = fields.Many2one('hr.job')
    struct_id = fields.Many2one('hr.payroll.structure', domain=_get_structure_domain)
    tag_ids = fields.Many2many('hr.employee.category', 'emp_tag_rel')
    all_employee_ids = fields.Many2many('hr.employee', string="Employee", domain="[('company_id', 'in', allowed_company_ids)]")
    employee_ids = fields.Many2many('hr.employee', 'employee_payslip_rel', string='Employees', required=True,
        domain=_get_employee_domain, compute="_compute_employee_ids", store=True, readonly=False)

    @api.depends('selection_mode', 'department_id', 'job_id', 'struct_id', 'tag_ids', 'all_employee_ids')
    def _compute_employee_ids(self):
        for record in self:
            domain = [('company_id', 'in', self.env.companies.ids), ('state', 'in', ['validated', 'paid'])]
            if record.selection_mode == "department":
                domain.append(('department_id', '=', record.department_id))
            elif record.selection_mode == "job_position":
                domain.append(('job_id', '=', record.job_id))
            elif record.selection_mode == "salary_structure":
                domain.append(('struct_id', '=', record.struct_id))
            elif record.selection_mode == "employee_tag":
                domain.append(('employee_id.category_ids', 'in', record.tag_ids))
            elif record.selection_mode == "employee":
                if record.all_employee_ids:
                    domain.append(('employee_id', 'in', record.all_employee_ids))

            payslips = record.env['hr.payslip'].search(domain)
            record.employee_ids = payslips.employee_id.filtered(lambda e: e.company_id.country_id.code == "IN")

    def action_generate_xlsx(self):
        self.ensure_one()
        return {
            'name': self.env._('Generate Gratuity Calculation Report in XLSX format'),
            'type': 'ir.actions.act_url',
            'url': '/export/gratuity_calculation_report/%s' % (self.id),
        }
