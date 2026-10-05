# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.addons.base.tests.files import PDF_RAW
from odoo.addons.l10n_ph.tests.common import TestPhCommon

PATCH_GENERATE_BILL_CERTIFICATE = 'odoo.addons.l10n_ph_reports.models.bir_2306_2307_report.L10n_Ph2306_2307ReportHandler._l10n_ph_generate_bill_certificate'


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPH23062307VendorBill(TestAccountReportsCommon, TestPhCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('ph')
    def setUpClass(cls):
        super().setUpClass()

        chart_template = cls.env["account.chart.template"].with_company(cls.company_data["company"])
        cls.tax_2307_10 = chart_template.ref('l10n_ph_tax_purchase_10_wi011')
        cls.tax_2306_12 = chart_template.ref('l10n_ph_tax_purchase_12_fwvat_ds')

        cls.report_2306 = cls.env.ref('l10n_ph_reports.2306_report')
        cls.report_2307 = cls.env.ref('l10n_ph_reports.2307_report')

        # Q4 2025: October = 1st month, November = 2nd month, December = 3rd month of the quarter.
        cls.bill_2307_oct = cls._create_bill(cls.partner_a, '2025-10-16', [(1000, cls.tax_2307_10)])
        cls.bill_2307_nov = cls._create_bill(cls.partner_a, '2025-11-16', [(2000, cls.tax_2307_10)])
        cls.bill_2306_oct = cls._create_bill(cls.partner_a, '2025-10-15', [(500, cls.tax_2306_12)])
        cls.bill_both = cls._create_bill(cls.partner_a, '2025-11-10', [(1000, cls.tax_2307_10), (500, cls.tax_2306_12)])
        cls.bill_no_wht = cls._create_bill(cls.partner_a, '2025-10-16', [(1000, cls.env['account.tax'])])
        (cls.bill_2307_oct + cls.bill_2307_nov + cls.bill_2306_oct + cls.bill_both + cls.bill_no_wht).action_post()
        cls.env.company.totals_below_sections = False
        cls.partner_a.invoice_sending_method = 'email'

        # Both taxes are withheld on payment: their journal items only exist once the bill is paid,
        # so every bill carrying one needs an actual payment registered to have anything to certify.
        cls._register_withholding_payment(cls.bill_2307_oct, '2025-10-16')
        cls._register_withholding_payment(cls.bill_2307_nov, '2025-11-16')
        cls._register_withholding_payment(cls.bill_2306_oct, '2025-10-15')
        cls._register_withholding_payment(cls.bill_both, '2025-11-10')

    @classmethod
    def _create_bill(cls, partner, invoice_date, lines):
        return cls.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': invoice_date,
            'partner_id': partner.id,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Test line',
                    'quantity': 1.0,
                    'price_unit': amount,
                    'tax_ids': tax.ids,
                }) for amount, tax in lines
            ],
        })

    @classmethod
    def _register_withholding_payment(cls, move, payment_date):
        """ Pay a bill in full, withholding whatever withholding taxes are set on its lines. """
        payment_register = cls.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=move.ids)\
            .create({'payment_date': payment_date})
        payment_register.withholding_line_ids.name = f'WH{move.id}'
        return payment_register._create_payments()

    def _certificate_options(self, report, move, date_from, date_to):
        """ Build report options scoped to a single move, mirroring AccountMove._l10n_ph_issue_certificate. """
        options = self._generate_options(report, date_from, date_to, default_options={
            'partner_ids': [move.commercial_partner_id],
            'unfold_all': True,
        })
        options['l10n_ph_certificate_move_id'] = move.id
        return options

    @staticmethod
    def _generate_bill_certificate(*args, **kwargs):
        return 'Form_2306_2307.pdf', PDF_RAW

    def _get_mail_message(self, move):
        return self.env['mail.message'].search([('model', '=', move._name), ('res_id', '=', move.id)], limit=1)

    # ------------------------------------------------------------------
    # Per-transaction scoping of the certificate data
    # ------------------------------------------------------------------
    def test_per_move_2307_month_placement(self):
        """ A single November bill (2nd month of the quarter) reports only its own amount, in the 2nd column. """
        options = self._certificate_options(self.report_2307, self.bill_2307_nov, '2025-10-01', '2025-12-31')
        lines = self.report_2307.with_context(l10n_ph_is_certificate_generation=True)._get_lines(options)

        # Partner/certificate line reflects only this bill (2000 @ 10% = 200), not partner_a's other Q4 2307 bills.
        cert_line = next(line for line in lines if line.unfoldable and line.groupby == 'tax_line_id,move_id')
        self.assertLinesValues(
            [cert_line],
            #    Amount of Income Payments, Tax Withheld
            [    1,                         2],
            [[                       2000.0, 200.0]],
            options,
        )
        self.assertEqual(cert_line.custom['first_month_base_total'], 0.0)
        self.assertEqual(cert_line.custom['second_month_base_total'], 2000.0)
        self.assertEqual(cert_line.custom['third_month_base_total'], 0.0)

    def test_per_move_isolation(self):
        """ Scoping to the October bill excludes the November bill from the same partner/quarter. """
        options = self._certificate_options(self.report_2307, self.bill_2307_oct, '2025-10-01', '2025-12-31')
        lines = self.report_2307.with_context(l10n_ph_is_certificate_generation=True)._get_lines(options)

        cert_line = next(line for line in lines if line.unfoldable and line.groupby == 'tax_line_id,move_id')
        self.assertLinesValues([cert_line], [1, 2], [[1000.0, 100.0]], options)
        self.assertEqual(cert_line.custom['first_month_base_total'], 1000.0)
        self.assertEqual(cert_line.custom['second_month_base_total'], 0.0)

    def test_per_move_both_forms_2306_scope(self):
        """ The 2306 section of a mixed bill reports only its final-withholding line, not the 2307 one. """
        options = self._certificate_options(self.report_2306, self.bill_both, '2025-10-01', '2025-12-31')
        lines = self.report_2306.with_context(l10n_ph_is_certificate_generation=True)._get_lines(options)

        cert_line = next(line for line in lines if line.unfoldable and line.groupby == 'tax_line_id,move_id')
        # Only the 12% final-withholding base (500 @ 12% = 60); the 2307 line (1000) is excluded.
        self.assertLinesValues([cert_line], [1, 2], [[500.0, 60.0]], options)

    # ------------------------------------------------------------------
    # Sending the certificate to the vendor
    # ------------------------------------------------------------------
    def test_certificate_exportable(self):
        """A posted PH vendor bill with a withholding tag is eligible and shows the standard Send button."""
        self.assertTrue(self.bill_both.l10n_ph_is_certificate_exportable)
        self.assertTrue(self.bill_both.display_send_button, "Eligible bills show the standard Send button.")

        self.assertFalse(
            self.bill_no_wht.l10n_ph_is_certificate_exportable,
            "Withholding certificate should not be exportable on bills without withholding tags.",
        )
        draft_bill = self._create_bill(self.partner_a, '2025-10-16', [(1000, self.tax_2307_10)])
        self.assertFalse(
            draft_bill.l10n_ph_is_certificate_exportable,
            "Withholding certificate should not be exportable on draft bills.",
        )

    def test_single_send_wizard_defaults(self):
        """The standard Send wizard is preconfigured with the certificate template, vendor recipient, and placeholder attachment."""
        self.partner_a.email = 'vendor@example.com'
        wizard = self._create_account_move_send_wizard_single(self.bill_both)

        self.assertEqual(wizard.template_id, self.env.ref('l10n_ph_reports.mail_template_bir_certificate'))
        self.assertEqual(wizard.mail_partner_ids, self.partner_a)
        placeholder_names = [vals['name'] for vals in wizard.mail_attachments_widget if vals.get('placeholder')]
        self.assertEqual(placeholder_names, [self.bill_both._l10n_ph_get_certificate_filename()])

    @patch(PATCH_GENERATE_BILL_CERTIFICATE, _generate_bill_certificate)
    def test_single_send(self):
        """Sending stores the certificate as the bill's document and emails it to the vendor."""
        self.partner_a.email = 'vendor@example.com'
        wizard = self._create_account_move_send_wizard_single(self.bill_both)
        wizard.action_send_and_print()

        self.assertEqual(self.bill_both.invoice_pdf_report_id.name, 'Form_2306_2307.pdf', "The certificate is the bill's generated document.")
        self.assertTrue(self.bill_both.is_move_sent)
        self.assertIn(self.partner_a, self._get_mail_message(self.bill_both).partner_ids)

    @patch(PATCH_GENERATE_BILL_CERTIFICATE, _generate_bill_certificate)
    def test_batch_send(self):
        """Batch send queues the bills for the standard cron, which emails the certificates."""
        self.partner_a.email = 'vendor@example.com'
        moves = self.bill_2307_oct + self.bill_2306_oct
        action = moves.action_l10n_ph_send_certificates()
        self.assertEqual(action['res_model'], 'account.move.send.batch.wizard')

        wizard = self._create_account_move_send_wizard_multi(moves)
        self.assertTrue(
            all(entry['noun'] == 'certificate(s)' for entry in wizard.summary_data.values()),
            "The batch summary refers to certificates instead of invoices.",
        )
        wizard.action_send_and_print()
        self.assertTrue(all(move.sending_data for move in moves), "Selected bills are queued for the cron.")

        with self.enter_registry_test_mode():
            self.env.ref('account.ir_cron_account_move_send').method_direct_trigger()

        for move in moves:
            self.assertTrue(move.is_move_sent)
            self.assertEqual(move.invoice_pdf_report_id.name, 'Form_2306_2307.pdf')
            self.assertIn(self.partner_a, self._get_mail_message(move).partner_ids)
