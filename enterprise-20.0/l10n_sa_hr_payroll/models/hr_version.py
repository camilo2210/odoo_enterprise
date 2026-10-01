from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_sa_housing_allowance = fields.Monetary(string='Saudi Housing Allowance', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_sa_transportation_allowance = fields.Monetary(string='Saudi Transportation Allowance', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_sa_other_allowances = fields.Monetary(string='Saudi Other Allowances', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_sa_number_of_days = fields.Integer(string='Number of Annual leave days ', default=21, groups="hr_payroll.group_hr_payroll_user",
                                            help='Number of Annual leave days per year that the employee is eligible to, it is used to compute the monthly provision for the annual leave days')
    l10n_sa_iqama_annual_amount = fields.Monetary(string="Iqama Annual Amount", groups="hr_payroll.group_hr_payroll_user", help="Employee's annual Iqama cost, prorated in each payslip throughout the year", tracking=1)
    l10n_sa_medical_insurance_annual_amount = fields.Monetary(string="Medical Insurance Annual Amount", groups="hr_payroll.group_hr_payroll_user", help="Employee's annual medical insurance cost, prorated in each payslip throughout the year", tracking=1)
    l10n_sa_work_permit_annual_amount = fields.Monetary(string="Work Permit Annual Amount", groups="hr_payroll.group_hr_payroll_user", help="Employees's annual work permit cost, prorated in each payslip throughout the year", tracking=1)

    l10n_sa_company_social_insurance_percentage = fields.Float(string='Company Social Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_company_oh_insurance_percentage = fields.Float(string='Company Occupational Hazard Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_company_unemployment_insurance_percentage = fields.Float(string='Company Unemployment Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_employee_social_insurance_percentage = fields.Float(string='Employee Social Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_employee_oh_insurance_percentage = fields.Float(string='Employee Occupational Hazard Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_employee_unemployment_insurance_percentage = fields.Float(string='Employee Unemployment Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_eos_number_of_days_in_year = fields.Selection(
        selection=[
            ('360', '360 days'),
            ('365', '365 days'),
            ('actual', 'Actual number of days in the year'),
        ],
        string="Number of days in Year", default='360', required=True, groups="hr_payroll.group_hr_payroll_user",
        tracking=1, help="Defines the number of days per year used to calculate the employee's length of service for end-of-service calculations.",
    )

    _l10n_sa_hr_payroll_number_of_days_constraint = models.Constraint(
        'CHECK(l10n_sa_number_of_days >= 0)',
        "Number of Days must be equal to or greater than 0",
    )

    _l10n_sa_hr_payroll_company_social_insurance_constraint = models.Constraint(
        'CHECK(l10n_sa_company_social_insurance_percentage >= 0 and l10n_sa_company_social_insurance_percentage <= 1)',
        'The value of Company Social Insurance must be between 0 and 100%',
    )

    _l10n_sa_hr_payroll_company_oh_insurance_constraint = models.Constraint(
        'CHECK(l10n_sa_company_oh_insurance_percentage >= 0 and l10n_sa_company_oh_insurance_percentage <= 1)',
        'The value of Company Occupational Hazard Insurance must be between 0 and 100%',
    )

    _l10n_sa_hr_payroll_company_unemployment_insurance_constraint = models.Constraint(
        'CHECK(l10n_sa_company_unemployment_insurance_percentage >= 0 and l10n_sa_company_unemployment_insurance_percentage <= 1)',
        'The value of Company Unemployment Insurance must be between 0 and 100%',
    )

    _l10n_sa_hr_payroll_employee_social_insurance_constraint = models.Constraint(
        'CHECK(l10n_sa_employee_social_insurance_percentage >= 0 and l10n_sa_employee_social_insurance_percentage <= 1)',
        'The value of Employee Social Insurance must be between 0 and 100%',
    )

    _l10n_sa_hr_payroll_employee_oh_insurance_constraint = models.Constraint(
        'CHECK(l10n_sa_employee_oh_insurance_percentage >= 0 and l10n_sa_employee_oh_insurance_percentage <= 1)',
        'The value of Employee Occupational Hazard Insurance must be between 0 and 100%',
    )

    _l10n_sa_hr_payroll_employee_unemployment_insurance_constraint = models.Constraint(
        'CHECK(l10n_sa_employee_unemployment_insurance_percentage >= 0 and l10n_sa_employee_unemployment_insurance_percentage <= 1)',
        'The value of Employee Unemployment Insurance must be between 0 and 100%',
    )

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "SA":
            whitelisted_fields += [
                "l10n_sa_housing_allowance",
                "l10n_sa_number_of_days",
                "l10n_sa_other_allowances",
                "l10n_sa_transportation_allowance",
                "l10n_sa_iqama_annual_amount",
                "l10n_sa_medical_insurance_annual_amount",
                "l10n_sa_work_permit_annual_amount",
            ]
        return whitelisted_fields

    def _l10n_sa_get_eosb_compensation(self, at_date=False):
        self.ensure_one()
        result = 0
        employee = self.employee_id
        start_date = employee._get_first_version_date()
        end_date = at_date or employee.departure_date
        total_years = employee._l10n_sa_get_number_of_years(start_date, end_date)
        compensation = (self._get_contract_wage() + self.l10n_sa_housing_allowance
                        + self.l10n_sa_transportation_allowance + self.l10n_sa_other_allowances)

        if reason_type := employee.departure_reason_id.l10n_sa_reason_type or at_date:
            if reason_type == 'fired':
                result = 0
            elif reason_type in ['end_of_contract', 'retired'] or at_date:
                if 1 <= total_years <= 5:
                    result = total_years * compensation / 2
                if total_years > 5:
                    result = (5 * compensation / 2) + ((total_years - 5) * compensation)
            elif reason_type in {'company_article_77', 'employee_article_77'}:
                sign = -1 if reason_type == 'employee_article_77' else 1
                if not employee.contract_date_end:
                    result = sign * max(2 * compensation, compensation / 2 * total_years)
                elif employee.contract_date_end >= employee.departure_date:
                    result = sign * max(2 * compensation, (employee.contract_date_end - employee.departure_date).days * compensation / 30)
                elif employee.contract_date_end < employee.departure_date:
                    result = sign * 2 * compensation
            elif reason_type == 'resigned':
                if 2 <= total_years < 10:
                    result = (total_years * compensation / 2) / 3
                elif total_years >= 10:
                    result = (5 * compensation / 2) + ((total_years - 5) * compensation)
        return employee.company_id.currency_id.round(result)
