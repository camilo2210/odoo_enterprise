# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, date, UTC
from zoneinfo import ZoneInfo

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestPayslipValidation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar = cls.env['resource.calendar'].create({
            'attendance_ids': [
                (0, 0,
                    {
                        'dayofweek': weekday,
                        'hour_from': hour,
                        'hour_to': hour + 4,
                    })
                for weekday in ['6', '0', '1', '2', '3']
                for hour in [9, 13]
            ],
            'name': 'Standard 40h/week',
        })
        cls.company_sa = cls.env["res.company"].create(
            {
                "name": "Company SA",
                "country_id": cls.env.ref("base.sa").id,
                "resource_calendar_id": cls.calendar.id,
                "tz": "Asia/Riyadh",
            }
        )
        cls.sa_structure_type = cls.env.ref("l10n_sa_hr_payroll.ksa_employee_payroll_structure_type")
        cls.sa_structure = cls.env.ref("l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure")
        cls.sa_emp = cls.env['hr.employee'].create({
            'name': "SA Emp",
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'structure_type_id': cls.sa_structure_type.id,
            'wage': 5000,
            'company_id': cls.company_sa.id,
            "tz": "Asia/Riyadh",
        })
        cls.sa_version = cls.sa_emp.version_id

    def test_1(self):
        check_in = datetime(2025, 7, 10, 9, 30, tzinfo=ZoneInfo("Etc/GMT-3"))
        sa_attendance = self.env['hr.attendance'].create({
            'employee_id': self.sa_emp.id,
            'check_in': check_in.astimezone(UTC).replace(tzinfo=None),
            # 'l10n_sa_late_hours_status': 'to_approve',
        })
        sa_attendance.action_approve_l10n_sa_late_hours()
        sa_payslip = self.env["hr.payslip"].create(
            {
                "name": "Payslip of SA",
                "employee_id": self.sa_emp.id,
                "version_id": self.sa_version.id,
                "struct_id": self.sa_structure.id,
                "date_from": date(2025, 7, 1),
                "date_to": date(2025, 7, 30),
            }
        )
        sa_payslip.compute_sheet()
        self.assertEqual(sa_payslip._get_input_line_amount('LATE_HOURS'), 0.5)

    def test_late_hours_visibility_only_for_sa_companies(self):
        company_us = self.env["res.company"].create({
            "name": "Company US",
            "country_id": self.env.ref("base.us").id,
        })
        us_emp = self.env['hr.employee'].create({
            'name': "US Emp",
            'company_id': company_us.id,
        })

        check_in = datetime(2025, 7, 10, 9, 30, tzinfo=ZoneInfo("Etc/GMT-3"))
        # Create attendance for Saudi employee
        sa_attendance = self.env['hr.attendance'].create({
            'employee_id': self.sa_emp.id,
            'check_in': check_in.astimezone(UTC).replace(tzinfo=None),
        })
        # Create attendance for US employee
        us_attendance = self.env['hr.attendance'].with_company(company_us).create({
            'employee_id': us_emp.id,
            'check_in': check_in.astimezone(UTC).replace(tzinfo=None),
        })

        self.assertTrue(sa_attendance.l10n_sa_late_hours_visible)
        self.assertFalse(us_attendance.l10n_sa_late_hours_visible)
