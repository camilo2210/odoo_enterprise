from odoo.tests.common import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestTRCustomerStatement(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company.account_fiscal_country_id = cls.env.ref('base.tr')

    def test_customer_statement_reconciliation_letter(self):
        partner = self.partner_a
        partner.lang = 'tr_TR'
        invoice = self.init_invoice(
            "out_invoice",
            partner,
            invoice_date="2026-06-02",
            amounts=[100.0, 200.0],
        )
        invoice.action_post()
        report = self.env.ref('account_reports.customer_statement_report')
        options = report.get_options({
            'partner_ids': partner.ids,
            'report_id': report.id,
        })
        handler = self.env[report.custom_handler_model_name]
        html = handler._get_pdf_export_html(options, report._get_lines(options), additional_context={})
        self.assertIn("Cari Hesap Mutabakat Formu", html)
        self.assertIn("Fatura Sayısı", html)
        self.assertIn("Mutabakat Sonucu:", html)
        self.assertIn("300.00", html)

    def test_customer_statement_uses_tr_mail_template(self):
        report = self.env.ref('account_reports.customer_statement_report')
        handler = self.env[report.custom_handler_model_name]
        options = report.get_options({
            'partner_ids': self.partner_a.ids,
            'report_id': report.id,
        })
        action = handler.action_send_statements(options)
        self.assertEqual(
            action['context']['default_mail_template_id'],
            self.env.ref('l10n_tr_reports.email_template_reconciliation_letter').id,
        )
