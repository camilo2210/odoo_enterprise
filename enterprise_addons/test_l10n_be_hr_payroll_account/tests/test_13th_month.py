# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo.tests import tagged
from odoo.addons.test_l10n_be_hr_payroll_account.tests.test_payslip import TestPayslipBase


@tagged('thirteen_month')
@tagged('at_install', '-post_install')  # LEGACY at_install
class Test13thMonth(TestPayslipBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.structure = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')
        cls.payslip = cls.create_payslip(cls.structure, datetime(2019, 12, 1), datetime(2019, 12, 31))

        cls.calendar_40h = cls.env['resource.calendar'].create({
            'name': '40h calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17}),
            ]
        })

        cls.env.company.resource_calendar_id = cls.calendar_40h
        cls.structure.type_id.default_resource_calendar_id = cls.calendar_40h

        cls.calendar_20h = cls.env['resource.calendar'].create({
            'name': '20h calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
            ]
        })

        cls.calendar_20h_three_days = cls.env['resource.calendar'].create({
            'name': '20h calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
            ]
        })

        med_work_entry_type = cls.env.ref('hr_work_entry.l10n_be_work_entry_type_partial_incapacity')
        cls.calendar_part_time_med = cls.env['resource.calendar'].create({
            'name': 'Part time med 40%',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17}),
            ]
        })

        credit_time_work_entry_type = cls.env.ref('hr_work_entry.l10n_be_work_entry_type_credit_time')
        cls.calendar_part_time_credit_time = cls.env['resource.calendar'].create({
            'name': 'Part time credit time 40%',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': credit_time_work_entry_type.id}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': credit_time_work_entry_type.id}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': credit_time_work_entry_type.id}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': credit_time_work_entry_type.id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': credit_time_work_entry_type.id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': credit_time_work_entry_type.id}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17}),
            ]
        })

        parental_leave_work_entry_type = cls.env.ref('hr_work_entry.l10n_be_work_entry_type_parental_time_off')
        cls.calendar_part_time_parental = cls.env['resource.calendar'].create({
            'name': 'Part time parental 40%',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': parental_leave_work_entry_type.id}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': parental_leave_work_entry_type.id}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': parental_leave_work_entry_type.id}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': parental_leave_work_entry_type.id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': parental_leave_work_entry_type.id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': parental_leave_work_entry_type.id}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17}),
            ]
        })

        cls.calendar_part_time_20_hours_per_week = cls.env['resource.calendar'].create({
            'name': 'Part time parental 50%',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': med_work_entry_type.id}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17, 'work_entry_type_id': med_work_entry_type.id}),
            ]
        })

    def test_end_of_year_bonus(self):
        self.update_version(date(2015, 1, 1))

        self.payslip.compute_sheet()

        self.check_payslip('end of year bonus', self.payslip, {
            'BONUS_BASIC': 2500.0,
            'BONUS_SALARY': 2500.0,
            'ONSS_BONUS': -326.75,
            'BONUS_GROSS': 2173.25,
            'BONUS_PP': -943.41,
            'NET': 1207.83,
        })

    def test_13th_month_paid_amount_full_year(self):
        self.update_version(date(2015, 1, 24))
        self.assertEqual(self.payslip._get_paid_amount_13th_month(), 2500, 'It should be the full December wage')

    def test_13th_month_paid_amount_after_july(self):
        self.update_version(date(2019, 7, 4))
        self.assertEqual(self.payslip._get_paid_amount_13th_month(), 0, 'This is not a full month')

    def test_13th_month_paid_amount_first_july(self):
        self.update_version(date(2019, 7, 1))
        self.assertEqual(self.payslip._get_paid_amount_13th_month(), 0, '13th month only for people who started before 01/07')

    def test_13th_month_paid_amount_month_start(self):
        self.update_version(date(2019, 6, 3))  # 3rd June 2019 is a Monday => June should count
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * 7 / 12, msg='It should count 7/12 months')

    def test_13th_month_paid_amount_month_middle(self):
        self.update_version(date(2019, 6, 10))  # in the middle of June => June should not count
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * 6 / 12, msg='It should count 6/12 months')

    def test_13th_month_paid_amount_multiple_contracts_gap(self):
        self.update_version(date(2019, 1, 1), date(2019, 3, 31))
        version = self.create_version(date(2019, 11, 1))
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 0, msg='It should count O months as the total is less than 6 months')

    def test_13th_month_paid_amount_multiple_contracts_middle(self):
        self.update_version(date(2019, 1, 1), date(2019, 3, 13))  # middle of the week
        version = self.create_version(date(2019, 3, 14))  # starts the following day
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), version.wage, msg='It should count all months')

    def test_13th_month_paid_amount_multiple_contracts_weekend(self):
        self.update_version(date(2019, 1, 1), date(2019, 3, 15))  # ends a Friday
        version = self.create_version(date(2019, 3, 18))  # starts the following Monday
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), version.wage, msg='It should count all months')

    def test_13th_month_paid_amount_multiple_contracts_next_week(self):
        self.update_version(date(2019, 1, 1), date(2019, 3, 15))  # ends a Friday
        version = self.create_version(date(2019, 3, 19))  # starts the following Tuesday
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), version.wage * 11 / 12, msg='It should count 11/12 months')

    def test_13th_month_become_part_time(self):
        self.update_version(date(2019, 1, 1), date(2019, 6, 30), wage=5000)
        version = self.create_version(date(2019, 7, 1), wage=2500)
        version.resource_calendar_id = self.calendar_20h
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), (5000 + 2500) / 2)

    def test_13th_month_become_part_time_other_calendar(self):
        self.update_version(date(2019, 1, 1), date(2019, 6, 30), wage=5000)
        version = self.create_version(date(2019, 7, 1), wage=2500)
        version.resource_calendar_id = self.calendar_20h_three_days
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), (5000 + 2500) / 2)

    def test_13th_month_become_part_time_middle_month(self):
        self.update_version(date(2019, 1, 1), date(2019, 6, 12), wage=5000)
        version = self.create_version(date(2019, 6, 13), wage=2500)
        version.resource_calendar_id = self.calendar_20h_three_days
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), (5000 * (5 / 12 + (12 / 30) / 12)) + 2500 * (6 / 12 + (18 / 30) / 12))

    def test_13th_month_become_full_time(self):
        self.update_version(date(2019, 1, 1), date(2019, 6, 30), wage=2500)
        self.version.resource_calendar_id = self.calendar_20h
        version = self.create_version(date(2019, 7, 1), wage=5000)
        version.resource_calendar_id = version.company_id.resource_calendar_id
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), (5000 + 2500) / 2)

    def test_13th_month_become_full_time_other_calendar(self):
        self.update_version(date(2019, 1, 1), date(2019, 6, 30), wage=2500)
        self.version.resource_calendar_id = self.calendar_20h_three_days
        version = self.create_version(date(2019, 7, 1), wage=5000)
        version.resource_calendar_id = version.company_id.resource_calendar_id
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), (5000 + 2500) / 2)

    def test_13th_month_become_full_time_middle_month(self):
        self.update_version(date(2019, 1, 1), date(2019, 6, 12), wage=2500)
        self.version.resource_calendar_id = self.calendar_20h_three_days
        version = self.create_version(date(2019, 6, 13), wage=5000)
        version.resource_calendar_id = version.company_id.resource_calendar_id
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), (2500 * (5 / 12 + (12 / 30) / 12)) + 5000 * (6 / 12 + (18 / 30) / 12))

    def test_13th_month_become_part_time_medical_half_year(self):
        self.update_version(date(2019, 1, 1), date(2019, 8, 30), wage=5000)
        version = self.create_version(date(2019, 9, 2), wage=5000)
        version.resource_calendar_id = self.calendar_part_time_med
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        # Medical part time should be assimilated as sick time off, less 60 days -> full wage
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 5000)

    def test_13th_month_become_full_time_from_part_time_medical_half_year(self):
        self.update_version(date(2019, 1, 1), date(2019, 4, 30), wage=(5000 * 0.4))
        self.version.resource_calendar_id = self.calendar_part_time_med
        version = self.create_version(date(2019, 5, 1), wage=5000)
        version.resource_calendar_id = version.company_id.resource_calendar_id
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        # Medical part time should be assimilated as sick time off, less 60 days -> full wage
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 5000)

    def test_13th_month_become_part_time_medical_full_year(self):
        version = self.update_version(date(2019, 1, 1), date(2019, 12, 31), wage=5000)
        version.resource_calendar_id = self.calendar_part_time_med
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        # Medical part time should be assimilated as sick time off, assimilated from 1st Jan to 20th May
        months_ratios = [1, 1, 1, 1, 26 / 31, 18 / 30, 16 / 31, 19 / 31, 17 / 30, 17 / 31, 18 / 30, 17 / 31]
        total_ratio = sum(ratio / 12 for ratio in months_ratios)
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 5000 * total_ratio)

    def test_13th_month_become_part_time_credit_time_full_year(self):
        version = self.update_version(date(2019, 1, 1), date(2019, 12, 31), wage=5000)
        version.resource_calendar_id = self.calendar_part_time_credit_time
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        # Credit time work entries should not count, result should be the prorated wage
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 5000 * 0.4)

    def test_13th_month_become_part_time_parental_full_year(self):
        version = self.update_version(date(2019, 1, 1), date(2019, 12, 31), wage=5000)
        version.resource_calendar_id = self.calendar_part_time_parental
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        # Parental time off work entries should not count, result should be the prorated wage
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 5000 * 0.4)

    def test_13th_month_salary_change(self):
        self.update_version(date(2019, 1, 1), date(2019, 6, 12), wage=2500)
        version = self.create_version(date(2019, 6, 13), wage=3000)
        self.payslip.write({
            'version_id': version.id,
            'date_from': datetime(2019, 12, 1),
            'date_to': datetime(2019, 12, 31),
        })
        # Basic for the 13th month is the December salary
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 3000)

    def test_13th_month_contract_interruption(self):
        self.update_version(date(2015, 1, 1), date(2019, 3, 1))
        self.create_version(date(2019, 9, 1), wage=3000)
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 0, msg='Not 6 months of seniority')

    def test_13th_month_unpaid_work_entry(self):
        self.update_version(date(2015, 1, 1))
        unpaid_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave')
        self.env['hr.leave'].create([
            {
                'name': 'Unpaid work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': unpaid_work_entry_type.id,
                'date_from': datetime(2019, 3, 1, 1, 0, 0),
                'date_to': datetime(2019, 3, 1, 23, 0, 0),
                'request_date_from': datetime(2019, 3, 1, 1, 0, 0),
                'request_date_to': datetime(2019, 3, 1, 23, 0, 0),
                'number_of_days': 1,
            },
        ])
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * 11 / 12, msg='It should count 11/12 months')

    def test_13th_month_unpaid_7_months_work_entry(self):
        self.update_version(date(2015, 1, 1))
        self.env['hr.leave'].create([
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
                'request_date_from': date(2019, 4, 1),
                'request_date_to': date(2019, 10, 31),
            }
        ])

        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * 5 / 12, msg='It should count 5/12 months')

    def test_13th_month_unpaid_work_entry_half_day(self):
        self.update_version(date(2015, 1, 1))
        unpaid_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave')
        attendance_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_attendance')
        attendance_work_entry_type.request_unit = 'hour'
        unpaid_work_entry_type.request_unit = 'half_day'
        attendance_work_entry_type.requires_allocation = False
        self.env['hr.leave'].create([
            {
                'name': 'Unpaid work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': unpaid_work_entry_type.id,
                'request_date_from': date(2019, 3, 1),
                'request_date_to': date(2019, 3, 1),
                'request_date_from_period': 'am',
                'request_date_to_period': 'am',
            },
            {
                'name': 'Attendance work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': attendance_work_entry_type.id,
                'request_date_from': date(2019, 3, 1),
                'request_date_to': date(2019, 3, 1),
                'request_hour_from': 12,
                'request_hour_to': 15,
            },
        ])
        # Should count all months as half days of absence have no impact
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage, msg='It should count all months')

    def test_13th_month_unpaid_work_entry_full_and_half_day(self):
        self.update_version(date(2015, 1, 1))
        unpaid_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave')
        attendance_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_attendance')
        attendance_work_entry_type.request_unit = 'hour'
        unpaid_work_entry_type.request_unit = 'half_day'
        attendance_work_entry_type.requires_allocation = False
        self.env['hr.leave'].create([
            {
                'name': 'Unpaid work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': unpaid_work_entry_type.id,
                'request_date_from': date(2019, 2, 1),
                'request_date_to': date(2019, 2, 1),
                'request_date_from_period': 'am',
                'request_date_to_period': 'pm',
            },
            {
                'name': 'Unpaid work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': unpaid_work_entry_type.id,
                'request_date_from': date(2019, 3, 1),
                'request_date_to': date(2019, 3, 1),
                'request_date_from_period': 'am',
                'request_date_to_period': 'am',
            },
            {
                'name': 'Attendance work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': attendance_work_entry_type.id,
                'request_date_from': datetime(2019, 3, 1),
                'request_date_to': datetime(2019, 3, 1),
                'request_hour_from': 12,
                'request_hour_to': 15,
            },
        ])
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * 11 / 12, msg='It should count 11/12 months')

    def test_13th_month_unpaid_work_entry_full_and_half_day_same_month(self):
        self.update_version(date(2015, 1, 1))
        unpaid_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave')
        attendance_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_attendance')
        attendance_work_entry_type.request_unit = 'hour'
        attendance_work_entry_type.requires_allocation = False
        self.env['hr.leave'].create([
            {
                'name': 'Unpaid work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': unpaid_work_entry_type.id,
                'request_date_from': date(2019, 2, 1),
                'request_date_to': date(2019, 2, 1),
                'request_date_from_period': 'am',
                'request_date_to_period': 'pm',
            },
            {
                'name': 'Unpaid work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': unpaid_work_entry_type.id,
                'request_date_from': date(2019, 2, 4),
                'request_date_to': date(2019, 2, 4),
                'request_date_from_period': 'am',
                'request_date_to_period': 'am',
            },
            {
                'name': 'Attendance work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': attendance_work_entry_type.id,
                'request_date_from': date(2019, 2, 4),
                'request_date_to': date(2019, 2, 4),
                'request_hour_from': 12,
                'request_hour_to': 15,
            },
        ])
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * 11 / 12, msg='It should count 11/12 months')

    def test_13th_month_with_variable_salary(self):
        self.update_version(date(2015, 1, 1))
        self.version.employee_id.write({
            'l10n_be_fictive_hire_date': date(2015, 1, 1),
        })
        monthly_pay = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        payslip = self.create_payslip(monthly_pay, datetime(2019, 1, 1), datetime(2019, 1, 31))
        payslip._set_input_value('COMMISSION', 200)
        payslip.compute_sheet()
        payslip.action_validate()
        # 200€ commission during the year -> average of 16.67€ per month
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 2516.67, places=2, msg='It should count full wage + commissions')

    def test_13th_month_with_variable_salary_capped(self):
        self.update_version(date(2015, 1, 1))
        self.version.employee_id.write({
            'l10n_be_fictive_hire_date': date(2015, 1, 1),
        })
        self.version.write({
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_d').id,
            'l10n_be_is_sale_representative': True,
        })
        monthly_pay = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        payslip = self.create_payslip(monthly_pay, datetime(2025, 1, 1), datetime(2025, 1, 31))
        payslip._set_input_value('COMMISSION', 20000)
        payslip.compute_sheet()
        payslip.action_validate()
        # 20 000€ commission during the year -> average of 1666.67€ per month
        # Theoritically, he should get 2500 + 1666.67 =  4166.67
        # But the minimum salary is 3037.86, so he should be capped to this amount
        self.payslip.write({
            'date_from': datetime(2025, 12, 1),
            'date_to': datetime(2025, 12, 31),
        })
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 3037.86, places=2, msg='It should cap the full wage + commissions')

    def test_13th_month_unpaid_with_variable_salary(self):
        self.update_version(date(2015, 1, 1))
        self.version.employee_id.write({
            'l10n_be_fictive_hire_date': date(2015, 1, 1),
        })
        monthly_pay = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        payslip = self.create_payslip(monthly_pay, datetime(2019, 1, 1), datetime(2019, 1, 31))
        payslip._set_input_value('COMMISSION', 200)
        payslip.compute_sheet()
        payslip.action_validate()
        self.env['hr.leave'].create([
            {
                'name': 'Unpaid work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
                'date_from': datetime(2019, 3, 1, 1, 0, 0),
                'date_to': datetime(2019, 3, 1, 23, 0, 0),
                'request_date_from': datetime(2019, 3, 1, 1, 0, 0),
                'request_date_to': datetime(2019, 3, 1, 23, 0, 0),
                'number_of_days': 1,
            },
        ])
        # 200€ commission during the year -> average of 16.67€ per month. Should not depend if unpaid during the month
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), (2500 * 11 / 12) + 16.67 * (11 / 12), places=2, msg='It should count full wage + commissions')

    def test_13th_month_unpredictable_reason_10_days(self):
        self.update_version(date(2015, 1, 1))
        self.env['hr.leave.allocation'].create([{
            'name': 'Paid Time Off',
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_unpredictable').id,
            'number_of_days': 10,
            'employee_id': self.employee.id,
            'state': 'confirm',
            'date_from': date(2019, 2, 1),
            'date_to': date(2019, 2, 14),
        }]).action_approve()
        self.env['hr.leave'].create([
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_unpredictable').id,
                'request_date_from': date(2019, 2, 1),
                'request_date_to': date(2019, 2, 14),
            }
        ])
        # 10 days of unpredictable are assimilated as work time
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage)

    def test_13th_month_unpredictable_reason_more_10_days(self):
        self.update_version(date(2015, 1, 1))
        self.env['hr.leave.allocation'].create([
            {
                'name': 'Paid Time Off 1',
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_unpredictable').id,
                'number_of_days': 10,
                'employee_id': self.employee.id,
                'state': 'confirm',
                'date_from': date(2019, 2, 1),
                'date_to': date(2019, 2, 14),
            },
            {
                'name': 'Paid Time Off 2',
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_unpredictable').id,
                'number_of_days': 2,
                'employee_id': self.employee.id,
                'state': 'confirm',
                'date_from': date(2019, 3, 1),
                'date_to': date(2019, 3, 4),
            }
        ]).action_approve()
        self.env['hr.leave'].create([
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_unpredictable').id,
                'request_date_from': date(2019, 2, 1),
                'request_date_to': date(2019, 2, 14),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_unpredictable').id,
                'request_date_from': date(2019, 3, 1),
                'request_date_to': date(2019, 3, 4),
            }
        ])
        # Only 10 days of unpredictable are assimilated as work time
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * ((11 / 12) + ((29 / 31) / 12)))

    def test_13th_month_long_term_sick_60_days(self):
        self.update_version(date(2015, 1, 1))
        self.env['hr.leave'].create([
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2019, 1, 1),
                'request_date_to': date(2019, 3, 1),
            }
        ])
        # First 60 days = sick time off (paid) + sick time off (without guaranteed salary)
        # They must be taken into account
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage)

    def test_13th_month_long_term_sick_more_60_days(self):
        self.update_version(date(2015, 1, 1))
        self.env['hr.leave'].create([
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2019, 1, 1),
                'request_date_to': date(2019, 4, 1),
            }
        ])
        # First 60 days = sick time off (paid) + sick time off (without guaranteed salary) -> taken
        # Next 30 days -> should not be taken into account
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * (10 / 12 + (1 / 31) / 12 + (29 / 30) / 12), places=2)

    def test_13th_month_long_term_sick_two_years_span(self):
        self.update_version(date(2015, 1, 1))
        self.env['hr.leave'].create([
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2018, 12, 1),
                'request_date_to': date(2019, 12, 31),
            }
        ])
        # Already 31 days assimilated previous year -> only 29 left if no come back for 14 consecutive days
        # Only first 29 days of 2019 to be taken into account (21 days of work)
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * (29 / 31) / 12, places=2)

    def test_13th_month_long_term_sick_back_to_work_not_enough(self):
        self.update_version(date(2015, 1, 1))
        all_leave_vals = [
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2018, 12, 1),
                'request_date_to': date(2019, 3, 1),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2019, 3, 14),
                'request_date_to': date(2019, 12, 31),
            }
        ]
        prev_leave = self.env['hr.leave']
        for leave_vals in all_leave_vals:
            prev_leave = self.env['hr.leave'].create([{
                **leave_vals,
                'l10n_be_sickness_relapse': bool(prev_leave),
                'l10n_be_sickness_relapse_origin_leave_id': prev_leave.id or False,
            }])
        # Already 31 days assimilated previous year -> only 29 left if no come back for 14 consecutive days
        # Only first 29 days of 2019 to be taken into account because come back of only 10 days (21 days of work + 8 days of work)
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * ((29 / 31) / 12 + (12 / 31) / 12), places=2)

    def test_13th_month_long_term_sick_back_to_work(self):
        self.update_version(date(2015, 1, 1))
        self.env['hr.leave'].create([
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2018, 12, 1),
                'request_date_to': date(2019, 3, 31),
            }
        ])
        # Already 31 days assimilated previous year -> only 29 left if no come back for 14 consecutive days
        # Take first 60 days as the employee is back after 31/03
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * (11 / 12 + ((1 / 31) / 12)), places=2)

    def test_13th_month_long_term_sick_back_to_work_half_day_sick(self):
        self.update_version(date(2015, 1, 1))
        self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').request_unit = 'half_day'
        all_leave_vals = [
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2018, 12, 1),
                'request_date_to': date(2019, 3, 31),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2019, 4, 4),
                'request_date_to': date(2019, 4, 4),
                'request_date_from_period': 'am',
                'request_date_to_period': 'am'
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2019, 4, 15),
                'request_date_to': date(2019, 12, 31),
            }
        ]
        prev_leave = self.env['hr.leave']
        for leave_vals in all_leave_vals:
            prev_leave = self.env['hr.leave'].create([{
                **leave_vals,
                'l10n_be_sickness_relapse': bool(prev_leave),
                'l10n_be_sickness_relapse_origin_leave_id': prev_leave.id or False,
            }])
        # Half day of sick time off doesn't interfere with the 14 consecutive days, but we remove half day in computation
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * (2 / 12 + ((1 / 31) / 12) + (13.5 / 30) / 12), places=2)

    def test_13th_month_multiple_sicknesses(self):
        self.update_version(date(2015, 1, 1))
        all_leave_vals = [
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2019, 2, 2),
                'request_date_to': date(2019, 2, 13),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2019, 4, 1),
                'request_date_to': date(2019, 4, 30),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2019, 8, 1),
                'request_date_to': date(2019, 9, 30),
            },
        ]
        prev_leave = self.env['hr.leave']
        for leave_vals in all_leave_vals:
            prev_leave = self.env['hr.leave'].create([{
                **leave_vals,
                'l10n_be_sickness_relapse': bool(prev_leave),
                'l10n_be_sickness_relapse_origin_leave_id': prev_leave.id or False,
            }])
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * (10 / 12 + ((18 / 31) / 12)), places=2)

    def test_half_day_sick_time_offs(self):
        self.update_version(date(2015, 1, 1))
        self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').request_unit = 'half_day'
        leaves_to_create = []
        current_date = date(2019, 1, 1)
        for _ in range(120):
            leaves_to_create += [
                {
                    'employee_id': self.employee.id,
                    'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                    'request_date_from': current_date,
                    'request_date_to': current_date,
                    'request_date_from_period': 'am',
                    'request_date_to_period': 'am'
                }
            ]
            if current_date.weekday() == 4:
                current_date += relativedelta(days=3)
            else:
                current_date += relativedelta(days=1)

        prev_leave = self.env['hr.leave']
        for leave_vals in leaves_to_create:
            prev_leave = self.env['hr.leave'].create([{
                **leave_vals,
                'l10n_be_sickness_relapse': bool(prev_leave),
                'l10n_be_sickness_relapse_origin_leave_id': prev_leave.id or False,
            }])

        # 120 half days = 60 days. Every work entry should be treated as working time -> full wage for 13th month
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage, places=2)

    def test_13th_month_assimilated_work_entries(self):
        self.update_version(date(2015, 1, 1))
        public_holiday = self.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday')
        recovery_public_holiday = self.env.ref('hr_work_entry.l10n_be_work_entry_type_prophylactic_time_off')
        small_unemployement = self.env.ref('hr_work_entry.l10n_be_work_entry_type_small_unemployment')
        paternity_time_off_legal = self.env.ref('hr_work_entry.l10n_be_work_entry_type_paternity_legal')
        paternity_time_off = self.env.ref('hr_work_entry.l10n_be_work_entry_type_paternity_company')
        work_accident = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week')
        educational_time_off = self.env.ref('hr_work_entry.l10n_be_work_entry_type_training_time_off')
        training = self.env.ref('hr_work_entry.l10n_be_work_entry_type_training')
        maternity_time_off = self.env.ref('hr_work_entry.l10n_be_work_entry_type_maternity')
        paid_time_off = self.env.ref('hr_work_entry.be_work_entry_type_legal_leave')

        (
            public_holiday +
            recovery_public_holiday +
            small_unemployement +
            paternity_time_off_legal +
            paternity_time_off +
            work_accident +
            educational_time_off +
            training +
            maternity_time_off +
            paid_time_off
        ).with_context(install_mode=True).requires_allocation = False

        self.env['hr.leave'].create([
            {
                'name': 'Public Holiday work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': public_holiday.id,
                'date_from': datetime(2019, 1, 1, 1, 0, 0),
                'date_to': datetime(2019, 1, 1, 23, 0, 0),
                'request_date_from': datetime(2019, 1, 1, 1, 0, 0),
                'request_date_to': datetime(2019, 1, 1, 23, 0, 0),
                'number_of_days': 1,
            },
            {
                'name': 'Public Holiday Recovery work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': recovery_public_holiday.id,
                'date_from': datetime(2019, 2, 1, 1, 0, 0),
                'date_to': datetime(2019, 2, 1, 23, 0, 0),
                'request_date_from': datetime(2019, 2, 1, 1, 0, 0),
                'request_date_to': datetime(2019, 2, 1, 23, 0, 0),
                'number_of_days': 1,
            },
            {
                'name': 'Small Unemployement work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': small_unemployement.id,
                'date_from': datetime(2019, 3, 1, 1, 0, 0),
                'date_to': datetime(2019, 3, 1, 23, 0, 0),
                'request_date_from': datetime(2019, 3, 1, 1, 0, 0),
                'request_date_to': datetime(2019, 3, 1, 23, 0, 0),
                'number_of_days': 1,
            },
            {
                'name': 'Paternity Time Off work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': paternity_time_off_legal.id,
                'date_from': datetime(2019, 4, 1, 1, 0, 0),
                'date_to': datetime(2019, 4, 1, 23, 0, 0),
                'request_date_from': datetime(2019, 4, 1, 1, 0, 0),
                'request_date_to': datetime(2019, 4, 1, 23, 0, 0),
                'number_of_days': 1,
            },
            {
                'name': 'Paternity Time Off work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': paternity_time_off.id,
                'date_from': datetime(2019, 4, 2, 1, 0, 0),
                'date_to': datetime(2019, 4, 2, 23, 0, 0),
                'request_date_from': datetime(2019, 4, 2, 1, 0, 0),
                'request_date_to': datetime(2019, 4, 2, 23, 0, 0),
                'number_of_days': 1,
            },
            {
                'name': 'Work Accident entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': work_accident.id,
                'date_from': datetime(2019, 5, 1, 1, 0, 0),
                'date_to': datetime(2019, 5, 1, 23, 0, 0),
                'request_date_from': datetime(2019, 5, 1, 1, 0, 0),
                'request_date_to': datetime(2019, 5, 1, 23, 0, 0),
                'number_of_days': 1,
            },
            {
                'name': 'Education time off work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': educational_time_off.id,
                'date_from': datetime(2019, 6, 3, 1, 0, 0),
                'date_to': datetime(2019, 6, 3, 23, 0, 0),
                'request_date_from': datetime(2019, 6, 3, 1, 0, 0),
                'request_date_to': datetime(2019, 6, 3, 23, 0, 0),
                'number_of_days': 1,
            },
            {
                'name': 'Training time off work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': training.id,
                'date_from': datetime(2019, 7, 1, 1, 0, 0),
                'date_to': datetime(2019, 7, 1, 23, 0, 0),
                'request_date_from': datetime(2019, 7, 1, 1, 0, 0),
                'request_date_to': datetime(2019, 7, 1, 23, 0, 0),
                'number_of_days': 1,
            },
            {
                'name': 'Maternity time off work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': maternity_time_off.id,
                'date_from': datetime(2019, 8, 1, 1, 0, 0),
                'date_to': datetime(2019, 8, 1, 23, 0, 0),
                'request_date_from': datetime(2019, 8, 1, 1, 0, 0),
                'request_date_to': datetime(2019, 8, 1, 23, 0, 0),
                'number_of_days': 1,
            },
            {
                'name': 'Paid time off work entry',
                'employee_id': self.employee.id,
                'work_entry_type_id': paid_time_off.id,
                'date_from': datetime(2019, 9, 2, 1, 0, 0),
                'date_to': datetime(2019, 9, 2, 23, 0, 0),
                'request_date_from': datetime(2019, 9, 2, 1, 0, 0),
                'request_date_to': datetime(2019, 9, 2, 23, 0, 0),
                'number_of_days': 1,
            },
        ])
        # All work entries are assimilated as work time = full wage for PFA
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage)

    def test_13th_month_full_leave(self):
        self.update_version(date(2024, 1, 1))
        all_leave_vals = [
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2024, 9, 17),
                'request_date_to': date(2024, 10, 13),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2024, 10, 14),
                'request_date_to': date(2024, 11, 30),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2024, 12, 1),
                'request_date_to': date(2025, 1, 12),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 1, 13),
                'request_date_to': date(2025, 2, 28),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 3, 1),
                'request_date_to': date(2025, 4, 13),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 4, 14),
                'request_date_to': date(2025, 6, 15),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 6, 16),
                'request_date_to': date(2025, 7, 15),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 7, 16),
                'request_date_to': date(2025, 8, 31),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 9, 1),
                'request_date_to': date(2025, 9, 30),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 10, 1),
                'request_date_to': date(2025, 11, 16),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 11, 17),
                'request_date_to': date(2025, 12, 31),
            },
        ]
        prev_leave = self.env['hr.leave']
        for leave_vals in all_leave_vals:
            prev_leave = self.env['hr.leave'].create([{
                **leave_vals,
                'l10n_be_sickness_relapse': bool(prev_leave),
                'l10n_be_sickness_relapse_origin_leave_id': prev_leave.id or False,
            }])
        self.payslip.date_from = date(2025, 12, 1)
        self.payslip.date_to = date(2025, 12, 31)
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), 0, places=2)

    def test_13th_month_maternity_leave(self):
        self.update_version(date(2025, 1, 1))
        all_leave_vals = [
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 7, 10),
                'request_date_to': date(2025, 7, 30),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 7, 31),
                'request_date_to': date(2025, 8, 6),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 8, 7),
                'request_date_to': date(2025, 8, 12),
            },
        ]
        prev_leave = self.env['hr.leave']
        for leave_vals in all_leave_vals:
            prev_leave = self.env['hr.leave'].create([{
                **leave_vals,
                'l10n_be_sickness_relapse': bool(prev_leave),
                'l10n_be_sickness_relapse_origin_leave_id': prev_leave.id or False,
            }])

        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_maternity').id,
            'request_date_from': date(2025, 8, 13),
            'request_date_to': date(2025, 11, 18),
        })

        self.env['resource.calendar.leaves'].create([{
            'name': 'Public Holiday',
            'calendar_id': self.employee.resource_calendar_id.id,
            'company_id': self.employee.company_id.id,
            'resource_id': False,
            'date_from': datetime(2025, 8, 15, 0, 0, 0),
            'date_to': datetime(2025, 8, 15, 23, 59, 59),
            'count_as': 'absence',
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday').id,
        }])

        self.payslip.date_from = date(2025, 12, 1)
        self.payslip.date_to = date(2025, 12, 31)
        # Maternity leave should count, 13th month should be 100% wage
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage, places=2)

    def test_13th_month_multiple_sick_leaves_1(self):
        self.update_version(date(2025, 1, 1), wage=4863.26)
        all_leave_vals = [
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 6, 2),
                'request_date_to': date(2025, 6, 15),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 6, 16),
                'request_date_to': date(2025, 7, 13),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 7, 14),
                'request_date_to': date(2025, 8, 10),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 10, 20),
                'request_date_to': date(2025, 10, 24),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 10, 25),
                'request_date_to': date(2025, 11, 16),
            },
        ]
        prev_leave = self.env['hr.leave']
        for leave_vals in all_leave_vals:
            prev_leave = self.env['hr.leave'].create([{
                **leave_vals,
                'l10n_be_sickness_relapse': bool(prev_leave),
                'l10n_be_sickness_relapse_origin_leave_id': prev_leave.id or False,
            }])

        self.payslip.date_from = date(2025, 12, 1)
        self.payslip.date_to = date(2025, 12, 31)
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * (9 / 12 + ((21 / 31) / 12 + (19 / 31) / 12 + (14 / 30) / 12)), places=2)

    def test_13th_month_multiple_sick_leaves_2(self):
        version = self.update_version(date(2024, 12, 9), date(2025, 3, 13), wage=1965.71)
        version.resource_calendar_id = self.calendar_part_time_20_hours_per_week

        version = self.create_version(date(2025, 3, 14), wage=4209.1)
        version.resource_calendar_id = self.calendar_40h

        all_leave_vals = [
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 2, 25),
                'request_date_to': date(2025, 2, 25),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 3, 14),
                'request_date_to': date(2025, 3, 14),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 3, 15),
                'request_date_to': date(2025, 5, 27),
            },
        ]
        prev_leave = self.env['hr.leave']
        for leave_vals in all_leave_vals:
            prev_leave = self.env['hr.leave'].create([{
                **leave_vals,
                'l10n_be_sickness_relapse': bool(prev_leave),
                'l10n_be_sickness_relapse_origin_leave_id': prev_leave.id or False,
            }])

        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_maternity').id,
            'request_date_from': date(2025, 5, 28),
            'request_date_to': date(2025, 9, 2),
        })

        self.payslip.date_from = date(2025, 12, 1)
        self.payslip.date_to = date(2025, 12, 31)
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), version.wage * (10 / 12 + ((14.5 / 30) / 12 + (4 / 31) / 12)), places=2)

    def test_13th_month_multiple_sick_leaves_3(self):
        self.update_version(date(2025, 1, 1), wage=2920.89)
        all_leave_vals = [
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 2, 21),
                'request_date_to': date(2025, 2, 21),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 3, 6),
                'request_date_to': date(2025, 4, 9),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 7, 23),
                'request_date_to': date(2025, 7, 25),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 7, 28),
                'request_date_to': date(2025, 8, 20),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 9, 25),
                'request_date_to': date(2025, 9, 26),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 11, 12),
                'request_date_to': date(2025, 11, 13),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 11, 19),
                'request_date_to': date(2025, 11, 19),
            },
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'request_date_from': date(2025, 11, 20),
                'request_date_to': date(2025, 11, 20),
            },
        ]
        prev_leave = self.env['hr.leave']
        for leave_vals in all_leave_vals:
            prev_leave = self.env['hr.leave'].create([{
                **leave_vals,
                'l10n_be_sickness_relapse': bool(prev_leave),
                'l10n_be_sickness_relapse_origin_leave_id': prev_leave.id or False,
            }])

        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_maternity').id,
            'request_date_from': date(2025, 4, 10),
            'request_date_to': date(2025, 7, 22),
        })

        self.payslip.date_from = date(2025, 12, 1)
        self.payslip.date_to = date(2025, 12, 31)
        self.assertAlmostEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage * (9 / 12 + ((28 / 31) / 12 + (28 / 30) / 12) + (26 / 30) / 12), places=2)

    def test_13th_month_forced_variable_salary(self):
        self.update_version(date(2015, 1, 1))
        forced_variable_salary_amount = 100
        self.payslip._set_input_value('VARIABLE', forced_variable_salary_amount)
        self.payslip.compute_sheet()
        self.payslip.action_validate()
        self.assertIn('VARIABLE', self.payslip.line_ids.mapped('code'), 'Forced variable salary rule is missing')
        self.assertEqual(self.payslip._get_paid_amount_13th_month(), self.version.wage + forced_variable_salary_amount, 'Forced variable salary is missing from basic wage')
