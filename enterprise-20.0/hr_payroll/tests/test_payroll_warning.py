# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged, TransactionCase


@tagged('-at_install', 'post_install')
class TestPayrollWarning(TransactionCase):

    def setUp(self):
        super().setUp()
        self.test_company = self.env['res.company'].create({
            'name': 'Test Company',
            'first_payrun_date': date(2025, 1, 1),
            'payroll_closing_date': '25',
        })
        self.monthly_structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Monthly Structure Type',
            'default_schedule_pay': 'monthly',
        })
        self.will_byers = self.env['hr.employee'].create({
            'name': 'Will Byers',
            'company_id': self.test_company.id,
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'structure_type_id': self.monthly_structure_type.id
        })
        self.Warning = self.env['hr.payroll.warning']

    @freeze_time('2025-11-14')
    def test_company_monthly_closing_date(self):
        closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        self.assertEqual(closing_date, date(2025, 11, 25), "Computed monthly closing date should match payroll_closing_date")

    @freeze_time('2025-11-26')
    def test_company_monthly_closing_date_rollover(self):
        closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        self.assertEqual(closing_date, date(2025, 12, 25), "Closing date should roll to next month when today is past the closing date")

    @freeze_time('2025-11-14')
    def test_company_monthly_closing_date_for_next_month(self):
        self.test_company.write({'payroll_closing_date': '5'})
        closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        self.assertEqual(closing_date, date(2025, 12, 5), "Closing date should be computed in the next month for early closing days")

    @freeze_time('2026-4-3')
    def test_company_monthly_closing_date_for_next_month_date(self):
        self.test_company.write({'payroll_closing_date': '5'})
        closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        self.assertEqual(closing_date, date(2026, 4, 5), "Closing date should be computed in the same month if today < closing day")

    @freeze_time('2025-11-14')
    def test_warning_date_before_next_payslip(self):
        warning = self.Warning.create({
            'name': 'Test Warning',
            'warning_type': 'domain',
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'warning_domain': "[('id', '=', %d)]" % self.will_byers.id,
            'closing_on': 'next_payslip',
            'warning_offset_days': -5,
        })
        monthly_closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        warning_date = warning._get_warning_date(self.will_byers, monthly_closing_date)
        self.assertEqual(warning_date, date(2025, 11, 20), "Warning date should be 5 days before the closing date")

    @freeze_time('2025-11-14')
    def test_warning_date_after_next_payslip(self):
        warning = self.Warning.create({
            'name': 'After Payslip Warning',
            'warning_type': 'domain',
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'warning_domain': "[('id', '=', %d)]" % self.will_byers.id,
            'closing_on': 'next_payslip',
            'warning_offset_days': 3,
        })
        monthly_closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        warning_date = warning._get_warning_date(self.will_byers, monthly_closing_date)
        self.assertEqual(warning_date, date(2025, 11, 28), "Warning date should be 3 days after the closing date")

    @freeze_time('2025-11-14')
    def test_warning_date_before_contract_start(self):
        warning = self.Warning.create({
            'name': 'Before Contract Start Warning',
            'warning_type': 'domain',
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'warning_domain': "[('id', '=', %d)]" % self.will_byers.id,
            'closing_on': 'contract_start',
            'warning_offset_days': -7,
        })
        monthly_closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        warning_date = warning._get_warning_date(self.will_byers, monthly_closing_date)
        self.assertEqual(warning_date, date(2024, 12, 25), "Warning date should be 7 days before the contract start date")

    @freeze_time('2025-11-14')
    def test_warning_date_before_contract_end(self):
        self.will_byers.write({'contract_date_end': date(2025, 12, 31)})
        warning = self.Warning.create({
            'name': 'Before Contract End Warning',
            'warning_type': 'domain',
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'warning_domain': "[('id', '=', %d)]" % self.will_byers.id,
            'closing_on': 'contract_end',
            'warning_offset_days': -5,
        })
        monthly_closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        warning_date = warning._get_warning_date(self.will_byers, monthly_closing_date)
        self.assertEqual(warning_date, date(2025, 12, 26), "Warning date should be 5 days before the contract end date")

    def test_warning_domain_records_active_ids_restriction(self):
        eleven = self.env['hr.employee'].create({
            'name': 'Eleven',
            'company_id': self.test_company.id,
        })
        warning = self.Warning.create({
            'name': 'Active Ids Warning',
            'warning_type': 'domain',
            'country_id': self.test_company.country_id.id,
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'warning_domain': [('id', 'in', [self.will_byers.id, eleven.id])],
        })
        self.assertEqual(
            warning._get_warning_domain_records(self.test_company),
            self.will_byers | eleven,
            "Without active_ids, every record matching the domain should be returned",
        )
        with self.assertQueryCount(0):  # If we pass records to check, no additional query should be made
            self.assertEqual(
                warning._get_warning_domain_records(self.test_company, records_to_check=self.will_byers),
                self.will_byers,
                "With active_ids, only the records within that restriction should be returned",
            )

    @freeze_time('2025-11-07')
    def test_other_schedule_closing_dates(self):
        monthly_closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        weekly_closing_date = self.Warning._get_schedule_closing_date('weekly', monthly_closing_date)
        bi_weekly_closing_date = self.Warning._get_schedule_closing_date('bi-weekly', monthly_closing_date)
        semi_monthly_closing_date = self.Warning._get_schedule_closing_date('semi-monthly', monthly_closing_date)

        self.assertEqual(weekly_closing_date, date(2025, 11, 10), "Weekly schedule should close on the next Monday")
        self.assertEqual(bi_weekly_closing_date, date(2025, 11, 17), "Bi-weekly schedule should close on the next bi-weekly Monday")
        self.assertEqual(semi_monthly_closing_date, date(2025, 11, 15), "Semi-monthly schedule should close on the 15th")

    @freeze_time('2025-11-14')
    def test_payroll_dashboard_basic_structure(self):
        warning = self.Warning.with_company(self.test_company).create({
            'name': 'Dashboard Warning',
            'warning_type': 'domain',
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'warning_domain': "[('id', '=', %d)]" % self.will_byers.id,
            'closing_on': 'next_payslip',
            'warning_offset_days': 0,
            'warning_color_class': 'warning',
        })

        monthly_closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        warning_date = warning._get_warning_date(self.will_byers, monthly_closing_date)
        dashboard_data = self.Warning.with_company(self.test_company).get_payroll_dashboard_data()
        self.assertIn(warning.id, dashboard_data['warning_ids'])

        warning_entry = self.Warning.with_company(self.test_company).get_payroll_dashboard_warning_cards([warning.id])[0]

        self.assertEqual(warning_entry['key'], f"monthly_{warning.id}", "Dashboard warning key should use the schedule prefix")
        self.assertEqual(warning_entry['warning_date'], warning_date, "Dashboard warning date should match the computed warning date")
        self.assertEqual(warning_entry['count'], 1, "Dashboard warning count should have the matching records")
        self.assertEqual(warning_entry['structure_type_suffix'], '', "Monthly schedule should not display a structure type suffix")
        self.assertEqual(warning_entry['color_class'], 'warning', "Dashboard warning color should match the warning configuration")
        self.assertIn(self.will_byers, warning_entry['warning_records'], "Dashboard warning records should include the employee")
        self.assertEqual(
            warning_entry['button_action']['res_id'],
            self.will_byers.id,
            "Dashboard warning action should target the matching record",
        )

        second_employee = self.env['hr.employee'].create({
            'name': 'Second Employee',
            'company_id': self.test_company.id,
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'structure_type_id': self.monthly_structure_type.id
        })
        warning.warning_domain = f"[('id', 'in', {self.will_byers.id, second_employee.id})]"
        monthly_closing_date = self.test_company._get_monthly_payroll_next_closing_date()
        warning_date = warning._get_warning_date(self.will_byers, monthly_closing_date)
        dashboard_data = self.Warning.with_company(self.test_company).get_payroll_dashboard_data()
        self.assertIn(warning.id, dashboard_data['warning_ids'])

        warning_entry = self.Warning.with_company(self.test_company).get_payroll_dashboard_warning_cards([warning.id])[0]

        self.assertEqual(warning_entry['key'], f"monthly_{warning.id}", "Dashboard warning key should use the schedule prefix")
        self.assertEqual(warning_entry['warning_date'], warning_date, "Dashboard warning date should match the computed warning date")
        self.assertEqual(warning_entry['count'], 2, "Dashboard warning count should have the matching records")
        self.assertEqual(warning_entry['structure_type_suffix'], '', "Monthly schedule should not display a structure type suffix")
        self.assertEqual(warning_entry['color_class'], 'warning', "Dashboard warning color should match the warning configuration")
        self.assertIn(self.will_byers, warning_entry['warning_records'], "Dashboard warning records should include the employee")
        self.assertIn(second_employee, warning_entry['warning_records'], "Dashboard warning records should include the employee")
        self.assertEqual(
            warning_entry['button_action']['domain'],
            [('id', 'in', [second_employee.id, self.will_byers.id])],
            "Dashboard warning action should target the matching records",
        )

    @freeze_time("2025-02-01")
    def test_payrun_employee_type(self):
        def _has_warning(name, warning_date):
            warnings_data = self.env['hr.payroll.warning'].with_company(self.will_byers.company_id).get_payroll_dashboard_warning_cards([])
            return any(
                warning_data['name'] == name and warning_data['warning_date'] == warning_date
                for warning_data in warnings_data
            )

        # 1. Employee type without payroll closing date
        self.will_byers.company_id.payroll_closing_date = 25
        employee_type = self.env.ref('hr.contract_type_employee')
        employee_type.payroll_closing_date = False
        self.will_byers.employee_type_id = employee_type.id
        self.assertFalse(_has_warning('Start Pay run - Feb 2025 (Employee)', date(2025, 2, 25)))
        self.assertTrue(_has_warning('Payrun: Feb 2025', date(2025, 2, 25)))

        # 2. Employee type with payroll closing date
        employee_type.payroll_closing_date = 31
        self.assertTrue(_has_warning('Start Pay run - Feb 2025 (Employee)', date(2025, 2, 28)))

    @freeze_time('2025-11-14')
    def test_payroll_dashboard_with_falsy_schedule_pay(self):
        self.monthly_structure_type.write({
            'default_schedule_pay': False,
            'country_id': False,
        })
        self.monthly_structure_type.default_schedule_pay = False
        warning = self.Warning.with_company(self.test_company).create({
            'name': 'Dashboard Warning',
            'warning_type': 'domain',
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'warning_domain': [('id', '=', self.will_byers.id)],
            'closing_on': 'next_payslip',
            'warning_offset_days': 0,
            'warning_color_class': 'warning',
        })

        dashboard_data = self.Warning.with_company(self.test_company).get_payroll_dashboard_data()
        closing_dates_data = dashboard_data['closing_dates_data']
        closing_entries = [entry for entry in closing_dates_data if not entry['schedule']]
        closing_entry = closing_entries[0]
        self.assertEqual(closing_entry['label'], ' Payrun')

        warning_entry = self.Warning.with_company(self.test_company).get_payroll_dashboard_warning_cards([warning.id])[0]
        self.assertEqual(warning_entry['structure_type_suffix'], '', "Schedule should not display a structure type suffix")

    def test_compute_issues_no_crash_with_empty_warning_records(self):
        """A warning whose python condition matches no records should not
        crash _compute_issues with
        AttributeError: 'base' object has no attribute 'version_ids'."""
        warning = self.env['hr.payroll.warning'].create({
            'name': 'Employee Model Warning',
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'warning_type': 'python',
            'evaluation_code': "pass",
        })
        version = self.will_byers.version_id
        version._compute_issues()
        self.assertFalse(warning.id in (version.issues or {}))

    def test_compute_issues_no_crash_with_empty_warning_records_on_version_model(self):
        """Same as above but for a warning whose model_name is 'hr.version',
        covering the other branch in _compute_issues."""
        warning = self.env['hr.payroll.warning'].create({
            'name': 'Test Warning on Version',
            'model_id': self.env.ref('hr.model_hr_version').id,
            'warning_type': 'python',
            'evaluation_code': "pass",
        })
        version = self.will_byers.version_id
        version._compute_issues()
        self.assertFalse(warning.id in (version.issues or {}))
