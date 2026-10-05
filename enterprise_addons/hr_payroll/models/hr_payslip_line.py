# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipLine(models.Model):
    _name = 'hr.payslip.line'
    _description = 'Payslip Line'
    _explanation = "Represents a single computed line on a payslip (e.g., Basic Salary calculation, specific deduction). It holds the computed amount and rate for a specific salary rule."
    _order = 'version_id, sequence, code'

    name = fields.Char(
        compute='_compute_name',
        inverse='_inverse_name',
        store=False,
    )
    custom_name = fields.Char()
    sequence = fields.Integer(required=True, index=True, default=5,
                              help='Use to arrange calculation sequence')
    code = fields.Char(related="salary_rule_id.code", store=True, readonly=True,
                       help="The code of salary rules can be used as reference in computation of other rules. "
                       "In that case, it is case sensitive.")
    sex = fields.Selection(related='version_id.sex', string="Sex")
    resource_calendar_id = fields.Many2one(related='version_id.resource_calendar_id', string="Working Hours")
    slip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, index=True, ondelete='cascade')
    struct_id = fields.Many2one(related='slip_id.struct_id', string='Structure', readonly=True)
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Rule', required=True, index=True)
    version_id = fields.Many2one('hr.version', string='Contract', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    employee_type_id = fields.Many2one(related='employee_id.employee_type_id')
    rate = fields.Float(string='Rate (%)', digits='Payroll Rate', default=100.0)
    amount = fields.Monetary(string='Base')
    quantity = fields.Float(digits='Payroll', default=1.0)
    total = fields.Monetary(string='Total')
    ytd = fields.Monetary(string='YTD')
    employer_cost = fields.Monetary(string="Employer Cost", compute="_compute_employer_cost", store=True)

    hide_amount = fields.Boolean(string='Hide Amount', related='salary_rule_id.hide_amount', readonly=True)
    amount_select = fields.Selection(related='salary_rule_id.amount_select', readonly=True)
    amount_fix = fields.Float(related='salary_rule_id.amount_fix', readonly=True)
    amount_percentage = fields.Float(related='salary_rule_id.amount_percentage', readonly=True)
    appears_on_payslip = fields.Selection(related='salary_rule_id.appears_on_payslip', readonly=True)
    category_ids = fields.Many2many(related='salary_rule_id.category_ids', readonly=True)
    partner_id = fields.Many2one(related='salary_rule_id.partner_id', readonly=True)

    date_from = fields.Date(string='From', related="slip_id.date_from", store=True)
    date_to = fields.Date(string='To', related="slip_id.date_to", store=True)
    company_id = fields.Many2one(related='slip_id.company_id')
    currency_id = fields.Many2one('res.currency', related='slip_id.currency_id')
    department_id = fields.Many2one(related='slip_id.department_id')
    job_id = fields.Many2one(related='slip_id.job_id')
    payslip_run_id = fields.Many2one(related='slip_id.payslip_run_id')
    explanation = fields.Text(string="Calculation Explanation", readonly=True)
    display_in_pdf_extra_info = fields.Boolean(related='salary_rule_id.display_in_pdf_extra_info', readonly=True)

    manually_modified = fields.Boolean(string='Manually Modified', help="Whether the line has been manually modified. If True, the line won't be updated by automatic recomputation.")

    _slip_id_code = models.Index("(slip_id, code)")

    @api.onchange('total')
    def _onchange_total(self):
        # The total is only edtiable when it equals the amount
        self.amount = self.total

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if 'employee_id' not in values or 'version_id' not in values:
                payslip = self.env['hr.payslip'].browse(values.get('slip_id'))
                values['employee_id'] = values.get('employee_id') or payslip.employee_id.id
                values['version_id'] = values.get('version_id') or payslip.version_id and payslip.version_id.id
                if not values['version_id']:
                    raise UserError(_('You must set a contract to create a payslip line.'))
        return super(HrPayslipLine, self).create(vals_list)

    @api.depends('salary_rule_id', 'salary_rule_id.appears_on_employee_cost_dashboard', 'total')
    def _compute_employer_cost(self):
        to_assign = self.filtered(
            lambda line: line.salary_rule_id and line.salary_rule_id.appears_on_employee_cost_dashboard
        )
        for line in to_assign:
            line.employer_cost = line.total
        (self - to_assign).employer_cost = 0

    @api.depends('custom_name', 'salary_rule_id.name')
    @api.depends_context('lang')
    def _compute_name(self):
        for line in self:
            line.name = line.custom_name or line.salary_rule_id.name

    def _inverse_name(self):
        to_sync = self.filtered(lambda line: line.name != line.salary_rule_id.name)
        for line in to_sync:
            line.custom_name = line.name
        (self - to_sync).custom_name = False

    def get_payslip_styling_dict(self):
        self.ensure_one()
        rule = self.salary_rule_id
        classes = []
        if rule.bold:
            classes.append('fw-bold')
        if rule.italic:
            classes.append('fst-italic')
        if rule.underline:
            classes.append('text-decoration-underline')
        if rule.space_above:
            classes.append('pt-4')
        if rule.indented:
            classes.append('ps-4')
        return {
            'line_style': f'color:{rule.color};',
            'line_class': ' '.join(classes),
            'o_title': 'd-none' if rule.title else ''
        }
