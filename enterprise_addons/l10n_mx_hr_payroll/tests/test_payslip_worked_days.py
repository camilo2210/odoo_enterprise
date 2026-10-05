# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.fields import Command
from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.tests.common import tagged


@tagged('-at_install', 'post_install_l10n', 'post_install')
class TestPayrollWorkedDays(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mexico = cls.env.ref('base.mx')
        cls.env.company.country_id = mexico.id
        cls._setup_common(
            country=mexico,
            structure=cls.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay'),
            structure_type=cls.env.ref('l10n_mx_hr_payroll.l10n_mx_employee'),
            version_fields={'wage': 30000.0},
        )

        cls.work_entry_types = {
            entry_type.code: entry_type
            for entry_type in cls.env['hr.work.entry.type'].search([('country_id', '=', cls.env.ref('base.mx').id)])
        }

    @classmethod
    def _create_worked_days(cls, name=False, code=False, number_of_days=0, number_of_hours=0, version_id=False):
        return Command.create({
            'name': name,
            'code': code,
            'work_entry_type_id': cls.work_entry_types[code].id,
            'number_of_days': number_of_days,
            'number_of_hours': number_of_hours,
            'version_id': version_id,
        })

    def test_monthly_payslip(self):
        payslip = self._generate_payslip(date(2030, 1, 1), date(2030, 1, 31))
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 30000.0)

        self._generate_leave(self.employee, date(2030, 1, 1), date(2030, 1, 15), self.work_entry_types['158.00'])
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 19000.0)

    def test_hourly_payslip(self):
        self.employee.write({
            'wage_type': 'hourly',
            'hourly_wage': 125.0,
        })
        payslip = self._generate_payslip(date(2030, 1, 1), date(2030, 1, 31))
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 30000.0)

        self._generate_leave(self.employee, date(2030, 1, 1), date(2030, 1, 15), self.work_entry_types['158.00'])
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 19000.0)

    def test_monthly_payslip_with_partial_leave(self):
        self.work_entry_types['158.00'].request_unit = 'hour'

        payslip = self._generate_payslip(date(2030, 1, 1), date(2030, 1, 31))
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 30000.0)

        self.env['hr.leave'].sudo().create({
            'employee_id': self.employee.id,
            'request_date_from': date(2030, 1, 1),
            'request_date_to': date(2030, 1, 1),
            'request_hour_from': 9.0,
            'request_hour_to': 11.0,
            'work_entry_type_id': self.work_entry_types['158.00'].id,
        })
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 29750.0)

    def test_partial_payslip(self):
        payslip = self._generate_payslip(date(2030, 1, 11), date(2030, 1, 21))
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 11000.0)

    def test_partial_payslip_new_hire_month_31_days(self):
        self.employee.contract_date_start = date(2030, 1, 11)
        payslip = self._generate_payslip(date(2030, 1, 1), date(2030, 1, 31))
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 21000.0)

    def test_partial_payslip_new_hire_month_28_days(self):
        self.employee.contract_date_start = date(2030, 2, 11)
        payslip = self._generate_payslip(date(2030, 2, 1), date(2030, 2, 28))
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 18000.0)

    def test_hourly_payslip_by_attendance(self):
        if self.env['ir.module.module']._get('hr_payroll_attendance').state != 'installed':
            self.skipTest("Skipping test because hr_payroll_attendance is not installed.")

        self.employee.write({
            'attendance_based': True,
            'wage_type': 'hourly',
            'hourly_wage': 125.0,
        })
        payslip = self._generate_payslip(date(2030, 1, 1), date(2030, 1, 31))

        worked_days_vals = [
            {'name': 'Attendance', 'code': '002.00', 'number_of_hours': 88, 'number_of_days': 11, 'version_id': self.version.id},
            {'name': 'Paid Time Off', 'code': '016.00', 'number_of_hours': 24, 'number_of_days': 3, 'version_id': self.version.id},
        ]
        payslip.write({
            "worked_days_line_ids": [self._create_worked_days(**vals) for vals in worked_days_vals],
        })
        payslip.compute_sheet()
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 14000.0)

        worked_days_vals = [
            {'name': 'Unpaid', 'code': '158.00', 'number_of_hours': 16, 'number_of_days': 2, 'version_id': self.version.id},
            {'name': 'Out of Contract', 'code': '000.00', 'number_of_hours': 32, 'number_of_days': 4, 'version_id': self.version.id},
        ]
        payslip.write({
            "worked_days_line_ids": [self._create_worked_days(**vals) for vals in worked_days_vals],
        })
        payslip.compute_sheet()
        self.assertEqual(payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'], 14000.0)

    @freeze_time('2026-03-10')
    def test_years_worked(self):
        """
        Test the number of years worked by an employee taking gaps between contracts into consideration
        """
        self.employee.contract_date_end = date(2025, 1, 31)
        new_contract_1 = self.employee.create_version({
            'date_version': date(2025, 2, 1),
            'contract_date_start': date(2025, 2, 1),
            'contract_date_end': date(2026, 1, 31),
        })
        new_contract_2 = self.employee.create_version({
            'date_version': date(2026, 3, 1),
            'contract_date_start': date(2026, 3, 1),
        })
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2026-01-01',
            'date_end': '2026-01-15',
            'structure_id': self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay').id,
        })

        payslip_run._generate_payslips()
        self.assertEqual(payslip_run.slip_ids.version_id.id, new_contract_1.id)
        self.assertEqual(payslip_run.slip_ids.l10n_mx_years_worked, 11)

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2026-03-01',
            'date_end': '2026-03-15',
            'structure_id': self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay').id,
        })

        payslip_run._generate_payslips()
        self.assertEqual(payslip_run.slip_ids.version_id.id, new_contract_2.id)
        self.assertEqual(payslip_run.slip_ids.l10n_mx_years_worked, 1)

    def test_compute_sheets_with_higher_seniority(self):
        """
        Ensure that computing a payslip for an employee with more than the maximum
        defined years in the holiday table does not raise a KeyError.
        """
        self.employee.write({
            'contract_date_start': '1985-01-01',
            'wage': 100000
        })
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2026-01-01',
            'date_end': '2026-02-01',
            'structure_id': self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay').id,
        })
        payslip_run._generate_payslips()
        # This should no longer raise KeyError
        self.assertTrue(payslip_run.slip_ids.compute_sheet())
