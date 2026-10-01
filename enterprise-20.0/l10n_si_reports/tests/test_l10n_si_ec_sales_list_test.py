from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.tools import misc
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nSIECSalesListXMLValues(AccountSalesReportCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('si')
    def setUpClass(cls):
        super().setUpClass()

        cls.si_company = cls.company_data['company']

        cls.si_company.write({'country_id': cls.env.ref('base.si').id, 'vat': 'SI12345679'})

        cls.tax_a3_goods = cls.env['account.tax'].search([('name', '=', '0% EU G'), ('company_id', '=', cls.si_company.id)], limit=1)
        cls.tax_a5_tri = cls.env['account.tax'].search([('name', '=', '0% EU G Tri'), ('company_id', '=', cls.si_company.id)], limit=1)
        cls.tax_a6_services = cls.env['account.tax'].search([('name', '=', '0% EU S'), ('company_id', '=', cls.si_company.id)], limit=1)
        (cls.tax_a3_goods | cls.tax_a5_tri | cls.tax_a6_services).write({'active': True})

        cls.partner_be = cls.env['res.partner'].create({'name': 'Partner BE', 'country_id': cls.env.ref('base.be').id, 'vat': 'BE0477472701'})
        cls.partner_at = cls.env['res.partner'].create({'name': 'Partner AT', 'country_id': cls.env.ref('base.at').id, 'vat': 'ATU12345675'})
        cls.partner_it = cls.env['res.partner'].create({'name': 'Partner IT', 'country_id': cls.env.ref('base.it').id, 'vat': 'IT12345670017'})
        cls.partner_fr = cls.env['res.partner'].create({'name': 'Partner FR', 'country_id': cls.env.ref('base.fr').id, 'vat': 'FR23334175221'})

        cls.product_good = cls.env['product.product'].create({'name': 'Product - Good', 'lst_price': 1.0})
        cls.product_service = cls.env['product.product'].create({'name': 'Product - Service', 'lst_price': 1.0, 'type': 'service'})

        cls.at_partner_invoice = cls.env['account.move'].create({
                'partner_id': cls.partner_at.id,
                'invoice_date': '2025-01-10',
                'move_type': 'out_invoice',
                'invoice_line_ids': [
                    Command.create({'product_id': cls.product_service.id, 'price_unit': 12500.0, 'tax_ids': [Command.set(cls.tax_a5_tri.ids)]}),
                ]})

        cls.it_partner_invoice = cls.env['account.move'].create({
                'partner_id': cls.partner_it.id,
                'invoice_date': '2025-03-25',
                'move_type': 'out_invoice',
                'invoice_line_ids': [
                    Command.create({'product_id': cls.product_service.id, 'price_unit': 500.0, 'tax_ids': [Command.set(cls.tax_a5_tri.ids)]}),
                    Command.create({'product_id': cls.product_good.id, 'price_unit': 35000.0, 'tax_ids': [Command.set(cls.tax_a6_services.ids)]}),
                    Command.create({'product_id': cls.product_good.id, 'price_unit': 151.0, 'tax_ids': [Command.set(cls.tax_a3_goods.ids)]}),
                ]})
        cls.fr_partner_invoice = cls.env['account.move'].create({
                'partner_id': cls.partner_fr.id,
                'invoice_date': '2025-04-05',
                'move_type': 'out_invoice',
                'invoice_line_ids': [
                    Command.create({'product_id': cls.product_good.id, 'price_unit': 8349.0, 'tax_ids': [Command.set(cls.tax_a3_goods.ids)]}),
                ]})
        cls.be_partner_invoice = cls.env['account.move'].create({
                'partner_id': cls.partner_be.id,
                'invoice_date': '2025-03-28',
                'move_type': 'out_invoice',
                'invoice_line_ids': [
                    Command.create({'product_id': cls.product_good.id, 'price_unit': 200.0, 'tax_ids': [Command.set(cls.tax_a6_services.ids)]}),
                    Command.create({'product_id': cls.product_good.id, 'price_unit': 1000.0, 'tax_ids': [Command.set(cls.tax_a3_goods.ids)]}),
                ]})
        (cls.at_partner_invoice + cls.it_partner_invoice + cls.fr_partner_invoice + cls.be_partner_invoice).action_post()

    @freeze_time('2025-12-31')
    def test_l10n_si_generate_vies_xml(self):
        report = self.env.ref('l10n_si_reports.l10n_si_ec_sales_report')
        options = report.get_options({
            'date': {
                'date_from': '2025-01-01',
                'date_to': '2025-12-31'
            }
        })
        xml_content = self.env[report.custom_handler_model_name].l10n_si_export_ec_sales_list_report_to_xml(options)
        generated_xml_bytes = xml_content.get('file_content')
        expected_xml_path = 'l10n_si_reports/tests/l10n_si_test_ec_sales_list.xml'
        expected_xml_bytes = misc.file_open(expected_xml_path, mode='rb').read()
        self.assertXMLEqual(generated_xml_bytes, expected_xml_bytes)
