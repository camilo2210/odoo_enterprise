from odoo import fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_om_employee_is_eos_eligible = fields.Boolean(readonly=False, groups="hr_payroll.group_hr_payroll_user")
    l10n_om_employee_old_age_disability_death_insurance_percentage = fields.Float(default=0.075, string='Employee Old Age, Disability and Death Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_employee_work_injury_insurance_percentage = fields.Float(default=0, string='Employee Work Injury and Occupational Disease Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_employee_unemployment_insurance_percentage = fields.Float(default=0.005, string='Employee Employment Security Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_employee_sick_leave_insurance_percentage = fields.Float(default=0, string='Employee Sick and Other Leaves Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_employee_maternity_leave_insurance_percentage = fields.Float(default=0, string='Employee Maternity Leave Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_company_old_age_disability_death_insurance_percentage = fields.Float(default=0.11, string='Company Old Age, Disability and Death Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_company_work_injury_insurance_percentage = fields.Float(default=0.01, string='Company Work Injury and Occupational Disease Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_company_unemployment_insurance_percentage = fields.Float(default=0.005, string='Company Employment Security Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_company_sick_leave_insurance_percentage = fields.Float(default=0.01, string='Company Sick and Other Leaves Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_company_maternity_leave_insurance_percentage = fields.Float(default=0.01, string='Company Maternity Leave Insurance %', groups="hr_payroll.group_hr_payroll_user")
    l10n_om_identification_type = fields.Selection(
        [
            ('passport', 'Passport'),
            ('civil_status_card', 'Civil Status Card'),
        ],
        default='passport', string="Identification Type", groups="hr_payroll.group_hr_payroll_user")

    _l10n_om_employee_old_age_disability_death_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_employee_old_age_disability_death_insurance_percentage >= 0 '
        'AND l10n_om_employee_old_age_disability_death_insurance_percentage <= 1)',
        'The value of Employee Old Age, Disability and Death Insurance must be between 0 and 100%',
    )

    _l10n_om_employee_work_injury_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_employee_work_injury_insurance_percentage >= 0 '
        'AND l10n_om_employee_work_injury_insurance_percentage <= 1)',
        'The value of Employee Work Injury and Occupational Disease Insurance must be between 0 and 100%',
    )

    _l10n_om_employee_unemployment_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_employee_unemployment_insurance_percentage >= 0 '
        'AND l10n_om_employee_unemployment_insurance_percentage <= 1)',
        'The value of Employee Employment Security Insurance must be between 0 and 100%',
    )

    _l10n_om_employee_sick_leave_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_employee_sick_leave_insurance_percentage >= 0 '
        'AND l10n_om_employee_sick_leave_insurance_percentage <= 1)',
        'The value of Employee Sick and Other Leaves Insurance must be between 0 and 100%',
    )

    _l10n_om_employee_maternity_leave_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_employee_maternity_leave_insurance_percentage >= 0 '
        'AND l10n_om_employee_maternity_leave_insurance_percentage <= 1)',
        'The value of Employee Maternity Leave Insurance must be between 0 and 100%',
    )

    _l10n_om_company_old_age_disability_death_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_company_old_age_disability_death_insurance_percentage >= 0 '
        'AND l10n_om_company_old_age_disability_death_insurance_percentage <= 1)',
        'The value of Company Old Age, Disability and Death Insurance must be between 0 and 100%',
    )

    _l10n_om_company_work_injury_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_company_work_injury_insurance_percentage >= 0 '
        'AND l10n_om_company_work_injury_insurance_percentage <= 1)',
        'The value of Company Work Injury and Occupational Disease Insurance must be between 0 and 100%',
    )

    _l10n_om_company_unemployment_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_company_unemployment_insurance_percentage >= 0 '
        'AND l10n_om_company_unemployment_insurance_percentage <= 1)',
        'The value of Company Employment Security Insurance must be between 0 and 100%',
    )

    _l10n_om_company_sick_leave_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_company_sick_leave_insurance_percentage >= 0 '
        'AND l10n_om_company_sick_leave_insurance_percentage <= 1)',
        'The value of Company Sick and Other Leaves Insurance must be between 0 and 100%',
    )

    _l10n_om_company_maternity_leave_insurance_constraint = models.Constraint(
        'CHECK(l10n_om_company_maternity_leave_insurance_percentage >= 0 '
        'AND l10n_om_company_maternity_leave_insurance_percentage <= 1)',
        'The value of Company Maternity Leave Insurance must be between 0 and 100%',
    )
