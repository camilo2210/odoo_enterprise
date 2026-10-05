# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, date
from odoo.tests import tagged

from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('at_install', '-post_install')
class TestPayslipComputation(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_payslip_worked_day_lines_for_fully_flexible_employee(self):
        flexible_structure = self.env['hr.payroll.structure'].create({
        'name': 'Flexible Employee Structure',
        'type_id': self.structure_type.id,
        'use_worked_day_lines': True,
        })
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Fully Flexible Calendar',
            'company_id': self.env.company.id,
            'calendar_type': 'undefined',
            'attendance_ids': [],
        })
        flexible_employee = self.env['hr.employee'].create({
            'name': 'Fully Flexible Employee',
            'company_id': self.env.company.id,
            'resource_calendar_id': flexible_calendar.id,
            'attendance_based': True,
        })
        flexible_contract = self.env['hr.version'].create({
            'name': 'Contract - Fully Flexible Employee',
            'employee_id': flexible_employee.id,
            'contract_date_start': date(2026, 1, 1),
            'date_version': date(2026, 1, 1),
            'wage': 5000.0,
            'structure_type_id': flexible_structure.type_id.id,
            'resource_calendar_id': flexible_calendar.id,
            'attendance_based': True,
        })

        self.env['hr.attendance'].create([
            {
                'employee_id': flexible_employee.id,
                'check_in': datetime(2026, 1, 1, 8, 0, 0),
                'check_out': datetime(2026, 1, 1, 16, 0, 0),
            },
        ])
        payslip = self.env['hr.payslip'].create({
            'employee_id': flexible_employee.id,
            'version_id': flexible_contract.id,
            'struct_id': flexible_structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
        })
        payslip._compute_worked_days_line_ids()
        self.assertRecordValues(
            payslip.worked_days_line_ids,
            [{
                'code': '002.00',
                'number_of_hours': 8.0,
                'amount': 5000.0,
            }]
        )

    def test_payslip_worked_day_lines_for_schedule_based_employee(self):
        schedule_structure = self.env['hr.payroll.structure'].create({
            'name': 'Scheduled Employee Structure',
            'type_id': self.structure_type.id,
            'use_worked_day_lines': True,
        })
        calendar = self.env.company.resource_calendar_id

        schedule_based_employee = self.env['hr.employee'].create({
            'name': 'Schedule Based Employee',
            'company_id': self.env.company.id,
            'resource_calendar_id': calendar.id,
            'attendance_based': False,
        })
        schedule_based_contract = self.env['hr.version'].create({
            'name': 'Contract - Schedule Based Employee',
            'employee_id': schedule_based_employee.id,
            'contract_date_start': date(2026, 1, 1),
            'date_version': date(2026, 1, 1),
            'wage': 5000.0,
            'structure_type_id': schedule_structure.type_id.id,
            'resource_calendar_id': calendar.id,
            'attendance_based': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': schedule_based_employee.id,
            'version_id': schedule_based_contract.id,
            'struct_id': schedule_structure.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
        })
        payslip._compute_worked_days_line_ids()
        self.assertRecordValues(
            payslip.worked_days_line_ids,
            [{
                'code': '002.00',
                'number_of_days': 22.0,
                'number_of_hours': 176.0,
                'amount': 5000.0,
            }]
        )
