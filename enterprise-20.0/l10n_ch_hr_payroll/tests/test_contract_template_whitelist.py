# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_ch = self.env['res.company'].create({
            'name': 'CH Co',
            'country_id': self.env.ref('base.ch').id,
        })
        self.employee_ch = self.env['hr.employee'].create({
            'name': 'CH Employee',
            'company_id': self.company_ch.id,
        })

    def test_ch_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_ch)
        social_insurance = self.env['l10n.ch.social.insurance'].create({
            'name': 'Test Social Insurance',
            'insurance_code': '048.000',
        })
        lpp_insurance = self.env['l10n.ch.lpp.insurance'].create({
            'name': 'Test LPP Insurance',
            'customer_number': '90012345',
            'contract_number': 'LPP-2026-98765',
            'insurance_code': 'LPP-BERN-100',
        })
        accident_insurance_group = self.env['l10n.ch.accident.group'].create({
            'name': 'Test Accident Insurance Group',
            'group_unit': 'A',
        })
        compensation_fund = self.env['l10n.ch.compensation.fund'].create({
            'name': 'Test Compensation Fund',
            'insurance_code': '004.000',
        })
        template = Version.create({
            'name': 'CH Template',
            'irregular_working_time': False,
            'l10n_ch_current_occupation_rate': 50.0,
            'l10n_ch_weekly_hours': 10,
            'l10n_ch_weekly_lessons': 5,
            'l10n_ch_contractual_13th_month_rate': 8.33,
            'l10n_ch_has_lesson': True,
            'l10n_ch_lesson_wage': 50.0,
            'l10n_ch_has_hourly': True,
            'hourly_wage': 50.0,
            'l10n_ch_has_monthly': False,
            'l10n_ch_lpp_not_insured': False,
            'l10n_ch_monthly_effective_days': 21.5,
            'l10n_ch_other_employers': False,
            'l10n_ch_other_employers_occupation_rate': 0.0,
            'l10n_ch_thirteen_month': True,
            'l10n_ch_14th_month': True,
            'l10n_ch_yearly_holidays': 25,
            'l10n_ch_yearly_paid_public_holidays': 10,
            'l10n_ch_contractual_holidays_rate': 10.0,
            'l10n_ch_contractual_public_holidays_rate': 15.0,
            'l10n_ch_contractual_vacation_pay': False,
            'l10n_ch_accident_insurance_line_id': False,
            'l10n_ch_additional_accident_insurance_line_ids': [Command.create({
                'solution_name': 'Accident Insurance Line',
            })],
            'l10n_ch_avs_status': 'youth',
            'l10n_ch_compensation_fund_id': compensation_fund.id,
            'l10n_ch_is_model': False,
            'l10n_ch_is_predefined_category': False,
            'l10n_ch_job_type': False,
            'l10n_ch_location_unit_id': False,
            'l10n_ch_lpp_insurance_id': lpp_insurance.id,
            'l10n_ch_lpp_entry_valid_as_of': '2026-01-01',
            'l10n_ch_lpp_entry_reason': 'entryCompany',
            'l10n_ch_lpp_solutions': [Command.create({
                'name': 'LPP Solution',
                'code': '01234567',
            })],
            'lpp_employee_amount': 100.0,
            'lpp_company_amount': 200.0,
            'l10n_ch_laa_group': accident_insurance_group.id,
            'laa_solution_number': '1',
            'l10n_ch_sickness_insurance_line_ids': [Command.create({
                'solution_name': 'Sickness Insurance Line',
            })],
            'l10n_ch_social_insurance_id': social_insurance.id,
            'l10n_ch_total_occupation_rate': 100.0,
        })

        contract = self.employee_ch.version_id

        self.assertAlmostEqual(contract.l10n_ch_contractual_13th_month_rate, 8.33, places=2)
        self.assertEqual(contract.l10n_ch_lesson_wage, 0.0)
        self.assertEqual(contract.l10n_ch_monthly_effective_days, 20.0)  # Default value

        self.employee_ch.contract_template_id = template
        self.employee_ch._onchange_contract_template_id()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
