# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged("post_install_l10n", "post_install", "-at_install")
class TestWpsReport(TestPayslipContractBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_sa = cls.env["res.company"].create(
            {
                "name": "Company SA",
                "country_id": cls.env.ref("base.sa").id,
            }
        )
        cls.richard_emp.write(
            {
                "company_id": cls.company_sa,
                "l10n_sa_employee_code": "454786",
                'l10n_sa_company_social_insurance_percentage': 1
            }
        )
        cls.partner_bank_account = cls.env["res.partner.bank"].create(
            {
                "account_number": "9876543210",
                "partner_id": cls.richard_emp.work_contact_id.id,
                "allow_out_payment": True,
                "bank_name": "Al Inma Bank",
                "clearing_label_id": cls.env.ref("base.clearing_label_sa").id,
                "clearing_number": "INMA",
                "l10n_sa_bank_establishment_code": "0002124",
            }
        )
        cls.sa_bank_account = cls.env["res.partner.bank"].create(
            {
                "account_number": "0123456789",
                "partner_id": cls.company_sa.partner_id.id,
                "allow_out_payment": True,
                "bank_name": "Al Inma Bank",
                "clearing_label_id": cls.env.ref("base.clearing_label_sa").id,
                "clearing_number": "INMA",
                "l10n_sa_bank_establishment_code": "0002124",
            }
        )
        cls.company_sa.write(
            {
                "l10n_sa_bank_account_id": cls.sa_bank_account.id,
                "l10n_sa_mol_establishment_code": "000111",
            }
        )
        cls.richard_emp.primary_bank_account_id = cls.partner_bank_account
        cls.richard_payslip = cls.env["hr.payslip"].create(
            {
                "name": "Payslip of Richard",
                "employee_id": cls.richard_emp.id,
                "version_id": cls.contract_cdi.id,
                "struct_id": cls.developer_pay_structure.id,
                "date_from": date(2025, 7, 1),
                "date_to": date(2025, 7, 30),
            }
        )
        cls.richard_payslip_2 = cls.env["hr.payslip"].create(
            {
                "name": "Payslip 2 of Richard",
                "employee_id": cls.richard_emp.id,
                "version_id": cls.contract_cdi.id,
                "struct_id": cls.developer_pay_structure.id,
                "date_from": date(2025, 8, 1),
                "date_to": date(2025, 8, 30),
            }
        )
        cls.richard_payslip_run = cls.env["hr.payslip.run"].create(
            {
                "name": "Test Batch",
                "date_start": date(2025, 7, 1),
                "date_end": date(2025, 8, 30),
                "company_id": cls.company_sa.id,
                "structure_id": cls.developer_pay_structure.id,
            },
        )
        cls.richard_payslip.payslip_run_id = cls.richard_payslip_run
        cls.richard_payslip_2.payslip_run_id = cls.richard_payslip_run
        cls.richard_payslip_run.action_confirm()
        cls.richard_emp.write({'review_state': '1_reviewed'})
        cls.richard_payslip_run.action_validate()

    def test_wps_report_generation(self):
        wizard = self.env["hr.payroll.payment.report.wizard"].create(
            {
                "payslip_ids": [self.richard_payslip.id, self.richard_payslip_2.id],
                "payslip_run_id": self.richard_payslip_run.id,
                "export_format": "l10n_sa_wps",
            }
        ).with_company(self.company_sa)
        wizard.generate_payment_report()
        wps_data = self.richard_payslip_run.slip_ids._l10n_sa_get_wps_data()
        self.assertEqual(len(wps_data), len(self.richard_payslip_run.slip_ids) + 1)
        all_codes = ["BASIC", "GROSS", "NET", "HOUALLOW"]
        all_line_values = self.richard_payslip_run.slip_ids._get_line_values(all_codes)
        self.assertEqual(len(wps_data), len(all_line_values[all_codes[0]]) + 1)
        for record, payslip in zip(wps_data[1:], self.richard_payslip_run.slip_ids):
            net = all_line_values["NET"][payslip.id]["total"]
            basic = all_line_values["BASIC"][payslip.id]["total"]
            gross = all_line_values["GROSS"][payslip.id]["total"]
            housing = all_line_values["HOUALLOW"][payslip.id]["total"]
            extra_income = gross - basic - housing
            deductions = gross - net

            self.assertEqual(
                record[0], self.env["hr.payslip"]._l10n_sa_format_float(net)
            )
            self.assertEqual(
                record[5], self.env["hr.payslip"]._l10n_sa_format_float(basic)
            )
            self.assertEqual(
                record[6], self.env["hr.payslip"]._l10n_sa_format_float(housing)
            )
            self.assertEqual(
                record[7], self.env["hr.payslip"]._l10n_sa_format_float(extra_income)
            )
            self.assertEqual(
                record[8], self.env["hr.payslip"]._l10n_sa_format_float(deductions)
            )
