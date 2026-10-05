from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.tools import file_open
from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class SlovakiaTaxReportTest(AccountSalesReportCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountSalesReportCommon.setup_country('sk')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.update({
            'name': 'Slovakian Company',
            'vat': 'SK2022749619',
            'phone': '+421900000000',
            'email': 'info@example.sk',
        })
        cls.company.partner_id.additional_identifiers = {'SK_EN': '12345678'}
        cls.company.partner_id.update({
            'name': 'Slovakian Company',
            'street': 'Mlynske nivy 1',
            'zip': '81101',
            'city': 'Bratislava',
            'phone': '+421900000001',
            'email': 'tax@example.sk',
        })

    @freeze_time('2019-12-31')
    def setUp(self):
        super().setUp()
        company = self.env.company
        sale_tax = self.env.ref(f'account.{company.id}_vy_tuz_19')
        purchase_tax = self.env.ref(f'account.{company.id}_vs_tuz_19')
        invoice_date = '2019-11-12'

        self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'journal_id': self.company_data['default_journal_sale'].id,
            'partner_id': self.partner_a.id,
            'invoice_date': invoice_date,
            'date': invoice_date,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_a.id,
                    'quantity': 1.0,
                    'name': 'product test 1',
                    'price_unit': 100,
                    'tax_ids': sale_tax.ids,
                }),
            ],
        }, {
            'move_type': 'in_invoice',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'partner_id': self.partner_a.id,
            'invoice_date': invoice_date,
            'date': invoice_date,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_b.id,
                    'quantity': 1.0,
                    'name': 'product test 2',
                    'price_unit': 50,
                    'tax_ids': purchase_tax.ids,
                }),
            ],
        }]).action_post()

    @freeze_time('2019-12-31')
    def test_generate_xml(self):
        report = self.env.ref('l10n_sk.l10n_sk_vat_report')
        options = report.get_options({})

        generated_xml = self.env[report.custom_handler_model_name].export_to_xml(options)['file_content']
        with file_open('l10n_sk_reports/tests/test_files/DPHv25_export.xml', 'rb') as expected_xml_file:
            expected_xml = expected_xml_file.read()

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(generated_xml),
            self.get_xml_tree_from_string(expected_xml),
        )
