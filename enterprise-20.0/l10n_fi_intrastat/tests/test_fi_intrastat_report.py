import io
import zipfile

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestFIIntrastatExport(AccountSalesReportCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountSalesReportCommon.setup_country('fi')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].country_id = cls.env.ref('base.fi')
        cls.company_data['company'].account_fiscal_country_id = cls.env.ref('base.fi')
        cls.company_data['company'].vat = 'FI12345671'

        # Create representative partner for agent VAT
        cls.representative = cls.env['res.partner'].create({
            'name': 'Finnish Accounting Firm',
            'street': 'Tilitoimisto Street 123',
            'city': 'Helsinki',
            'zip': '00100',
            'country_id': cls.env.ref('base.fi').id,
            'vat': 'FI87654321',
            'phone': '+358401234567',
            'email': 'info@tilitoimisto.fi',
        })
        cls.company_data['company'].account_representative_id = cls.representative.id

        cls.report = cls.env.ref('account_intrastat.intrastat_report')
        cls.report_handler = cls.env['account.intrastat.goods.report.handler']

        sweden = cls.env.ref('base.se')

        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Swedish Partner',
            'country_id': sweden.id,
            'vat': 'SE123456789701',
        })

        cls.product_laptop = cls.env['product.product'].create({
            'name': 'Laptop',
            'intrastat_code_id': cls.env.ref('account_intrastat.commodity_code_2018_84713000').id,
            'intrastat_supplementary_unit_amount': 1,
            'weight': 10.5,
            'intrastat_origin_country_id': cls.env.ref('base.fi').id,
        })
        cls.product_wireless_router = cls.env['product.product'].create({
            'name': 'Wireless Router',
            'intrastat_code_id': cls.env.ref('account_intrastat.commodity_code_2018_84713000').id,
            'intrastat_supplementary_unit_amount': 2,
            'weight': 0.3,
            'intrastat_origin_country_id': cls.env.ref('base.fi').id,
        })

        cls.inwards_vendor_bill = cls.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': cls.partner_a.id,
            'invoice_date': '2025-09-15',
            'date': '2025-09-15',
            'intrastat_country_id': sweden.id,
            'intrastat_transport_mode_id': cls.env.ref('account_intrastat.account_intrastat_transport_1').id,
            'company_id': cls.company_data['company'].id,
            'invoice_line_ids': [Command.create({
                'intrastat_transaction_id': cls.env.ref('account_intrastat.account_intrastat_transaction_11').id,
                'product_id': cls.product_laptop.id,
                'quantity': 5,
                'price_unit': 1000,
            })]
        })

        cls.outwards_customer_invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner_a.id,
            'invoice_date': '2025-09-15',
            'date': '2025-09-15',
            'intrastat_country_id': sweden.id,
            'intrastat_transport_mode_id': cls.env.ref('account_intrastat.account_intrastat_transport_2').id,
            'company_id': cls.company_data['company'].id,
            'invoice_line_ids': [Command.create({
                'product_id': cls.product_wireless_router.id,
                'intrastat_transaction_id': cls.env.ref('account_intrastat.account_intrastat_transaction_11').id,
                'quantity': 3,
                'price_unit': 500,
            })]
        })

        cls.inwards_vendor_bill.action_post()
        cls.outwards_customer_invoice.action_post()

    def test_fi_intrastat_csv_export(self):
        options = self._generate_options(
            self.report,
            '2025-09-01',
            '2025-09-30',
            {'unfold_all': True, 'export_mode': 'file'}
        )

        lines = self.report._get_lines(options)
        self.assertTrue(lines)

        file_response = self.report_handler.fi_intrastat_export_to_csv(options)
        self.assertEqual(file_response['file_type'], 'zip')

        # Extract and check ZIP content
        with io.BytesIO(file_response['file_content']) as zip_buffer:
            with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                # Should contain arrivals and dispatches files
                self.assertIn('arrivals_intrastat_(goods)_sep_2025.csv', zip_file.namelist())
                self.assertIn('dispatches_intrastat_(goods)_sep_2025.csv', zip_file.namelist())

                # Check arrivals CSV content
                with zip_file.open('arrivals_intrastat_(goods)_sep_2025.csv') as f:
                    arrivals_content = f.read().decode('utf-8')
                arrivals_lines = arrivals_content.strip().split('\n')
                self.assertEqual(len(arrivals_lines), 2)  # Header + 1 data row

                expected_arrival_header = (
                    "Data provider;Period;Direction;Agent;CN8 code;Nature of transaction;"
                    "Country of consignment;Country of origin;Mode of transport;Net mass;"
                    "Quantity in supplementary units;Invoice value in euros;Statistical value in euros;Row reference"
                )
                self.assertEqual(arrivals_lines[0], expected_arrival_header)

                expected_arrival_row = "FI12345671;202509;1;FI87654321;84713000;11;SE;FI;1;52;5;5000;;"
                self.assertEqual(arrivals_lines[1], expected_arrival_row)

                # Check dispatches CSV content
                with zip_file.open('dispatches_intrastat_(goods)_sep_2025.csv') as f:
                    dispatches_content = f.read().decode('utf-8')
                dispatches_lines = dispatches_content.strip().split('\n')
                self.assertEqual(len(dispatches_lines), 2)  # Header + 1 data row

                expected_dispatch_header = (
                    "Data provider;Period;Direction;Trading partner;CN8 code;Nature of transaction;"
                    "Country of destination;Country of origin;Mode of transport;Net mass;"
                    "Quantity in supplementary units;Invoice value in euros;Statistical value in euros;Row reference"
                )
                self.assertEqual(dispatches_lines[0], expected_dispatch_header)

                expected_dispatch_row = "FI12345671;202509;2;SE123456789701;84713000;11;SE;FI;2;0;6;1500;;"
                self.assertEqual(dispatches_lines[1], expected_dispatch_row)
