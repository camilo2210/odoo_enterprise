from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nVnTaxReport(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('vn')
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_a.write({
            'country_id': cls.env.ref('base.vn').id,
            'vat': '0123456789',
        })
        cls.partner_b.write({
            'country_id': cls.env.ref('base.vn').id,
            'vat': '9876543210',
        })

        cls.tax_report = cls.env.ref('l10n_vn.form_01_gtgt_report')
        cls.appendix142_report = cls.env.ref('l10n_vn_reports.appendix_142_report')

        cls.sales_report = cls.env.ref('l10n_vn_reports.sales_tax_report')
        cls.purchase_report = cls.env.ref('l10n_vn_reports.purchase_tax_report')

        company_id = cls.company_data['company'].id
        cls.tax_sale_10 = cls.env.ref(f'account.{company_id}_tax_sale_vat10')
        cls.tax_sale_5 = cls.env.ref(f'account.{company_id}_tax_sale_vat5')
        cls.tax_purchase_10 = cls.env.ref(f'account.{company_id}_tax_purchase_vat10')
        cls.tax_purchase_5 = cls.env.ref(f'account.{company_id}_tax_purchase_vat5')
        cls.tax_purchase_import_10 = cls.env.ref(f'account.{company_id}_tax_purchase_import_vat10')
        cls.tax_sale_8 = cls.env.ref(f'account.{company_id}_tax_sale_vat8')
        cls.tax_purchase_8 = cls.env.ref(f'account.{company_id}_tax_purchase_vat8')
        cls.tax_purchase_import_8 = cls.env.ref(f'account.{company_id}_tax_purchase_import_vat8')

    @freeze_time('2024-06-30')
    def test_sales_tax_report(self):
        """ Test that the sales tax report correctly generates and aggregates invoice data. """
        # Create invoices with different tax rates
        self.env['account.move'].create([
            {
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': '2024-06-15',
                'invoice_line_ids': [
                    Command.create({
                        'name': 'Product A',
                        'quantity': 1,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(self.tax_sale_10.ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'partner_id': self.partner_b.id,
                'invoice_date': '2024-06-20',
                'invoice_line_ids': [
                    Command.create({
                        'name': 'Product B',
                        'quantity': 1,
                        'price_unit': 500.0,
                        'tax_ids': [Command.set(self.tax_sale_5.ids)],
                    }),
                ],
            },
        ]).action_post()

        options = self._generate_options(self.sales_report, '2024-06-01', '2024-06-30', {'unfold_all': True})

        self.assertLinesValues(
            self.sales_report._get_lines(options),
            #   Name,                                            Invoice Number, Invoice Date,    Customer,       Tax ID,   Description, Untaxed Amount,  VAT Amount
            [      0,                                                         1,            2,           3,            4,             5,              6,          7],
            [
             ('June 2024',                                                   '',           '',          '',           '',            '',             '',         ''),
                 ('VAT on sales of goods and services 0%',                   '',           '',          '',           '',            '',             '',         ''),
                     ('Total VAT on sales of goods and services 0%',         '',           '',          '',           '',            '',             '',         ''),
                 ('VAT on sales of goods and services 5%',                   '',           '',          '',           '',            '',          500.0,       25.0),
                     ('INV/2024/00002',                                      '', '06/20/2024', 'partner_b', '9876543210',            '',          500.0,       25.0),
                         ('VAT Payable 5%',                                  '',           '',          '',           '',            '',          500.0,       25.0),
                     ('Total INV/2024/00002',                                '', '06/20/2024', 'partner_b', '9876543210',            '',          500.0,       25.0),
                 ('Total VAT on sales of goods and services 5%',             '',           '',          '',           '',            '',          500.0,       25.0),
                 ('VAT on sales of goods and services 8%',                   '',           '',          '',           '',            '',             '',         ''),
                     ('Total VAT on sales of goods and services 8%',         '',           '',          '',           '',            '',             '',         ''),
                 ('VAT on sales of goods and services 10%',                  '',           '',          '',           '',            '',         1000.0,      100.0),
                     ('INV/2024/00001',                                      '', '06/15/2024', 'partner_a', '0123456789',            '',         1000.0,      100.0),
                         ('VAT Payable 10%',                                 '',           '',          '',           '',            '',         1000.0,      100.0),
                     ('Total INV/2024/00001',                                '', '06/15/2024', 'partner_a', '0123456789',            '',         1000.0,      100.0),
                 ('Total VAT on sales of goods and services 10%',            '',           '',          '',           '',            '',         1000.0,      100.0),
                 ('VAT Exemption on sales of goods and services',            '',           '',          '',           '',            '',             '',         ''),
                     ('Total VAT Exemption on sales of goods and services',  '',           '',          '',           '',            '',             '',         ''),
                 ('Grand Total',                                             '',           '',          '',           '',            '',         1500.0,      125.0),
            ],
            options,
        )

    @freeze_time('2024-06-30')
    def test_purchase_tax_report(self):
        """ Test that the purchase tax report correctly generates and aggregates vendor bill data. """
        # Create vendor bills with different tax rates
        self.env['account.move'].create([
            {
                'move_type': 'in_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': '2024-06-15',
                'invoice_line_ids': [
                    Command.create({
                        'name': 'Service A',
                        'quantity': 2,
                        'price_unit': 500.0,
                        'tax_ids': [Command.set(self.tax_purchase_10.ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'partner_id': self.partner_b.id,
                'invoice_date': '2024-06-20',
                'invoice_line_ids': [
                    Command.create({
                        'name': 'Service B',
                        'quantity': 1,
                        'price_unit': 300.0,
                        'tax_ids': [Command.set(self.tax_purchase_5.ids)],
                    }),
                ],
            },
        ]).action_post()

        options = self._generate_options(self.purchase_report, '2024-06-01', '2024-06-30', {'unfold_all': True})
        self.assertLinesValues(
            self.purchase_report._get_lines(options),
            #   Name,                                                Invoice Number, Invoice Date,    Customer,       Tax ID,   Description, Untaxed Amount,  VAT Amount
            [      0,                                                             1,            2,           3,            4,             5,              6,          7],
            [
             ('June 2024',                                                       '',           '',          '',           '',            '',             '',         ''),
                 ('VAT on purchase of goods and services 0%',                    '',           '',          '',           '',            '',             '',         ''),
                     ('Total VAT on purchase of goods and services 0%',          '',           '',          '',           '',            '',             '',         ''),
                 ('VAT on purchase of goods and services 5%',                    '',           '',          '',           '',            '',          300.0,       15.0),
                     ('BILL/2024/06/0002',                                       '', '06/20/2024', 'partner_b', '9876543210',            '',          300.0,       15.0),
                         ('Deductible VAT 5%',                                   '',           '',          '',           '',            '',          300.0,       15.0),
                     ('Total BILL/2024/06/0002',                                 '', '06/20/2024', 'partner_b', '9876543210',            '',          300.0,       15.0),
                 ('Total VAT on purchase of goods and services 5%',              '',           '',          '',           '',            '',          300.0,       15.0),
                 ('VAT on purchase of goods and services 8%',                    '',           '',          '',           '',            '',             '',         ''),
                     ('Total VAT on purchase of goods and services 8%',          '',           '',          '',           '',            '',             '',         ''),
                 ('VAT on purchase of goods and services 10%',                   '',           '',          '',           '',            '',         1000.0,      100.0),
                     ('BILL/2024/06/0001',                                       '', '06/15/2024', 'partner_a', '0123456789',            '',         1000.0,      100.0),
                         ('Deductible VAT 10%',                                  '',           '',          '',           '',            '',         1000.0,      100.0),
                     ('Total BILL/2024/06/0001',                                 '', '06/15/2024', 'partner_a', '0123456789',            '',         1000.0,      100.0),
                 ('Total VAT on purchase of goods and services 10%',             '',           '',          '',           '',            '',         1000.0,      100.0),
                 ('VAT on Purchase of Goods and Services Tax Exempt',            '',           '',          '',           '',            '',             '',         ''),
                     ('Total VAT on Purchase of Goods and Services Tax Exempt',  '',           '',          '',           '',            '',             '',         ''),
                 ('Grand Total',                                                 '',           '',          '',           '',            '',         1300.0,      115.0),
            ],
            options,
        )

    @freeze_time('2025-10-31')
    def test_vn_tax_report(self):
        invoice_vals = [
            {'type': 'in_invoice', 'date': '2025-10-12', 'price': 5000000, 'tax': [self.tax_purchase_5.id]},
            {'type': 'in_invoice', 'date': '2025-10-15', 'price': 15000000, 'tax': [self.tax_purchase_10.id]},

            # laptop (no import duty)
            {'type': 'in_invoice', 'date': '2025-10-12', 'price': 80000000, 'tax': []},
            {'type': 'in_invoice', 'date': '2025-10-12', 'price': 80000000, 'tax': [self.tax_purchase_import_10.id]},
            # cosmetics (20% import duty)
            {'type': 'in_invoice', 'date': '2025-10-15', 'price': 200000000, 'tax': []},
            # Base amount is product price + 20% import duty, import tax is applied on the total
            {'type': 'in_invoice', 'date': '2025-10-15', 'price': 240000000, 'tax': [self.tax_purchase_import_10.id]},

            {'type': 'out_invoice', 'date': '2025-10-10', 'price': 20000000, 'tax': [self.tax_sale_10.id]},
        ]
        for move in invoice_vals:
            self._create_invoice(
                move_type=move['type'],
                invoice_date=move['date'],
                post=True,
                invoice_line_ids=[self._prepare_invoice_line(price_unit=move['price'], tax_ids=move['tax'], quantity=1)],
            )

        options = self._generate_options(self.tax_report, '2025-10-01', '2025-10-31')
        lines = self.tax_report._get_lines(options)
        self.assertLinesValues(
            lines,
            # Name                                                                                                                                                              Code,    Untaxed Amount,               Code,     VAT Amount
            [0,                                                                                                                                                                    1,                 2,                  3,              4],
            [
                ('A. No transactions occurred within the period (marked "X")',                                                                                                '[21]',                '',                 '',             ''),
                ('B. Deductible VAT carried forward from the previous period',                                                                                                    '',                '',             '[22]',           0.00),
                ('C. VAT declaration payable to the State\'s budget',                                                                                                             '',                '',                 '',             ''),
                ('I. Purchased Goods and Services during the period',                                                                                                             '',                '',                 '',             ''),
                ('1. Untaxed amount and VAT amount of purchased Goods and Services',                                                                                          '[23]',      340000000.00,             '[24]',    33750000.00),
                    ('Including: imported Goods and Services',                                                                                                               '[23a]',      320000000.00,            '[24a]',    32000000.00),
                ('Total 1. Untaxed amount and VAT amount of purchased Goods and Services',                                                                                    '[23]',      340000000.00,             '[24]',    33750000.00),
                ('2. VAT amount of goods and services subject to be deductible this period',                                                                                      '',                '',             '[25]',    33750000.00),
                ('II. Sold Goods and Services during the period',                                                                                                                 '',                '',                 '',             ''),
                ('1. Sold Goods and Services not subjected to VAT',                                                                                                           '[26]',              0.00,                 '',             ''),
                ('2. Sold Goods and Services subjected to VAT ([27]=[29]+[30]+[32]+[32a]; [28]=[31]+[33])',                                                                   '[27]',       20000000.00,             '[28]',     2000000.00),
                    ('a. Sold Goods and Services subjected to 0% VAT',                                                                                                        '[29]',              0.00,                 '',             ''),
                    ('b. Sold Goods and Services subjected to 5% VAT',                                                                                                        '[30]',              0.00,             '[31]',           0.00),
                    ('c. Sold Goods and Services subjected to 10% VAT',                                                                                                       '[32]',       20000000.00,             '[33]',     2000000.00),
                    ('d. Sold Goods and Services not required to declaird and pay VAT',                                                                                      '[32a]',              0.00,                 '',             ''),
                ('Total 2. Sold Goods and Services subjected to VAT ([27]=[29]+[30]+[32]+[32a]; [28]=[31]+[33])',                                                             '[27]',       20000000.00,             '[28]',     2000000.00),
                ('3. Total revenue and VAT amount on sold Goods and Services ([34]=[26]+[27]; [35]=[28])',                                                                    '[34]',       20000000.00,             '[35]',     2000000.00),
                ('III. VAT amount incurred in the period ([36]=[35]-[25])',                                                                                                       '',                '',             '[36]',   -31750000.00),
                ('IV. Increase and Decrease Adjustment of deductible VAT amount in the previous period',                                                                          '',                '',                 '',             ''),
                ('1. Decrease Adjustment',                                                                                                                                        '',                '',             '[37]',           0.00),
                ('2. Increase Adjustment',                                                                                                                                        '',                '',             '[38]',           0.00),
                ('V. Handover of deductible VAT amount in the period',                                                                                                            '',                '',            '[39a]',           0.00),
                ('VI. Determination of deductible VAT responsibility in the period',                                                                                              '',                '',                 '',             ''),
                ('1. Payable VAT amount of manufacturing and business activities in the period {[40a] = ([36]-[22]+[37]-[38]-[39a]) ≥ 0}',                                        '',                '',            '[40a]',           0.00),
                ('2. Input VAT of investment projects compensated with payable VAT of manufacturing and business activities in the same period ([40b] ≤ [40a])',                  '',                '',            '[40b]',           0.00),
                ('3. Payable VAT amount in the period ([40]=[40a] - [40b])',                                                                                                      '',                '',             '[40]',           0.00),
                ('4. Remaining VAT amount not deductible in the period {[40a] = ([36]-[22]+[37]-[38]-[39a]) ≤ 0}',                                                                '',                '',             '[41]',    31750000.00),
                    ('4.1. VAT amount requested for refund ([42] ≤ [41])',                                                                                                        '',                '',             '[42]',           0.00),
                    ('4.2. Deductible VAT amount bring forward to the next period ([43]=[41]-[42])',                                                                              '',                '',             '[43]',    31750000.00),
                ('Total 4. Remaining VAT amount not deductible in the period {[40a] = ([36]-[22]+[37]-[38]-[39a]) ≤ 0}',                                                          '',                '',             '[41]',    31750000.00),
            ],
            options,
        )

    @freeze_time('2025-10-31')
    def test_vn_appendix142_report_pdf_empty_lines(self):
        """Test that generating a PDF export with no lines does not crash and returns correct empty sections."""
        options = self._generate_options(self.appendix142_report, '2025-10-01', '2025-10-31')
        handler = self.env['l10n_vn_reports.appendix_142.report.handler']

        # With empty lines, sections should be empty with 0 total
        sections = handler._get_pdf_sections(self.appendix142_report, options, [])
        self.assertEqual(sections['purchase_lines'], [])
        self.assertEqual(sections['sales_lines'], [])
        self.assertEqual(sections['section_3_total'], 0)

        # With None lines (coerced to []), same result
        sections = handler._get_pdf_sections(self.appendix142_report, options, None)
        self.assertEqual(sections['purchase_lines'], [])
        self.assertEqual(sections['sales_lines'], [])
        self.assertEqual(sections['section_3_total'], 0)

        # Full PDF export should not crash either
        result = handler._get_pdf_export_html(options, lines=[], additional_context=None,
                                              template='l10n_vn_reports.l10n_vn_appendix142_report_pdf_export',
                                              report=self.appendix142_report)
        self.assertTrue(result)

    @freeze_time('2025-10-31')
    def test_vn_appendix142_report(self):
        options = self._generate_options(self.appendix142_report, '2025-10-01', '2025-10-31')
        report_information = self.appendix142_report.get_report_information(options)
        self.assertEqual(
            report_information['warnings'], {'l10n_vn_reports.no_data_warning': {'alert_type': 'warning'}}
        )

        invoice_vals = [
            {'type': 'in_invoice', 'date': '2025-10-12', 'price': 5000000, 'tax': [self.tax_purchase_5.id]},
            {'type': 'in_invoice', 'date': '2025-10-15', 'price': 100000, 'tax': [self.tax_purchase_8.id]},
            {'type': 'in_invoice', 'date': '2025-10-12', 'price': 100000, 'tax': []},
            {'type': 'in_invoice', 'date': '2025-10-12', 'price': 100000, 'tax': [self.tax_purchase_import_8.id]},
        ]
        for move in invoice_vals:
            self._create_invoice(
                move_type=move['type'],
                invoice_date=move['date'],
                post=True,
                invoice_line_ids=[self._prepare_invoice_line(price_unit=move['price'], tax_ids=move['tax'], quantity=1)],
            )

        report_information = self.appendix142_report.get_report_information(options)
        self.assertEqual(
            report_information['warnings'], {'l10n_vn_reports.no_sales_warning': {'alert_type': 'warning'}}
        )

        self._create_invoice(
            move_type='out_invoice',
            invoice_date='2025-10-10',
            post=True,
            invoice_line_ids=[self._prepare_invoice_line(price_unit=20000000, tax_ids=[self.tax_sale_8.id], quantity=1)],
        )

        lines = self.appendix142_report._get_lines(options)
        self.assertLinesValues(
            lines,
            # Name                                                                                 Untaxed Amount,                           VAT Amount
            [0,                                                                                                 1,                                    2],
            [
                ('I. Purchased Goods and Services in the period with 8% VAT rate',                'Untaxed amount',                         'VAT amount'),
                (None,                                                                                    200000.0,                              16000.0),
                ('Total',                                                                                 200000.0,                              16000.0),
                ('II. Sold Goods and Services in the period',                                     'Untaxed amount',             'Deducted amount of VAT'),
                (None,                                                                                  20000000.0,                             400000.0),
                ('Total',                                                                               20000000.0,                             400000.0),
                ('III. Difference of VAT amount between Purchased and Sold Goods and Services in the period which applies the 8% VAT rate:',
                                                                                                                '',                             384000.0),
            ],
            options,
        )

        # Verify PDF sections are correctly computed from the report lines
        handler = self.env['l10n_vn_reports.appendix_142.report.handler']
        sections = handler._get_pdf_sections(self.appendix142_report, options, lines)

        # purchase_lines: section 1 header + data + total (3 lines)
        self.assertEqual(len(sections['purchase_lines']), 3)
        self.assertEqual(sections['purchase_lines'][0].name, 'Goods and Services')

        # sales_lines: section 2 header + data + total (3 lines)
        self.assertEqual(len(sections['sales_lines']), 3)
        self.assertEqual(sections['sales_lines'][0].name, 'Goods and Services')

        # section_3_total: difference = 400000 - 16000 = 384000
        self.assertEqual(sections['section_3_total'], 384000.0)
