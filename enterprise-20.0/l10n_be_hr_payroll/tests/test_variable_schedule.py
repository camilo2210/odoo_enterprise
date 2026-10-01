# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestVariableSchedule(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.variable_calendar = cls.env['resource.calendar'].create({
            'name': 'Variable Calendar',
            'calendar_type': 'variable',
            'days_per_week': 5.0,
            'hours_per_week': 38.0,
            'full_time_required_hours': 38,
            'attendance_ids': [(0, 0, {
                'date': date(1, 1, 1) + timedelta(days=i),
                'hour_from': 8,
                'hour_to': 15.6,
                'recurrency': True,
                'recurrency_interval': 1,
                'recurrency_type': 'weeks',
            }) for i in range(5)],
        })

        cls.employee = cls.create_employee({
            'name': 'Variable Schedule Employee',
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'resource_calendar_id': cls.variable_calendar.id,
        })

    def test_variable_matches_fixed(self):
        emp_fixed = self.create_employee({
            'name': 'Fixed Schedule Employee',
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
        })

        payslip_fixed, payslip_variable = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2024',
            'employee_id': emp_fixed.id,
            'version_id': emp_fixed.version_id.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        }, {
            'name': 'Payslip Jan 2024',
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        }])

        days_fixed = payslip_fixed.worked_days_line_ids.mapped('number_of_days')
        hours_fixed = payslip_fixed.worked_days_line_ids.mapped('number_of_hours')

        days_variable = payslip_variable.worked_days_line_ids.mapped('number_of_days')
        hours_variable = payslip_variable.worked_days_line_ids.mapped('number_of_hours')

        self.assertEqual(days_fixed, days_variable, "Variable and Fixed payslips should have the same value")
        self.assertEqual(hours_fixed, hours_variable, "Variable and Fixed payslips should have the same value")

        payslip_fixed.compute_sheet()
        payslip_variable.compute_sheet()

        fixed_totals = {l.code: l.total for l in payslip_fixed.line_ids}
        variable_totals = {l.code: l.total for l in payslip_variable.line_ids}
        self.assertDictEqual(fixed_totals, variable_totals)

    def test_biweekly_recurrence(self):
        calendar = self.variable_calendar.copy({
            'days_per_week': 2.5,
            'hours_per_week': 19.0,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'date': date(2025, 1, 6) + timedelta(days=i), 'hour_from': 8, 'hour_to': 15.6,
                        'recurrency': True, 'recurrency_interval': 2, 'recurrency_type': 'weeks'})
                for i in range(5)
            ],
        })
        self.employee.version_id.resource_calendar_id = calendar
        version = self.employee.version_id
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': version.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
        })
        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 10)
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 76.0, places=2)

    def test_mixed_fixed_and_variable_calendar(self):
        self.employee.create_version({
            'date_version': date(2024, 4, 16),
            'resource_calendar_id': self.resource_calendar.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2024, 4, 1),
            'date_to': date(2024, 4, 30),
        })

        work_lines = payslip.worked_days_line_ids
        self.assertEqual(sum(work_lines.mapped('number_of_days')), 22)
        self.assertAlmostEqual(sum(work_lines.mapped('number_of_hours')), 167.2, places=2)

    def test_hours_per_week_helper_variable_calendar(self):
        """_l10n_be_get_hours_per_week must be safe for variable calendars, which
        store 0 in hours_per_week unless it was set explicitly."""
        version = self.employee.version_id

        # Stored weekly hours (38) are used as-is.
        self.assertAlmostEqual(version._l10n_be_get_hours_per_week(2024), 38.0, places=2)

        # Without stored weekly hours the value is reconstructed from attendances
        # (5 days/week * 7.6h ≈ 38h) instead of dividing by zero.
        calendar_no_hours = self.variable_calendar.copy({'hours_per_week': 0.0, 'days_per_week': 0.0})
        version.resource_calendar_id = calendar_no_hours
        self.assertAlmostEqual(
            version._l10n_be_get_hours_per_week(2024), 38.0, delta=1.5,
            msg="A variable calendar without stored hours should be averaged from its attendances",
        )

    def test_daily_wage_variable_calendar_without_days(self):
        """_compute_daily_wage must not divide by zero when the calendar stores 0
        days_per_week (variable calendars); it falls back to the reference calendar."""
        calendar_no_days = self.variable_calendar.copy({'hours_per_week': 0.0, 'days_per_week': 0.0})
        version = self.employee.version_id
        version.resource_calendar_id = calendar_no_days
        self.assertGreater(
            version.l10n_be_daily_wage, 0,
            "Daily wage should fall back to the reference calendar instead of raising ZeroDivisionError",
        )

    def test_recurrence_ends_mid_month(self):
        self.variable_calendar.attendance_ids.write({
            'recurrency_end_type': 'date',
            'recurrency_until': date(2024, 1, 17),
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        })

        self.assertEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 13)
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_hours')), 98.8, places=2)
