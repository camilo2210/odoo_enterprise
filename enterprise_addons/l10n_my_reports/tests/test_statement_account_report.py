# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools import html2plaintext
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestStatementAccountReport(AccountTestInvoicingCommon):

    def test_report_generation_with_and_without_domain(self):
        """Test that the statement account report can be generated with and without a domain"""
        partner = self.env['res.partner'].create({'name': 'Test Partner'})
        report = self.env.ref('l10n_my_reports.action_report_statement_account')
        result = report._render_qweb_pdf(report.id, partner.ids, data={
            'date_to': '2024-01-01',
            'domain': [('date', '<=', '2024-01-01')],
        })
        self.assertTrue(result, "Report should generate with domain")
        result = report._render_qweb_pdf(report.id, partner.ids, data={
            'date_to': '2024-01-01',
        })
        self.assertTrue(result, "Report should generate without domain")

    def test_total_and_total_overdue_amounts_follow_selected_date(self):
        """Test that Total amount and Total Overdue amounts in the report respect the selected statement date"""
        with freeze_time('2024-02-26'):
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': fields.Date.to_date('2024-02-20'),
                'invoice_line_ids': [Command.create({
                    'name': 'invoice',
                    'quantity': 1,
                    'price_unit': 200.0,
                    'tax_ids': [],
                })],
            })
            invoice.action_post()
            invoice.line_ids.filtered('date_maturity').date_maturity = fields.Date.to_date('2024-02-15')

        for date_to, total, overdue in (
            (fields.Date.to_date('2024-01-31'), 0.0, 0.0),
            (fields.Date.to_date('2024-02-26'), 200.0, 200.0),
        ):
            html = self.env['ir.actions.report']._render_qweb_html(
                'l10n_my_reports.report_statement_account',
                self.partner_a.ids,
                data={'date_to': date_to, 'domain': [('date', '<=', date_to)]},
            )[0]
            text = html2plaintext(html)
            for label, expected_amount in zip(['Total', 'Total Overdue'], [total, overdue]):
                match = re.search(rf'{label}:\*?\n.*?([\d.]+)', text)
                self.assertIsNotNone(match, f"Could not find a {label} value in the text.")
                report_amount = float(match.group(1))
                self.assertAlmostEqual(report_amount, expected_amount, places=2)
