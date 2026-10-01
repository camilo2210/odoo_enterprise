from datetime import date

from odoo.addons.hr_payroll.tests.common_payment_report import TestPaymentReportBase
from odoo.tests.common import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPaymentReportCH(TestPaymentReportBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({
            'country_id': cls.env.ref('base.ch').id,
        })

    def test_payslip_payment_report_default(self):
        action = self.payslip.action_payslip_payment_report()
        self.assertEqual(
            action['context']['default_export_format'],
            'iso20022_ch',
        )

    def test_payrun_payment_report_default(self):
        action = self.payrun.action_payment_report()
        self.assertEqual(
            action['context']['default_export_format'],
            'iso20022_ch',
        )


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPaymentReportSepa(TestPaymentReportBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_de = cls.env['res.company'].create({
            'name': 'Company DE',
            'country_id': cls.env.ref('base.de').id,
            'currency_id': cls.env.ref('base.EUR').id,
        })
        cls.employee.company_id = cls.company_de
        cls.contract.company_id = cls.company_de
        cls.payrun.write({
            'company_id': cls.company_de.id,
            'date_start': date(2025, 1, 1),
        })

        cls.payslip_de = cls.env['hr.payslip'].create({
            'name': 'Test Payslip DE',
            'employee_id': cls.employee.id,
            'company_id': cls.company_de.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
        })

    def test_payslip_payment_report_default(self):
        action = self.payslip_de.with_company(self.company_de).action_payslip_payment_report()
        self.assertEqual(
            action['context']['default_export_format'],
            'sepa',
        )

    def test_payrun_payment_report_default(self):
        action = self.payrun.with_company(self.company_de).action_payment_report()
        self.assertEqual(
            action['context']['default_export_format'],
            'sepa',
        )
