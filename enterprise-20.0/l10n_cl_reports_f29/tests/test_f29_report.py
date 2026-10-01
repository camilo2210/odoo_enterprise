from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo import fields, Command
from odoo.tests import tagged
from odoo.tests.common import freeze_time


@freeze_time('2025-03-31')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestF29VatClosingEntry(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('cl')
    def setUpClass(cls):
        """Set up the test environment with Chilean configuration."""
        super().setUpClass()

        cls.company = cls.company_data['company']
        cls.report = cls.env.ref('l10n_cl_reports_f29.tax_report_f29')
        cls.return_type = cls.env.ref('l10n_cl_reports.cl_f29_tax_return_type')

        cls.taxes = {}
        for tax_code in ['ITAX_19', 'OTAX_19', 'I_IR2C_2025', 'I_RTI']:
            cls.taxes[tax_code] = cls.env['account.chart.template'].ref(tax_code)

        # Partner
        cls.partner_sale = cls.env['res.partner'].create({
            'name': 'Test Sale Partner',
            'vat': '76086428-5',
            'l10n_cl_sii_taxpayer_type': '1',
            'country_id': cls.env.ref('base.cl').id,
        })
        cls.partner_fee = cls.env['res.partner'].create({
            'name': 'Test Fee Partner',
            'vat': '13009922-K',
            'l10n_cl_sii_taxpayer_type': '2',
            'country_id': cls.env.ref('base.cl').id,
        })
        cls.partner_supermarket = cls.env['res.partner'].create({
            'name': 'Cencosud Retail S.A.',
            'vat': '81201000-K',
            'l10n_cl_sii_taxpayer_type': '1',
            'country_id': cls.env.ref('base.cl').id,
            'l10n_cl_activity_description': 'Supermercados',
        })

        # Product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 1000.0,
        })

        # Moves
        def get_journal_of_type(type):
            return cls.env['account.journal'].search(
                [('company_id', '=', cls.company.id), ('type', '=', type)],
                limit=1
            )

        sale_journal = get_journal_of_type('sale')
        purchase_journal = get_journal_of_type('purchase')
        misc_journal = get_journal_of_type('general')

        moves_data = [
            {
                'move_type': 'out_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_a_f_dte').id,
                'partner_id': cls.partner_sale.id,
                'journal_id': sale_journal.id,
                'date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'price_unit': 145443289.47,
                    'tax_ids': [Command.set(cls.taxes['ITAX_19'].ids)],
                })],
            },
            {
                'move_type': 'in_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_a_f_dte').id,
                'l10n_latam_document_number': '1001',
                'partner_id': cls.partner_sale.id,
                'journal_id': purchase_journal.id,
                'date': '2025-03-15',
                'invoice_date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'price_unit': 54189078.42,
                    'tax_ids': [Command.set(cls.taxes['OTAX_19'].ids)],
                })],
            },
            {
                'move_type': 'in_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_m_d_dtn').id,
                'l10n_latam_document_number': '1002',
                'partner_id': cls.partner_fee.id,
                'journal_id': purchase_journal.id,
                'date': '2025-03-15',
                'invoice_date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'price_unit': 10000000.0,
                    'tax_ids': [Command.set(cls.taxes['I_IR2C_2025'].ids)],
                })],
            },
            {
                'move_type': 'in_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_fc_f_dte').id,
                'l10n_latam_document_number': '1003',
                'partner_id': cls.partner_sale.id,
                'journal_id': purchase_journal.id,
                'date': '2025-03-15',
                'invoice_date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'price_unit': 33810.0,
                    'tax_ids': [Command.set([cls.taxes['OTAX_19'].id, cls.taxes['I_RTI'].id])],
                })],
            },
            {
                'move_type': 'entry',
                'journal_id': misc_journal.id,
                'date': '2025-03-15',
                'line_ids': [
                    Command.create({'account_id': cls.env['account.chart.template'].ref('account_410110').id, 'debit': 1000000.0}),
                    Command.create({'account_id': cls.env['account.chart.template'].ref('account_210730').id, 'credit': 1000000.0}),
                ],
            },
            {
                'move_type': 'out_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_y_f_dte').id,
                'l10n_latam_document_number': '1',
                'partner_id': cls.partner_sale.id,
                'journal_id': sale_journal.id,
                'date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 100000.0,
                    'tax_ids': [],
                })],
            },
            {
                'move_type': 'out_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_fe_dte').id,
                'l10n_latam_document_number': '2',
                'partner_id': cls.partner_sale.id,
                'journal_id': sale_journal.id,
                'date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 200000.0,
                    'tax_ids': [],
                })],
            },
            {
                'move_type': 'out_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_b_f_dte').id,
                'l10n_latam_document_number': '3',
                'partner_id': cls.partner_sale.id,
                'journal_id': sale_journal.id,
                'date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 300000.0,
                    'tax_ids': [Command.set(cls.taxes['ITAX_19'].ids)],
                })],
            },
            {
                'move_type': 'out_refund',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_nc_f_dte').id,
                'l10n_latam_document_number': '4',
                'partner_id': cls.partner_sale.id,
                'journal_id': sale_journal.id,
                'date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 40000.0,
                    'tax_ids': [Command.set(cls.taxes['ITAX_19'].ids)],
                })],
            },
            {
                'move_type': 'out_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_nd_f_dte').id,
                'l10n_latam_document_number': '5',
                'partner_id': cls.partner_sale.id,
                'journal_id': sale_journal.id,
                'date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 50000.0,
                    'tax_ids': [Command.set(cls.taxes['ITAX_19'].ids)],
                })],
            },
            {
                'move_type': 'in_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_y_f_dte').id,
                'l10n_latam_document_number': '6',
                'partner_id': cls.partner_sale.id,
                'journal_id': purchase_journal.id,
                'date': '2025-03-15',
                'invoice_date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 60000.0,
                    'tax_ids': [],
                })],
            },
            {
                'move_type': 'in_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_a_f_dte').id,
                'l10n_latam_document_number': '8',
                'partner_id': cls.partner_sale.id,
                'journal_id': purchase_journal.id,
                'date': '2025-03-15',
                'invoice_date': '2025-03-15',
                'fiscal_position_id': cls.env['account.chart.template'].ref('afpt_fixed_asset').id,
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 80000.0,
                    'tax_ids': [Command.set(cls.taxes['OTAX_19'].ids)],
                })],
            },
            {
                'move_type': 'in_refund',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_nc_f_dte').id,
                'l10n_latam_document_number': '9',
                'partner_id': cls.partner_sale.id,
                'journal_id': purchase_journal.id,
                'date': '2025-03-15',
                'invoice_date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 9000.0,
                    'tax_ids': [Command.set(cls.taxes['OTAX_19'].ids)],
                })],
            },
            {
                'move_type': 'in_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_nd_f_dte').id,
                'l10n_latam_document_number': '10',
                'partner_id': cls.partner_sale.id,
                'journal_id': purchase_journal.id,
                'date': '2025-03-15',
                'invoice_date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 10000.0,
                    'tax_ids': [Command.set(cls.taxes['OTAX_19'].ids)],
                })],
            },
            {
                'move_type': 'in_invoice',
                'l10n_latam_document_type_id': cls.env.ref('l10n_cl.dc_a_f_dte').id,
                'l10n_latam_document_number': '11',
                'partner_id': cls.partner_supermarket.id,
                'journal_id': purchase_journal.id,
                'date': '2025-03-15',
                'invoice_date': '2025-03-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product.id,
                    'price_unit': 110000.0,
                    'tax_ids': [Command.set(cls.taxes['OTAX_19'].ids)],
                })],
            },
        ]
        cls.env['account.move'].create(moves_data).action_post()

    def setUp(self):
        super().setUp()
        self.env['account.report.external.value'].search([('company_id', '=', self.company.id)]).unlink()

    def assert_return_lines(self, closing_move_lines, expected_lines):
        self.assertEqual(len(closing_move_lines), len(expected_lines))
        for expected in expected_lines:
            move_line = closing_move_lines.filtered(lambda l: l.name == expected['name'])
            self.assertTrue(move_line, f"Line with name '{expected['name']}' not found.")
            self.assertAlmostEqual(move_line.debit, expected['debit'], places=0)
            self.assertAlmostEqual(move_line.credit, expected['credit'], places=0)

    def assert_report_lines(self, lines, expected_lines, options):
        filtered_lines = [line for line in lines if line.name in [exp[0] for exp in expected_lines]]

        self.assertEqual(len(filtered_lines), len(expected_lines))
        self.assertLinesValues(
            sorted(filtered_lines, key=lambda x: x.name),
            [0, 1, 2, 3, 4, 5],
            sorted(expected_lines, key=lambda x: x[0]),
            options
        )

    def test_vat_closing_entry_with_postponement(self):
        period_from = fields.Date.from_string('2025-03-01')
        period_to = fields.Date.from_string('2025-03-31')
        tax_return = self.env['account.return'].create({
            'name': self.return_type._get_return_name(self.company, period_from, period_to),
            'type_id': self.return_type.id,
            'company_id': self.company.id,
            'date_from': period_from,
            'date_to': period_to,
        })

        self.env['account.report.external.value'].create([
            {
                'company_id': self.company.id,
                'target_report_expression_id': self.env.ref('l10n_cl_reports_f29.f29_04_child_1_bool_l3_010').id,
                'value': 1,
                'target_report_expression_label': 'balance',
                'name': 'VAT Tax Postponement',
                'date': period_to,
            },
            {
                'company_id': self.company.id,
                'target_report_expression_id': self.env.ref('l10n_cl_reports_f29.f29_04_child_9_tax_l2_075').id,
                'value': 1.214,
                'target_report_expression_label': 'balance',
                'name': 'Manual value (062 rate)',
                'date': period_to,
            },
        ])

        options = self._generate_options(self.report, period_from, period_to)
        options['unfold_all'] = True

        expected_values = [
            ('Exempt Income', 2, '', 300000, '', ''),
            ('(585) Export documents', 1, '(020)', 200000, '', ''),
            ('(586) Exempt Invoices issued for sales and services or for 3rd parties reps', 1, '(142)', 100000, '', ''),
            ('Total Exempt Income', 2, '', 300000, '', ''),
            ('(023) Generates Debit', 4, '(538)', 145753289, '(538)', 27693125),
            ('(503) Invoices issued for sales and services or for 3rd parties reps', 1, '(503)', 145443289,
             '(502)', 27634225),
            ('(110) Receipts', 1, '(110)', 300000, '(111)', 57000),
            ('(512) Debit Notes', 1, '(512)', 50000, '(513)', 9500),
            ('(509) Credit Notes', 1, '(509)', -40000, '(510)', -7600),
            ('Total (023) Generates Debit', 4, '(538)', 145753289, '(538)', 27693125),
            ('Credit and Purchases', '', '', '', '', ''),
            ('Without Credit Rights', 0, '', 0, '', 0),
            ('(564) Internal affected', 0, '(564)', 0, '(521)', 0),
            ('(566) Imports', 0, '(566)', 0, '', ''),
            ('(562) internal exempt or not taxed', 1, '(562)', 60000, '', ''),
            ('Total Without Credit Rights', 0, '', 0, '', 0),
            ('Purchases with credit rights', 6, '(049)', 54413888, '(537)', 10338639),
            ('Internal', 6, '', 54413888, '', 10338639),
            ('(519) Received invoices from the current activity', 4, '(519)', 54412888, '(520)', 10338449),
            ('(761) Received invoices from supermarkets an similar suppliers', 0, '(761)', 0, '(762)', 0),
            ('(524) Fixed Assets Invoices', 0, '(524)', 0, '(525)', 0),
            ('(527) Received Credit notes over received invoices and issued invoices over subject change', 1,
             '(527)', -9000, '(528)', -1710),
            ('(531) Received debit notes and issued debit notes by subject change invoices', 1, '(531)', 10000,
             '(532)', 1900),
            ('Imports (DIN)', 0, '', 0, '(535-553)', 0),
            ('(34-35) Income declarations (DIN) activity imports and/or fixed asssets imports', 0, '(534-536)', 0,
             '(535-553)', 0),
            ('Total Imports (DIN)', 0, '', 0, '(535-553)', 0),
            ('Total Purchases with credit rights', 6, '(049)', 54413888, '(537)', 10338639),
            ('Subject Change (Withholding Agent)', 1, '', '', '', -6424),
            ('(113) Total VAT withholded to 3rd parties (Art. 14 DL 825 Rate)', 1, '', '', '(039)', -6424),
            ('Total Subject Change (Withholding Agent)', 1, '', '', '', -6424),
            ('Taxes for the Period (Negative: Balance in Favor of the Company)', '', '', '', '(547)', 4216663),
            ('VAT Tax Postponement', '', '', 'Yes', '(755)', 17354486),
            ('VAT Tax Debit', '', '', '', '(538)', 27693125),
            ('VAT Tax Credit', '', '', '', '(537)', 10338639),
            ('VAT Determined (If negative the value will be 0 and added to remaining for next period)', '', '', 'Yes',
             '(089)', 0),
            ('Remaining CF', '', '', '', '(077)', 0),
            ("Workers' Tax", '', '', '', '(048)', 1000000),
            ('Withholding Fees Over Rents Law 21133', '', '', '', '(151)', 1450000),
            ('PPM Tax Base', '', '', 146053289, '(563)', ''),
            ('PPM Rate (IMPORTANT: Must remain 0 if PPM Base is negative)', '', '(115)', '1.21%', '(062)', 1773087),
            ('Withholding Subject Change', '', '', '', '(596)', -6424),
            ('Total Taxes for the Period (Negative: Balance in Favor of the Company)', '', '', '', '(547)', 4216663),
        ]

        self.assert_report_lines(self.report._get_lines(options), expected_values, options)

        wizard_action = tax_return.action_submit()
        wizard = self.env['l10n_cl_reports_f29.return.submission.wizard'].with_context(wizard_action['context']).create({
            'return_id': tax_return.id,
        })
        with self.allow_pdf_render():
            wizard.action_proceed_with_submission()
            tax_return.action_validate()

        self.assertTrue(tax_return.closing_move_ids)
        move = tax_return.closing_move_ids
        expected_lines = [
            {"name": "F29 (538) VAT Tax Debit", "debit": 27693125.0, "credit": 0.0},
            {"name": "F29 (537) VAT Tax Credit", "debit": 0.0, "credit": 10338639.0},
            {"name": "F29 (755) VAT Tax Postponement", "debit": 0.0, "credit": 17354486.0},
            {"name": "F29 (151) Withholding Fees Over Rents Law 21133", "debit": 1450000.0, "credit": 0.0},
            {"name": "F29 (596) Withholding Subject Change", "debit": 0.0, "credit": 6424.0},
            {"name": "F29 (048) Workers' Tax", "debit": 1000000.0, "credit": 0.0},
            {"name": "F29 (062) PPM Rate (IMPORTANT: Must remain 0 if PPM Base is negative)", "debit": 1773087.0,
             "credit": 0.0},
            {"name": "F29 (547) Total Taxes for the Period", "debit": 0.0, "credit": 4216663.0},
        ]

        self.assert_return_lines(move.line_ids, expected_lines)
        self.assertAlmostEqual(tax_return.period_amount_to_pay, 4216663.0, places=0)

    def test_vat_closing_entry_without_postponement(self):
        period_from = fields.Date.from_string('2025-03-01')
        period_to = fields.Date.from_string('2025-03-31')
        tax_return = self.env['account.return'].create({
            'name': self.return_type._get_return_name(self.company, period_from, period_to),
            'type_id': self.return_type.id,
            'company_id': self.company.id,
            'date_from': period_from,
            'date_to': period_to,
        })

        self.env['account.report.external.value'].create([
            {
                'company_id': self.company.id,
                'target_report_expression_id': self.env.ref('l10n_cl_reports_f29.f29_04_child_1_bool_l3_010').id,
                'value': 0,
                'target_report_expression_label': 'balance',
                'name': 'VAT Tax Postponement',
                'date': period_to,
            },
            {
                'company_id': self.company.id,
                'target_report_expression_id': self.env.ref('l10n_cl_reports_f29.f29_04_child_9_tax_l2_075').id,
                'value': 1.214,
                'target_report_expression_label': 'balance',
                'name': 'Manual value (062 rate)',
                'date': period_to,
            },
        ])

        options = self._generate_options(self.report, period_from, period_to)
        options['unfold_all'] = True

        expected_values = [
            ('Exempt Income', 2, '', 300000, '', ''),
            ('(585) Export documents', 1, '(020)', 200000, '', ''),
            ('(586) Exempt Invoices issued for sales and services or for 3rd parties reps', 1, '(142)', 100000, '', ''),
            ('Total Exempt Income', 2, '', 300000, '', ''),
            ('(023) Generates Debit', 4, '(538)', 145753289, '(538)', 27693125),
            ('(503) Invoices issued for sales and services or for 3rd parties reps', 1, '(503)', 145443289,
             '(502)', 27634225),
            ('(110) Receipts', 1, '(110)', 300000, '(111)', 57000),
            ('(512) Debit Notes', 1, '(512)', 50000, '(513)', 9500),
            ('(509) Credit Notes', 1, '(509)', -40000, '(510)', -7600),
            ('Total (023) Generates Debit', 4, '(538)', 145753289, '(538)', 27693125),
            ('Credit and Purchases', '', '', '', '', ''),
            ('Without Credit Rights', 0, '', 0, '', 0),
            ('(564) Internal affected', 0, '(564)', 0, '(521)', 0),
            ('(566) Imports', 0, '(566)', 0, '', ''),
            ('(562) internal exempt or not taxed', 1, '(562)', 60000, '', ''),
            ('Total Without Credit Rights', 0, '', 0, '', 0),
            ('Purchases with credit rights', 6, '(049)', 54413888, '(537)', 10338639),
            ('Internal', 6, '', 54413888, '', 10338639),
            ('(519) Received invoices from the current activity', 4, '(519)', 54412888, '(520)', 10338449),
            ('(761) Received invoices from supermarkets an similar suppliers', 0, '(761)', 0, '(762)', 0),
            ('(524) Fixed Assets Invoices', 0, '(524)', 0, '(525)', 0),
            ('(527) Received Credit notes over received invoices and issued invoices over subject change', 1,
             '(527)', -9000, '(528)', -1710),
            ('(531) Received debit notes and issued debit notes by subject change invoices', 1, '(531)', 10000,
             '(532)', 1900),
            ('Imports (DIN)', 0, '', 0, '(535-553)', 0),
            ('(34-35) Income declarations (DIN) activity imports and/or fixed asssets imports', 0, '(534-536)', 0,
             '(535-553)', 0),
            ('Total Imports (DIN)', 0, '', 0, '(535-553)', 0),
            ('Total Purchases with credit rights', 6, '(049)', 54413888, '(537)', 10338639),
            ('Subject Change (Withholding Agent)', 1, '', '', '', -6424),
            ('(113) Total VAT withholded to 3rd parties (Art. 14 DL 825 Rate)', 1, '', '', '(039)', -6424),
            ('Total Subject Change (Withholding Agent)', 1, '', '', '', -6424),
            ('Taxes for the Period (Negative: Balance in Favor of the Company)', '', '', '', '(547)', 21571149),
            ('VAT Tax Postponement', '', '', 'No', '(755)', 0),
            ('VAT Tax Debit', '', '', '', '(538)', 27693125),
            ('VAT Tax Credit', '', '', '', '(537)', 10338639),
            ('VAT Determined (If negative the value will be 0 and added to remaining for next period)', '', '', 'Yes',
             '(089)', 17354486),
            ('Remaining CF', '', '', '', '(077)', 0),
            ("Workers' Tax", '', '', '', '(048)', 1000000),
            ('Withholding Fees Over Rents Law 21133', '', '', '', '(151)', 1450000),
            ('PPM Tax Base', '', '', 146053289, '(563)', ''),
            ('PPM Rate (IMPORTANT: Must remain 0 if PPM Base is negative)', '', '(115)', '1.21%', '(062)', 1773087),
            ('Withholding Subject Change', '', '', '', '(596)', -6424),
            ('Total Taxes for the Period (Negative: Balance in Favor of the Company)', '', '', '', '(547)', 21571149),
        ]

        self.assert_report_lines(self.report._get_lines(options), expected_values, options)

        wizard_action = tax_return.action_submit()
        wizard = self.env['l10n_cl_reports_f29.return.submission.wizard'].with_context(wizard_action['context']).create({
            'return_id': tax_return.id,
        })
        with self.allow_pdf_render():
            wizard.action_proceed_with_submission()
            tax_return.action_validate()

        self.assertTrue(tax_return.closing_move_ids)
        move = tax_return.closing_move_ids
        expected_lines = [
            {"name": "F29 (538) VAT Tax Debit", "debit": 27693125.0, "credit": 0.0},
            {"name": "F29 (537) VAT Tax Credit", "debit": 0.0, "credit": 10338639.0},
            {"name": "F29 (151) Withholding Fees Over Rents Law 21133", "debit": 1450000.0, "credit": 0.0},
            {"name": "F29 (596) Withholding Subject Change", "debit": 0.0, "credit": 6424.0},
            {"name": "F29 (048) Workers' Tax", "debit": 1000000.0, "credit": 0.0},
            {"name": "F29 (062) PPM Rate (IMPORTANT: Must remain 0 if PPM Base is negative)", "debit": 1773087.0,
             "credit": 0.0},
            {"name": "F29 (547) Total Taxes for the Period", "debit": 0.0, "credit": 21571149.0},
        ]

        self.assert_return_lines(move.line_ids, expected_lines)
        self.assertAlmostEqual(tax_return.total_amount_to_pay, 21571149.0, places=0)

    @freeze_time('2025-05-31')
    def test_no_moves(self):
        period_from = fields.Date.from_string('2025-05-01')
        period_to = fields.Date.from_string('2025-05-31')
        tax_return = self.env['account.return'].create({
            'name': self.return_type._get_return_name(self.company, period_from, period_to),
            'type_id': self.return_type.id,
            'company_id': self.company.id,
            'date_from': period_from,
            'date_to': period_to,
        })

        options = self._generate_options(self.report, period_from, period_to)
        options['unfold_all'] = True

        expected_values = [
            ('Exempt Income', 0, '', 0, '', ''),
            ('(585) Export documents', 0, '(020)', 0, '', ''),
            ('(586) Exempt Invoices issued for sales and services or for 3rd parties reps', 0, '(142)', 0, '', ''),
            ('Total Exempt Income', 0, '', 0, '', ''),
            ('(023) Generates Debit', 0, '(538)', 0, '(538)', 0),
            ('(503) Invoices issued for sales and services or for 3rd parties reps', 0, '(503)', 0, '(502)', 0),
            ('(110) Receipts', 0, '(110)', 0, '(111)', 0),
            ('(512) Debit Notes', 0, '(512)', 0, '(513)', 0),
            ('(509) Credit Notes', 0, '(509)', 0, '(510)', 0),
            ('Total (023) Generates Debit', 0, '(538)', 0, '(538)', 0),
            ('Credit and Purchases', '', '', '', '', ''),
            ('Without Credit Rights', 0, '', 0, '', 0),
            ('(564) Internal affected', 0, '(564)', 0, '(521)', 0),
            ('(566) Imports', 0, '(566)', 0, '', ''),
            ('(562) internal exempt or not taxed', 0, '(562)', 0, '', ''),
            ('Total Without Credit Rights', 0, '', 0, '', 0),
            ('Purchases with credit rights', 0, '(049)', 0, '(537)', 0),
            ('Internal', 0, '', 0, '', 0),
            ('(519) Received invoices from the current activity', 0, '(519)', 0, '(520)', 0),
            ('(761) Received invoices from supermarkets an similar suppliers', 0, '(761)', 0, '(762)', 0),
            ('(524) Fixed Assets Invoices', 0, '(524)', 0, '(525)', 0),
            ('(527) Received Credit notes over received invoices and issued invoices over subject change', 0,
             '(527)', 0, '(528)', 0),
            ('(531) Received debit notes and issued debit notes by subject change invoices', 0, '(531)', 0,
             '(532)', 0),
            ('Imports (DIN)', 0, '', 0, '(535-553)', 0),
            ('(34-35) Income declarations (DIN) activity imports and/or fixed asssets imports', 0, '(534-536)', 0,
             '(535-553)', 0),
            ('Total Imports (DIN)', 0, '', 0, '(535-553)', 0),
            ('Total Purchases with credit rights', 0, '(049)', 0, '(537)', 0),
            ('Subject Change (Withholding Agent)', 0, '', '', '', 0),
            ('(113) Total VAT withholded to 3rd parties (Art. 14 DL 825 Rate)', 0, '', '', '(039)', 0),
            ('Total Subject Change (Withholding Agent)', 0, '', '', '', 0),
            ('Taxes for the Period (Negative: Balance in Favor of the Company)', '', '', '', '(547)', 0),
            ('VAT Tax Postponement', '', '', 'No', '(755)', 0),
            ('VAT Tax Debit', '', '', '', '(538)', 0),
            ('VAT Tax Credit', '', '', '', '(537)', 0),
            ('VAT Determined (If negative the value will be 0 and added to remaining for next period)', '', '', 'No',
             '(089)', 0),
            ('Remaining CF', '', '', '', '(077)', 0),
            ("Workers' Tax", '', '', '', '(048)', 0),
            ('Withholding Fees Over Rents Law 21133', '', '', '', '(151)', 0),
            ('PPM Tax Base', '', '', 0, '(563)', ''),
            ('PPM Rate (IMPORTANT: Must remain 0 if PPM Base is negative)', '', '(115)', '0.00%', '(062)', 0),
            ('Withholding Subject Change', '', '', '', '(596)', 0),
            ('Total Taxes for the Period (Negative: Balance in Favor of the Company)', '', '', '', '(547)', 0),
        ]

        self.assert_report_lines(self.report._get_lines(options), expected_values, options)

        wizard_action = tax_return.action_submit()
        wizard = self.env['l10n_cl_reports_f29.return.submission.wizard'].with_context(wizard_action['context']).create({
            'return_id': tax_return.id,
        })
        with self.allow_pdf_render():
            wizard.action_proceed_with_submission()
            tax_return.action_validate()

        self.assertEqual(tax_return.state, 'reviewed')
        self.assertTrue(tax_return.closing_move_ids)
        move = tax_return.closing_move_ids

        expected_lines = [
            {"name": "Tax Received Adjustment", "debit": 0.0, "credit": 0.0},
            {"name": "Tax Paid Adjustment", "debit": 0.0, "credit": 0.0},
        ]

        self.assert_return_lines(move.line_ids, expected_lines)
        self.assertAlmostEqual(tax_return.total_amount_to_pay, 0.0)
