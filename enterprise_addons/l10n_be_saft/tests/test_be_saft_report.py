from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestBESaftReport(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_chart_template('be_comp')
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].write({
            'city': 'Bruxelles',
            'zip': '1000',
            'vat': 'BE0477472701',
            'phone': '+32 2 555 01 23',
            'website': 'https://www.example.com',
            'email': 'info@example.com',
            'street': 'Rue de Croissant 67',
            'country_id': cls.env.ref('base.be').id,
        })
        cls.company_data['company'].partner_id._set_additional_identifier(
            'BE_EN', '0477472701'
        )
        cls.env['res.partner'].create({
            'name': 'Mr Big CEO',
            'is_company': False,
            'phone': '+32 2 555 01 00',
            'email': 'big.CEO@example.com',
            'parent_id': cls.company_data['company'].partner_id.id,
        })

        (cls.partner_a + cls.partner_b).write({
            'street': 'Saftstraat 1',
            'city': 'Antwerpen',
            'zip': '2000',
            'country_id': cls.env.ref('base.be').id,
            'phone': '+32 3 555 11 22',
        })

        cls.partner_a._set_additional_identifier('BE_EN', '0428759497')
        cls.partner_b._set_additional_identifier('BE_EN', '0845253743')

        cls.product_a.default_code = 'PA'
        cls.product_b.default_code = 'PB'

        cls.tax_21_ic_purchase = cls.env['account.chart.template'].ref('attn_VAT-IN-V81-21-ROW-CC')
        cls.tax_21_purchase = cls.env['account.chart.template'].ref('attn_VAT-IN-V81-21')
        cls.tax_6_purchase = cls.env['account.chart.template'].ref('attn_VAT-IN-V81-06')

    @freeze_time('2022-01-01')
    def test_be_saft_report_values(self):
        invoices = self.env['account.move'].create([
            # DOMESTIC PURCHASE TAX EXPECTED SAF-T STRUCTURE
            # -----------------------------------------------------------------------------------------
            #                                     |           TaxInformation          |
            # recordid | account | debit | credit | TaxCode | perc | base | TaxAmount
            # -----------------------------------------------------------------------------------------
            # 1        | 600000.1| 100   |        | 81      | 21   | 100  | 100
            # -----------------------------------------------------------------------------------------
            # 2        | 600000.1| 50    |        | 81      | 6    | 50   | 50
            # -----------------------------------------------------------------------------------------
            # 3        | 411000  | 21    |        | 59      | 21   | 100  | 21
            # -----------------------------------------------------------------------------------------
            # 4        | 411000  | 3     |        | 59      | 6    | 50   | 3
            # -----------------------------------------------------------------------------------------
            # 5        | 440001  |       | 174    |         |      |      |
            # -----------------------------------------------------------------------------------------
            {
                'move_type': 'in_invoice',
                'invoice_date': '2019-06-30',
                'date': '2019-06-30',
                'partner_id': self.partner_b.id,
                'invoice_payment_term_id': self.pay_terms_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': self.product_a.id,
                        'quantity': 1.0,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(self.tax_21_purchase.ids)],
                    }),
                    Command.create({
                        'product_id': self.product_b.id,
                        'quantity': 1.0,
                        'price_unit': 50.0,
                        'tax_ids': [Command.set(self.tax_6_purchase.ids)],
                    }),
                ],
            },

            # INTERCOMMUNITY PURCHASE TAX EXPECTED SAF-T STRUCTURE
            # -----------------------------------------------------------------------------------------
            #                                     |           TaxInformation          |
            # recordid | account | debit | credit | TaxCode | perc | base | TaxAmount
            # -----------------------------------------------------------------------------------------
            # 1        | 600000.1| 100   |        | 81      | 21   | 100  | 100
            #          |         |       |        | 87      | 21   | 100  | 100
            # -----------------------------------------------------------------------------------------
            # 2        | 411000  | 21    |        | 59      | 21   | 100  | 21
            # -----------------------------------------------------------------------------------------
            # 3        | 451057  |       | 21     | 57      | 21   | 100  | 21
            # -----------------------------------------------------------------------------------------
            # 4        | 440001  |       | 100    |         |      |      |
            # -----------------------------------------------------------------------------------------
            {
                'move_type': 'in_invoice',
                'invoice_date': '2019-01-30',
                'date': '2019-01-30',
                'partner_id': self.partner_b.id,
                'invoice_payment_term_id': self.pay_terms_a.id,
                'invoice_line_ids': [Command.create({
                    'product_id': self.product_b.id,
                    'quantity': 1.0,
                    'price_unit': 100.0,
                    'tax_ids': [Command.set(self.tax_21_ic_purchase.ids)],
                })],
            },

            # Credit note of a purchase (vendor refund)
            # -----------------------------------------------------------------------------------------
            #                                     |           TaxInformation          |
            # recordid | account | debit | credit | TaxCode | perc | base | TaxAmount
            # -----------------------------------------------------------------------------------------
            # 1        | 600000.1|       | 100    | 81      | 21   | 100  | -100
            #          |         |       |        | 85      | 21   | 100  |  100
            # -----------------------------------------------------------------------------------------
            # 2        | 411000  |       | 21     | 63      | 21   | 100  |  21
            # -----------------------------------------------------------------------------------------
            # 3        | 440001  | 121   |        |         |      |     |
            # -----------------------------------------------------------------------------------------
            {
                'move_type': 'in_refund',
                'invoice_date': '2019-01-30',
                'date': '2019-01-30',
                'partner_id': self.partner_b.id,
                'invoice_payment_term_id': self.pay_terms_a.id,
                'invoice_line_ids': [Command.create({
                    'product_id': self.product_b.id,
                    'quantity': 1.0,
                    'price_unit': 100.0,
                    'tax_ids': [Command.set(self.tax_21_purchase.ids)],
                })],
            },
        ])
        invoices.action_post()
        self.env.flush_all()

        # An expression from another country's tax report must not duplicate Belgian tax tags.
        self.env['account.report'].create({
            'name': 'Foreign Tax Report',
            'country_id': self.env.ref('base.fr').id,
            'line_ids': [Command.create({
                'name': 'Foreign Tax Report Line',
                'expression_ids': [Command.create({
                    'label': 'balance',
                    'engine': 'tax_tags',
                    'formula': '81',
                })],
            })],
        })

        report = self.env.ref('account_reports.general_ledger_report')
        options = self._generate_options(report, fields.Date.from_string('2019-01-01'), fields.Date.from_string('2019-12-31'))
        generated_xml = self.env[report.custom_handler_model_name].with_context(skip_xsd=True).l10n_be_export_saft_to_xml(options)['file_content']

        with file_open("l10n_be_saft/tests/xml/expected_test_saft_report.xml", "rb") as expected_xml:
            self.assertXmlTreeEqual(
                self.get_xml_tree_from_string(generated_xml),
                self.get_xml_tree_from_string(expected_xml.read()),
            )
