# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.addons.test_l10n_ph_hr_payroll_account.tests.common import TestL10NPhHrPayrollCommon

from odoo.exceptions import UserError
from odoo.tests.common import tagged
from freezegun import freeze_time


@tagged("post_install", "post_install_l10n", "-at_install", "payslips_validation")
class TestSSSContribution(TestL10NPhHrPayrollCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({
            'l10n_ph_hr_payroll_sss_number': '03-1234567-8',
            'l10n_ph_hr_payroll_sss_branch_code': '1',
        })

        # A regular employee, employed well before the period.
        cls.regular_employee = cls._setup_employee(
            country=cls.country,
            structure_type=cls.structure_type,
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2021, 1, 1),
                'contract_date_start': date(2021, 1, 1),
                'wage': 30000.0,
            },
            employee_fields={
                'name': 'Jennifer Beatriz Hidalgo',
                'l10n_ph_hr_payroll_sss_number': '01-2345678-9',
            },
        )
        # An employee hired during the period.
        cls.new_employee = cls._setup_employee(
            country=cls.country,
            structure_type=cls.structure_type,
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2026, 6, 16),
                'contract_date_start': date(2026, 6, 16),
                'wage': 20000.0,
                'job_title': 'Programmer',
            },
            employee_fields={
                'name': 'Jerrom Gabriel Andrada Jr.',
                'l10n_ph_hr_payroll_sss_number': '02-1234867-8',
            },
        )
        # An employee leaving during the period.
        cls.departing_employee = cls._setup_employee(
            country=cls.country,
            structure_type=cls.structure_type,
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2021, 1, 1),
                'contract_date_start': date(2021, 1, 1),
                'wage': 25000.0,
            },
            employee_fields={
                'name': 'Beulah Grace Chopitea',
                'l10n_ph_hr_payroll_sss_number': '03-1233355-6',
            },
        )
        # An employee that did not earn anything over the period.
        cls.no_earnings_employee = cls._setup_employee(
            country=cls.country,
            structure_type=cls.structure_type,
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2021, 1, 1),
                'contract_date_start': date(2021, 1, 1),
                'wage': 0.0,
            },
            employee_fields={
                'name': 'Gaudencio Galvan',
                'l10n_ph_hr_payroll_sss_number': '04-1233555-5',
            },
        )

    def _generate_june_payslips(self):
        """ Generate and validate the June 2026 payslip of every employee. """
        self.env['hr.employee.departure'].create([{
            'employee_id': self.departing_employee.id,
            'dismissal_date': date(2026, 6, 30),
            'departure_reason_id': self.env.ref('l10n_ph_hr_payroll.hr_departure_reason_mandatory_retirement').id,
        }])

        for employee in (self.regular_employee, self.new_employee, self.departing_employee, self.no_earnings_employee):
            self._set_test_employee(employee)
            date_from = max(date(2026, 6, 1), employee.contract_date_start)
            self._generate_payslip(date_from, date(2026, 6, 30)).action_validate()

    @freeze_time('2026-07-05')
    def test_sss_contribution_txt(self):
        """ Ensure the generated file follows the SSS input file specification, one row per eligible employee. """
        self._generate_june_payslips()

        sheet = self.env['l10n_ph_hr_payroll.sss_contribution'].create({})
        # The period and name default to the previous month.
        self.assertEqual(sheet.period_start_date, date(2026, 6, 1))
        self.assertEqual(sheet.period_end_date, date(2026, 6, 30))
        self.assertEqual(sheet.name, 'SSS Contribution - June 2026')

        sheet.action_generate_declarations()
        sheet.action_generate_txt()

        self.assertEqual(sheet.txt_filename, 'SSS_0312345678_062026.txt')
        rows = [row.split(';') for row in sheet.txt_file.decode().split('\r\n')]
        self.assertEqual(len(rows), 4)
        rows_per_employee = {row[2]: row for row in rows}

        # Field 8 is the taxable cash earnings of the period; here it equals the wage, a full month of basic pay only.
        # A regular employee: remark N, no hire/termination date, no position.
        self.assertEqual(rows_per_employee['0123456789'], [
            '0312345678', '001', '0123456789', 'HIDALGO', 'JENNIFER', 'NULL', 'B',
            '30000.00', 'N', 'NULL', 'NULL',
        ])
        # A newly hired employee: remark 1, hire date and position.
        self.assertEqual(rows_per_employee['0212348678'], [
            '0312345678', '001', '0212348678', 'ANDRADA', 'JERROM', 'JR.', 'G',
            '20000.00', '1', '06162026', 'PROGRAMMER',
        ])
        # A leaving employee: remark 2, termination date, no position.
        self.assertEqual(rows_per_employee['0312333556'], [
            '0312345678', '001', '0312333556', 'CHOPITEA', 'BEULAH', 'NULL', 'G',
            '25000.00', '2', '06302026', 'NULL',
        ])
        # An employee with no earnings: remark 3, and 0 taxable cash earnings to report.
        self.assertEqual(rows_per_employee['0412335555'], [
            '0312345678', '001', '0412335555', 'GALVAN', 'GAUDENCIO', 'NULL', 'NULL',
            '0.00', '3', 'NULL', 'NULL',
        ])

    @freeze_time('2026-07-05')
    def test_sss_contribution_missing_data(self):
        """ Ensure the file is blocked while the data the SSS requires is missing. """
        self._generate_june_payslips()
        self.regular_employee.l10n_ph_hr_payroll_sss_number = False
        # A position is only expected, but then required, for the newly hired employees.
        self.new_employee.version_ids.job_title = False

        sheet = self.env['l10n_ph_hr_payroll.sss_contribution'].create({})
        sheet.action_generate_declarations()

        with self.assertRaises(UserError) as error:
            sheet.action_generate_txt()
        self.assertIn('The SS Number is not set.', str(error.exception))
        self.assertIn('The Position is required for a newly hired employee.', str(error.exception))

    @freeze_time('2026-07-05')
    def test_sss_termination_reported_in_its_period(self):
        """ Test that a departure is reported only in the period holding it, whatever its length. """
        self.env['hr.employee.departure'].create([{
            'employee_id': self.departing_employee.id,
            'dismissal_date': date(2026, 6, 30),
            'departure_reason_id': self.env.ref('l10n_ph_hr_payroll.hr_departure_reason_mandatory_retirement').id,
        }])
        self._set_test_employee(self.departing_employee)
        self.departing_employee.schedule_pay = 'semi-monthly'
        self._generate_payslip(date(2026, 6, 1), date(2026, 6, 15)).action_validate()
        self._generate_payslip(date(2026, 6, 16), date(2026, 6, 30)).action_validate()

        # Still working in the first half, so reported as a regular employee there, and as leaving in the second half.
        first_half = self.env['l10n_ph_hr_payroll.sss_contribution'].create({
            'period_start_date': date(2026, 6, 1),
            'period_end_date': date(2026, 6, 15),
        })
        first_half.action_generate_declarations()
        self.assertEqual(first_half.line_ids.l10n_ph_sss_remarks, 'N')

        second_half = self.env['l10n_ph_hr_payroll.sss_contribution'].create({
            'period_start_date': date(2026, 6, 16),
            'period_end_date': date(2026, 6, 30),
        })
        second_half.action_generate_declarations()
        self.assertEqual(second_half.line_ids.l10n_ph_sss_remarks, '2')

    @freeze_time('2026-07-05')
    def test_sss_dedup_confirmed_overlapping(self):
        """ Test that a confirmed report locks its employees out of any later overlapping report, but drafts don't. """
        self._set_test_employee(self.regular_employee)
        self.regular_employee.schedule_pay = 'semi-monthly'
        self._generate_payslip(date(2026, 6, 1), date(2026, 6, 15)).action_validate()
        self._generate_payslip(date(2026, 6, 16), date(2026, 6, 30)).action_validate()
        # A second employee only earns in the second half, so overlapping reports are never left empty.
        self._set_test_employee(self.new_employee)
        self._generate_payslip(date(2026, 6, 16), date(2026, 6, 30)).action_validate()

        first_half = self.env['l10n_ph_hr_payroll.sss_contribution'].create({
            'period_start_date': date(2026, 6, 1),
            'period_end_date': date(2026, 6, 15),
        })
        first_half.action_generate_declarations()
        self.assertIn(self.regular_employee, first_half.line_ids.employee_id)
        first_half.action_confirm_declaration()

        # An overlapping report leaves out the employee already reported, but keeps the others.
        full_month = self.env['l10n_ph_hr_payroll.sss_contribution'].create({
            'period_start_date': date(2026, 6, 1),
            'period_end_date': date(2026, 6, 30),
        })
        full_month.action_generate_declarations()
        self.assertNotIn(self.regular_employee, full_month.line_ids.employee_id)
        self.assertIn(self.new_employee, full_month.line_ids.employee_id)

        # A non-overlapping report is unaffected.
        second_half = self.env['l10n_ph_hr_payroll.sss_contribution'].create({
            'period_start_date': date(2026, 6, 16),
            'period_end_date': date(2026, 6, 30),
        })
        second_half.action_generate_declarations()
        self.assertIn(self.regular_employee, second_half.line_ids.employee_id)

        # Once the first report is back to draft, it stops locking the employee out.
        first_half.action_draft_declaration()
        full_month.action_generate_declarations()
        self.assertIn(self.regular_employee, full_month.line_ids.employee_id)

    @freeze_time('2026-07-05')
    def test_sss_file_lifecycle(self):
        """ Ensure a generated file is logged to the chatter, and dropped when the report is reset to draft. """
        self._generate_june_payslips()
        sheet = self.env['l10n_ph_hr_payroll.sss_contribution'].create({})
        sheet.action_generate_declarations()
        sheet.action_generate_txt()

        self.assertTrue(sheet.txt_file)
        self.assertIn(sheet.txt_filename, sheet.message_ids.attachment_ids.mapped('name'))

        sheet.action_confirm_declaration()
        sheet.action_draft_declaration()
        self.assertFalse(sheet.txt_file)
        self.assertFalse(sheet.txt_filename)
