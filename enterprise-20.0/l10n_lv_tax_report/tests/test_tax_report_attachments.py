from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nLvTaxReportAttachments(TestAccountReportsCommon):

    @classmethod
    def _read_file(cls, path, *args):
        with file_open(path, *args) as f:
            content = f.read()
        return content

    @classmethod
    @TestAccountReportsCommon.setup_country('lv')
    def setUpClass(cls):
        super().setUpClass()

        cls.company.write({
            'street': 'Mana iela',
            'city': 'Rīga',
            'zip': 'LV-1010',
            'phone': '+371 20 00 00 00',
            'email': 'info@company_1_data.lv',
            'website': 'company1data.lv',
            'vat': 'LV41234567891',
        })
        cls.Template = cls.env['account.chart.template'].with_company(cls.company)

        # Domestic partners
        cls.partner_domestic_a = cls.partner_a
        cls.partner_domestic_a.write({
            'name': 'domestic_a',
            'vat': 'LV40003032949',
            'country_id': cls.env.ref('base.lv').id,
        })
        cls.partner_domestic_b = cls.partner_domestic_a.copy({
            'name': 'domestic_b',
            'vat': 'LV40203295309',
            'country_id': cls.env.ref('base.lv').id,
        })
        cls.partner_domestic_c = cls.partner_domestic_b.copy({
            'name': 'domestic_c',
            'vat': 'LV40003520643',
            'country_id': cls.env.ref('base.lv').id,
        })
        # EU partners
        cls.partner_eu_a = cls.partner_b
        cls.partner_eu_a.write({
            'name': 'eu_a',
            'vat': 'BE0477472701',
            'country_id': cls.env.ref('base.be').id,
        })
        cls.partner_eu_b = cls.partner_eu_a.copy({
            'name': 'eu_b',
            'vat': 'DE0477472701',
            'country_id': cls.env.ref('base.de').id,
        })
        cls.partner_eu_c = cls.partner_eu_a.copy({
            'name': 'eu_c',
            'vat': 'GR047747210',
            'country_id': cls.env.ref('base.gr').id,
        })
        cls.partner_eu_d = cls.partner_eu_a.copy({
            'name': 'eu_d',
            'vat': 'FR23334175221',
            'country_id': cls.env.ref('base.fr').id,
        })

        cls.other_currency = cls.setup_other_currency('USD', rounding=0.01, rates=([('2019-01-01', 0.5)]))

        # Special document type tags
        cls.unreportable_document_type_tag = cls.env.ref("l10n_lv.tag_pvn_doc_type_X")
        tax_report_line_41_tag = cls.env['l10n_lv.tax.report.handler']._get_tax_tags([('name', '=', '41')])[:1]

        # Domestic taxes
        cls.tax_sale_domestic_21G = cls.Template.ref("VAT_S_G_21_LV")
        cls.tax_purchase_domestic_21S = cls.Template.ref("VAT_P_S_21_LV")
        cls.tax_purchase_domestic_car = cls.Template.ref("VAT_P_C_21_LV")
        cls.tax_purchase_domestic_representation = cls.Template.ref("VAT_P_R_21_LV")
        # EU taxes
        cls.tax_sale_eu_0G = cls.Template.ref("VAT_S_EU_G_0_LV")
        cls.tax_purchase_eu_21S = cls.Template.ref("VAT_P_EU_S_21_LV")
        cls.tax_purchase_eu_21G = cls.Template.ref("VAT_P_EU_G_21_LV")
        # Special document_type taxes for testing purposes
        cls.tax_sale_domestic_unreportable = cls.env['account.tax'].create({
            'name': "0% Unreportable",
            'amount': 0,
            'company_id': cls.company_data['company'].id,
            'type_tax_use': 'sale',
            'invoice_repartition_line_ids': [
                Command.create({
                    'repartition_type': 'base',
                    # The tag `tax_report_line_41_tag` is just so that the line shows up in the report
                    # The tag `unreportable_document_type_tag` determines the document type ('X')
                    'tag_ids': [Command.set((tax_report_line_41_tag + cls.unreportable_document_type_tag).ids)],
                }),
                Command.create({
                    'repartition_type': 'tax',
                    'tag_ids': [Command.set((tax_report_line_41_tag + cls.unreportable_document_type_tag).ids)],
                }),
            ],
            'refund_repartition_line_ids': [
                Command.create({
                    'repartition_type': 'base',
                    'tag_ids': [Command.set((tax_report_line_41_tag + cls.unreportable_document_type_tag).ids)],
                }),
                Command.create({
                    'repartition_type': 'tax',
                    'tag_ids': [Command.set((tax_report_line_41_tag + cls.unreportable_document_type_tag).ids)],
                }),
            ],
        })

        cls.test_invoices = cls._setup_test_invoices()

    @classmethod
    def _setup_test_invoices(cls):
        # Domestic sales (Attachment 1-III)
        domestic_sales = [
            # partner_domestic_a (transactions above and below 150€, sum of small transactions below 150€)
            # Also 2 moves with special unreportable document type tag ('X')
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.tax_sale_domestic_21G.ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.tax_sale_domestic_unreportable.ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.tax_sale_domestic_unreportable.ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 10.0,
                        'tax_ids': [Command.set(cls.tax_sale_domestic_21G.ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 10.0,
                        'tax_ids': [Command.set(cls.tax_sale_domestic_21G.ids)],
                    }),
                ],
            },
            # partner_domestic_b (only small transactions, stays below 150€ in total)
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_b.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_sale_domestic_21G.ids)],
                    }),
                ],
            },
            # partner_domestic_c (only small transactions, sum above 150€ in total)
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_sale_domestic_21G.ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_sale_domestic_21G.ids)],
                    }),
                ],
            },
        ]

        # Domestic purchases (Attachment 1-I)
        domestic_purchases = [
            # partner_domestic_a (transactions above and below 150€, sum of small transactions below 150€)
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-12-31',
                'date': '2020-12-31',
                'partner_id': cls.partner_domestic_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.tax_purchase_domestic_21S.ids)],
                    }),
                    # Multiple transactions in single move
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        # Special tax with only 50% appearing deductible
                        'tax_ids': [Command.set(cls.tax_purchase_domestic_car.ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-12-31',
                'date': '2020-12-31',
                'partner_id': cls.partner_domestic_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        # Special tax with only 40% appearing deductible
                        'tax_ids': [Command.set(cls.tax_purchase_domestic_representation.ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-12-31',
                'date': '2020-12-31',
                'partner_id': cls.partner_domestic_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 10.0,
                        'tax_ids': [Command.set(cls.tax_purchase_domestic_21S.ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-12-31',
                'date': '2020-12-31',
                'partner_id': cls.partner_domestic_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 10.0,
                        'tax_ids': [Command.set(cls.tax_purchase_domestic_21S.ids)],
                    }),
                ],
            },
            # partner_domestic_b (only small transactions, stays below 150€ in total)
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_b.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_purchase_domestic_21S.ids)],
                    }),
                ],
            },
            # partner_domestic_c (only small transactions, sum above 150€ in total)
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_purchase_domestic_21S.ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_domestic_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_purchase_domestic_21S.ids)],
                    }),
                ],
            },
        ]

        # EU sales (Attachment 2)
        eu_sales = [
            # partner_eu_a (transactions above and below 150€, sum of small transactions below 150€)
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.tax_sale_eu_0G.ids)],
                    }),
                    # Multiple transactions in single move
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.tax_sale_eu_0G.ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 10.0,
                        'tax_ids': [Command.set(cls.tax_sale_eu_0G.ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 10.0,
                        'tax_ids': [Command.set(cls.tax_sale_eu_0G.ids)],
                    }),
                ],
            },
            # partner_eu_b (only small transactions, stays below 150€ in total)
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_b.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_sale_eu_0G.ids)],
                    }),
                ],
            },
            # partner_eu_c (only small transactions, sum above 150€ in total)
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_sale_eu_0G.ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_sale_eu_0G.ids)],
                    }),
                ],
            },
            # partner_eu_d (only 1 transaction above 150€ in company currency and below 150€ in document currency)
            {
                'move_type': 'out_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_d.id,
                'currency_id': cls.other_currency.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_sale_eu_0G.ids)],
                    }),
                ],
            },
        ]

        # EU purchases (Attachment 1-II)
        eu_purchases = [
            # partner_eu_a (transactions above and below 150€, sum of small transactions below 150€)
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-12-31',
                'date': '2020-12-31',
                'partner_id': cls.partner_eu_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.tax_purchase_eu_21S.ids)],
                    }),
                    # Multiple transactions in single move
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.tax_purchase_eu_21G.ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-12-31',
                'date': '2020-12-31',
                'partner_id': cls.partner_eu_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 10.0,
                        'tax_ids': [Command.set(cls.tax_purchase_eu_21S.ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-12-31',
                'date': '2020-12-31',
                'partner_id': cls.partner_eu_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 10.0,
                        'tax_ids': [Command.set(cls.tax_purchase_eu_21S.ids)],
                    }),
                ],
            },
            # partner_eu_b (only small transactions, stays below 150€ in total)
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_b.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_purchase_eu_21S.ids)],
                    }),
                ],
            },
            # partner_eu_c (only small transactions, sum above 150€ in total)
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_purchase_eu_21S.ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_purchase_eu_21S.ids)],
                    }),
                ],
            },
            # partner_eu_d (only 1 transaction above 150€ in company currency and below 150€ in document currency)
            {
                'move_type': 'in_invoice',
                'invoice_date': '2020-01-01',
                'date': '2020-01-01',
                'partner_id': cls.partner_eu_d.id,
                'currency_id': cls.other_currency.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.tax_purchase_eu_21S.ids)],
                    }),
                ],
            },
        ]
        invoices = cls.env['account.move'].create(
            domestic_sales + domestic_purchases + eu_sales + eu_purchases
        )
        invoices.action_post()
        return invoices

    def test_report_attachment_1_i(self):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_attachment_1i')
        options = self._generate_options(report, fields.Date.to_date('2020-01-01'), fields.Date.to_date('2020-12-31'))
        lines = report._get_lines(options)[1:]  # We remove the first line as it is just a summary line

        self.assertLinesValues(
            lines,
            #            | partner                       |  transaction                     | document
            #            | vat               name        |  type    base_amount  tax_amount | type    number               date
            [0,            1,                2,             3,       4,           5,           6,     7,                    8],
            [
                ('',       'LV40003032949',  'domestic_a',  'A',     1000.0,      210.0,      '1',    'BILL/2020/12/0001',  '12/31/2020'),
                ('',       'LV40003032949',  'domestic_a',  'C',      500.0,      105.0,      '1',    'BILL/2020/12/0001',  '12/31/2020'),
                ('',       'LV40003032949',  'domestic_a',  'A',      400.0,       84.0,      '1',    'BILL/2020/12/0002',  '12/31/2020'),
                ('',       'LV40003520643',  'domestic_c',  'V',      200.0,       42.0,      '',    '',                   ''),
                ('',       '',               '',            'T',      120.0,       25.2,      '',     '',                   ''),
                ('Total ', '',               '',            '',      2220.0,      466.2,      '',     '',                   ''),
            ],
            options,
        )

    def test_report_attachment_1_ii(self):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_attachment_1ii')
        options = self._generate_options(report, fields.Date.to_date('2020-01-01'), fields.Date.to_date('2020-12-31'))
        lines = report._get_lines(options)[1:]  # We remove the first line as it is just a summary line

        self.assertLinesValues(
            lines,
            #            |  partner                | transaction             |  document
            #            |  vat              name  | type   base     tax     |  base       currency      number            date
            [0,             1,               2,       3,       4,       5,      6,         7,            8,                9],
            [
                ('',       'BE0477472701',   'eu_a',  'G',     1000.0,  210.0,  '1,000.0', 'EUR',        'BILL/2020/12/0005', '12/31/2020'),
                ('',       'BE0477472701',   'eu_a',  'P',     1000.0,  210.0,  '1,000.0', 'EUR',        'BILL/2020/12/0005', '12/31/2020'),
                ('',       'FR23334175221',  'eu_d',  'P',      200.0,   42.0,    '100.0', 'USD',        'BILL/2020/01/0007', '01/01/2020'),
                ('',       'EL047747210',    'eu_c',  'V',      200.0,   42.0,    '200.0', 'EUR',        '',               ''),
                ('',       '',               '',      'T',      120.0,   25.2,    '120.0', 'EUR',        '',               ''),
                ('Total ', '',               '',      '',      2520.0,  529.2,  '',        '',           '',               ''),
            ],
            options,
        )

    def test_report_attachment_1_iii(self):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_attachment_1iii')
        options = self._generate_options(report, fields.Date.to_date('2020-01-01'), fields.Date.to_date('2020-12-31'))
        lines = report._get_lines(options)[1:]  # We remove the first line as it is just a summary line

        self.assertLinesValues(
            # line: vat declaration line code / number
            lines,
            #            |  partner                       | transaction             | document
            #            |  vat              name         | line    base     tax    | type       number            date
            [0,             1,               2,             3,     4,       5,       6,         7,                8],
            [
                ('',       'LV40003032949',  'domestic_a',  '41',  1000.0,  210.0,   '1',       'INV/2020/00001', '01/01/2020'),
                ('',       'LV40003032949',  'domestic_a',  '',    2000.0,    0.0,   'X',       '',               ''),
                ('',       'LV40003520643',  'domestic_c',  '',     200.0,   42.0,   'V',       '',               ''),
                ('',       '',               '',            '',     120.0,   25.2,   'T',       '',               ''),
                ('Total ', '',               '',            '',    3320.0,  277.2,   '',        '',               ''),
            ],
            options,
        )

    def test_report_attachment_2(self):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_attachment_2')
        options = self._generate_options(report, fields.Date.to_date('2020-01-01'), fields.Date.to_date('2020-12-31'))
        lines = report._get_lines(options)[1:]  # We remove the first line as it is just a summary line

        self.assertLinesValues(
            lines,
            #            |  partner        | transaction    |
            #            |  vat            | base     type  | partner_replacement_vat
            [0,             1,               2,       3,      4],
            [
                ('',       'BE0477472701',   2000.0,  'G',    ''),
                ('',       'BE0477472701',     10.0,  'G',    ''),
                ('',       'BE0477472701',     10.0,  'G',    ''),
                ('',       'DE0477472701',    100.0,  'G',    ''),
                ('',       'EL047747210',     100.0,  'G',    ''),
                ('',       'EL047747210',     100.0,  'G',    ''),
                ('',       'FR23334175221',   200.0,  'G',    ''),
                ('Total ', '',               2520.0,  '',     ''),
            ],
            options,
        )

    def test_xml_export(self):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_with_attachments')
        custom_handler = self.env[report.custom_handler_model_name]

        options = self._generate_options(report, fields.Date.to_date('2020-01-01'), fields.Date.to_date('2020-12-31'))
        report_xml = custom_handler.export_tax_report_to_xml(options)['file_content']
        expected_xml = self._read_file('l10n_lv_tax_report/tests/files/expected_export.xml').encode()

        report_xml_tree = self.get_xml_tree_from_string(report_xml)
        expected_xml_tree = self.get_xml_tree_from_string(expected_xml)
        self.assertXmlTreeEqual(report_xml_tree, expected_xml_tree)

    def test_xml_export_dates(self):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_with_attachments')
        custom_handler = self.env[report.custom_handler_model_name]

        subtests = [
            # Year
            {
                "start_date": '2000-01-01',
                "end_date": '2000-12-31',
                "expected_date_xml_snippet": """
                    <ParskGads>2000</ParskGads>
                """
            },
            # Quarter
            {
                "start_date": '2001-04-01',
                "end_date": '2001-06-30',
                "expected_date_xml_snippet": """
                    <ParskGads>2001</ParskGads>
                    <ParskCeturknis>2</ParskCeturknis>
                """
            },
            # Month
            {
                "start_date": '2002-08-01',
                "end_date": '2002-08-31',
                "expected_date_xml_snippet": """
                    <ParskGads>2002</ParskGads>
                    <ParskMen>08</ParskMen>
                """
            },
        ]

        for test in subtests:
            start_date = test['start_date']
            end_date = test['end_date']
            expected_date_xml_snippet = test['expected_date_xml_snippet']
            with self.subTest(sub_test_name=f"date range: {start_date} - {end_date}"):
                # Check Year
                options = self._generate_options(report, fields.Date.to_date(start_date), fields.Date.to_date(end_date))
                report_xml = custom_handler.export_tax_report_to_xml(options)['file_content']
                expected_xml = f"""
<DokPVNv7 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <Precizejums>false</Precizejums>
    {expected_date_xml_snippet}
    <NmrKods>41234567891</NmrKods>
    <Talrunis>+37120000000</Talrunis>
    <Epasts>info@company_1_data.lv</Epasts>
    <PVN>___ignore___</PVN>
    <PVN1I>___ignore___</PVN1I>
    <PVN1II>___ignore___</PVN1II>
    <PVN1III>___ignore___</PVN1III>
    <PVN2>___ignore___</PVN2>
</DokPVNv7>
            """

                report_xml_tree = self.get_xml_tree_from_string(report_xml)
                expected_xml_tree = self.get_xml_tree_from_string(expected_xml)
                self.assertXmlTreeEqual(report_xml_tree, expected_xml_tree)
