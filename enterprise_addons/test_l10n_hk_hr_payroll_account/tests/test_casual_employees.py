# Part of Odoo. See LICENSE file for full copyright and licensing details.
import calendar
import csv
import io
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from dateutil.rrule import WEEKLY, rrule
from odoo.tests import tagged

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCasualEmployees(TestL10NHkHrPayrollAccountCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_attendance.group_hr_attendance_manager')
        cls._set_test_employee(cls._setup_employee(
            country=cls.env.ref('base.hk'),
            structure_type=cls.env.ref('l10n_hk_hr_payroll.structure_type_casual_employee_cap57'),
            resource_calendar=cls.env.ref('l10n_hk_hr_payroll.calendar_hk_casual'),
            contract_fields={
                'date_version': date(2026, 1, 5),
                'contract_date_start': date(2026, 1, 5),
                'wage_type': 'hourly',
                'hourly_wage': 112.5,
                'schedule_pay': 'weekly',
                'identification_id': 'D123456A',
                'attendance_based': True,
                'l10n_hk_mpf_scheme_id': cls.mpf_scheme.id,
                'l10n_hk_mpf_registration_status': 'next_contribution',
                'l10n_hk_mpf_contribution_start': 'at_due_date',
                'l10n_hk_mpf_scheme_join_date': date(2026, 1, 5),
            },
            employee_fields={
                'private_phone': '91234567',
                'private_email': 'd.lee@example.com',
                'private_street': "15 Queen's Road Central",
                'private_state_id': cls.env.ref('base.state_hk_hk').id,
                'birthday': date(1998, 5, 20),
                'l10n_hk_surname': 'Lee',
                'l10n_hk_given_name': 'David',
                'sex': 'male',
                'marital': 'single',
                'wage': 0.0,  # Uses hourly wage
                'employee_type_id': cls.env.ref('l10n_hk_hr_payroll.l10n_hk_contract_type_mpf_casual').id,
            },
        ))
        cls.work_entry_type_overtime = cls.env.ref('hr_work_entry.hk_work_entry_type_overtime')
        cls.work_entry_type_overtime.request_unit = 'hour'
        cls.env['hr.time.rule'].sudo().search([]).write({'active': False})
        cls.env['hr.time.rule'].sudo().create({
            'name': 'HK Daily schedule overtime',
            'working_hours_mode': 'schedule_day',
            'work_entry_type_id': cls.work_entry_type_overtime.id,
            'condition_work_entry_type_ids': [cls.env.ref('hr_work_entry.hk_work_entry_type_attendance').id],
            'country_id': cls.env.ref('base.hk').id,
        })
        cls.env.company.attendance_work_entry_type_id = cls.env.ref('hr_work_entry.hk_work_entry_type_attendance').id

    def _make_attendance(self, employee, check_in, check_out):
        """
        Helper to create attendances for the given employee, helps by managing timezones.
        :param employee: The attending employee.
        :param check_in: The check in time, in the employee TZ.
        :param check_out: The check out time, in the employee TZ.
        :return: The data dict to create the attendance.
        """
        tz = employee._get_tz()
        # Set the tz of the provided date to the employee tz, translate it to UTC, then remove the tzinfo.
        check_in = check_in.replace(tzinfo=ZoneInfo(tz)).astimezone(UTC).replace(tzinfo=None)
        check_out = check_out.replace(tzinfo=ZoneInfo(tz)).astimezone(UTC).replace(tzinfo=None)
        return {
            'employee_id': employee.id,
            'check_in': check_in,
            'check_out': check_out,
        }

    def test_first_payslip(self):
        """ Simply test to generate a payslip for our casual employee. """
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2026, 1, 5, 8), datetime(2026, 1, 5, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 6, 8), datetime(2026, 1, 6, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 7, 8), datetime(2026, 1, 7, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 8, 8), datetime(2026, 1, 8, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 9, 8), datetime(2026, 1, 9, 18)),
        ])
        payslip = self._generate_payslip(date(2026, 1, 5), date(2026, 1, 9))
        self._validate_worked_days(payslip, {
            '040.00': (0.25, 2, 225.0),
            '002.00': (4.5, 36, 4050.0),
        })
        self._validate_payslip(
            payslip,
            {
                'BASIC': 4275.0,
                '713_GROSS': 4275.0,
                'GROSS': 4275.0,
                'ERMC': -210.0,
                'EEMC': -210.0,
                'NET': 4065.0,
                'MEA': 4065.0,
            },
        )

    def test_mpf_exempt(self):
        """ Test the payslip of a casual employee exempt of mandatory contributions. """
        self.employee.l10n_hk_mpf_exempt = True
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2026, 1, 5, 8), datetime(2026, 1, 5, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 6, 8), datetime(2026, 1, 6, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 7, 8), datetime(2026, 1, 7, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 8, 8), datetime(2026, 1, 8, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 9, 8), datetime(2026, 1, 9, 18)),
        ])
        payslip = self._generate_payslip(date(2026, 1, 5), date(2026, 1, 9))
        self._validate_worked_days(payslip, {
            '040.00': (0.25, 2, 225.0),
            '002.00': (4.5, 36, 4050.0),
        })
        self._validate_payslip(
            payslip,
            {
                'BASIC': 4275.0,
                '713_GROSS': 4275.0,
                'GROSS': 4275.0,
                'NET': 4275.0,
                'MEA': 4275.0,
            },
        )

    # Note: we don't test all use cases for voluntary since the rules are the same as for general employees.

    def test_voluntary_mpf(self):
        """ Test the payslip of an employee with voluntary contributions. """
        self.employee.l10n_hk_member_class_id = self.member_class
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2026, 1, 5, 8), datetime(2026, 1, 5, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 6, 8), datetime(2026, 1, 6, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 7, 8), datetime(2026, 1, 7, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 8, 8), datetime(2026, 1, 8, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 9, 8), datetime(2026, 1, 9, 18)),
        ])
        payslip = self._generate_payslip(date(2026, 1, 5), date(2026, 1, 9))
        self._validate_worked_days(payslip, {
            '040.00': (0.25, 2, 225.0),
            '002.00': (4.5, 36, 4050.0),
        })
        self._validate_payslip(
            payslip,
            {
                'BASIC': 4275.0,
                '713_GROSS': 4275.0,
                'GROSS': 4275.0,
                'ERMC': -210.0,
                'EEMC': -210.0,
                'EEVC': -3.75,
                'ERVC': -3.75,
                'NET': 4061.25,
                'MEA': 4061.25,
            },
        )

    def test_voluntary_mpf_exempt(self):
        """ Test the payslip of an employee with voluntary contributions and exemption of mandatory contributions. """
        self.employee.l10n_hk_member_class_id = self.member_class
        self.employee.l10n_hk_mpf_exempt = True
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2026, 1, 5, 8), datetime(2026, 1, 5, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 6, 8), datetime(2026, 1, 6, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 7, 8), datetime(2026, 1, 7, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 8, 8), datetime(2026, 1, 8, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 9, 8), datetime(2026, 1, 9, 18)),
        ])
        payslip = self._generate_payslip(date(2026, 1, 5), date(2026, 1, 9))
        self._validate_worked_days(payslip, {
            '040.00': (0.25, 2, 225.0),
            '002.00': (4.5, 36, 4050.0),
        })
        self._validate_payslip(
            payslip,
            {
                'BASIC': 4275.0,
                '713_GROSS': 4275.0,
                'GROSS': 4275.0,
                'EEVC': -213.75,
                'ERVC': -213.75,
                'NET': 4061.25,
                'MEA': 4061.25,
            },
        )

    def test_age_boundary_above_65(self):
        """ Test an employee that turns 65 on the last day of the week. """
        self.employee.birthday = date(1961, 1, 9)
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2026, 1, 5, 8), datetime(2026, 1, 5, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 6, 8), datetime(2026, 1, 6, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 7, 8), datetime(2026, 1, 7, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 8, 8), datetime(2026, 1, 8, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 9, 8), datetime(2026, 1, 9, 18)),
        ])
        payslip = self._generate_payslip(date(2026, 1, 5), date(2026, 1, 9))
        self._validate_worked_days(payslip, {
            '040.00': (0.25, 2, 225.0),
            '002.00': (4.5, 36, 4050.0),
        })
        self._validate_payslip(
            payslip,
            {
                'BASIC': 4275.0,
                '713_GROSS': 4275.0,
                'GROSS': 4275.0,
                'ERMC': -160.0,
                'EEMC': -160.0,
                'NET': 4115.0,
                'MEA': 4115.0,
            },
        )

    def test_age_boundary_below_18(self):
        """ Test an employee that turns 65 on the second day of the week. """
        self.employee.birthday = date(2008, 1, 6)
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2026, 1, 5, 8), datetime(2026, 1, 5, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 6, 8), datetime(2026, 1, 6, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 7, 8), datetime(2026, 1, 7, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 8, 8), datetime(2026, 1, 8, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 9, 8), datetime(2026, 1, 9, 18)),
        ])
        payslip = self._generate_payslip(date(2026, 1, 5), date(2026, 1, 9))
        self._validate_worked_days(payslip, {
            '040.00': (0.25, 2, 225.0),
            '002.00': (4.5, 36, 4050.0),
        })
        self._validate_payslip(
            payslip,
            {
                'BASIC': 4275.0,
                '713_GROSS': 4275.0,
                'GROSS': 4275.0,
                'ERMC': -165.0,
                'EEMC': -165.0,
                'NET': 4110.0,
                'MEA': 4110.0,
            },
        )

    def test_zero_work_week(self):
        """ Test a payslip for a week when an employee didn't work. """
        payslip = self._generate_payslip(date(2026, 1, 5), date(2026, 1, 9))
        self._validate_worked_days(payslip, {})
        self._validate_payslip(
            payslip,
            {
                'BASIC': 0.0,
                '713_GROSS': 0.0,
                'GROSS': 0.0,
                'NET': 0.0,
                'MEA': 0.0,
            },
        )

    def test_cross_month_week(self):
        """ Test a payslip for a week that sits between two months, just to be safe. """
        self.employee.contract_date_start = date(2025, 12, 29)
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2025, 12, 29, 8), datetime(2025, 12, 29, 16)),
            self._make_attendance(self.employee, datetime(2025, 12, 30, 8), datetime(2025, 12, 30, 16)),
            self._make_attendance(self.employee, datetime(2025, 12, 31, 8), datetime(2025, 12, 31, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 2, 8), datetime(2026, 1, 2, 18)),
        ])
        payslip = self._generate_payslip(date(2025, 12, 29), date(2026, 1, 2))
        self._validate_worked_days(payslip, {
            '040.00': (0.25, 2, 225.0),
            '002.00': (4.5, 36, 4050.0),
        })
        self._validate_payslip(
            payslip,
            {
                'BASIC': 4275.0,
                '713_GROSS': 4275.0,
                'GROSS': 4275.0,
                'ERMC': -210.0,
                'EEMC': -210.0,
                'NET': 4065.0,
                'MEA': 4065.0,
            },
        )

    # For eMPF the only difference is the new employee declaration; which should set the employee type accordingly.

    def test_empf_report_new_casual_employee(self):
        """ Test the empf for a casual employee. They are picked up from the first month (no holiday period) and are tagged 'CEE' """
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2026, 1, 5, 8), datetime(2026, 1, 5, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 6, 8), datetime(2026, 1, 6, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 7, 8), datetime(2026, 1, 7, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 8, 8), datetime(2026, 1, 8, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 9, 8), datetime(2026, 1, 9, 18)),
        ])
        report = self._create_payrun_and_report(
            date(2026, 1, 1),
            date(2026, 1, 31),
            payrun_data={
                'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_casual_employee_salary').id,
                'date_start': date(2026, 1, 5),
                'date_end': date(2026, 1, 9),
            },
        )
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                'MT00298', '123456789012', 'MLY', '', '20260105', '20260109', '', 'CEE', 'HKID', 'D123456A', '20260105', 'N',  # General info
                '', '', '20260105', '20260109', '', '', '', '4275.0', '', '210.0', '210.0', '', '', '', '', '', '420.0',  # Contribution info
                'M', 'Lee', 'David', '', '', '20260105', '19980520', '', '', 'NEW', '', '', 'd.lee@example.com', '852', '91234567',  # New member info
                '', '', ''  # Termination info
            ]],
        )

    def test_severance_payment(self):
        """ Validate calculation of severance payment. """
        date_start = date(2026, 1, 1)
        date_end = date(2027, 12, 31)
        self.version.write({
            'date_version': date_start,
            'contract_date_start': date_start,
            "l10n_hk_member_class_id": self.member_class.id,
            'attendance_based': False,  # To avoid needing to generate attendance for each week.
        })
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date_end,
            'departure_reason_id': self.env.ref('l10n_hk_hr_payroll.hr_departure_reason_redundancy').id,
        }])

        for dt in rrule(WEEKLY, dtstart=date(2027, 12, 6), until=date(2027, 11, 30)):
            # Start on a monday, each payslip end date is the friday of the same week.
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(days=4 - calendar.weekday(dt.date().year, dt.date().month, dt.date().day)))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        payslip = self._generate_payslip(
            date_from=date(2027, 12, 1),
            date_to=date(2027, 12, 31),
        )
        result = {
            'TERMINATION_PAYMENT_POST_TRANSITION': 30000.0,
            'TERMINATION_PAYMENT': 30000.0,
        }
        self._validate_payslip(payslip, result, skip_lines=True)

    def test_commission(self):
        """ Simply test to generate a payslip for our casual employee. """
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2026, 1, 5, 8), datetime(2026, 1, 5, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 6, 8), datetime(2026, 1, 6, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 7, 8), datetime(2026, 1, 7, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 8, 8), datetime(2026, 1, 8, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 9, 8), datetime(2026, 1, 9, 18)),
        ])
        payslip = self._generate_payslip(date(2026, 1, 5), date(2026, 1, 9))
        payslip._set_input_value('COMMISSION', 600)
        payslip.compute_sheet()
        self._validate_worked_days(payslip, {
            '040.00': (0.25, 2, 225.0),
            '002.00': (4.5, 36, 4050.0),
        })
        self._validate_payslip(
            payslip,
            {
                'BASIC': 4275.0,
                '713_GROSS': 4875.0,
                'GROSS': 4875.0,
                'ERMC': -230.0,
                'EEMC': -230.0,
                'NET': 4645.0,
                'MEA': 4645.0,
                'COMMISSION': 600.0,
            },
        )

    def test_empf_exception(self):
        """ Ensure that a misconfiguration of a casual employee set to contribute at due date is properly contributing right away. """
        self.employee.write({
            'l10n_hk_member_class_id': self.member_class,
            'l10n_hk_mpf_contribution_start': 'at_due_date',
        })
        self.env['hr.attendance'].create([
            self._make_attendance(self.employee, datetime(2026, 1, 5, 8), datetime(2026, 1, 5, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 6, 8), datetime(2026, 1, 6, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 7, 8), datetime(2026, 1, 7, 16)),
            self._make_attendance(self.employee, datetime(2026, 1, 8, 8), datetime(2026, 1, 8, 12)),
            self._make_attendance(self.employee, datetime(2026, 1, 9, 8), datetime(2026, 1, 9, 18)),
        ])
        report = self._create_payrun_and_report(
            date(2026, 1, 5),
            date(2026, 1, 9),
            payrun_data={
                'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_casual_employee_salary').id,
                'date_start': date(2026, 1, 1),
                'date_end': date(2026, 1, 31),
            },
        )
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                'MT00298', '123456789012', 'MLY', '', '20260101', '20260131', '', 'CEE', 'HKID', 'D123456A', '20260105', 'N',  # General info
                '', '', '20260101', '20260131', '', '', '', '4275.0', '', '210.0', '210.0', '3.75', '', '3.75', '', '', '427.5',  # Contribution info
                'M', 'Lee', 'David', '', '', '20260105', '19980520', 'GT1', '20260105', 'NEW', '', '', 'd.lee@example.com', '852', '91234567',  # New member info
                '', '', ''  # Termination info
            ]],
        )
