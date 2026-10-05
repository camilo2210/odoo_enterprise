# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_sa(self, companies):
        prepaid_medical_insurance = 'sa_account_104021'
        prepaid_sponsorship_fees = 'sa_account_104032'
        payables = 'sa_account_201002'
        leave_days_provision = 'sa_account_201006'
        accrued_others = 'sa_account_201016'
        gosi_employee_payable = 'sa_account_201022'
        end_of_service_provision = 'sa_account_202001'
        basic_salary = 'sa_account_400003'
        housing_allowance = 'sa_account_400004'
        transportation_allowance = 'sa_account_400005'
        leave_salary = 'sa_account_400007'
        end_of_service_indemnity = 'sa_account_400008'
        medical_insurance = 'sa_account_400009'
        life_insurance = 'sa_account_400010'
        staff_other_allowances = 'sa_account_400012'
        visa_expenses = 'sa_account_400014'
        salary_deductions = 'sa_account_400090'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #          KSA Employee Payroll Structure          #
        # ================================================ #

        basic_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id),
            ('code', '=', 'BASIC')
        ], limit=1)
        rules_mapping[basic_rule]['debit'] = basic_salary

        house_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_housing_allowance_salary_rule')
        rules_mapping[house_rule]['debit'] = housing_allowance

        transport_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_transportation_allowance_salary_rule')
        rules_mapping[transport_rule]['debit'] = transportation_allowance

        other_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_other_allowances_salary_rule')
        rules_mapping[other_rule]['debit'] = staff_other_allowances

        social_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_social_insurance_contribution')
        rules_mapping[social_rule]['debit'] = gosi_employee_payable
        rules_mapping[social_rule]['credit'] = life_insurance

        social_insurance_employee_contribution_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_social_insurance_employee_contribution')
        rules_mapping[social_insurance_employee_contribution_rule]['debit'] = gosi_employee_payable

        expenses_reimbursement_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_expenses_reimbursement')
        rules_mapping[expenses_reimbursement_rule]['debit'] = payables

        for xml_id in [
            'ksa_saudi_unpaid_days',
            'ksa_saudi_employee_payroll_structure_deduction_sick_leave',
        ]:
            rule = self.env.ref(f'l10n_sa_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = salary_deductions

        overtime_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_overtime')
        rules_mapping[overtime_rule]['debit'] = staff_other_allowances

        provision_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_end_of_service_provision_salary_rule')
        rules_mapping[provision_rule]['debit'] = end_of_service_indemnity
        rules_mapping[provision_rule]['credit'] = end_of_service_provision

        annual_leave_provision_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_annual_leave_provision')
        rules_mapping[annual_leave_provision_rule]['debit'] = leave_salary
        rules_mapping[annual_leave_provision_rule]['credit'] = leave_days_provision

        remaining_leave_days_compensation_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_remaining_leave_days_compensation')
        rules_mapping[remaining_leave_days_compensation_rule]['debit'] = leave_days_provision

        end_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_end_of_service_salary_rule')
        rules_mapping[end_rule]['debit'] = end_of_service_provision

        provision_correction_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_end_of_service_provision_correction_salary_rule')
        rules_mapping[provision_correction_rule]['debit'] = end_of_service_provision
        rules_mapping[provision_correction_rule]['credit'] = end_of_service_indemnity

        exit_re_entry_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_exit_re_entry')
        rules_mapping[exit_re_entry_rule]['debit'] = staff_other_allowances

        medical_insurance_rule = self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure_medical_insureance')
        rules_mapping[medical_insurance_rule]['debit'] = medical_insurance
        rules_mapping[medical_insurance_rule]['credit'] = prepaid_medical_insurance

        for xml_id in [
            'ksa_saudi_employee_payroll_structure_iqama',
            'ksa_saudi_employee_payroll_structure_work_permit',
        ]:
            rule = self.env.ref(f'l10n_sa_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = visa_expenses
            rules_mapping[rule]['credit'] = prepaid_sponsorship_fees

        for xml_id in [
            'l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_attachment_of_salary_rule',
            'l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_assignment_of_salary_rule',
        ]:
            rule = self.env.ref(f'l10n_sa_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = salary_deductions

        child_support_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_child_support')
        rules_mapping[child_support_rule]['debit'] = staff_other_allowances

        deduction_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_deduction_salary_rule')
        rules_mapping[deduction_rule]['debit'] = salary_deductions

        reimbursement_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_hr_payroll_ksa_saudi_employee_payroll_structure_reimbursement_salary_rule')
        rules_mapping[reimbursement_rule]['debit'] = payables

        for xml_id in [
            'ksa_saudi_employee_payroll_structure_loan_deduction',
            'ksa_saudi_employee_payroll_structure_salary_advance_recovery',
        ]:
            rule = self.env.ref(f'l10n_sa_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = salary_deductions

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id),
            ('code', '=', 'NET')
        ], limit=1)
        rules_mapping[net_rule]['credit'] = payables

        self._configure_payroll_account(
            companies,
            "SA",
            account_refs=[
                prepaid_medical_insurance, prepaid_sponsorship_fees, payables, leave_days_provision, accrued_others, gosi_employee_payable,
                end_of_service_provision, basic_salary, housing_allowance, transportation_allowance, leave_salary,
                end_of_service_indemnity, medical_insurance, life_insurance, staff_other_allowances, visa_expenses,
                salary_deductions
            ],
            rules_mapping=rules_mapping,
            default_account=payables
        )
