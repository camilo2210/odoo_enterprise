# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from odoo.tests.common import tagged

from odoo.addons.hr_payroll.tests.common import TestPayslipBase


@tagged('post_install', '-at_install')
class TestVariableSchedule(TestPayslipBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.variable_calendar = cls.env['resource.calendar'].create({
            'name': 'Variable Calendar',
            'hours_per_day': 8,
            'days_per_week': 5,
            'hours_per_week': 40,
            'full_time_required_hours': 40,
            'calendar_type': 'variable',
            'attendance_ids': (
                # January 2026 till February 2026 first half: Mon-Fri 8h (Jan 1 = Thu, offsets [0,1,4,5,6] = Thu-Wed)
                [(0, 0, {'date': date(2026, 1, 1) + timedelta(days=d), 'hour_from': 8, 'hour_to': 16,
                         'recurrency': True, 'recurrency_interval': 1, 'recurrency_type': 'weeks',
                         'recurrency_end_type': 'date', 'recurrency_until': date(2026, 2, 14)})
                 for d in [0, 1, 4, 5, 6]] +
                # February 2026 second half (Feb 15-28): Mon-Fri 4h (Feb 16 = Mon)
                [(0, 0, {'date': date(2026, 2, 16) + timedelta(days=i), 'hour_from': 8, 'hour_to': 12,
                         'recurrency': True, 'recurrency_interval': 1, 'recurrency_type': 'weeks',
                         'recurrency_end_type': 'date', 'recurrency_until': date(2026, 2, 28)})
                 for i in range(5)] +
                # March 2026: every 4 days from Mar 1 (Sun)
                [(0, 0, {'date': date(2026, 3, 1), 'hour_from': 8, 'hour_to': 16,
                         'recurrency': True, 'recurrency_interval': 4, 'recurrency_type': 'days',
                         'recurrency_end_type': 'date', 'recurrency_until': date(2026, 3, 31)})]
            ),
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Little Frog',
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'resource_calendar_id': cls.variable_calendar.id,
            'structure_type_id': cls.structure_type.id,
            'wage': 5000,
        })

    def test_variable_full_time_payslip(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
            'struct_id': self.developer_pay_structure.id,
        })
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 176.0, places=2)
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 22)

    def test_variable_full_time_then_half_time(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 2, 1),
            'date_to': date(2026, 2, 28),
            'struct_id': self.developer_pay_structure.id,
        })
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 120.0, places=2)
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 15)  # (10 full-time) + (10/2 half-time days)

    def test_variable_every_4_days(self):
        # Mar 1, 5, 9, 13, 17, 21, 25, 29 = 8 occurrences * 8h = 64h.
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
            'struct_id': self.developer_pay_structure.id,
        })
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 64.0, places=2)
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 8)

    def test_variable_empty_period(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2025, 12, 1),
            'date_to': date(2025, 12, 31),
            'struct_id': self.developer_pay_structure.id,
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 0)
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 0)
