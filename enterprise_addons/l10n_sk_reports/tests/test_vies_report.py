from freezegun import freeze_time

from odoo import Command
from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon
from odoo.tests import tagged
from odoo.tools import file_open


@tagged('post_install_l10n', 'post_install', '-at_install')
class SlovakiaVIESReportTest(AccountSalesReportCommon):
    @classmethod
    @AccountSalesReportCommon.setup_country('sk')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.update({
            'name': 'Slovakian Company',
            'vat': 'SK2022749619',
        })
        cls.company.partner_id.update({
            'name': 'Slovakian Company',
            'street': 'Mlynske nivy',
            'street2': '1',
            'zip': '81109',
            'city': 'Bratislava',
            'phone': '+421900000001',
            'email': 'tax@example.sk',
        })

        cls.tax_eu_goods = cls.env.ref(f'account.{cls.company.id}_vy_eu_m')
        cls.tax_eu_services = cls.env.ref(f'account.{cls.company.id}_vy_eu_s')
        cls.tax_eu_triangular = cls.env.ref(f'account.{cls.company.id}_vy_eu_t')
        cls.moves = cls.env['account.move'].create([
            {
                'move_type': 'out_invoice',
                'partner_id': cls.partner_a.id,
                'invoice_date': '2024-01-15',
                'date': '2024-01-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_a.id,
                    'quantity': 1.0,
                    'price_unit': 1000.25,
                    'tax_ids': [Command.set(cls.tax_eu_goods.ids)],
                })],
            },
            {
                'move_type': 'out_invoice',
                'partner_id': cls.partner_a.id,
                'invoice_date': '2024-01-15',
                'date': '2024-01-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_a.id,
                    'quantity': 1.0,
                    'price_unit': 250.25,
                    'tax_ids': [Command.set(cls.tax_eu_goods.ids)],
                })],
            },
            {
                'move_type': 'out_invoice',
                'partner_id': cls.partner_a.id,
                'invoice_date': '2024-01-15',
                'date': '2024-01-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_a.id,
                    'quantity': 1.0,
                    'price_unit': 500.49,
                    'tax_ids': [Command.set(cls.tax_eu_services.ids)],
                })],
            },
            {
                'move_type': 'out_refund',
                'partner_id': cls.partner_a.id,
                'invoice_date': '2024-01-15',
                'date': '2024-01-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_a.id,
                    'quantity': 1.0,
                    'price_unit': 100.00,
                    'tax_ids': [Command.set(cls.tax_eu_services.ids)],
                })],
            },
            {
                'move_type': 'out_invoice',
                'partner_id': cls.partner_b.id,
                'invoice_date': '2024-01-15',
                'date': '2024-01-15',
                'invoice_line_ids': [Command.create({
                    'product_id': cls.product_a.id,
                    'quantity': 1.0,
                    'price_unit': 200.50,
                    'tax_ids': [Command.set(cls.tax_eu_triangular.ids)],
                })],
            },
        ])
        cls.moves.action_post()

    @freeze_time('2024-02-01')
    def test_sk_vies_report_lines(self):
        report = self.env.ref('l10n_sk_reports.vies_summary_report')
        options = self._generate_options(report, '2024-01-01', '2024-01-31')
        self.assertLinesValues(
            report._get_lines({**options, 'unfold_all': True}),
            #   Partner                   Country code,              VAT Number,               Transaction Code     Total Value
            [   0,                        1,                         2,                        3,                   4],
            [
              ('VIES Summary Statement',                      '',                        '',    '',                 1851.49),
                (self.partner_a.name,     self.partner_a.vat[:2],    self.partner_a.vat[2:],   '0',                 1250.50),
                (self.partner_a.name,     self.partner_a.vat[:2],    self.partner_a.vat[2:],   '1',                  400.49),
                (self.partner_b.name,     self.partner_b.vat[:2],    self.partner_b.vat[2:],   '2',                  200.50),
            ],
            options,
        )

    @freeze_time('2024-02-01')
    def test_sk_vies_report_xml_export(self):
        report = self.env.ref('l10n_sk_reports.vies_summary_report')
        options = self._generate_options(report, '2024-01-01', '2024-01-31')
        generated_xml = self.env[report.custom_handler_model_name].export_to_xml(options)['file_content']

        with file_open('l10n_sk_reports/tests/test_files/SVDPHv20_export.xml', 'rb') as expected_xml_file:
            expected_xml = expected_xml_file.read()

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(generated_xml),
            self.get_xml_tree_from_string(expected_xml),
        )
