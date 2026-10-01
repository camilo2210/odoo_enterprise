# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nPhHrPayrollPreviousEmployment(models.Model):
    _name = "l10n_ph_hr_payroll.previous_employment"
    _description = "Details of the employee's Previous Employment"

    name = fields.Char(
        string="Employer's name",
        groups="hr_payroll.group_hr_payroll_user",
        required=True,
    )
    version_ids = fields.One2many(
        comodel_name='hr.version',
        inverse_name='l10n_ph_hr_payroll_prev_employment_id',
        domain="[('employee_id', '=', employee_id)]",
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        ondelete='cascade',
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(related='employee_id.company_id')
    currency_id = fields.Many2one(related='employee_id.currency_id')

    tin = fields.Char(
        string="Employer's TIN",
        groups="hr_payroll.group_hr_payroll_user",
        help="TIN of this employee's previous employer, if any.",
    )
    address = fields.Char(
        string="Employer's Address",
        groups="hr_payroll.group_hr_payroll_user",
        help="Registered Address of this employee's previous employer, if any.",
    )
    zip = fields.Char(
        string="Employer's ZIP",
        groups="hr_payroll.group_hr_payroll_user",
        help="ZIP of this employee's previous employer, if any.",
    )

    taxable_income = fields.Monetary(
        string='Taxable Income',
        groups="hr_payroll.group_hr_payroll_user",
        help="Total taxable compensation from the previous employer's BIR Form 2316 (Item 21).",
        compute='_compute_taxable_income',
        store=True,
    )
    tax_withheld = fields.Monetary(
        string='Tax Withheld',
        groups="hr_payroll.group_hr_payroll_user",
        help="Total tax withheld from the previous employer's BIR Form 2316 (Item 26).",
    )
    nontax_13th_month = fields.Monetary(
        string='Non-tax 13th Month',
        groups="hr_payroll.group_hr_payroll_user",
        help="Total non-taxable 13th month and other benefits from the previous employer's BIR Form 2316 (Item 36).",
    )
    nontax_basic_mwe = fields.Monetary(
        string='Basic/Statutory Minimum Wage',
        groups="hr_payroll.group_hr_payroll_user",
        help="Basic/Statutory Minimum Wage (MWE) from the previous employer's BIR Form 2316 (Item 29).",
    )
    holiday_pay = fields.Monetary(
        string='Holiday Pay (MWE)',
        groups="hr_payroll.group_hr_payroll_user",
        help="Holiday Pay (MWE) from the previous employer's BIR Form 2316 (Item 30).",
    )
    overtime_pay = fields.Monetary(
        string='Overtime Pay (MWE)',
        groups="hr_payroll.group_hr_payroll_user",
        help="Overtime Pay (MWE) from the previous employer's BIR Form 2316 (Item 31).",
    )
    night_shift_differential = fields.Monetary(
        string='Night Shift Differential (MWE)',
        groups="hr_payroll.group_hr_payroll_user",
        help="Night Shift Differential (MWE) from the previous employer's BIR Form 2316 (Item 32).",
    )
    hazard_pay = fields.Monetary(
        string='Hazard Pay (MWE)',
        groups="hr_payroll.group_hr_payroll_user",
        help="Hazard Pay from the previous employer's BIR Form 2316 (Item 33).",
    )
    nontax_de_minimis = fields.Monetary(
        string='Non-Taxable De Minimis',
        groups="hr_payroll.group_hr_payroll_user",
        help="Non-taxable De Minimis benefits from the previous employer's BIR Form 2316 (Item 35).",
    )
    nontax_statutory_contributions = fields.Monetary(
        string='Non-Taxable SSS/GSIS/PHIC/HDMF',
        groups="hr_payroll.group_hr_payroll_user",
        help="Non-taxable SSS, GSIS, PAGIBIG, and Union dues from the previous employer's BIR Form 2316 (Item 36).",
    )
    nontax_salaries_other = fields.Monetary(
        string='Non-Taxable Salaries & Other',
        groups="hr_payroll.group_hr_payroll_user",
        help="Non-taxable salaries and other compensation from the previous employer's BIR Form 2316 (Item 37).",
    )
    nontaxable_income = fields.Monetary(
        string='Non-Taxable Income',
        groups="hr_payroll.group_hr_payroll_user",
        help="Total non-taxable compensation from the previous employer's BIR Form 2316.",
        compute='_compute_nontaxable_income',
        store=True,
    )
    taxable_basic_salary = fields.Monetary(
        string='Taxable Basic Salary',
        groups="hr_payroll.group_hr_payroll_user",
        help="Taxable basic salary from the previous employer's BIR Form 2316 (Item 39).",
    )
    taxable_13th_month = fields.Monetary(
        string='Taxable 13th Month',
        groups="hr_payroll.group_hr_payroll_user",
        help="Taxable 13th month pay and other benefits from the previous employer's BIR Form 2316 (Item 48).",
    )
    taxable_salaries_other = fields.Monetary(
        string='Taxable Salaries & Other',
        groups="hr_payroll.group_hr_payroll_user",
        help="Taxable salaries and other compensation from the previous employer's BIR Form 2316 (Items 40-47 & 49-51).",
    )

    # These are some guardrails to avoid mistyping important amounts, or avoid reaching an 'impossible' state when testing that would result in invalid report files.
    _pos_amount_only = models.Constraint(
        'CHECK(tax_withheld >= 0 AND taxable_basic_salary >= 0 AND taxable_13th_month >= 0 AND taxable_salaries_other >= 0 AND nontax_basic_mwe >= 0 AND holiday_pay >= 0 AND overtime_pay >= 0 AND night_shift_differential >= 0 AND hazard_pay >= 0 AND nontax_13th_month >= 0 AND nontax_de_minimis >= 0 AND nontax_statutory_contributions >= 0 AND nontax_salaries_other >= 0)',
        'Previous employment amounts cannot be negative.',
    )
    _tax_withheld_total = models.Constraint(
        'CHECK(tax_withheld <= taxable_income)',
        'The Tax Withheld amount cannot be greater than the Total Taxable Income.',
    )
    _13th_month_cap = models.Constraint(
        'CHECK(nontax_13th_month <= 90000)',
        'Non-taxable 13th Month pay cannot exceed the statutory limit of ₱90,000.',
    )

    @api.constrains('version_ids')
    def _constrains_version_ids(self):
        """ In case the previous employment is unlinked from ALL versions, we still keep the employee set to allow re-linking. """
        for record in self:
            if len(record.version_ids.employee_id) > 1:
                raise ValidationError(record.env._("A Previous Employement record can only be linked to a single employee."))

    @api.depends('taxable_basic_salary', 'taxable_13th_month', 'taxable_salaries_other')
    def _compute_taxable_income(self):
        for record in self:
            record.taxable_income = record.taxable_basic_salary + record.taxable_13th_month + record.taxable_salaries_other

    @api.depends(
        'nontax_basic_mwe', 'holiday_pay', 'overtime_pay', 'night_shift_differential',
        'hazard_pay', 'nontax_13th_month', 'nontax_de_minimis',
        'nontax_statutory_contributions', 'nontax_salaries_other'
    )
    def _compute_nontaxable_income(self):
        for record in self:
            record.nontaxable_income = sum([
                record.nontax_basic_mwe,
                record.holiday_pay,
                record.overtime_pay,
                record.night_shift_differential,
                record.hazard_pay,
                record.nontax_13th_month,
                record.nontax_de_minimis,
                record.nontax_statutory_contributions,
                record.nontax_salaries_other,
            ])
