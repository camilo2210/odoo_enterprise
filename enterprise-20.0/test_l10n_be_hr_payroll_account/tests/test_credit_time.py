# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.tools.float_utils import float_compare
from odoo.tests import tagged, freeze_time
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', '-at_install', 'credit_time')
class TestCreditTime(TestPayslipValidationCommon, TestBelgiumCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_user') \
                               | cls.env.ref('fleet.fleet_group_manager')
        cls.env.company.partner_id.tz = "Europe/Brussels"
        cls.env.user.tz = "Europe/Brussels"

        cls.company_data['company'].write({
            'country_id': cls.env.ref('base.be').id,
        })
        cls.company_data['company'].current_payroll_config_id.write({
            'onss_importance_code': '1',
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
        })

        cls.env.company.resource_calendar_id = cls.env['resource.calendar'].create({
            'name': 'Standard 38 hours/week',
            'company_id': cls.env.company.id,
            'hours_per_day': 7.6,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (5, 0, 0),
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6})
            ],
        })
        cls.classic_38h_calendar = cls.env.company.resource_calendar_id
        cls.classic_38h_calendar.reference_calendar_id = cls.classic_38h_calendar
        cls.env.ref('hr.structure_type_employee_cp200').sudo().default_resource_calendar_id = cls.classic_38h_calendar

        cls.model_a3 = cls.env["fleet.vehicle.model"].sudo().create({
            'name': ' A3',
            'brand_id': cls.env.ref('fleet.brand_audi').id,
            'vehicle_type': 'car',
        }).sudo(False)

        cls.partner = cls.env['res.partner'].create({'name': 'Roger'})

        with freeze_time('2020-01-01'):
            cls.car = cls.env['fleet.vehicle'].sudo().create({
                'model_id': cls.model_a3.id,
                'license_plate': '1-JFC-094',
                'acquisition_date': '2020-01-01',
                'contract_date_start': '2020-01-01',
                'co2': 88,
                'driver_id': cls.partner.id,
                'car_value': 38000,
                'company_id': cls.env.company.id,
            }).sudo(False)

        employee = cls.env['hr.employee'].sudo().create({
            'name': 'My Credit Time Employee',
            'user_partner_id': cls.partner.id,
            'work_contact_id': cls.partner.id,
            'company_id': cls.env.company.id,
            'resource_calendar_id': cls.classic_38h_calendar.id,
            'contract_date_start': datetime.date(2015, 1, 1),
            'date_version': datetime.date(2015, 1, 1),
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'wage': 3000,
            'fuel_card': 150,
            'meal_voucher_amount': 7.45,
            'l10n_be_lsa_monthly_pro_base_amount': 150,
            'commission_on_target': 1000,
            'ip_wage_rate': 0.25,
            'transport_mode_car': True,
            'car_id': cls.car.id,
            'bus_transport_employee_amount': 34,
            'distance_home_work': 30,
            'internet': 38,
            'mobile': 30,
            'laptop': 100,
            'l10n_be_worker_code_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495').id,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        })
        cls.original_version = employee.version_id.sudo(False)
        cls.employee = employee.sudo(False)

        # Activate the benefit
        cls.env['hr.contract.salary.benefit'].with_context(active_test=False).search([('res_field_id.name', '=', 'l10n_be_lsa_monthly_pro_base_amount')]).active = True

    def test_full_time_credit_time(self):
        # Test case:369.23
        # Classic 38h/week until 4th of March 2020 included --> 3 normal days
        # Full Time Credit Time from the 5th of March 2020 to 30th of April 2020
        # Generate work entries for March and check both payslips

        new_calendar = self.env['resource.calendar'].sudo().create({
            'name': 'Credit Time Calendar',
            'company_id': self.env.company.id,
            'hours_per_day': 0,
            'attendance_ids': [(5, 0, 0)] +
                [(0, 0, {
                    'dayofweek': dayofweek,
                    'hour_from': hour_from,
                    'hour_to': hour_to,
                    'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_credit_time').id
                }) for dayofweek, hour_from, hour_to in [
                    ("0", 8.0, 12.0),
                    ("0", 13.0, 16.6),
                    ("1", 8.0, 12.0),
                    ("1", 13.0, 16.6),
                    ("2", 8.0, 12.0),
                    ("2", 13.0, 16.6),
                    ("3", 8.0, 12.0),
                    ("3", 13.0, 16.6),
                    ("4", 8.0, 12.0),
                    ("4", 13.0, 16.6),
                ]],
        })

        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.env.company.ids).new({
            'version_id': self.original_version.id,
            'date_start': datetime.date(2020, 3, 5),
            'date_end': datetime.date(2020, 4, 30),
            'resource_calendar_id': new_calendar.id,
        })
        wizard.action_validate()

        versions = self.env['hr.version'].search([('employee_id', '=', self.employee.id)])
        new_version = versions[1]
        self.assertEqual(len(versions), 3)
        self.assertEqual(self.original_version.date_end, datetime.date(2020, 3, 4))
        self.assertEqual(new_version.date_start, datetime.date(2020, 3, 5))
        self.assertEqual(new_version._get_contract_wage(), 3000)

        # Generate Work Entries
        date_start = datetime.date(2020, 3, 1)
        date_stop = datetime.date(2020, 3, 31)
        work_entries_vals = (self.original_version | new_version).generate_work_entries(date_start, date_stop)
        # The work entries are generated until today, so only take those from march
        work_entries_vals = [vals for vals in work_entries_vals if vals['date'].month == 3]

        work_entries_1 = [vals for vals in work_entries_vals if vals['version_id'] == self.original_version]
        work_entries_2 = [vals for vals in work_entries_vals if vals['version_id'] == new_version]
        self.assertEqual(len(work_entries_1), 3)  # 2, 3, 4 March
        self.assertEqual(len(work_entries_2), 19)  # 5-6 (2), 9-13 (5), 16-20 (5), 23-27 (5), 30-31 (2) March

        # Generate Payslip
        payslip_run = self.env["hr.payslip.run"].create({
            "date_start": "2020-03-01",
            "date_end": "2020-03-31",
            "structure_id": self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
        })

        payslip_run._generate_payslips()

        self.assertEqual(len(payslip_run.slip_ids), 1)

        payslip = payslip_run.slip_ids[0]
        payslip_versions = payslip.worked_days_line_ids.mapped('version_id')

        self.assertEqual(len(set(payslip_versions)), 2)

        self.assertIn(self.original_version, payslip_versions)
        self.assertEqual(len(payslip.worked_days_line_ids), 2)  # One attendance line, One out of contract
        attendance_line = payslip.worked_days_line_ids.filtered(lambda wd: wd.code == '002.00')
        self.assertAlmostEqual(attendance_line.amount, 415.38, places=2)
        self.assertEqual(attendance_line.number_of_days, 3.0)
        self.assertAlmostEqual(attendance_line.number_of_hours, 22.8, places=2)
        self.assertIn(new_version, payslip_versions)
        credit_time_line = payslip.worked_days_line_ids.filtered(lambda wd: wd.code == '147.00')
        self.assertEqual(credit_time_line.amount, 0)
        self.assertEqual(credit_time_line.number_of_days, 19.0)
        self.assertEqual(float_compare(credit_time_line.number_of_hours, 144.4, 2), 0)

        self._validate_payslip(payslip)

    def test_4_5_time_credit_time(self):
        # Test case:
        # Classic 38h/week until 4th of March 2020 included --> 3 normal days
        # 4/5 Credit Time from the 5th of March 2020 to 30th of April 2020
        # The employee won't work on wednesday
        # Generate work entries for March and check both payslips

        new_calendar = self.env['resource.calendar'].sudo().create({
            'name': 'Credit Time Calendar',
            'company_id': self.env.company.id,
            'hours_per_day': 7.6,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6})
            ] + [
                (0, 0, {
                    'dayofweek': dayofweek,
                    'hour_from': hour_from,
                    'hour_to': hour_to,
                    'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_credit_time').id
                }) for dayofweek, hour_from, hour_to in [
                    ("2", 8.0, 12.0),
                    ("2", 13.0, 16.6),
                ]
            ],
        })

        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.env.company.ids).new({
            'version_id': self.original_version.id,
            'date_start': datetime.date(2020, 3, 5),
            'date_end': datetime.date(2020, 4, 30),
            'wage': 2400 * (5 / 4),
            'resource_calendar_id': new_calendar.id,
        })
        wizard.action_validate()

        versions = self.env['hr.version'].search([('employee_id', '=', self.employee.id)])
        new_version = versions[1]
        self.assertEqual(len(versions), 3)
        self.assertEqual(self.original_version.date_end, datetime.date(2020, 3, 4))
        self.assertEqual(new_version.date_start, datetime.date(2020, 3, 5))

        # Generate Work Entries
        date_start = datetime.date(2020, 3, 1)
        date_stop = datetime.date(2020, 3, 31)
        work_entries_vals = (self.original_version | new_version).generate_work_entries(date_start, date_stop)
        # The work entries are generated until today, so only take those from march
        work_entries_vals = [vals for vals in work_entries_vals if vals['date'].month == 3]

        work_entries_1 = [vals for vals in work_entries_vals if vals['version_id'] == self.original_version]
        work_entries_2 = [vals for vals in work_entries_vals if vals['version_id'] != self.original_version]
        self.assertEqual(len(work_entries_1), 3)  # 2, 3, 4 March
        self.assertTrue(all(vals['work_entry_type_id'] == self.env.ref('hr_work_entry.be_work_entry_type_attendance') for vals in work_entries_1))
        self.assertEqual(len(work_entries_2), 19)  # 5-6 (2), 9-13 (5), 16-20 (5), 23-27 (5), 30-31 (2) March
        attendance_we = [vals for vals in work_entries_2 if vals['work_entry_type_id'] == self.env.ref('hr_work_entry.be_work_entry_type_attendance')]
        credit_time_we = [vals for vals in work_entries_2 if vals['work_entry_type_id'] == self.env.ref('hr_work_entry.l10n_be_work_entry_type_credit_time')]
        self.assertEqual(len(credit_time_we), 3)  # 11,18,25
        self.assertEqual(len(attendance_we), 16)  # Remaining days

        payslip_run = self.env["hr.payslip.run"].create({
            "date_start": "2020-03-01",
            "date_end": "2020-03-31",
            "structure_id": self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
        })

        payslip_run._generate_payslips()

        self.assertEqual(len(payslip_run.slip_ids), 1)

        payslip = payslip_run.slip_ids[0]
        payslip_versions = payslip.worked_days_line_ids.mapped('version_id')
        self.assertEqual(len(set(payslip_versions)), 2)
        self.assertIn(self.original_version, payslip_versions)
        self.assertEqual(len(payslip.worked_days_line_ids), 3)  # Attendance, credit time, out of contract
        attendance_line = payslip.worked_days_line_ids.filtered(lambda wd: wd.code == '002.00' and wd.version_id == self.original_version)
        self.assertAlmostEqual(attendance_line.amount, 415.38, places=2)
        self.assertEqual(attendance_line.number_of_days, 3.0)
        self.assertAlmostEqual(attendance_line.number_of_hours, 22.8, places=2)

        self.assertIn(new_version, payslip_versions)
        attendance_line_new_version = payslip.worked_days_line_ids.filtered(lambda wd: wd.code == '002.00' and wd.version_id == new_version)
        self.assertAlmostEqual(attendance_line_new_version.amount, 1984.62, places=2)
        self.assertEqual(attendance_line_new_version.number_of_days, 16.0)
        self.assertEqual(float_compare(attendance_line_new_version.number_of_hours, 121.6, 2), 0)
        credit_time_line = payslip.worked_days_line_ids.filtered(lambda wd: wd.code == '147.00' and wd.version_id == new_version)
        self.assertEqual(credit_time_line.amount, 0)
        self.assertEqual(credit_time_line.number_of_days, 3)
        self.assertEqual(float_compare(credit_time_line.number_of_hours, 22.8, 2), 0)

        self._validate_payslip(payslip)
