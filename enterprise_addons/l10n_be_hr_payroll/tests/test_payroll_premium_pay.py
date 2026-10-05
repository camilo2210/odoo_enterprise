# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from datetime import date, datetime
from freezegun import freeze_time

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'premium_pay')
class TestPayrollPremiumPay(TestPayrollBase, TestBelgiumCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        resource_calendar = cls.env['resource.calendar'].create({
                'name': 'Test Calendar',
                'attendance_ids': [(5, 0, 0),
                    (0, 0, {'dayofweek': '0', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '1', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '2', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '3', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '4', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                ]
            })
        cls._setup_common(
            country=cls.env.ref('base.be'),
            structure=cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary'),
            structure_type=cls.env.ref('hr.structure_type_employee_cp200'),
            resource_calendar=resource_calendar,
            version_fields={
                'name': 'A',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'wage': 2500.0,
                'l10n_be_worker_code_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495').id,
            },
            tz='Europe/Brussels',
        )
        cls.employee.write({
            'l10n_be_fictive_hire_date': date(2025, 1, 1),
        })
        cls.resource_calendar = resource_calendar
        cls.attendance_type = cls.env.ref('hr_work_entry.be_work_entry_type_attendance')
        cls.night = cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_NIGHT')
        cls.premium_work_entry_type = cls.env['hr.work.entry.type'].create({
            'name': 'Premium Pay',
            'code': 'PREMIUM_PAY',
            'requires_allocation': False,
            'request_unit': 'hour',
            'unit_of_measure': 'hour',
            'category_ids': [
                Command.link(cls.env.ref('l10n_be_hr_payroll.REMUNERATION_BASE').id),
            ],
            'optional_category_ids': [
                Command.link(cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_NIGHT').id),
                Command.link(cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_SUN').id),
                Command.link(cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_HOLIDAY').id),
                Command.link(cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_TEAM').id),
                Command.link(cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_MISC').id),
                Command.link(cls.env.ref('l10n_be_hr_payroll.TEMP_UNEMP').id),
                Command.link(cls.env.ref('l10n_be_hr_payroll.FLEXIBLE_WORK_CAT2').id),
                Command.link(cls.env.ref('l10n_be_hr_payroll.FLEXIBLE_WORK_CAT34').id),
                Command.link(cls.env.ref('l10n_be_hr_payroll.FLEXIBLE_WORK_CAT5PLUS').id),
            ],
        })
        cls.premium_cold_night = cls.env['hr.salary.rule.category'].create({
            'name': 'Premium Pay Cold Night',
            'code': 'PREMIUM_PAY_COLD_NIGHT',
            'parent_id': cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_NIGHT').id,
            'country_id': cls.env.ref('base.be').id,
            'premium_amount_per_hour': 1.0,
            'optional_on_work_entry_type_ids': [Command.link(cls.premium_work_entry_type.id)],
        })
        cls.premium_team_a = cls.env['hr.salary.rule.category'].create({
            'name': 'Premium Pay Team - Equipe A',
            'code': 'PREMIUM_PAY_TEAM_A',
            'parent_id': cls.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_TEAM').id,
            'country_id': cls.env.ref('base.be').id,
            'premium_amount_per_day': 10.5,
            'premium_percentage_hourly_rate': 2.0,
            'optional_on_work_entry_type_ids': [Command.link(cls.premium_work_entry_type.id)],
        })

    @freeze_time('2025-01-01')
    def test_premium_pay_whole_flow(self):
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.premium_work_entry_type.id,
            'request_date_from': date(2025, 1, 7),
            'request_date_to': date(2025, 1, 7),
            'request_hour_from': 10,
            'request_hour_to': 14,
            'category_options_ids': [
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_NIGHT').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_SUN').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_HOLIDAY').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_TEAM').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_MISC').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.TEMP_UNEMP').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.FLEXIBLE_WORK_CAT2').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.FLEXIBLE_WORK_CAT34').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.FLEXIBLE_WORK_CAT5PLUS').id),
            ],
        })

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'PREMNIGHT': 6.34, 'PREMSUN': 8.0, 'PREMHOL': 8.0, 'PREMTEAM': 1.14, 'PREMMISC': 8.0, 'TEMPUNEMP': 2.0, 'FLEXCAT2': 0.7, 'FLEXCAT34': 1.08, 'FLEXCAT5PLUS': 1.27, 'BASIC': 2536.53}
        self.assertAlmostEqual(sum(payslip.worked_days_line_ids.mapped('number_of_days')), 23, 5)
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    @freeze_time('2025-01-01')
    def test_premium_pay_cap_amount(self):
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.premium_work_entry_type.id,
            'request_date_from': date(2025, 1, 7),
            'request_date_to': date(2025, 1, 7),
            'request_hour_from': 9,
            'request_hour_to': 16,
            'category_options_ids': [
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_SUN').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_HOLIDAY').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.TEMP_UNEMP').id),
            ],
        })

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'PREMSUN': 12, 'PREMHOL': 12, 'TEMPUNEMP': 2}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    @freeze_time('2025-01-01')
    def test_premium_pay_half_day_attendance(self):
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.premium_work_entry_type.id,
            'request_date_from': date(2025, 1, 7),
            'request_date_to': date(2025, 1, 7),
            'request_duration': 'am',
            'category_options_ids': [
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_SUN').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_HOLIDAY').id),
                Command.link(self.env.ref('l10n_be_hr_payroll.TEMP_UNEMP').id),
            ],
        })

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'PREMSUN': 7.6, 'PREMHOL': 7.6, 'TEMPUNEMP': 1.97}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    @freeze_time('2025-01-01')
    def test_premium_pay_custom_child_with_parent(self):
        # A custom premium pay on the worked time adds its own amounts on top of the legal rate
        # of its parent, summed on the same payslip line. The hours are credited to the parent
        # only once even though both the parent and the child options are on the leave.
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.premium_work_entry_type.id,
            'request_date_from': date(2025, 1, 7),
            'request_date_to': date(2025, 1, 7),
            'request_hour_from': 10,
            'request_hour_to': 14,
            'category_options_ids': [
                Command.link(self.env.ref('l10n_be_hr_payroll.PREMIUM_PAY_NIGHT').id),
                Command.link(self.premium_cold_night.id),
            ],
        })

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        # 4 hours x (1.5862 legal + 1.0 custom)
        self._validate_payslip(payslip, {'PREMNIGHT': 10.34}, skip_lines=True)

    @freeze_time('2025-01-01')
    def test_premium_pay_custom_child_without_parent(self):
        # A custom premium pay cannot be computed without its parent: hours carrying only the
        # child option also get the parent legal rate, as if the parent option was present.
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.premium_work_entry_type.id,
            'request_date_from': date(2025, 1, 7),
            'request_date_to': date(2025, 1, 7),
            'request_hour_from': 10,
            'request_hour_to': 14,
            'category_options_ids': [Command.link(self.premium_cold_night.id)],
        })

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        # Same result as with the parent option explicitly present
        self._validate_payslip(payslip, {'PREMNIGHT': 10.34}, skip_lines=True)

    @freeze_time('2025-01-01')
    def test_premium_pay_custom_child_per_day_and_percentage(self):
        # Custom premium pays can grant a fixed amount per day and a percentage of the worked
        # day own hourly rate, on top of the legal rate of their parent.
        self.employee.resource_calendar_id.write({'hours_per_day': 8, 'hours_per_week': 40})
        for attendance in self.employee.resource_calendar_id.attendance_ids:
            attendance.write({'duration_hours': 8})
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.premium_work_entry_type.id,
            'request_date_from': date(2025, 1, 7),
            'request_date_to': date(2025, 1, 7),
            'request_hour_from': 13,
            'request_hour_to': 17,
            'category_options_ids': [Command.link(self.premium_team_a.id)],
        })

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        worked_days = payslip.worked_days_line_ids.filtered('code')
        average_hourly_wage = sum(worked_days.mapped('amount')) / sum(worked_days.mapped('number_of_hours'))
        premium_line = payslip.worked_days_line_ids.filtered('category_options_ids')
        team_rate_percentage = payslip._rule_parameter('cp_200_premium_pay_team_hourly_rate')
        # legal % on 4 hours + custom 2% of the worked day line own rate + 10.5€ prorated to its days
        expected = team_rate_percentage / 100 * average_hourly_wage * 4 \
            + 2.0 / 100 * premium_line.amount + 10.5 * premium_line.number_of_days
        self._validate_payslip(payslip, {'PREMTEAM': expected}, skip_lines=True)

    def _worked_days_totals(self, payslip):
        lines = payslip.worked_days_line_ids
        return sum(lines.mapped('number_of_hours')), sum(lines.mapped('number_of_days'))

    @freeze_time('2025-01-01')
    def test_worked_days_partly_optioned_day_still_counts_as_one(self):
        """A day where only part of the attendances carry an option is still a full worked day."""
        baseline = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        _baseline_hours, baseline_days = self._worked_days_totals(baseline)

        # Tuesdays become 5.6h of plain attendance plus 2h carrying the night option.
        tuesdays = self.resource_calendar.attendance_ids.filtered(lambda a: a.dayofweek == '1')
        tuesdays.sudo().duration_hours = 5.6
        self.env['resource.calendar.attendance'].sudo().create({
            'calendar_id': self.resource_calendar.id,
            'dayofweek': '1',
            'duration_hours': 2,
            'hour_from': 0,
            'hour_to': 0,
            'category_options_ids': [Command.set(self.night.ids)],
        })

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        self.assertTrue(payslip.worked_days_line_ids.filtered(
            lambda line: self.night in line.category_options_ids))
        _hours, days = self._worked_days_totals(payslip)
        self.assertAlmostEqual(days, baseline_days, 2)

    def test_worked_day_split_across_working_time_types(self):
        shift_type = self.attendance_type.copy({'name': 'Night Shift', 'code': 'NIGHT_SHIFT'})
        monday = self.resource_calendar.attendance_ids.filtered(lambda attendance: attendance.dayofweek == '0')
        monday.write({'duration_hours': 6, 'hour_from': 8, 'hour_to': 14})
        monday.copy({
            'duration_hours': 2,
            'hour_from': 14,
            'hour_to': 16,
            'work_entry_type_id': shift_type.id,
            'category_options_ids': [Command.set(self.night.ids)],
        })
        day = date(2025, 1, 6)
        payslip = self._generate_payslip(day, day)
        lines = payslip.worked_days_line_ids
        plain_line = lines.filtered(lambda line: line.work_entry_type_id == self.attendance_type)
        night_line = lines.filtered(lambda line: line.work_entry_type_id == shift_type)

        self.assertAlmostEqual(sum(lines.mapped('number_of_hours')), 8)
        self.assertAlmostEqual(sum(lines.mapped('number_of_days')), 1)
        self.assertEqual(plain_line.number_of_hours, 6)
        self.assertFalse(plain_line.category_options_ids)
        self.assertEqual(night_line.number_of_hours, 2)
        self.assertEqual(night_line.category_options_ids, self.night)

    @freeze_time('2025-01-01')
    def test_worked_days_split_by_option(self):
        """Attendance time carrying an option gets its own worked days line."""
        baseline = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        baseline_hours, baseline_days = self._worked_days_totals(baseline)

        tuesdays = self.resource_calendar.attendance_ids.filtered(lambda a: a.dayofweek == '1')
        tuesdays.sudo().category_options_ids = [Command.set(self.night.ids)]

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        night_lines = payslip.worked_days_line_ids.filtered(
            lambda line: self.night in line.category_options_ids)
        plain_lines = payslip.worked_days_line_ids - night_lines

        # The night time is reported apart from the rest of the attendances.
        self.assertEqual(len(night_lines), 1)
        self.assertTrue(plain_lines)
        self.assertFalse(plain_lines.category_options_ids)
        self.assertEqual(night_lines.work_entry_type_id, self.attendance_type)
        self.assertAlmostEqual(night_lines.number_of_hours, 4 * 7.6, 2, "The 4 tuesdays of January 2025")

        # Splitting the lines reports the same time differently, it does not create any.
        hours, days = self._worked_days_totals(payslip)
        self.assertAlmostEqual(hours, baseline_hours, 2)
        self.assertAlmostEqual(days, baseline_days, 2)

        # The options are named in the description, and the categories are readable on the line.
        self.assertTrue(night_lines.name.endswith('(%s)' % self.night.name))
        self.assertFalse(plain_lines.filtered(lambda line: self.night.name in line.name))
        self.assertEqual(night_lines.category_ids, self.attendance_type.category_ids)
        self.assertTrue(night_lines.category_ids)

        # The lines can be grouped by option in the worked days report.
        groups = self.env['hr.payslip.worked_days']._read_group(
            [('payslip_id', '=', payslip.id)],
            groupby=['category_options_ids'],
            aggregates=['number_of_hours:sum'])
        self.assertAlmostEqual(dict(groups)[self.night], night_lines.number_of_hours, 2)

    @freeze_time('2025-01-01')
    def test_adhoc_night_hours_preserve_regular_attendance(self):
        """Recording a night shift preserves the hours of the scheduled attendance."""
        baseline = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        baseline_hours, _baseline_days = self._worked_days_totals(baseline)
        self.assertFalse(self.attendance_type.is_extra_hours)

        # 20:00 to 22:00 in Europe/Brussels, the employee is not supposed to work then.
        self.env['resource.calendar.leaves'].sudo().create({
            'name': 'Night shift',
            'calendar_id': self.resource_calendar.id,
            'resource_id': self.employee.resource_id.id,
            'company_id': self.env.company.id,
            'date_from': datetime(2025, 1, 7, 19, 0),
            'date_to': datetime(2025, 1, 7, 21, 0),
            'work_entry_type_id': self.attendance_type.id,
            'count_as': 'working_time',
            'category_options_ids': [Command.set(self.night.ids)],
        })

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        night_lines = payslip.worked_days_line_ids.filtered(
            lambda line: self.night in line.category_options_ids)
        plain_lines = payslip.worked_days_line_ids - night_lines

        self.assertAlmostEqual(night_lines.number_of_hours, 2, 2)
        self.assertAlmostEqual(sum(plain_lines.mapped('number_of_hours')), baseline_hours, 2)
        self.assertAlmostEqual(self._worked_days_totals(payslip)[0], baseline_hours + 2, 2)
        self.assertTrue(payslip._get_line_values(['PREMNIGHT'])['PREMNIGHT'][payslip.id]['total'] > 0)

    @freeze_time('2025-01-01')
    def test_attendance_encoded_from_the_payslip_calendar(self):
        """Attendance time can be encoded as a time entry, with its options, from the payslip calendar."""
        # The payroll time entry gantt narrows the time types to the ones of the company country.
        # It drops the time off selectable and allocation clauses that the employee facing form applies.
        leave_form = self.env['hr.leave'].sudo().new({'employee_id': self.employee.id})
        self.assertIn(self.attendance_type, leave_form.allowed_work_entry_type_ids._origin,
                      "HR must be offered the attendance type when encoding a time entry")

        baseline = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        baseline_hours, _baseline_days = self._worked_days_totals(baseline)

        # 20:00 to 22:00 in Europe/Brussels, outside of the working schedule.
        leave = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.attendance_type.id,
            'request_date_from': date(2025, 1, 7),
            'request_date_to': date(2025, 1, 7),
            'request_hour_from': 20,
            'request_hour_to': 22,
            'category_options_ids': [Command.set(self.night.ids)],
        })
        if leave.state != 'validate':
            leave.action_approve()
        self.assertAlmostEqual(leave.number_of_hours, 2, 2, "The encoded hours are kept as such")

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        night_lines = payslip.worked_days_line_ids.filtered(
            lambda line: self.night in line.category_options_ids)
        plain_lines = payslip.worked_days_line_ids - night_lines

        self.assertAlmostEqual(night_lines.number_of_hours, 2, 2)
        self.assertAlmostEqual(sum(plain_lines.mapped('number_of_hours')), baseline_hours, 2)
        self.assertAlmostEqual(self._worked_days_totals(payslip)[0], baseline_hours + 2, 2)
        self.assertTrue(payslip._get_line_values(['PREMNIGHT'])['PREMNIGHT'][payslip.id]['total'] > 0)

    def test_payroll_gantt_is_isolated_from_the_time_off_one(self):
        """The wider list of time types reaches the payslip calendar and nothing else."""
        payroll_gantt = self.env.ref('hr_payroll.hr_leave_gantt_view_payroll_encoding')
        payroll_form = self.env.ref('hr_payroll.hr_leave_view_form_payroll_encoding')
        regular_gantt = self.env.ref('hr_holidays_gantt.hr_leave_gantt_view')

        # The payslip calendar routes to the payroll gantt, which opens the payroll form.
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        views = {view_type: view_id for view_id, view_type in payslip.action_open_employee_calendar()['views']}
        self.assertEqual(views['gantt'], payroll_gantt.id)
        payroll_arch = self.env['hr.leave'].get_view(payroll_gantt.id, 'gantt')['arch']
        self.assertIn('form_view_id="%s"' % payroll_form.id, payroll_arch)
        self.assertIn('hr_leave_gantt_multi_create_view_payroll', payroll_arch)

        # The gantt of the time off app keeps the employee facing views.
        regular_arch = self.env['hr.leave'].get_view(regular_gantt.id, 'gantt')['arch']
        self.assertNotIn('form_view_id', regular_arch)
        self.assertNotIn('multi_create_view_payroll', regular_arch)

        # The payroll form is never the one odoo falls back on for a time off.
        self.assertNotEqual(self.env['ir.ui.view'].sudo().default_view('hr.leave', 'form'), payroll_form.id)
        # It keeps what the manager form brings, the payslip state of the leave included.
        manager_fields = self._form_field_names(self.env.ref('hr_holidays.hr_leave_view_form_manager'))
        self.assertFalse(manager_fields - self._form_field_names(payroll_form))

    def _form_field_names(self, view):
        arch = self.env['hr.leave'].get_view(view.id, 'form')['arch']
        return set(re.findall(r'<field name="([^"]+)"', arch))

    def test_sickness_relapse_is_dropped_when_the_type_changes(self):
        """A leave turned into an attendance must not stay flagged as a sickness relapse."""
        sick = self.env['hr.work.entry.type'].search([
            ('code', '=', '013.00'), ('country_id', '=', self.env.ref('base.be').id)], limit=1)
        origin = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 1, 6), 'request_date_to': date(2025, 1, 6)})
        if origin.state != 'validate':
            origin.action_validate()
        relapse = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 1, 7), 'request_date_to': date(2025, 1, 7)})
        self.assertEqual(relapse.l10n_be_sickness_relapse_origin_leave_id, origin)
        self.assertTrue(relapse.l10n_be_sickness_relapse)

        relapse.sudo().write({'state': 'confirm'})
        relapse.sudo().write({'work_entry_type_id': self.attendance_type.id})
        relapse.invalidate_recordset()
        self.assertFalse(relapse.l10n_be_sickness_relapse_origin_leave_id,
                         "The origin is dropped in database, not only in cache")
        self.assertFalse(relapse.l10n_be_sickness_relapse)
        self.assertFalse(relapse.l10n_be_sickness_can_relapse)

        # Going back to a sickness detects the consecutive days again.
        relapse.sudo().write({'work_entry_type_id': sick.id})
        relapse.invalidate_recordset()
        self.assertTrue(relapse.l10n_be_sickness_can_relapse)
        self.assertEqual(relapse.l10n_be_sickness_relapse_origin_leave_id, origin)

    def test_sickness_relapse_origin_survives_a_split_bucket_code_change(self):
        """A leave moved between two relapse-eligible sickness codes keeps its origin.

        010.00/082.00/072.00/082.01/072.01 are relapse-eligible per `sick_work_entry_types_codes`, alongside 013.00/122.00/123.00.
        So moving between them must not drop the origin leave, unlike moving to an outright attendance.
        """
        sick = self.env['hr.work.entry.type'].search([
            ('code', '=', '013.00'), ('country_id', '=', self.env.ref('base.be').id)], limit=1)
        leave264 = self.env['hr.work.entry.type'].search([
            ('code', '=', '010.00'), ('country_id', '=', self.env.ref('base.be').id)], limit=1)
        origin = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 3, 3), 'request_date_to': date(2025, 3, 3)})
        if origin.state != 'validate':
            origin.action_validate()
        relapse = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 3, 4), 'request_date_to': date(2025, 3, 4)})
        self.assertEqual(relapse.l10n_be_sickness_relapse_origin_leave_id, origin)

        relapse.sudo().write({'state': 'confirm'})
        relapse.sudo().write({'work_entry_type_id': leave264.id})
        relapse.invalidate_recordset()
        self.assertEqual(relapse.l10n_be_sickness_relapse_origin_leave_id, origin,
                         "A split-bucket sickness code still chains to its relapse origin")

    def test_sickness_relapse_origin_survives_a_relapse_gap(self):
        """A manually linked origin outside the immediate relapse window is kept.

        The field's domain allows any leave within the relapse period, not only the one ending the day before.
        So a leave can be linked to a gapped origin.
        A later write on an unrelated dependency, such as the work entry type when a leave moves between split-bucket sickness codes, must not silently drop that link just because there is no immediate day-before match.
        """
        sick = self.env['hr.work.entry.type'].search([
            ('code', '=', '013.00'), ('country_id', '=', self.env.ref('base.be').id)], limit=1)
        leave264 = self.env['hr.work.entry.type'].search([
            ('code', '=', '010.00'), ('country_id', '=', self.env.ref('base.be').id)], limit=1)
        origin = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 4, 1), 'request_date_to': date(2025, 4, 1)})
        if origin.state != 'validate':
            origin.action_validate()
        relapse = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 4, 4), 'request_date_to': date(2025, 4, 4),
            'l10n_be_sickness_relapse_origin_leave_id': origin.id})
        if relapse.state != 'validate':
            relapse.action_validate()
        self.assertIn(origin, relapse.allowed_l10n_be_sickness_relapse_origin_leave_ids,
                      "The gapped leave is still a valid relapse candidate")
        self.assertEqual(relapse.l10n_be_sickness_relapse_origin_leave_id, origin)

        relapse.sudo().write({'state': 'confirm'})
        relapse.sudo().write({'work_entry_type_id': leave264.id})
        relapse.invalidate_recordset()
        self.assertEqual(relapse.l10n_be_sickness_relapse_origin_leave_id, origin,
                         "A manually-linked gap origin is not dropped by an unrelated dependency change")

    def test_sickness_relapse_origin_is_resolved_without_reading_can_relapse_first(self):
        """The origin leave is a real stored value, resolved on its own.

        It must not depend on some other caller having read `l10n_be_sickness_can_relapse` first to trigger its computation.
        """
        sick = self.env['hr.work.entry.type'].search([
            ('code', '=', '013.00'), ('country_id', '=', self.env.ref('base.be').id)], limit=1)
        origin = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 2, 3), 'request_date_to': date(2025, 2, 3)})
        if origin.state != 'validate':
            origin.action_validate()
        relapse = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 2, 4), 'request_date_to': date(2025, 2, 4)})

        # Drop every cached value, including any the create() call happened to prime.
        # Then read the origin straight away, without ever touching l10n_be_sickness_can_relapse first as the rest of this file does.
        relapse.invalidate_recordset()
        self.assertEqual(relapse.l10n_be_sickness_relapse_origin_leave_id, origin,
                         "The origin leave is resolved on its own, not as a side effect of some other field's compute happening to run first.")

        # It is genuinely persisted, not merely recomputed into a non-stored cache.
        # Flushed explicitly: raw SQL bypasses the ORM's own flush-before-read hook.
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT l10n_be_sickness_relapse_origin_leave_id FROM hr_leave WHERE id = %s", (relapse.id,))
        self.assertEqual(self.env.cr.fetchone()[0], origin.id)

    def test_sickness_relapse_recovers_after_origin_validation(self):
        sick = self.env['hr.work.entry.type'].search([
            ('code', '=', '013.00'), ('country_id', '=', self.env.ref('base.be').id)], limit=1)
        origin = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 1, 6), 'request_date_to': date(2025, 1, 6),
            'state': 'confirm',
        })
        origin.write({'state': 'confirm'})
        self.assertEqual(origin.state, 'confirm')
        relapse = self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id, 'work_entry_type_id': sick.id,
            'request_date_from': date(2025, 1, 7), 'request_date_to': date(2025, 1, 7),
            'state': 'confirm',
        })
        self.env.flush_all()
        self.assertFalse(relapse.l10n_be_sickness_relapse_origin_leave_id)
        origin.action_approve()
        self.env.invalidate_all()
        self.assertTrue(relapse.l10n_be_sickness_can_relapse)
        self.assertIn(origin, relapse.allowed_l10n_be_sickness_relapse_origin_leave_ids)
        self.assertEqual(relapse.l10n_be_sickness_relapse_origin_leave_id, origin)
        relapse.flush_recordset()
        relapse.invalidate_recordset()
        self.assertEqual(relapse.l10n_be_sickness_relapse_origin_leave_id, origin)
