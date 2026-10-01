# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_vn(self, companies):
        staff_costs = 'chart6421'               # 6421 Employees management costs
        employees_payable = 'chart334'          # 334  Employees payable
        social_insurance = 'chart3383'          # 3383 Social insurance
        health_insurance = 'chart3384'          # 3384 Health insurance
        unemployment_insurance = 'chart3386'    # 3386 Unemployment insurance
        trade_union_fees = 'chart3382'          # 3382 Trade union fees
        personal_income_tax = 'chart3335'       # 3335 Personal income tax
        advances = 'chart141'                   # 141  Advances
        other_payables = 'chart3388'            # 3388 Other payables

        rules_mapping = defaultdict(dict)

        def rule(xml_id):
            return self.env.ref(f'l10n_vn_hr_payroll.{xml_id}')

        # ================================================ #
        #          Vietnam: Regular Pay Structure          #
        # ================================================ #

        # Remuneration paid to the employee: wage, allowances, overtime, bonuses and termination payments
        for xml_id in (
            'l10n_vn_rule_basic',
            'l10n_vn_rule_position_allowance',
            'l10n_vn_rule_responsibility_allowance',
            'l10n_vn_rule_hazard_allowance',
            'l10n_vn_rule_seniority_allowance',
            'l10n_vn_rule_regional_allowance',
            'l10n_vn_rule_mobility_allowance',
            'l10n_vn_rule_attraction_allowance',
            'l10n_vn_rule_fixed_supplement',
            'l10n_vn_rule_meal_allowance',
            'l10n_vn_rule_fuel_allowance',
            'l10n_vn_rule_phone_allowance',
            'l10n_vn_rule_housing_allowance',
            'l10n_vn_rule_childcare_allowance',
            'l10n_vn_rule_uniform_allowance',
            'l10n_vn_rule_per_diem',
            'l10n_vn_rule_other_taxable_allowance',
            'l10n_vn_rule_other_exempt_allowance',
            'l10n_vn_rule_reimbursement',
            'l10n_vn_rule_overtime_normal_day',
            'l10n_vn_rule_overtime_weekly_rest',
            'l10n_vn_rule_overtime_public_holiday',
            'l10n_vn_rule_night_work',
            'l10n_vn_rule_overtime_night',
            'l10n_vn_rule_gross_up',
            'l10n_vn_rule_performance_bonus',
            'l10n_vn_rule_thirteenth_month_bonus',
            'l10n_vn_rule_tet_bonus',
            'l10n_vn_rule_attendance_bonus',
            'l10n_vn_rule_other_bonus',
            'l10n_vn_rule_unused_leave_payout',
            'l10n_vn_rule_severance_allowance',
            'l10n_vn_rule_job_loss_allowance',
            'l10n_vn_rule_other_termination_payment',
        ):
            rules_mapping[rule(xml_id)]['debit'] = staff_costs

        # Compulsory insurance and trade union funding borne by the employer: staff costs vs payables
        for xml_id, payable in (
            ('l10n_vn_rule_social_insurance_retirement_employer', social_insurance),
            ('l10n_vn_rule_social_insurance_sickness_employer', social_insurance),
            ('l10n_vn_rule_social_insurance_accident_employer', social_insurance),
            ('l10n_vn_rule_health_insurance_employer', health_insurance),
            ('l10n_vn_rule_unemployment_insurance_employer', unemployment_insurance),
            ('l10n_vn_rule_union_funding', trade_union_fees),
        ):
            rules_mapping[rule(xml_id)]['debit'] = staff_costs
            rules_mapping[rule(xml_id)]['credit'] = payable

        # Amounts withheld from the employee (negative lines): credited to the payables
        for xml_id, payable in (
            ('l10n_vn_rule_social_insurance_employee', social_insurance),
            ('l10n_vn_rule_health_insurance_employee', health_insurance),
            ('l10n_vn_rule_unemployment_insurance_employee', unemployment_insurance),
            ('l10n_vn_rule_union_dues', trade_union_fees),
            ('l10n_vn_rule_personal_income_tax', personal_income_tax),
            ('l10n_vn_rule_advance_recovery', advances),
            ('l10n_vn_rule_voluntary_pension', other_payables),
            ('l10n_vn_rule_attachment_of_salary', other_payables),
            ('l10n_vn_rule_assignment_of_salary', other_payables),
            ('l10n_vn_rule_child_support', other_payables),
            ('l10n_vn_rule_deduction', other_payables),
        ):
            rules_mapping[rule(xml_id)]['debit'] = payable

        # Social insurance benefits advanced to the employee: claim on the social insurance agency
        rules_mapping[rule('l10n_vn_rule_si_benefit_advance')]['debit'] = social_insurance

        # Net salary payable to the employee
        rules_mapping[rule('l10n_vn_rule_net')]['credit'] = employees_payable

        self._configure_payroll_account(
            companies,
            "VN",
            account_refs=[
                staff_costs, employees_payable, social_insurance, health_insurance, unemployment_insurance,
                trade_union_fees, personal_income_tax, advances, other_payables,
            ],
            rules_mapping=rules_mapping,
            default_account=staff_costs,
        )
