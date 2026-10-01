# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nDo606Export(TestAccountReportsCommon):
    """ 606 export for a DO company without e-CF: the NCF is the move reference.

    Whether DO journals use LATAM fiscal documents depends on `l10n_do_edi`
    being installed: it is what overrides `_localization_use_documents` for
    DO. `l10n_do_reports` doesn't depend on it, so both configurations reach
    the 606, and `_l10n_do_get_ncf` reads the NCF off a different field in
    each. Pin the flag rather than inherit it from the installed modules, or
    the outcome silently follows the build's module set.

    `TestL10nDo606ExportWithDocuments` re-runs everything below with
    documents enabled.
    """

    l10n_do_use_documents = False

    @classmethod
    @TestAccountReportsCommon.setup_country('do')
    def setUpClass(cls):
        super().setUpClass()

        cls._l10n_do_set_use_documents(cls.company_data['default_journal_purchase'])

        cls.report = cls.env.ref('account_reports.journal_report')
        cls.handler = cls.env['account.journal.report.handler']
        cls.company_data['company'].vat = '131243932'

        cls.partner_rnc = cls.env['res.partner'].create({
            'name': 'RNC Vendor',
            'vat': '111222338',
            'country_id': cls.env.ref('base.do').id,
        })
        cls.partner_cedula = cls.env['res.partner'].create({
            'name': 'Cédula Vendor',
            'additional_identifiers': {'DO_CEDULA': '00113918205'},
            'country_id': cls.env.ref('base.do').id,
        })
        cls.partner_foreign = cls.env['res.partner'].create({
            'name': 'Foreign Vendor',
            'vat': 'BE0477472701',
            'country_id': cls.env.ref('base.be').id,
        })

        chart_template = cls.env['account.chart.template'].with_company(cls.company_data['company'])
        cls.tax_18_purch = chart_template.ref('tax_18_purch')
        cls.tax_18_purch_serv = chart_template.ref('tax_18_purch_serv')
        cls.ret_100_tax_person = chart_template.ref('ret_100_tax_person')
        cls.ret_10_income_person = chart_template.ref('ret_10_income_person')
        cls.tax_isc = chart_template.ref('tax_10_telco')
        cls.tax_tip = chart_template.ref('tax_tip_purch')

        cls.product_good = cls.env['product.product'].create({'name': 'Good', 'type': 'consu'})
        cls.product_service = cls.env['product.product'].create({'name': 'Service', 'type': 'service'})

    @classmethod
    def _l10n_do_set_use_documents(cls, journal):
        journal.l10n_latam_use_documents = cls.l10n_do_use_documents

    @classmethod
    def _l10n_do_ncf_vals(cls, ref):
        """ Values carrying the NCF, on whichever field `_l10n_do_get_ncf` reads. """
        if cls.l10n_do_use_documents:
            return {'l10n_latam_document_number': ref}
        return {'ref': ref}

    @classmethod
    def _create_vendor_bill(cls, partner, invoice_lines, move_type='in_invoice', ref='B0100000001', post=True):
        move = cls.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': fields.Date.from_string('2024-04-14'),
            'date': fields.Date.from_string('2024-04-14'),
            **cls._l10n_do_ncf_vals(ref),
            'invoice_line_ids': [
                Command.create({
                    'product_id': product.id,
                    'price_unit': price,
                    'quantity': 1,
                    'tax_ids': [Command.set(taxes.ids)],
                })
                for product, price, taxes in invoice_lines
            ],
        })
        if post:
            move.action_post()
        return move

    @classmethod
    def _create_reversal(cls, bill, ref='B0400000001'):
        values = {
            'invoice_date': fields.Date.from_string('2024-04-20'),
            # Pin the accounting date: left out, `_get_accounting_date` pushes it
            # to the end of the month, since the invoice date is in the past.
            'date': fields.Date.from_string('2024-04-20'),
        }
        if cls.l10n_do_use_documents:
            values['l10n_latam_document_type_id'] = cls.env.ref('l10n_do.ecf_34').id
        reversal = bill._reverse_moves([values])
        reversal.write(cls._l10n_do_ncf_vals(ref))
        reversal.action_post()
        return reversal

    def _get_rows(self, moves):
        return self.handler._l10n_do_get_606_rows(moves)

    def test_606_bill_goods_and_services(self):
        bill = self._create_vendor_bill(self.partner_rnc, [
            (self.product_service, 2000.0, self.tax_18_purch_serv),
            (self.product_good, 6000.0, self.tax_18_purch),
        ])
        rows = self._get_rows(bill)
        self.assertEqual(rows, [[
            '111222338', '1', '09', 'B0100000001', '',
            '20240414', '',
            '2000.00', '6000.00', '8000.00',
            '1440.00',  # 18% of 8000
            '', '', '', '1440.00', '',
            '', '', '', '', '', '',
            '02',
        ]])

    def test_606_bill_withholdings(self):
        # 1000 services from an individual: +180 ITBIS, -180 ITBIS withheld (R293-11), -100 ISR fees
        bill = self._create_vendor_bill(self.partner_cedula, [
            (self.product_service, 1000.0, self.tax_18_purch_serv + self.ret_100_tax_person + self.ret_10_income_person),
        ])
        rows = self._get_rows(bill)
        row = rows[0]
        self.assertEqual(row[0], '00113918205')  # the Cédula is reported instead of an RNC
        self.assertEqual(row[1], '2')  # Cédula
        self.assertEqual(row[7], '1000.00')  # services
        self.assertEqual(row[10], '180.00')  # ITBIS invoiced
        self.assertEqual(row[11], '180.00')  # ITBIS withheld
        self.assertEqual(row[16], '02')  # ISR type: service fees, zero-padded
        self.assertEqual(row[17], '100.00')  # ISR withheld

    def test_606_credit_note(self):
        bill = self._create_vendor_bill(self.partner_rnc, [(self.product_good, 1000.0, self.tax_18_purch)])
        reversal = self._create_reversal(bill)
        rows = self._get_rows(reversal)
        row = rows[0]
        self.assertEqual(row[3], 'B0400000001')  # NCF
        self.assertEqual(row[4], 'B0100000001')  # modified NCF
        self.assertEqual(row[8], '1000.00')  # goods, reported positive
        self.assertEqual(row[10], '180.00')  # ITBIS, reported positive

    def test_606_credit_note_payment_date_left_empty(self):
        """ Credit notes must not report a Fecha Pago: their reconciliation points
        back to the original invoice, so the "payment" date would precede the NCF
        date and be rejected by DGII. The invoice side keeps reporting it.
        """
        bill = self._create_vendor_bill(self.partner_rnc, [(self.product_good, 1000.0, self.tax_18_purch)])
        reversal = self._create_reversal(bill)
        payable_lines = (bill + reversal).line_ids.filtered(
            lambda line: line.account_id.account_type == 'liability_payable'
        )
        self.assertTrue(all(payable_lines.mapped('reconciled')), "posting the reversal reconciles it with the bill")

        self.assertEqual(self._get_rows(reversal)[0][6], '', "the credit note must leave Fecha Pago empty")
        self.assertEqual(self._get_rows(bill)[0][6], '20240420', "the bill still reports its payment date")

    def test_606_isc_and_tip(self):
        bill = self._create_vendor_bill(self.partner_rnc, [
            (self.product_service, 1000.0, self.tax_18_purch_serv + self.tax_isc + self.tax_tip),
        ])
        rows = self._get_rows(bill)
        row = rows[0]
        self.assertEqual(row[19], '100.00')  # ISC 10%
        self.assertEqual(row[21], '100.00')  # tip 10%

    def test_606_foreign_vendor_excluded(self):
        bill = self._create_vendor_bill(self.partner_foreign, [(self.product_good, 1000.0, self.tax_18_purch)])
        self.assertEqual(self._get_rows(bill), [])

    def test_606_payment_date(self):
        bill = self._create_vendor_bill(self.partner_rnc, [(self.product_good, 1000.0, self.tax_18_purch)])
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=bill.ids,
        ).create({'payment_date': '2024-04-15'})._create_payments()
        self.assertTrue(payment)
        row = self._get_rows(bill)[0]
        self.assertEqual(row[6], '20240415')

    def test_606_txt_export(self):
        self._create_vendor_bill(self.partner_rnc, [(self.product_good, 1000.0, self.tax_18_purch)])
        options = self._generate_options(self.report, '2024-04-01', '2024-04-30')
        self.assertTrue(any(button['action_param'] == 'l10n_do_export_606_to_txt' for button in options['buttons']))
        export = self.handler.l10n_do_export_606_to_txt(options)
        self.assertEqual(export['file_name'], 'DGII_F_606_131243932_202404.TXT')
        self.assertEqual(export['file_type'], 'txt')
        # No trailing CRLF after the last line: don't strip() before splitting,
        # or a regression in that behavior would go unnoticed.
        lines = export['file_content'].decode().split('\r\n')
        self.assertEqual(lines[0], '606|131243932|202404|1')
        self.assertEqual(len(lines), 2, "header + a single detail line, no trailing empty line")
        fields = lines[1].split('|')
        self.assertEqual(fields[:4], ['111222338', '1', '09', 'B0100000001'])
        self.assertEqual(fields[-1], '02', "Forma de Pago is zero-padded")

    def test_606_warning_period_not_month(self):
        """ The 606 is filed per calendar month: any other period raises a
        non-blocking warning on the report.
        """
        warning = 'l10n_do_reports.warning_606_period_not_month'
        for date_from, date_to, expected in (
            ('2024-04-01', '2024-04-30', False),  # single month: no warning
            ('2024-04-01', '2024-06-30', True),   # quarter
            ('2024-01-01', '2024-12-31', True),   # year
            ('2024-04-10', '2024-05-09', True),   # custom range not matching a month
        ):
            with self.subTest(date_from=date_from, date_to=date_to):
                options = self._generate_options(self.report, date_from, date_to)
                warnings = self.report.get_report_information(options)['warnings']
                self.assertEqual(warning in warnings, expected)

    def test_606_export_is_per_company(self):
        """ The 606 is filed per company: with several DO companies selected in
        the report options, the export only carries the active company's moves,
        under the active company's RNC (no cross-company aggregation).
        """
        # Active company: the only bill expected in the export.
        self._create_vendor_bill(self.partner_rnc, [(self.product_good, 1000.0, self.tax_18_purch)])

        # A second DO company with its own period bill, which must be excluded.
        company_data_2 = self.setup_other_company(name='DO Company 2')
        company_2 = company_data_2['company']
        self._l10n_do_set_use_documents(company_data_2['default_journal_purchase'])
        tax_18_purch_2 = self.env['account.chart.template'].with_company(company_2).ref('tax_18_purch')
        self.env['account.move'].with_company(company_2).create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_rnc.id,
            'invoice_date': fields.Date.from_string('2024-04-14'),
            'date': fields.Date.from_string('2024-04-14'),
            **self._l10n_do_ncf_vals('B0100009999'),
            'invoice_line_ids': [Command.create({
                'product_id': self.product_good.id,
                'price_unit': 5000.0,
                'quantity': 1,
                'tax_ids': [Command.set(tax_18_purch_2.ids)],
            })],
        }).action_post()

        # Both companies selected in the multi-company selector.
        report = self.report.with_context(
            allowed_company_ids=[self.company_data['company'].id, company_2.id],
        )
        options = self._generate_options(report, '2024-04-01', '2024-04-30')
        self.assertEqual(len(options['companies']), 2, "both companies are selected in the options")

        export = self.handler.l10n_do_export_606_to_txt(options)
        # Filed under the active company's RNC, with only its single row.
        self.assertEqual(export['file_name'], 'DGII_F_606_131243932_202404.TXT')
        lines = export['file_content'].decode().split('\r\n')
        self.assertEqual(lines[0], '606|131243932|202404|1')
        self.assertEqual(len(lines), 2, "the second company's bill must not be exported")
        self.assertTrue(lines[1].startswith('111222338|1|09|B0100000001'))


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nDo606ExportWithDocuments(TestL10nDo606Export):
    """ Same assertions for a DO company running e-CF (`l10n_do_edi`
    installed): the NCF is the LATAM fiscal document number instead.
    """

    # the tests all live on the base class
    allow_inherited_tests_method = True
    l10n_do_use_documents = True
