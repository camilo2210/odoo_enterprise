# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io
import unittest
from datetime import datetime
from freezegun import freeze_time
from textwrap import dedent
try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None


from odoo import Command
from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class L10nThaiTaxReportTest(AccountSalesReportCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountSalesReportCommon.setup_country('th')
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_b.write({
            'country_id': cls.env.ref('base.th').id,
            "vat": "0107537002443",
            "additional_identifiers": {"TH_BRANCH_CODE": "12345"},
            "l10n_th_company_type": "ltd_partner",
        })
        cls.partner_individual = cls.env['res.partner'].create({
            'name': 'Individual Partner',
            'country_id': cls.env.ref('base.th').id,
            "vat": "1103900016621"
        })

        # Prepare tax references
        cls.ChartTemplate = cls.env['account.chart.template'].with_company(cls.company_data['company'])
        cls.tax_wht_co_1 = cls.ChartTemplate.ref('tax_wht_co_1')
        cls.tax_wht_co_2 = cls.ChartTemplate.ref('tax_wht_co_2')
        cls.tax_wht_co_3 = cls.ChartTemplate.ref('tax_wht_co_3')
        cls.tax_wht_pers_1 = cls.ChartTemplate.ref('tax_wht_pers_1')
        cls.tax_wht_pers_2 = cls.ChartTemplate.ref('tax_wht_pers_2')
        cls.tax_input_vat = cls.ChartTemplate.ref('tax_input_vat')
        cls.tax_output_vat = cls.ChartTemplate.ref('tax_output_vat')
        cls.tax_output_vat_0 = cls.ChartTemplate.ref('tax_output_vat_0')

        # Create withholding sequences and assign to taxes
        cls.withholding_sequence_pnd3 = cls.env['ir.sequence'].create({
            'implementation': 'no_gap',
            'name': 'Withholding Sequence PND3',
            'padding': 4,
            'number_increment': 1,
        })
        cls.withholding_sequence_pnd53 = cls.env['ir.sequence'].create({
            'implementation': 'no_gap',
            'name': 'Withholding Sequence PND53',
            'padding': 4,
            'number_increment': 1,
        })

        (cls.tax_wht_pers_1 | cls.tax_wht_pers_2).withholding_sequence_id = cls.withholding_sequence_pnd3
        (cls.tax_wht_co_1 | cls.tax_wht_co_2 | cls.tax_wht_co_3).withholding_sequence_id = cls.withholding_sequence_pnd53

        cls.company.update({
            'street': 'Street',
            'zip': '50110',
        })
        cls.company.partner_id.write({
            'additional_identifiers': {'TH_BRANCH_CODE': '12345'},
        })

    def compare_xlsx_data(self, report_data, expected_data):
        if load_workbook is None:
            raise unittest.SkipTest("openpyxl not available")
        report_file = io.BytesIO(report_data)
        xlsx = load_workbook(filename=report_file, data_only=True)
        sheet = xlsx.worksheets[0]
        sheet_values = list(sheet.values)

        result = []

        for row in sheet_values[6:]:
            result.append([v if v is not None else '' for v in list(row)])

        self.assertEqual(result, expected_data)

    @freeze_time('2023-06-30')
    def test_pnd53_report(self):
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'partner_id': self.partner_b.id,
            'invoice_date': '2023-05-20',
            'date': '2023-05-20',
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product_a.id,
                    'quantity': 1,
                    'name': 'product test 1',
                    'price_unit': 1000,
                    'tax_ids': self.tax_wht_co_3.ids
                }),
                (0, 0, {
                    'product_id': self.product_b.id,
                    'quantity': 1,
                    'name': 'product test 2',
                    'price_unit': 1000,
                    'tax_ids': self.tax_wht_co_2.ids
                })
            ]
        })
        move.action_post()

        # Register payment to apply withholding taxes
        self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=move.ids,
        ).create({
            'payment_date': '2023-05-20',
        })._create_payments()

        report = self.env.ref('l10n_th_reports.tax_report_pnd53')
        options = self._generate_options(report, '2023-05-01', '2023-05-31')

        report_data = self.env['l10n_th.pnd53.report.handler'].export_pnd53_to_csv(options)['file_content']
        expected = ("No.|Tax ID|Title|Contact Name|Street|Street2|City|State|Zip|Branch Number|Payment Date|Tax Rate|Total Amount|WHT Amount|WHT Condition|Tax Type\n"
                    f"1|{self.partner_b.vat}|ห้างหุ้นส่วนจำกัด|Partner B||||||12345|20/05/2023|3.00|1000.00|30.00|1|ค่าจ้างรับทำงานให้\n"
                    f"2|{self.partner_b.vat}|ห้างหุ้นส่วนจำกัด|Partner B||||||12345|20/05/2023|2.00|1000.00|20.00|1|ค่าโฆษณา\n").encode()

        self.assertEqual(report_data, expected)

    @freeze_time('2023-06-30')
    def test_pnd3_report(self):
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'partner_id': self.partner_individual.id,
            'invoice_date': '2023-05-20',
            'date': '2023-05-20',
            'company_id': self.company_data['company'].id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product_a.id,
                    'quantity': 1,
                    'name': 'product test 1',
                    'price_unit': 1000,
                    'tax_ids': self.tax_wht_pers_1.ids
                }),
                (0, 0, {
                    'product_id': self.product_b.id,
                    'quantity': 1,
                    'name': 'product test 2',
                    'price_unit': 1000,
                    'tax_ids': self.tax_wht_pers_2.ids
                })
            ]
        })
        move.action_post()

        # Register payment to apply withholding taxes
        self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=move.ids,
        ).create({
            'payment_date': '2023-05-20',
        })._create_payments()

        report = self.env.ref('l10n_th_reports.tax_report_pnd3')
        options = self._generate_options(report, '2023-05-01', '2023-05-31')

        report_data = self.env['l10n_th.pnd3.report.handler'].export_pnd3_to_csv(options)['file_content']
        expected = ("No.|Tax ID|Title|Contact Name|Street|Street2|City|State|Zip|Branch Number|Payment Date|Tax Rate|Total Amount|WHT Amount|WHT Condition|Tax Type\n"
                    f"1|{self.partner_individual.vat}|คุณ|Individual Partner|||||||20/05/2023|1.00|1000.00|10.00|1|ค่าขนส่ง\n"
                    f"2|{self.partner_individual.vat}|คุณ|Individual Partner|||||||20/05/2023|2.00|1000.00|20.00|1|ค่าโฆษณา\n").encode()

        self.assertEqual(report_data, expected)

    @freeze_time('2023-06-30')
    def test_vat_tax_report_branch_name(self):
        self.init_invoice("out_invoice", self.partner_b, "2023-05-20", amounts=[1000, 1000], taxes=[self.tax_wht_co_3, self.tax_output_vat], post=True)

        report = self.env.ref('l10n_th.tax_report')
        options = report.get_options({})

        report_data = self.env['l10n_th.tax.report.handler'].l10n_th_print_sale_tax_report(options)['file_content']
        expected = [
            ['No.', 'Tax Invoice No.', 'Reference', 'Invoice Date', 'Contact Name', 'Tax ID', 'Company Information', 'Total Amount', 'Total Excluding VAT Amount', 'Vat Amount'],
            [1, 'INV/2023/00001', '', datetime(2023, 5, 20), 'Partner B', self.partner_b.vat, 'Branch 12345', 2140.0, 2000.0, 140.0],
            ['', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', 'Total', 2140.0, 2000.0, 140]
        ]
        self.compare_xlsx_data(report_data, expected)

    @freeze_time('2023-06-30')
    def test_vat_sales_tax_report(self):
        self.init_invoice("out_invoice", self.partner_b, "2023-05-20", amounts=[1000, 1000], taxes=[self.tax_wht_co_3, self.tax_output_vat], post=True)

        report = self.env.ref('l10n_th.tax_report')
        options = report.get_options({})

        report_data = self.env['l10n_th.tax.report.handler'].l10n_th_print_sale_tax_report(options)['file_content']
        expected = [
            ['No.', 'Tax Invoice No.', 'Reference', 'Invoice Date', 'Contact Name', 'Tax ID', 'Company Information', 'Total Amount', 'Total Excluding VAT Amount', 'Vat Amount'],
            [1, 'INV/2023/00001', '', datetime(2023, 5, 20), 'Partner B', self.partner_b.vat, 'Branch 12345', 2140.0, 2000.0, 140.0],
            ['', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', 'Total', 2140.0, 2000.0, 140]
        ]
        self.compare_xlsx_data(report_data, expected)

    @freeze_time('2023-06-30')
    def test_vat_purchase_tax_report_full_refund(self):
        self.init_invoice("in_invoice", self.partner_b, "2023-05-20", amounts=[1000, 1000], taxes=[self.tax_wht_co_3, self.tax_input_vat], post=True)

        # Reversed move should not be included in the report
        move_to_reverse = self.init_invoice("in_invoice", self.partner_b, "2023-05-20", amounts=[1000, 1000], taxes=[self.tax_wht_co_3, self.tax_input_vat], post=True)
        move_to_reverse._reverse_moves([{"invoice_date": move_to_reverse.date}], cancel=True)

        report = self.env.ref('l10n_th.tax_report')
        options = report.get_options({})

        report_data = self.env['l10n_th.tax.report.handler'].l10n_th_print_purchase_tax_report(options)['file_content']
        expected = [
            ['No.', 'Tax Invoice No.', 'Reference', 'Invoice Date', 'Contact Name', 'Tax ID', 'Company Information', 'Total Amount', 'Total Excluding VAT Amount', 'Vat Amount'],
            [1, 'RBILL/2023/05/0001', '', datetime(2023, 5, 31), 'Partner B', self.partner_b.vat, 'Branch 12345', -2140.0, -2000.0, -140.0],
            [2, 'BILL/2023/05/0002', '', datetime(2023, 5, 20), 'Partner B', self.partner_b.vat, 'Branch 12345', 2140.0, 2000.0, 140.0],
            [3, 'BILL/2023/05/0001', '', datetime(2023, 5, 20), 'Partner B', self.partner_b.vat, 'Branch 12345', 2140.0, 2000.0, 140.0],
            ['', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', 'Total', 2140.0, 2000.0, 140.0]
        ]
        self.compare_xlsx_data(report_data, expected)

    @freeze_time('2023-06-30')
    def test_vat_purchase_tax_report_partial_refund(self):
        move_to_partial_refund = self.init_invoice("in_invoice", self.partner_b, "2023-05-20", amounts=[1000, 1000], taxes=[self.tax_wht_co_3, self.tax_input_vat], post=True)
        reverse_move = move_to_partial_refund._reverse_moves([{"invoice_date": move_to_partial_refund.date, "date": move_to_partial_refund.date}])
        reverse_move.write({'invoice_line_ids': [
            Command.update(line.id, {
                'price_unit': 500,
            }) for line in reverse_move.invoice_line_ids
        ]})
        reverse_move.action_post()
        report = self.env.ref('l10n_th.tax_report')
        options = report.get_options({})

        report_data = self.env['l10n_th.tax.report.handler'].l10n_th_print_purchase_tax_report(options)['file_content']
        expected = [
            ['No.', 'Tax Invoice No.', 'Reference', 'Invoice Date', 'Contact Name', 'Tax ID', 'Company Information', 'Total Amount', 'Total Excluding VAT Amount', 'Vat Amount'],
            [1, 'RBILL/2023/05/0001', '', datetime(2023, 5, 20), 'Partner B', self.partner_b.vat, 'Branch 12345', -1070.0, -1000.0, -70.0],
            [2, 'BILL/2023/05/0001', '', datetime(2023, 5, 20), 'Partner B', self.partner_b.vat, 'Branch 12345', 2140.0, 2000.0, 140.0],
            ['', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', 'Total', 1070.0, 1000.0, 70.0]
        ]
        self.compare_xlsx_data(report_data, expected)

    @freeze_time('2025-11-01')
    def test_vat_report_csv_export(self):
        report = self.env.ref('l10n_th.tax_report')
        invoice_vals = [
            {'type': 'out_invoice', 'date': '2025-10-10', 'price': [200, 400], 'tax': [self.tax_output_vat.id]},
            {'type': 'in_invoice', 'date': '2025-10-15', 'price': [350, 280], 'tax': [self.tax_input_vat.id]},
        ]
        for move in invoice_vals:
            self._create_invoice(
                move_type=move['type'],
                invoice_date=move['date'],
                post=True,
                invoice_line_ids=[
                    self._prepare_invoice_line(price_unit=move['price'][0], tax_ids=move['tax'], quantity=2),
                    self._prepare_invoice_line(price_unit=move['price'][1], tax_ids=move['tax'], quantity=3),
                ]
            )
        options = report.get_options({})
        options['export_mode'] = 'file'
        report_data = self.env['l10n_th.tax.report.handler'].l10n_th_export_csv(options)['file_content']
        expeced_data = dedent('''\
            Sequence Number|Branch Number (5)|Number (20)|Postal/ZIP Code (5)|Taxable Sales Amount [Item 4] (15,2)|Output Tax This Month [Item 5] (15,2)|Purchase Amount [Item 6] (15,2)|Input Tax This Month[Item 7] (15,2)|VAT Payable or Access (Refund) [Item 8 or 9] (15,2)\r
            1|12345|Street|50110|1600.00|112.00|1540.00|107.80|4.20\r
        ''')
        self.assertEqual(report_data, expeced_data)

    @freeze_time('2025-11-01')
    def test_generate_th_pp30_report(self):
        invoice_vals = [
            {'type': 'out_invoice', 'date': '2025-10-10', 'price': 1000, 'tax': [self.tax_output_vat.id]},
            {'type': 'out_invoice', 'date': '2025-10-12', 'price': 2000, 'tax': [self.tax_output_vat_0.id]},
            {'type': 'in_invoice', 'date': '2025-10-15', 'price': 300, 'tax': [self.tax_input_vat.id]},
        ]
        for move in invoice_vals:
            self._create_invoice(
                move_type=move['type'],
                invoice_date=move['date'],
                post=True,
                invoice_line_ids=[self._prepare_invoice_line(price_unit=move['price'], tax_ids=move['tax'], quantity=2)],
            )

        report = self.env.ref('l10n_th.tax_report')
        options = self._generate_options(report, '2025-10-01', '2025-10-31')
        self.assertLinesValues(
            report._get_lines(options),
            #   Name                                                                                                    Balance
            [   0,                                                                                                           1],
            [
                # --- Output Tax Section ---
                ('Output Tax',),
                ('1. Sales amount',                                                                                    6000.00),
                ('2. Less sales subject to 0% tax rate',                                                               4000.00),
                ('3. Less exempted sales',                                                                                0.00),
                ('4. Taxable sales amount(1. -2. -3.)',                                                                2000.00),
                ('5. Output tax',                                                                                       140.00),

                # --- Input Tax Section ---
                ('Input Tax',),
                ('6. Purchase amount that is entitled to deduction of input tax from output tax in tax computation',    600.00),
                ('7. Input tax (according to invoice of purchase amount in 6.)',                                         42.00),

                # --- Value Added Tax Section ---
                ('Value Added Tax',),
                ('8. Tax payable (if 5. is greater than 7.)',                                                            98.00),
                ('9. Excess tax payable (if 5. is less than 7.)',                                                         0.00),
                ('10. Excess tax payment carried forward from last period',                                               0.00),

                # --- Net Tax Section ---
                ('Net Tax',),
                ('11. Net tax payable (if 8. is greater than 10.)',                                                      98.00),
                ('12. Net excess tax payable ((if 10. is greater than 8.) or (9. plus 10.))',                             0.00),
            ],
            options,
        )
