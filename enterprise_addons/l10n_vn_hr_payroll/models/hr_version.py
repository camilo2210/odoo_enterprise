# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_vn_pit_method = fields.Selection([
        ('progressive', "Resident - Progressive Schedule"),
        ('flat_casual', "Casual Income - 10% Withholding"),
        ('flat_non_resident', "Non-resident - 20% Flat Rate"),
    ], string="Personal Income Tax Method", default='progressive', required=True,
        groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Resident employees on a labour contract of at least three months are taxed with the "
             "progressive schedule after the personal and dependant deductions.\n"
             "Payments to residents without a labour contract or on a contract shorter than three months "
             "(including payments made after the termination) are withheld at 10% when they reach the threshold.\n"
             "Non-residents are taxed at 20% of their income without any deduction.")
    l10n_vn_dependants = fields.Integer(string="Registered Dependants",
        groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Dependants registered with the tax authority, each one grants the monthly dependant deduction.")
    l10n_vn_minimum_wage_region = fields.Selection([
        ('1', "Zone I"),
        ('2', "Zone II"),
        ('3', "Zone III"),
        ('4', "Zone IV"),
    ], string="VN: Minimum Wage Zone", default='1', required=True,
        groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Regional minimum wage zone of the place of work. It sets the floor of the insurance "
             "contribution wage and the ceiling of the unemployment insurance contribution.")
    l10n_vn_union_member = fields.Boolean(string="Trade Union Member",
        groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Trade union dues (1% of the contribution wage, capped) are withheld from the members.")
    l10n_vn_insurance_exempt = fields.Boolean(string="Exempt from Compulsory Insurance",
        groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Intra-corporate transferees, employees who reached the retirement age and employees covered "
             "by an international social security agreement are outside the compulsory insurance schemes.")
    l10n_vn_net_salary = fields.Boolean(string="Net Salary Agreement",
        groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="The wage is the agreed net amount: the employee's compulsory insurance contributions and "
             "personal income tax are borne by the employer and grossed up on the payslip.")
    l10n_vn_tax_code = fields.Char(string="Personal Tax Code", groups="hr.group_hr_user", tracking=1,
        help="Tax code (MST) of the employee, the personal identification number may serve this purpose.")

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == 'VN':
            whitelisted_fields += [
                'l10n_vn_pit_method',
                'l10n_vn_minimum_wage_region',
                'l10n_vn_union_member',
                'l10n_vn_insurance_exempt',
                'l10n_vn_net_salary',
            ]
        return whitelisted_fields
