# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import ValidationError

from odoo.addons.hr_payroll.tests.common import TestPayslipBase


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestHrPayslipPaymentReport(TestPayslipBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_bank_account = cls.env['res.partner.bank'].create({
            'account_number': "9876543210",
            'partner_id': cls.richard_emp.work_contact_id.id,
            'allow_out_payment': True,
        })
        cls.richard_emp.bank_account_ids = [Command.set([cls.partner_bank_account.id])]
        cls.payslip = cls.env['hr.payslip'].create({
            'name': 'Test Payslip',
            'employee_id': cls.richard_emp.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
        })

    def test_payslip_payment_report_fields_and_attachment(self):
        self.payslip.compute_sheet()
        self.payslip.action_payslip_done()

        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.payslip.id],
            'payslip_run_id': self.payslip.payslip_run_id.id,
            'export_format': 'csv',
        })
        wizard.generate_payment_report()

        attachment_count = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'hr.payslip'),
            ('res_id', '=', self.payslip.id),
            ('res_field', '=', 'payment_report'),
        ])

        self.assertTrue(self.payslip.payment_report, "Payment report should be set initially.")
        self.assertTrue(self.payslip.payment_report_filename)
        self.assertTrue(self.payslip.payment_report_date)
        self.assertEqual(attachment_count, 1, "Attachment should exist before clearing.")

        self.payslip.action_payslip_draft()
        self.env.cr.flush()

        attachment_count = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'hr.payslip'),
            ('res_id', '=', self.payslip.id),
            ('res_field', '=', 'payment_report'),
        ])

        self.assertFalse(self.payslip.payment_report, "Payment report should be cleared.")
        self.assertFalse(self.payslip.payment_report_filename, "Filename should be cleared.")
        self.assertFalse(self.payslip.payment_report_date, "Date should be cleared.")
        self.assertEqual(attachment_count, 0, "Attachment should be deleted after clearing.")

    def test_generate_payslip_payment_report_with_include_unpaid_enabled(self):
        """Test that the payslip payment report is generated with 'include_unpaid' enabled."""
        self.payslip.compute_sheet()
        self.payslip.action_payslip_done()

        action = self.payslip.action_payslip_payment_report()
        wizard = self.env['hr.payroll.payment.report.wizard'].with_context(
            action['context']
        ).create({'include_unpaid': True})
        wizard.generate_payment_report()

        self.assertEqual(wizard.unpaid_payslips, self.payslip)
        self.assertTrue(self.payslip.payment_report)

    def _create_extra_validated_payslip(self):
        """A second validated payslip of the same version, outside the wizard's payslip_ids."""
        payslip = self.env['hr.payslip'].create({
            'name': 'Test Payslip 2',
            'employee_id': self.richard_emp.id,
            'date_from': date(2025, 2, 1),
            'date_to': date(2025, 2, 28),
        })
        payslip.compute_sheet()
        payslip.action_payslip_done()
        return payslip

    def test_mark_as_paid_marks_every_payslip_of_the_report(self):
        """Payslips added through 'include_unpaid' end up paid, not only the wizard's own ones."""
        self.payslip.compute_sheet()
        self.payslip.action_payslip_done()
        other_payslip = self._create_extra_validated_payslip()

        action = self.payslip.action_payslip_payment_report()
        wizard = self.env['hr.payroll.payment.report.wizard'].with_context(
            action['context']
        ).create({'include_unpaid': True})

        self.assertEqual(wizard.unpaid_payslips, self.payslip | other_payslip)

        wizard.mark_as_paid()

        self.assertEqual(self.payslip.state, 'paid')
        self.assertEqual(other_payslip.state, 'paid', "The extra payslip of the report should be paid too.")

    def test_mark_as_paid_without_include_unpaid_ignores_other_payslips(self):
        """Without 'include_unpaid' only the wizard's own payslips are paid."""
        self.payslip.compute_sheet()
        self.payslip.action_payslip_done()
        other_payslip = self._create_extra_validated_payslip()

        action = self.payslip.action_payslip_payment_report()
        wizard = self.env['hr.payroll.payment.report.wizard'].with_context(
            action['context']
        ).create({'include_unpaid': False})
        wizard.mark_as_paid()

        self.assertEqual(self.payslip.state, 'paid')
        self.assertEqual(other_payslip.state, 'validated', "A payslip left out of the report should stay unpaid.")

    def test_mark_as_paid_follows_the_unpaid_payslips_selection(self):
        """The user can narrow down the selection, and only that selection is paid."""
        self.payslip.compute_sheet()
        self.payslip.action_payslip_done()
        other_payslip = self._create_extra_validated_payslip()

        action = self.payslip.action_payslip_payment_report()
        wizard = self.env['hr.payroll.payment.report.wizard'].with_context(
            action['context']
        ).create({
            'include_unpaid': True,
            'unpaid_payslips': [Command.set(other_payslip.ids)],
        })
        wizard.mark_as_paid()

        self.assertEqual(other_payslip.state, 'paid')
        self.assertEqual(self.payslip.state, 'validated', "A payslip removed from the report should stay unpaid.")


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestHrPayrunPaymentReport(TestHrPayslipPaymentReport):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.payslip_run = cls.env['hr.payslip.run'].create({
            'name': 'Test Batch',
            'date_start': date(2025, 1, 1),
            'date_end': date(2025, 1, 31),
            'structure_id': cls.developer_pay_structure.id,
        })
        cls.payslip.payslip_run_id = cls.payslip_run

    def test_payrun_payment_report_fields_and_attachment(self):
        self.payslip_run.action_confirm()
        self.payslip_run.action_validate()

        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.payslip.id],
            'payslip_run_id': self.payslip.payslip_run_id.id,
            'export_format': 'csv',
        })
        wizard.mark_as_paid()

        attachment_count = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'hr.payslip.run'),
            ('res_id', '=', self.payslip_run.id),
            ('res_field', '=', 'payment_report'),
        ])

        self.assertTrue(self.payslip_run.payment_report, "Payrun payment report should be set initially.")
        self.assertTrue(self.payslip_run.payment_report_filename)
        self.assertTrue(self.payslip_run.payment_report_format)
        self.assertTrue(self.payslip_run.payment_report_date)
        self.assertEqual(attachment_count, 1, "Payrun report attachment should exist before clearing.")

        #  Because the payslips are marked as "paid" upon report generation.So, payrun cannot be set to draft
        with self.assertRaises(ValidationError):
            self.payslip_run.action_draft()
