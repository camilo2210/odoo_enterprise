# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDashboardWarnings(TestPayrollCommon):

    def check_warnings(self, warning_ids, warning_name, expected_employees):
        self.assertTrue(all(isinstance(warning_id, int) for warning_id in warning_ids), "There should be warnings to check")
        warnings = self.env['hr.payroll.warning'].get_payroll_dashboard_warning_cards(warning_ids)
        applicable_warnings = [warning for warning in warnings if warning['name'] == warning_name]
        if not expected_employees:
            self.assertEqual(applicable_warnings, [])
        else:
            self.assertTrue(applicable_warnings, f"Warning '{warning_name}' should be present in the dashboard warnings")
            self.assertEqual(expected_employees, applicable_warnings[0]['warning_records'])

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.new_employee = cls.create_employee({
            'name': 'Test Employee',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': date(2025, 3, 31),
            'fixed_term': True,
        })
        cls.second_version = cls.new_employee.create_version({
            'date_version': date(2025, 4, 1),
            'contract_date_start': date(2025, 4, 1),
            'contract_date_end': date(2025, 6, 30),
        })
        cls.third_version = cls.new_employee.create_version({
            'date_version': date(2025, 7, 1),
            'contract_date_start': date(2025, 7, 1),
            'contract_date_end': date(2025, 9, 30),
        })
        cls.fourth_version = cls.new_employee.create_version({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'contract_date_end': date(2025, 12, 31),
        })

    @freeze_time("2025-11-01")
    def test_4th_cdd_warning_4_cdd(self):
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, '4th consecutive fixed-term contract', self.new_employee)

    @freeze_time("2025-11-01")
    def test_4th_cdd_warning_3_cdd_1_cdi(self):
        self.fourth_version.write({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'contract_date_end': False,
            'fixed_term': False,
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, '4th consecutive fixed-term contract', self.env['hr.employee'])

    @freeze_time("2025-11-01")
    def test_4th_cdd_warning_less_three_months(self):
        self.second_version.write({
            'date_version': date(2025, 4, 1),
            'contract_date_start': date(2025, 4, 1),
            'contract_date_end': date(2025, 4, 30),
        })
        self.third_version.write({
            'date_version': date(2025, 5, 1),
            'contract_date_start': date(2025, 5, 1),
            'contract_date_end': date(2025, 9, 30),
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, '4th consecutive fixed-term contract', self.env['hr.employee'])

    @freeze_time("2025-08-01")
    def test_4th_cdd_warning_3_cdd(self):
        self.fourth_version.unlink()
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, '4th consecutive fixed-term contract', self.env['hr.employee'])

    @freeze_time("2025-12-01")
    def test_4th_cdd_warning_more_two_years(self):
        self.new_employee.version_ids[0].write({
            'date_version': date(2023, 1, 1),
            'contract_date_start': date(2023, 1, 1),
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, '4th consecutive fixed-term contract', self.env['hr.employee'])

    @freeze_time("2025-12-01")
    def test_4th_cdd_warning_cdd_then_cdi(self):
        self.fourth_version.write({
            'contract_date_end': date(2025, 12, 10),
        })
        self.new_employee.create_version({
            'date_version': date(2025, 12, 11),
            'contract_date_start': date(2025, 12, 11),
            'contract_date_end': False,
            'fixed_term': False,
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, '4th consecutive fixed-term contract', self.env['hr.employee'])

    @freeze_time("2025-12-01")
    def test_4th_cdd_one_less_3_months(self):
        self.third_version.write({
            'contract_date_end': date(2025, 9, 20),
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, '4th consecutive fixed-term contract', self.env['hr.employee'])

    @freeze_time("2025-12-01")
    def test_4th_cdd_warning_more_two_years_span(self):
        self.fourth_version.write({
            'contract_date_end': date(2027, 1, 10),
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, '4th consecutive fixed-term contract', self.env['hr.employee'])

    @freeze_time("2026-01-01")
    def test_sales_rep_wrong_salary_scale(self):
        sales_rep_employee = self.create_employee({
            'name': 'Sales Rep',
            'date_version': date(2025, 12, 1),
            'contract_date_start': date(2025, 12, 1),
            'contract_date_end': False,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_a').id,
            'l10n_be_is_sale_representative': True,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id
        })

        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, 'Invalid Salary Scale for Sales Representatives', self.env['hr.employee'])

        # 6 months < seniority < 4 years
        sales_rep_employee.write({
            'date_version': date(2025, 7, 1),
            'contract_date_start': date(2025, 7, 1),
            'l10n_be_fictive_hire_date': date(2025, 7, 1),
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, 'Invalid Salary Scale for Sales Representatives', sales_rep_employee)
        sales_rep_employee.write({
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_c').id,
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, 'Invalid Salary Scale for Sales Representatives', self.env['hr.employee'])

        # 4 years < seniority
        sales_rep_employee.write({
            'date_version': date(2019, 7, 1),
            'contract_date_start': date(2019, 7, 1),
            'l10n_be_fictive_hire_date': date(2019, 7, 1),
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, 'Invalid Salary Scale for Sales Representatives', sales_rep_employee)
        sales_rep_employee.write({
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_d').id,
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, 'Invalid Salary Scale for Sales Representatives', self.env['hr.employee'])

        # No contract, no warning
        sales_rep_employee.write({
            'contract_date_start': False,
            'l10n_be_fictive_hire_date': False,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_a').id,
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, 'Invalid Salary Scale for Sales Representatives', self.env['hr.employee'])

    def test_non_matching_birthday_warning(self):
        """
        Set NISS -> birthday becomes date(1988, 1, 1) -> change birthday -> check warning is raised
        """
        self.new_employee.write({
            'niss': 88010119776,
        })
        self.new_employee.write({
            'birthday': date(1988, 1, 2),
        })
        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, 'Employees with inconsistent birthday', self.new_employee)

    @freeze_time("2026-06-01")
    def test_min_wage_warning_student_non_existent_category(self):
        self.create_employee({
            'name': 'Student',
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'contract_date_end': False,
            'birthday': date(2008, 1, 1),
            'l10n_be_dimona_category': 'stu',
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp302_cat_22').id,
        })
        # Must not raise:
        self.env['hr.employee']._get_l10n_be_min_wage_invalid_employees()

    def test_mobility_budget_and_not_eco_vehicle_warning(self):
        brand = self.env['fleet.vehicle.model.brand'].sudo().create({'name': "Test Brand"})
        model = self.env['fleet.vehicle.model'].sudo().create({'name': "Test Model", 'brand_id': brand.id})
        car = self.env['fleet.vehicle'].sudo().create({
            'name': "Not Eco-Friendly Car",
            'license_plate': "Test Car",
            'company_id': self.belgian_company.id,
            'model_id': model.id,
            'contract_date_start': date(2020, 10, 8),
            'co2': 90.0,
            'car_value': 38000.0,
            'fuel_type': "diesel",
            'acquisition_date': date(2020, 1, 1)
        })
        self.new_employee.write({
            'car_id': car.id,
            'transport_mode_car': True,
            'l10n_be_mobility_budget': True,
        })

        warning_ids = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(warning_ids, 'Employees with mobility budget and company car with CO2 > 0', self.new_employee)
