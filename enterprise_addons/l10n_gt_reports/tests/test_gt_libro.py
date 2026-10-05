# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install_l10n', 'post_install', '-at_install', *AccountTestInvoicingCommon.extra_tags)
class TestGtLibro(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('gt')
    @AccountTestInvoicingCommon.setup_chart_template('gt')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.l10n_gt_edi_vat_affiliation = 'GEN'
        cls.company.partner_id.write({
            'name': "My GT Company",
            'vat': '11201220K',
        })
        cls.partner_a.write({
            'name': "Empresa Guatemalteca S. A.",
            'vat': '2492334',
            'country_id': cls.env.ref('base.gt').id,
        })
        cls.partner_foreign = cls.env['res.partner'].create({
            'name': "Foreign Buyer",
            'country_id': cls.env.ref('base.us').id,
        })
        # Products and taxes copied from the chart ones so they keep valid accounts.
        cls.goods_product = cls.product_a.copy({'name': "GT Goods", 'type': 'consu'})
        cls.service_product = cls.product_a.copy({'name': "GT Service", 'type': 'service'})
        cls.tax_sale_exempt = cls.tax_sale_a.copy({'name': "IVA Exento", 'amount': 0.0})
        cls.tax_sale_petroleo = cls.tax_sale_a.copy({'name': "IDP", 'amount': 5.0, 'l10n_gt_edi_short_name': 'PETROLEO'})
        cls.report = cls.env.ref('l10n_gt_reports.l10n_gt_libro_report')

    # -- helpers ----------------------------------------------------------------------------

    def _post_doc(self, line_specs, *, move_type='out_invoice', partner=None, ref=None, date='2025-03-15', doc_type=None):
        """ line_specs: list of (product, price_unit, taxes_recordset). """
        vals = {
            'move_type': move_type,
            'partner_id': partner or self.partner_a,
            'invoice_date': date,
            'invoice_line_ids': [Command.create({
                'product_id': product.id,
                'quantity': 1,
                'price_unit': price_unit,
                'tax_ids': [Command.set(taxes.ids)],
            }) for product, price_unit, taxes in line_specs],
        }
        if ref is not None:
            vals['ref'] = ref
        invoice = self._create_invoice(**vals)
        invoice.l10n_gt_edi_doc_type = doc_type or invoice.l10n_gt_edi_doc_type or 'FACT'
        invoice.action_post()
        return invoice

    def _options(self, book='sale', date_from='2025-01-01', date_to='2025-12-31'):
        return self.report.get_options({
            'l10n_gt_libro_book': book,
            'date': {'filter': 'custom', 'mode': 'range', 'date_from': date_from, 'date_to': date_to},
        })

    def _render(self, book='sale', date_from='2025-01-01', date_to='2025-12-31'):
        options = self._options(book, date_from, date_to)
        labels = [col['expression_label'] for col in options['columns']]
        return [
            {label: col.no_format for label, col in zip(labels, line.columns)} | {'name': line.name}
            for line in self.report._get_lines(options)
        ]

    def _render_pdf_html(self, book='sale', date_from='2025-01-01', date_to='2025-12-31'):
        options = self._options(book, date_from, date_to)
        lines = self.report._filter_out_folded_children(self.report._get_lines(options))
        # Route through the handler: it injects the legal header/footer context the template needs.
        handler = self.env['l10n_gt.libro.report.handler']
        return options, str(handler._get_pdf_export_html(options, lines))

    def _pdf_text(self, html):
        """ The rendered text, so the assertions read the printed book rather than its markup. """
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))

    def _summary(self, book='sale', date_from='2025-01-01', date_to='2025-12-31'):
        handler = self.env['l10n_gt.libro.report.handler']
        options = self._options(book, date_from, date_to)
        return handler._l10n_gt_summary_rows(options, self.report._get_lines(options))

    def _assert_single_doc(self, book, invoice, base_bucket, *, transaction='L', specific_type=''):
        """ Assert the book has one detail row + a total row tying back to the invoice, with the
        whole untaxed base landing in ``base_bucket`` and the taxes split IVA vs specific. """
        rows = self._render(book)
        self.assertEqual(len(rows), 2, "expected one detail line and one total line")
        detail, total = rows
        rnd = self.company.currency_id.round
        book_sign = -1.0 if invoice.is_sale_document(include_receipts=True) else 1.0
        refund_sign = -1.0 if invoice.move_type in ('out_refund', 'in_refund') else 1.0

        def tax_total(short_name):
            lines = invoice.line_ids.filtered(lambda line: line.tax_line_id.l10n_gt_edi_short_name == short_name)
            return rnd(book_sign * sum(lines.mapped('balance')))

        base = rnd(refund_sign * invoice.amount_untaxed)
        for bucket in ('taxed_goods', 'taxed_services', 'exempt_goods', 'exempt_services'):
            self.assertEqual(detail[bucket], base if bucket == base_bucket else 0.0, bucket)
        self.assertEqual(detail['vat_amount'], tax_total('IVA'))
        self.assertEqual(detail['specific_tax_subtotal'], base if specific_type else 0.0, 'specific_tax_subtotal')
        self.assertEqual(detail['specific_tax_amount'], tax_total('PETROLEO'))
        self.assertEqual(detail['amount_total'], rnd(refund_sign * invoice.amount_total))
        self.assertEqual(detail['transaction_type'], transaction)
        self.assertEqual(detail['specific_tax_type'], specific_type)
        self.assertEqual(total['amount_total'], rnd(refund_sign * invoice.amount_total))
        return detail

    # -- tests ------------------------------------------------------------------------------

    def test_libro_ventas_goods_taxable(self):
        invoice = self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        detail = self._assert_single_doc('sale', invoice, 'taxed_goods')
        self.assertEqual(detail['id_type'], 'NIT')
        self.assertEqual(detail['doc_type'], 'FACT')

    def test_libro_ventas_id_type_cui(self):
        """ A customer booked under their CUI rather than a NIT is reported as such. """
        partner_cui = self.env['res.partner'].create({
            'name': "Ciudadano Guatemalteco",
            'country_id': self.env.ref('base.gt').id,
            'additional_identifiers': {'GT_CUI': '1234567890101'},
        })
        invoice = self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)], partner=partner_cui)
        detail = self._assert_single_doc('sale', invoice, 'taxed_goods')
        self.assertEqual(detail['id_type'], 'CUI')

    def test_libro_ventas_exempt_goods(self):
        invoice = self._post_doc([(self.goods_product, 1000.0, self.tax_sale_exempt)])
        detail = self._assert_single_doc('sale', invoice, 'exempt_goods')
        self.assertEqual(detail['vat_amount'], 0.0)

    def test_libro_ventas_services(self):
        invoice = self._post_doc([(self.service_product, 800.0, self.tax_sale_a)])
        self._assert_single_doc('sale', invoice, 'taxed_services')

    def test_libro_ventas_specific_tax(self):
        invoice = self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a | self.tax_sale_petroleo)])
        detail = self._assert_single_doc('sale', invoice, 'taxed_goods', specific_type='IDP')
        self.assertGreater(detail['specific_tax_amount'], 0.0)

    def test_libro_ventas_export_transaction(self):
        invoice = self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)], partner=self.partner_foreign)
        detail = self._assert_single_doc('sale', invoice, 'taxed_goods', transaction='E')
        self.assertEqual(detail['id_type'], '', "a foreign customer has neither a NIT nor a CUI")

    def test_libro_ventas_credit_note(self):
        invoice = self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)], move_type='out_refund')
        detail = self._assert_single_doc('sale', invoice, 'taxed_goods')
        self.assertLess(detail['amount_total'], 0.0, "credit notes read negative")

    def test_libro_ventas_mixed_goods_services(self):
        """ One document with a goods line and a services line yields a single row that fills
        both the goods and the services buckets (the per-move multi-bucket aggregation). """
        invoice = self._post_doc([
            (self.goods_product, 1000.0, self.tax_sale_a),
            (self.service_product, 500.0, self.tax_sale_a),
        ])
        detail = self._render('sale')[0]
        self.assertGreater(detail['taxed_goods'], 0.0)
        self.assertGreater(detail['taxed_services'], 0.0)
        self.assertAlmostEqual(detail['taxed_goods'] + detail['taxed_services'], invoice.amount_untaxed, places=2)
        self.assertEqual(detail['amount_total'], invoice.amount_total)

    def test_libro_compras_ref_split(self):
        invoice = self._post_doc([(self.goods_product, 1000.0, self.tax_purchase_a)], move_type='in_invoice', ref='ABC-998877')
        detail = self._assert_single_doc('purchase', invoice, 'taxed_goods')
        self.assertEqual(detail['fel_series'], 'ABC')
        self.assertEqual(detail['fel_number'], '998877')

    def test_libro_compras_import_transaction(self):
        invoice = self._post_doc([(self.goods_product, 1000.0, self.tax_purchase_a)], move_type='in_invoice', partner=self.partner_foreign, ref='X-1')
        self._assert_single_doc('purchase', invoice, 'taxed_goods', transaction='I')

    def test_book_filter_separates_sales_and_purchases(self):
        """ The Tax Type option scopes the book: sales show only under Sales, purchases only under
        Purchases. Receipts are FEL documents too, so each book lists them next to its invoices. """
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)], move_type='out_receipt')
        self._post_doc([(self.goods_product, 1000.0, self.tax_purchase_a)], move_type='in_invoice', ref='ABC-1')
        self._post_doc([(self.goods_product, 1000.0, self.tax_purchase_a)], move_type='in_receipt', ref='ABC-2')
        self.assertEqual(len(self._render('sale')), 3)      # 2 sales + total
        self.assertEqual(len(self._render('purchase')), 3)  # 2 purchases + total

    def test_excludes_cancelled(self):
        """ Cancelling a document keeps it out of the book (the report filter is posted-only). """
        invoice = self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        invoice.button_cancel()
        self.assertEqual(invoice.state, 'cancel')
        self.assertEqual(self._render('sale'), [])

    def test_empty_period(self):
        self.assertEqual(self._render('sale', '2099-01-01', '2099-12-31'), [])

    def test_pdf_sales_legal_layout(self):
        """ The printed sales book opens on the legal header (book title, tax identification and
        period) and closes on the document count and total tax debit. """
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        _options, html = self._render_pdf_html('sale')
        text = self._pdf_text(html)
        self.assertIn("Sales Book", text)               # report title
        self.assertIn("11201220K", text)                # company NIT
        self.assertIn("My GT Company", text)            # trade name
        # Formatted like the framework formats the Date column, so both follow the language (en_US
        # in tests, dd/MM/yyyy in the es_419 the book is filed in).
        self.assertIn("01/01/2025 to 12/31/2025", text)
        self.assertIn("Quetzales (Q)", text)
        self.assertIn("Number of documents:", text)
        self.assertIn("Total tax debit:", text)

    def test_pdf_purchase_legal_layout(self):
        """ The purchase book swaps to its own legal title and closing figure. """
        _options, html = self._render_pdf_html('purchase')
        text = self._pdf_text(html)
        self.assertIn("Purchases and Received Services Book", text)
        self.assertIn("Total tax credit:", text)

    def test_rounding_unit_repaint_keeps_transaction_type_words(self):
        """ The rounding-unit filter does not rebuild the lines: it strips every cell to its raw
        values and has format_column_values_from_client regenerate the names, which would revert
        the transaction type to its single-letter code without the handler override. """
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        options = self._options('sale')
        client_keys = {'no_format', 'figure_type', 'format_params', 'is_zero', 'blank_if_zero'}
        client_lines = [
            {
                'unfolded': bool(line.unfolded),
                'columns': [
                    {key: value for key, value in column.as_dict().items() if key in client_keys}
                    for column in line.columns
                ],
            }
            for line in self.report._get_lines(options)
        ]
        formatted = self.report.dispatch_report_action(options, 'format_column_values_from_client', client_lines)
        labels = [column['expression_label'] for column in options['columns']]
        detail = formatted[0]
        self.assertEqual(detail.columns[labels.index('transaction_type')].name, "Local")
        self.assertTrue(detail.columns[labels.index('amount_total')].name)

    def test_pdf_hides_specific_tax_columns_when_unused(self):
        """ When no document in the book carries a specific tax, the PDF drops the three
        specific-tax detail columns and the summary's specific-tax column. """
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        _options, html = self._render_pdf_html('sale')
        self.assertNotIn("Specific Tax", html)

    def test_pdf_keeps_specific_tax_columns_when_used(self):
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a | self.tax_sale_petroleo)])
        _options, html = self._render_pdf_html('sale')
        self.assertIn("Specific Tax Type", html)
        self.assertIn("Specific Tax Subtotal", html)
        self.assertIn("Specific Tax Amount", html)
        self.assertIn("IDP", html)

    def test_csv_keeps_specific_tax_columns_when_unused(self):
        """ The CSV is a data export: it keeps the specific-tax columns even when they are empty
        (only the PDF hides them). """
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        options = self._options('sale')
        result = self.report.dispatch_report_action(options, 'l10n_gt_libro_export_to_csv')
        content = result['file_content'].decode('utf-8-sig')
        self.assertIn("Specific Tax Type", content)
        self.assertIn("Specific Tax Subtotal", content)

    def test_csv_export(self):
        """ The CSV button (routed through dispatch_report_action like the real download) yields the
        legal header, then the detail grid (header + one row per document + totals), then the
        summary. """
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        options = self._options('sale')
        result = self.report.dispatch_report_action(options, 'l10n_gt_libro_export_to_csv')
        self.assertEqual(result['file_type'], 'csv')
        content = result['file_content'].decode('utf-8-sig')
        lines = content.splitlines()
        # The legal header sits above the detail grid (the book title, then the company identification).
        self.assertIn("Sales Book", lines[0], "the book title is the first row")
        self.assertIn("Tax ID Number", content)
        self.assertIn("Fiscal Address", content)
        self.assertIn("Goods Taxable", content, "the detail header is written")
        self.assertIn("Total", content, "the detail totals row is written")
        # The summary is appended below the detail grid (same data as the PDF).
        self.assertIn("Summary", content)
        self.assertIn("Number of documents:", content)
        self.assertIn("Goods Local", content)

    def test_no_xlsx_export_button(self):
        """ The book ships PDF + CSV only; the framework's generic XLSX export (which would bypass
        the summary) is removed from the export buttons. """
        options = self._options('sale')
        action_params = {button.get('action_param') for button in options['buttons']}
        self.assertNotIn('export_to_xlsx', action_params, "the XLSX button is dropped")
        self.assertIn('l10n_gt_libro_export_to_csv', action_params, "the CSV button is present")

    def test_summary_buckets(self):
        """ Summary: a local goods sale and a foreign services sale land in the matching
        Goods Local and Services Foreign rows. """
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        self._post_doc([(self.service_product, 1000.0, self.tax_sale_a)], partner=self.partner_foreign)
        rows, _total = self._summary('sale')
        labels = {row['label'] for row in rows}
        self.assertIn("Goods Local", labels)
        self.assertIn("Services Foreign", labels)
        self.assertNotIn("Small Taxpayer (FPEQ/FCAP)", labels, "all-zero rows are hidden")

    def test_summary_mixed_doc_splits_vat(self):
        """ A mixed goods+services document splits its VAT between the Goods and Services rows
        proportionally to the taxable base (equal bases -> equal VAT). """
        invoice = self._post_doc([
            (self.goods_product, 1000.0, self.tax_sale_a),
            (self.service_product, 1000.0, self.tax_sale_a),
        ])
        rows, _total = self._summary('sale')
        goods = next(row for row in rows if row['label'] == "Goods Local")
        services = next(row for row in rows if row['label'] == "Services Local")
        goods_vat = float(goods['vat'].replace(',', ''))
        services_vat = float(services['vat'].replace(',', ''))
        self.assertGreater(goods_vat, 0.0)
        self.assertGreater(services_vat, 0.0)
        # The whole document VAT is allocated across the two rows; nothing is lost.
        self.assertEqual(round(goods_vat + services_vat, 2), self.company.currency_id.round(invoice.amount_tax))

    def test_summary_small_taxpayer_row(self):
        """ FPEQ/FCAP documents land wholly in the Small Taxpayer row, not in Goods/Services. """
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)], doc_type='FPEQ')
        rows, _total = self._summary('sale')
        labels = {row['label'] for row in rows}
        self.assertIn("Small Taxpayer (FPEQ/FCAP)", labels)
        self.assertNotIn("Goods Local", labels)

    def test_pdf_summary_table_rendered(self):
        """ The Summary table is part of the printed book. """
        self._post_doc([(self.goods_product, 1000.0, self.tax_sale_a)])
        _options, html = self._render_pdf_html('sale')
        self.assertIn("Summary", html)
        self.assertIn("Goods Local", html)
