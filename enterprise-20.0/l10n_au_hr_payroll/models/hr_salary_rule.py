# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrSalaryRule(models.Model):
    """Australian payroll extension to hr.salary.rule.

    Carries the per-input-type metadata (ETP type, PAYGW treatment, STP payroll code, ...)
    that used to live on hr.payslip.input.type before the upstream refactor merged inputs
    into salary rules.
    """
    _inherit = "hr.salary.rule"

    l10n_au_etp_type = fields.Selection(
        selection=[
            ('excluded', 'Excluded'),
            ('non_excluded', 'Non-Excluded')],
        string="ETP Type",
        help="""Included: ETP for which the smaller of the ETP cap and the whole-of-income cap applies.
        Excluded: ETP for which only the ETP cap applies.""")
    l10n_au_payment_type = fields.Selection(
        selection=[
            ("etp", "ETP"),
            ("allowance", "Allowance"),
            ("deduction", "Deduction"),
            ("leave", "Leave"),
            ("other", "Other"),
        ],
        string="Payment Type",
        help=""""The payment type will affect the tax calculations on the employee's payslip.
        - ETP: employment termination payment
        - Allowance: regular (or one-time) allowance provided to the employee.
        - Deduction: fees. workplace giving, child support
        - Leave: related to leave payments
        - Other: all payments not falling in the upper sections' logic."
        """
    )
    l10n_au_superannuation_treatment = fields.Selection(
        selection=[
            ("ote", "OTE"),
            ("salary", "Salary & Wages"),
            ("not_salary", "Not Salary & Wages"),
        ],
        string="Superannuation Treatment",
        help="""
        - OTE: this input type will be subjected to the superannuation guarantee %.
        - Salary & Wages: regular payment not subjected to the super guarantee % (e.g. overtime).
        - Not salary & wages: other payments (e.g. worker's compensation, parental leave,...)
        """
    )
    l10n_au_paygw_treatment = fields.Selection(
        [('regular', 'Regular'),
         ('no_paygw', 'No PAYG Withholding'),
         ('special', 'Taxed above ATO limit'),
         ],
        string="PAYGW Treatment",
        help="""
        - Regular: taxed as per regular tax schedule.
        - No PAYG Withholding: not taxed.
        - Taxed above ATO limit: taxed until the ATO limit set for certain allowance types in the payroll rule parameters (e.g. cent per km, travel allowances,...).
        """
    )
    l10n_au_payroll_code = fields.Selection(
        selection=[
            ("LD", "LD"),
            ("MD", "MD"),
            ("AD", "AD"),
            ("OD", "OD"),
            ("RD", "RD"),
            ("G", "G"),
            ("T", "T"),
            ("X", "X"),
            ("Bonus and Commissions", "Bonus and Commissions"),
            ("E", "E"),
            ("R", "R"),
            ("Overtime", "Overtime"),
            ("W", "W"),
            ("QN", "QN"),
            ("Directors' fees", "Directors' fees"),
            ("KN", "KN"),
            ("C", "C"),
            ("CD", "CD"),
            ("O", "O"),
            ("F", "F"),
            ("Gross", "Gross"),
        ],
        string="STP Code",
        help="STP code used to report the payment amount to the ATO."
    )
    l10n_au_payroll_code_description = fields.Selection(
        selection=[
            ('G1', 'G1'),
            ('H1', 'H1'),
            ('ND', 'ND'),
            ('T1', 'T1'),
            ('U1', 'U1'),
            ('V1', 'V1'),
        ],
        string="Payroll Code Description",
        help="Additional STP reporting code required by the ATO for certain allowances."
    )
    l10n_au_quantity = fields.Boolean(string="AU Quantity Flag")
    l10n_au_requires_details = fields.Boolean(string="Requires Details")
    l10n_au_input_uom = fields.Selection([("days", "Day(s)"), ("kms", "Kilometer(s)")], string="Input UoM")
