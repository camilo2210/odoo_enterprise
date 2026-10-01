# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase
from datetime import date


class TestPaymentReportBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.struct_type = cls.env['hr.payroll.structure.type'].create({'name': 'Regular'})
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Regular structure',
            'type_id': cls.struct_type.id,
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'company_id': cls.company.id,
        })

        cls.contract = cls.env['hr.version'].create({
            'name': 'Test Contract',
            'employee_id': cls.employee.id,
            'company_id': cls.company.id,
            'contract_date_start': date(2025, 1, 1),
            'date_version': date(2025, 1, 1),
            'wage': 1000,
        })

        cls.payslip = cls.env['hr.payslip'].create({
            'name': 'Test Payslip',
            'employee_id': cls.employee.id,
            'company_id': cls.company.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
            'version_id': cls.contract.id,
        })

        cls.payrun = cls.env['hr.payslip.run'].create({
            'name': 'Test Payrun',
            'date_start': date(2025, 1, 1),
            'date_end': date(2025, 1, 31),
            'structure_id': cls.structure.id,
        })
        cls.payslip.payslip_run_id = cls.payrun.id

    def test_payslip_payment_report_default(self):
        action = self.payslip.action_payslip_payment_report()
        self.assertEqual(
            action['context'].get('default_export_format'),
            'csv',
        )

    def test_payrun_payment_report_default_csv(self):
        action = self.payrun.action_payment_report()
        self.assertEqual(
            action['context'].get('default_export_format'),
            'csv',
        )
