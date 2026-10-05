# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayslipInput(models.Model):
    _name = 'hr.payslip.input'
    _description = 'Payslip Input'
    _order = 'payslip_id, sequence'

    name = fields.Char(string="Description", compute='_compute_name', store=True, readonly=False)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', related='payslip_id.employee_id')
    date_from = fields.Date(related='payslip_id.date_from')
    sequence = fields.Integer(required=True, index=True, default=10)
    struct_id = fields.Many2one(
        related='payslip_id.struct_id',
        string='Salary Structure',
        store=False,
    )
    salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        string='Salary Rule',
        required=True,
        index=True,
        ondelete='cascade',
        # Only rules that actually consume a manual input: salary-input rules read it
        # natively, other rules opt in with input_usage_payslip (e.g. python rules
        # reading inputs[...]).
        domain="['&', ('struct_ids', 'in', struct_id), '|', '|', ('condition_select', '=', 'property_input'), ('amount_select', '=', 'property_input'), ('input_usage_payslip', '=', True)]",
    )
    code = fields.Char(related='salary_rule_id.code',
        help="The code that can be used in the salary rules")
    amount = fields.Float(
        string="Value",
        digits='Payroll Rate',
        compute='_compute_amount', store=True, readonly=False,
        help="Used in computation. E.g. a rule for salesmen with 1% commission of basic salary per product can be defined as: "
             "result = inputs['SALEURO'].amount * version.wage * 0.01.")
    version_id = fields.Many2one(
        related='payslip_id.version_id', string='Employee Record', required=True,
        help="The version this input should be applied to")
    department_id = fields.Many2one(related='payslip_id.department_id')
    job_id = fields.Many2one(related='payslip_id.job_id')
    payslip_run_id = fields.Many2one(related='payslip_id.payslip_run_id')
    input_suffix = fields.Char(
        related='salary_rule_id.input_suffix',
        readonly=True,
    )
    user_instructions = fields.Html(related='salary_rule_id.user_instructions', readonly=True)

    @api.depends('salary_rule_id')
    def _compute_name(self):
        for line in self:
            line.name = line.salary_rule_id.input_name

    @api.depends('salary_rule_id')
    def _compute_amount(self):
        for line in self:
            line.amount = line.salary_rule_id.input_default_value
