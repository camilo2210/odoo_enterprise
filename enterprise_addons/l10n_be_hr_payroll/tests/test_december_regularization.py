from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDecemberRegularization(TestPayrollCommon):

    @classmethod
    def _create_and_validate_payslip(cls, employee, version, date_from, date_to):
        """ Helper to create a payslip, compute it and validate it."""
        payslip = cls.env['hr.payslip'].create({
            'name': f"Payslip {date_from.strftime('%Y-%m')}",
            'employee_id': employee.id,
            'version_id': version.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        payslip.compute_sheet()
        payslip.action_payslip_done()
        return payslip

    @classmethod
    def _get_month_dates(cls, year, month):
        date_from = date(year, month, 1)
        date_to = date_from + relativedelta(months=1, days=-1)
        return date_from, date_to

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        be_attendance_type = cls.env.ref('hr_work_entry.be_work_entry_type_attendance')
        cls.half_time_resource_calendar = cls.env['resource.calendar'].create({
            'name': 'My Test Calendar',
            'company_id': cls.belgian_company.id,
            'hours_per_day': 4,
            'hours_per_week': 19,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': be_attendance_type.id}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': be_attendance_type.id}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': be_attendance_type.id}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': be_attendance_type.id}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 11, 'work_entry_type_id': be_attendance_type.id})
            ]
        })
        cls.paid_time_off_type = cls.env.ref('hr_work_entry.be_work_entry_type_legal_leave')
        cls.structure_holidays_n1 = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')

        """ Employee 1 data (full time -> halftime) """
        cls.employee_1 = cls.env['hr.employee'].create({
            'name': 'Test Employee 1',
            'company_id': cls.belgian_company.id,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        })
        # force the Annual CP200 sectorial bonus to 0 -> to not influence the calculation of the regularization
        cls.employee_1.version_id.l10n_be_sectorial_bonus_compensatory_amount = cls.env['hr.rule.parameter']._get_parameter_from_code(
                                                                                        'l10n_be_sectorial_bonus', date.today(),
                                                                                        ) + 100

        cls.version_2024_empl_1 = cls.employee_1.create_version({
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 3000,
            'resource_calendar_id': cls.resource_calendar.id,
        })
        cls.version_2025_empl_1 = cls.employee_1.create_version({
            'date_version': date(2025, 1, 1),
            'wage': 2000,
            'resource_calendar_id': cls.half_time_resource_calendar.id,  # 50%
        })

        cls.env['hr.leave.allocation'].create({
            'work_entry_type_id': cls.paid_time_off_type.id,
            'number_of_days': 10,
            'employee_id': cls.employee_1.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 12, 31),
        }).action_approve()

        cls.env['hr.leave'].create({
            'work_entry_type_id': cls.paid_time_off_type.id,
            'date_from': datetime(2025, 8, 4, 1, 0, 0),
            'date_to': datetime(2025, 8, 15, 23, 0, 0),
            'request_date_from': datetime(2025, 8, 4, 1, 0, 0),
            'request_date_to': datetime(2025, 8, 15, 23, 0, 0),
            'number_of_days': 10,
            'employee_id': cls.employee_1.id,
        }).action_approve()

        # Monthly payslips
        for month in range(1, 13):
            date_from, date_to = cls._get_month_dates(2024, month)
            cls._create_and_validate_payslip(
                cls.employee_1,
                cls.version_2024_empl_1,
                date_from,
                date_to
            )
        for month in range(1, 11):
            date_from, date_to = cls._get_month_dates(2025, month)
            cls._create_and_validate_payslip(
                cls.employee_1,
                cls.version_2025_empl_1,
                date_from,
                date_to
            )
        # Double Holiday payslip in June 2025
        june_double_2025_payslip_emp_1 = cls.env['hr.payslip'].create({
            'name': 'June 2025 - Double Holiday Payslip',
            'version_id': cls.version_2025_empl_1.id,
            'date_from': datetime(2025, 6, 1),
            'date_to': datetime(2025, 6, 30),
            'employee_id': cls.employee_1.id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id
        })
        june_double_2025_payslip_emp_1.compute_sheet()
        june_double_2025_payslip_emp_1.action_payslip_done()

        """ Employee 2 data (salary raise scenario) """
        cls.employee_2 = cls.env['hr.employee'].create({
            'name': 'Test Employee 2',
            'company_id': cls.belgian_company.id,
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 3000,
            'resource_calendar_id': cls.resource_calendar.id,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        })
        cls.version_2024_empl_2 = cls.employee_2.version_id
        cls.version_2025_empl_2 = cls.employee_2.create_version({
            'date_version': date(2025, 7, 1),
            'wage': 4000,
            'resource_calendar_id': cls.resource_calendar.id,
        })

        cls.env['hr.leave.allocation'].create({
            'work_entry_type_id': cls.paid_time_off_type.id,
            'number_of_days': 20,
            'employee_id': cls.employee_2.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 12, 31),
        }).action_approve()

        cls.env['hr.leave'].create([
            {
                'work_entry_type_id': cls.paid_time_off_type.id,
                'date_from': datetime(2025, 3, 4, 1, 0, 0),
                'date_to': datetime(2025, 3, 10, 23, 0, 0),
                'request_date_from': datetime(2025, 3, 4, 1, 0, 0),
                'request_date_to': datetime(2025, 3, 10, 23, 0, 0),
                'number_of_days': 5,
                'employee_id': cls.employee_2.id,
            },
            {
                'work_entry_type_id': cls.paid_time_off_type.id,
                'date_from': datetime(2025, 8, 4, 1, 0, 0),
                'date_to': datetime(2025, 8, 15, 23, 0, 0),
                'request_date_from': datetime(2025, 8, 4, 1, 0, 0),
                'request_date_to': datetime(2025, 8, 15, 23, 0, 0),
                'number_of_days': 10,
                'employee_id': cls.employee_2.id,
            },
            {
                'work_entry_type_id': cls.paid_time_off_type.id,
                'date_from': datetime(2025, 10, 4, 1, 0, 0),
                'date_to': datetime(2025, 10, 10, 23, 0, 0),
                'request_date_from': datetime(2025, 10, 4, 1, 0, 0),
                'request_date_to': datetime(2025, 10, 10, 23, 0, 0),
                'number_of_days': 5,
                'employee_id': cls.employee_2.id
            }
        ]).action_approve()

        # Monthly payslips
        for month in range(1, 13):
            date_from, date_to = cls._get_month_dates(2024, month)
            cls._create_and_validate_payslip(
                cls.employee_2,
                cls.version_2024_empl_2,
                date_from,
                date_to
            )
        for month in range(1, 7):
            date_from, date_to = cls._get_month_dates(2025, month)
            cls._create_and_validate_payslip(
                cls.employee_2,
                cls.version_2024_empl_2,
                date_from,
                date_to
            )
        for month in range(7, 11):
            date_from, date_to = cls._get_month_dates(2025, month)
            cls._create_and_validate_payslip(
                cls.employee_2,
                cls.version_2025_empl_2,
                date_from,
                date_to
            )
        # Double Holiday payslip in June 2025
        june_double_2025_payslip_emp_2 = cls.env['hr.payslip'].create({
            'name': 'June 2025 - Double Holiday Payslip',
            'version_id': cls.version_2024_empl_2.id,
            'date_from': datetime(2025, 6, 1),
            'date_to': datetime(2025, 6, 30),
            'employee_id': cls.employee_2.id,
            'struct_id': cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id
        })
        june_double_2025_payslip_emp_2.compute_sheet()
        june_double_2025_payslip_emp_2.action_payslip_done()

    @freeze_time("2025-12-20")
    def test_01_december_regularization_after_switch_from_full_time_to_half_time(self):
        """
        Scenario 1: the employee worked full time during the first year with a wage of 3000
        and switched to a 50% work regime with a wage of 2000 in the second year.
        The employee accrued 20 days of leave but, due to the 50% work schedule,
        could only take 10 days off during the second year.
        The employee should therefore receive compensation for the remaining leave days.
        If the employee has not received sufficient Double Holiday Pay (92% of the first-year remuneration),
        the missing amount should also be compensated.
        """
        self._create_and_validate_payslip(
            self.employee_1,
            self.version_2025_empl_1,
            date_from=date(2025, 11, 1),
            date_to=date(2025, 11, 30)
        )

        december_2025_payslip = self._create_and_validate_payslip(
            self.employee_1,
            self.version_2025_empl_1,
            date_from=date(2025, 12, 1),
            date_to=date(2025, 12, 31)
        )

        # 1. Check regularization in the december payslip
        simple_december_line = december_2025_payslip.line_ids.filtered(lambda l: l.code == 'SIMPLE_DECEMBER')
        double_december_basic_line = december_2025_payslip.line_ids.filtered(lambda l: l.code == 'DOUBLE_DECEMBER_BASIC')

        self.assertTrue(simple_december_line, "The December payslip should contain SIMPLE_DECEMBER.")
        self.assertTrue(double_december_basic_line, "The December payslip should contain DOUBLE_DECEMBER_BASIC.")

        self.assertAlmostEqual(simple_december_line.total, 1838.12, places=0,
                               msg="December Payslip: Simple Holiday Regularization amount mismatch")

        self.assertAlmostEqual(double_december_basic_line.total, 921.2, places=0,
                               msg="December Payslip: Double Holiday Regularization amount mismatch")

        # 2. Check that holiday regularization is not computed twice if an employee leaves in December
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee_1.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 12, 31),
            'l10n_be_notice_respect': 'without'
        })
        departure_notice._generate_termination_holidays()
        departure_payslip_n1 = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_1.id),
            ('struct_id', '=', self.structure_holidays_n1.id),
        ])
        for code in ['PAY_SIMPLE', 'PAY_DOUBLE', 'PAY_DOUBLE_COMPLEMENTARY']:
            total = sum(departure_payslip_n1.line_ids.filtered(lambda l: l.code == code).mapped('total'))
            self.assertAlmostEqual(total, 0.0, places=0, msg=f"Departure in December: {code} amount mismatch")

    @freeze_time("2025-11-01")
    def test_02_departure_holiday_attest_n1_after_switch_from_full_time_to_half_time(self):
        """ Scenario 1: check regularization in the holiday attest by departure """
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee_1.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 11, 1),
            'l10n_be_notice_respect': 'without'
        })
        departure_notice._generate_termination_holidays()

        departure_payslip_n1 = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_1.id),
            ('struct_id', '=', self.structure_holidays_n1.id),
        ])
        simple_december_line = departure_payslip_n1.line_ids.filtered(lambda l: l.code == 'PAY_SIMPLE')
        double_december_basic_line = departure_payslip_n1.line_ids.filtered(
            lambda l: l.code == 'PAY_DOUBLE')
        double_december_complementary_line = departure_payslip_n1.line_ids.filtered(
            lambda l: l.code == 'PAY_DOUBLE_COMPLEMENTARY')
        self.assertTrue(simple_december_line, "The Termination Holiday Attest N-1 payslip should contain PAY_SIMPLE.")
        self.assertTrue(double_december_basic_line, "The Termination Holiday Attest N-1 payslip should contain PAY_DOUBLE.")
        self.assertTrue(double_december_complementary_line, "The Termination Holiday Attest N-1 payslip should contain PAY_DOUBLE_COMPLEMENTARY.")
        self.assertAlmostEqual(simple_december_line.total, 1838.12, places=0,
                               msg="Departure: Simple Holiday Regularization amount mismatch")
        self.assertAlmostEqual(double_december_basic_line.total, 851.11, places=0,
                               msg="Departure: Double Holiday Regularization amount mismatch")
        self.assertAlmostEqual(double_december_complementary_line.total, 70.09, places=0,
                               msg="Departure: Double Complementary Holiday Regularization amount mismatch")

    @freeze_time("2025-12-20")
    def test_03_december_regularization_after_salary_raise(self):
        """
        Scenario 2: the employee receives Double Holiday Pay in June, gets a salary raise in July,
        and takes their main holiday in August.
        The Double Holiday Pay must be recalculated based on the August wage, and the employee should receive
        the corresponding compensation.
        """
        self._create_and_validate_payslip(
            self.employee_2,
            self.version_2025_empl_2,
            date_from=date(2025, 11, 1),
            date_to=date(2025, 11, 30)
        )
        december_2025_payslip = self._create_and_validate_payslip(
            self.employee_2,
            self.version_2025_empl_2,
            date_from=date(2025, 12, 1),
            date_to=date(2025, 12, 31)
        )

        # 1. Check regularization in the december payslip
        simple_december_line = december_2025_payslip.line_ids.filtered(lambda l: l.code == 'SIMPLE_DECEMBER')
        double_december_basic_line = december_2025_payslip.line_ids.filtered(lambda l: l.code == 'DOUBLE_DECEMBER_BASIC')

        self.assertFalse(simple_december_line, "The December payslip should not contain SIMPLE_DECEMBER.")
        self.assertTrue(double_december_basic_line, "The December payslip should contain DOUBLE_DECEMBER_BASIC.")
        self.assertAlmostEqual(double_december_basic_line.total, 920.0, places=0,
                                   msg="December Payslip: Double Holiday December amount mismatch")

        # 2. Check that holiday regularization is not computed twice if an employee leaves in December
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee_2.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 12, 31),
            'l10n_be_notice_respect': 'without'
        })
        departure_notice._generate_termination_holidays()
        departure_payslip_n1 = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_2.id),
            ('struct_id', '=', self.structure_holidays_n1.id),
        ])
        for code in ['PAY_SIMPLE', 'PAY_DOUBLE', 'PAY_DOUBLE_COMPLEMENTARY']:
            total = sum(departure_payslip_n1.line_ids.filtered(lambda l: l.code == code).mapped('total'))
            self.assertAlmostEqual(total, 0.0, places=0, msg=f"Departure in December: {code} amount mismatch")

    @freeze_time("2025-11-01")
    def test_04_departure_holiday_attest_n1_after_salary_raise(self):
        """
        Scenario 2 : check regularization in the holiday attest by departure
        """
        employee_departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee_2.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 11, 1),
            'l10n_be_notice_respect': 'without'
        })
        employee_departure._generate_termination_holidays()

        departure_payslip_n1 = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_2.id),
            ('struct_id', '=', self.structure_holidays_n1.id),
        ])

        simple_december_line = departure_payslip_n1.line_ids.filtered(lambda l: l.code == 'PAY_SIMPLE')
        double_december_basic_line = departure_payslip_n1.line_ids.filtered(
            lambda l: l.code == 'PAY_DOUBLE')
        double_december_complementary_line = departure_payslip_n1.line_ids.filtered(
            lambda l: l.code == 'PAY_DOUBLE_COMPLEMENTARY')

        self.assertAlmostEqual(simple_december_line.total, 0.0, places=0,
                               msg="Departure: Simple Holiday Regularization amount mismatch")
        self.assertAlmostEqual(double_december_basic_line.total, 850.0, places=0,
                               msg="Departure: Double Holiday Regularization amount mismatch")
        self.assertAlmostEqual(double_december_complementary_line.total, 70.0, places=0,
                               msg="Departure: Double Complementary Holiday Regularization amount mismatch")

    def test_05_fictitious_remuneration_mid_year_salary_increase(self):
        """
        Ensure that fictive remuneration for assimilated unpaid absences (N-1)
        evaluates historical wages strictly based on the absence period,
        preventing inflated bases when an employee receives a mid-year raise.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee (Fictitious Remuneration)',
            'company_id': self.belgian_company.id,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        })
        version_before_raise = employee.create_version({
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 3000,
            'resource_calendar_id': self.resource_calendar.id,
        })

        unpaid_leave_type = self.env['hr.work.entry.type'].search([('code', '=', '122.00')], limit=1)
        self.env['hr.leave'].create({
            'work_entry_type_id': unpaid_leave_type.id,
            'date_from': datetime(2024, 7, 1, 7, 0, 0),
            'date_to': datetime(2024, 7, 5, 16, 0, 0),
            'request_date_from': date(2024, 7, 1),
            'request_date_to': date(2024, 7, 5),
            'number_of_days': 5,
            'employee_id': employee.id,
        }).action_approve()

        version_after_raise = employee.create_version({
            'date_version': date(2024, 7, 15),
            'wage': 4000,
            'resource_calendar_id': self.resource_calendar.id,
        })

        self.env['hr.leave'].create({
            'work_entry_type_id': unpaid_leave_type.id,
            'date_from': datetime(2024, 7, 22, 7, 0, 0),
            'date_to': datetime(2024, 7, 26, 16, 0, 0),
            'request_date_from': date(2024, 7, 22),
            'request_date_to': date(2024, 7, 26),
            'number_of_days': 5,
            'employee_id': employee.id,
        }).action_approve()

        self._create_and_validate_payslip(employee, version_before_raise, date(2024, 7, 1), date(2024, 7, 31))

        fictitious_remuneration = employee._get_fictitious_remuneration_previous_year(date(2025, 6, 1))
        expected_fictitious_remuneration = ((5 * version_before_raise.wage) + (5 * version_after_raise.wage)) * 3 / 13 / 5

        self.assertAlmostEqual(fictitious_remuneration, expected_fictitious_remuneration, places=2,
                                msg="Fictitious remuneration did not evaluate the wages period-by-period.")

    @freeze_time("2025-12-20")
    def test_06_compute_input_line_ids_does_not_duplicate_on_recompute(self):
        """
        Calling _compute_input_line_ids() a second time must not duplicate its input lines.
        This proves the method body itself is idempotent, not the full ORM recompute path.
        """
        december_2025_payslip = self._create_and_validate_payslip(
            self.employee_1,
            self.version_2025_empl_1,
            date_from=date(2025, 12, 1),
            date_to=date(2025, 12, 31)
        )

        december_2025_payslip._compute_input_line_ids()

        simple_december_inputs = december_2025_payslip.input_line_ids.filtered(lambda l: l.code == 'SIMPLE_DECEMBER')
        double_december_basic_inputs = december_2025_payslip.input_line_ids.filtered(lambda l: l.code == 'DOUBLE_DECEMBER_BASIC')

        self.assertEqual(len(simple_december_inputs), 1,
                          "SIMPLE_DECEMBER input line should not be duplicated on recompute.")
        self.assertEqual(len(double_december_basic_inputs), 1,
                          "DOUBLE_DECEMBER_BASIC input line should not be duplicated on recompute.")
