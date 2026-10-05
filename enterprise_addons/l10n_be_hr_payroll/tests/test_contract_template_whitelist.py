# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_be = self.env['res.company'].create({
            'name': 'BE Co',
            'country_id': self.env.ref('base.be').id,
        })
        self.employee_be = self.env['hr.employee'].create({
            'name': 'BE Employee',
            'company_id': self.company_be.id,
            'certificate': 'bachelor',  # Required for rd_percentage field validation
        })
        self.employee_be.version_id.l10n_be_lsa_monthly_pro_other_amount = 150

    def test_be_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_be)

        template = Version.create({
            'name': 'BE Template',
            'wage': 4000.0,
            'wage_type': 'monthly',
            'hourly_wage': 25.0,
            'commission_on_target': 5000.0,
            'l10n_be_lsa_monthly_pro_other_amount': 200.0,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_b').id,
            'ip_wage_rate': 0.25,
            'ip_artist': True,
            'ip_onss': False,
            'mobile': 50.0,
            'internet': 30.0,
            'has_laptop': True,
            'meal_voucher_amount': 8.0,
            'meal_voucher_calculation_method': 'hours',
            'eco_checks': 250.0,
            'l10n_be_group_insurance_rate': 0.025,
            'l10n_be_mobility_budget': True,
            'l10n_be_mobility_budget_amount': 500.0,
            'l10n_be_mobility_budget_amount_monthly': 50.0,
            'has_hospital_insurance': True,
            'insurance_amount': 100.0,
            'insured_relative_spouse': True,
            'insured_relative_adults': 1,
            'insured_relative_children': 2,
            'l10n_be_has_ambulatory_insurance': True,
            'l10n_be_ambulatory_insurance_amount': 75.0,
            'l10n_be_ambulatory_insured_spouse': True,
            'l10n_be_ambulatory_insured_adults': 1,
            'l10n_be_ambulatory_insured_children': 2,
            'transport_mode_car': True,
            'fuel_card': 150.0,
            'car_atn': 200.0,
            'private_car_employee_kilometer': 25,
            'distance_home_work': 25,
            'distance_home_work_unit': 'kilometers',
            'private_car_reimbursed_amount': 0.3,
            'train_transport_employee_kilometer': 17,
            'bus_transport_employee_amount': 50.0,
            'no_onss': False,
            'no_withholding_taxes': False,
            'l10n_be_resident_situation': 'resident',
            'rd_percentage': 0.05,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        })
        contract = self.employee_be.version_id

        self.assertEqual(contract.commission_on_target, 0.0)
        self.assertEqual(contract.ip_wage_rate, 0.0)

        self.employee_be.contract_template_id = template
        self.employee_be._onchange_contract_template_id()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
