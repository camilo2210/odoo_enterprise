# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date


from odoo.addons.l10n_in_hr_payroll_account.tests.common import TestPayrollAccountCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEnetCSVReport(TestPayrollAccountCommon):

    def _prepare_payslip_run(self):
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2023-01-01',
            'date_end': '2023-01-31',
            'name': 'January Batch',
            'company_id': self.company_in.id,
            'structure_id': self.structure.id,
        })

        payslip_run._generate_payslips()
        payslip_run.action_validate()
        return payslip_run

    def test_enet_csv_report_creation(self):
        payslip_run = self._prepare_payslip_run()
        self.assertEqual(payslip_run.state, "02_close", "Payslip run should be in Done state")

        # Generating the CSV report for the batch
        enet_report_dict = self.env["hr.payroll.payment.report.wizard"].create({
            'payslip_ids': payslip_run.slip_ids.ids,
            'payslip_run_id': payslip_run.id,
            'export_format': 'enet',
            'l10n_in_payment_method': 'enet_rtgs'
        }).generate_enet_csv()

        enet_report = self.env['hr.payroll.payment.report.wizard'].browse(enet_report_dict['res_id'])

        self.assertTrue(payslip_run.payment_report, "CSV File should be generated!")
        self.assertTrue(enet_report.l10n_in_enet_csv, "CSV File should be generated!")
        self.assertEqual(enet_report.l10n_in_enet_filename_csv, 'RTGS_' + enet_report.l10n_in_reference + '.csv')
        self.assertTrue(payslip_run.payment_report_filename)

    def test_enet_csv_report_from_payslip(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.rahul_emp.id,
            'date_from': date(2023, 1, 1),
            'date_to': date(2023, 1, 31),
            'company_id': self.company_in.id,
        })
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self.assertEqual(payslip.state, "validated", "Payslip should be in validated state")

        # Generating the CSV report from the payslip
        enet_report_dict = self.env["hr.payroll.payment.report.wizard"].create({
            'payslip_ids': payslip.ids,
            'export_format': 'enet',
            'l10n_in_payment_method': 'enet_rtgs'
        }).generate_enet_csv()

        enet_report = self.env['hr.payroll.payment.report.wizard'].browse(enet_report_dict['res_id'])

        self.assertTrue(payslip.payment_report, "CSV File should be generated!")
        self.assertTrue(enet_report.l10n_in_enet_csv, "CSV File should be generated!")
        self.assertEqual(enet_report.l10n_in_enet_filename_csv, 'RTGS_' + enet_report.l10n_in_reference + '.csv')
        self.assertTrue(payslip.payment_report_filename)
