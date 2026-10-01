# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.date_utils import start_of

from dateutil.relativedelta import relativedelta


class HrSalaryAttachmentGenerateMultiWizard(models.TransientModel):
    _name = 'hr.salary.attachment.generate.multi.wizard'
    _description = 'Generate payslip adjustments for multiple employees'

    employee_ids = fields.Many2many('hr.employee', string='Employees', required=True,
        domain=lambda self: [('company_id', 'in', self.env.companies.ids)])
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    salary_rule_id = fields.Many2one('hr.salary.rule', string="Salary Rule", required=True,
        domain=[('input_usage_payslip', '=', True)])
    description = fields.Char(string="Note")
    amount = fields.Monetary('Payslip Amount', required=True, help='Amount to pay each payslip.')
    is_recurring = fields.Boolean('Repeat')
    date_start = fields.Date('Start Date', required=True, default=lambda r: start_of(fields.Date.context_today(r), 'month'))
    date_end = fields.Date('End Date', default=False, help='Date at which this assignment has been set as completed.')
    date_estimated_end = fields.Date(
        'Estimated End Date',
        help='Approximated end date.',
    )
    remaining_time = fields.Char('Remaining Time', compute='_compute_remaining_time', help='Remaining time to be paid.')

    _check_amount = models.Constraint(
        'CHECK (amount > 0)',
        'Oops! Let’s keep the payslip amount strictly positive. We want to deduct money from our employee’s payslip, not add to it!'
    )
    _check_dates = models.Constraint(
        'CHECK (date_start <= date_end)',
        "End date may not be before the starting date.",
    )

    @api.depends('is_recurring', 'date_end', 'date_estimated_end')
    def _compute_remaining_time(self):
        self.ensure_one()
        date_end = self.date_estimated_end or self.date_end
        if not self.is_recurring or not date_end:
            self.remaining_time = False
        else:
            delta = relativedelta(date_end, fields.Date.context_today(self).replace(day=1))
            if delta:
                if delta.years:
                    self.remaining_time = self.env._("%(years)s years", years=delta.years)
                elif delta.months:
                    self.remaining_time = self.env._("%(months)s months", months=delta.months)
                else:
                    self.remaining_time = self.env._("few days")
            else:
                self.remaining_time = False

    def action_generate_salary_adjustments(self):
        salary_adjustments = self.env['hr.salary.attachment'].create([{
            'employee_id': employee.id,
            'company_id': self.company_id.id,
            'description': self.description,
            'salary_rule_id': self.salary_rule_id.id,
            'is_recurring': self.is_recurring,
            'amount': self.amount,
            'date_start': self.date_start,
            'date_estimated_end': self.date_estimated_end,
            'date_end': self.date_end,
            'state': '1_open',
        } for employee in self.employee_ids])

        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Generated Payslip Adjustments'),
            "views": [[self.env.ref('hr_payroll.hr_salary_attachment_view_tree').id, "list"], [self.env.ref('hr_payroll.hr_salary_attachment_view_form').id, "form"]],
            'view_mode': 'list',
            'res_model': 'hr.salary.attachment',
            'domain': [('id', 'in', salary_adjustments.ids)],
            'context': {
                'active_id': False,
            },
        }
