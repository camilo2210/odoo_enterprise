from freezegun import freeze_time

from odoo.addons.sale.tests.common import TestSaleCommon
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo import Command
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestPleKardexLandedCost(TestSaleCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data["company"].country_id = cls.env.ref("base.pe")
        cls.company_data["company"].vat = "20512528458"
        cls.partner_a.write({"country_id": cls.env.ref("base.pe").id, "vat": "20557912879"})
        cls.company_data['product_order_no'].categ_id.property_cost_method = "average"
        cls.company_data['product_order_no'].is_storable = True
        cls.landed_cost_product = cls.env['product.product'].create({
            'name': 'Landed Cost',
            'type': 'service',
            'landed_cost_ok': True,
            'property_account_expense_id': cls.company_data['default_account_expense'].id,
        })

    @freeze_time('2026-01-01')
    def test_kardex_report_landed_cost(self):
        """Ensure that a landed cost is reported as its own Kardex line.

        The receipt line keeps the goods cost while the landed cost is shown
        separately with operation type 26, on top of the running balance.
        """
        # Purchase
        purchase = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({
                    'name': self.company_data['product_order_no'].name,
                    'product_id': self.company_data['product_order_no'].id,
                    'product_qty': 5.0,
                    'uom_id': self.company_data['product_order_no'].uom_id.id,
                    'price_unit': 500.0,
                })],
        })
        purchase.button_confirm()

        picking = purchase.picking_ids
        picking.move_line_ids.write({'quantity': 5.0, 'picked': True})
        picking.button_validate()

        purchase.action_create_invoice()
        invoice = purchase.invoice_ids
        invoice.write({
            'invoice_date': '2026-01-01',
            'l10n_latam_document_type_id': self.env.ref("l10n_pe.document_type01").id,
            'l10n_latam_document_number': "BILL/2026/01/0001",
        })
        invoice.action_post()

        # Add a landed cost on the receipt
        landed_cost = self.env['stock.landed.cost'].create({
            'name': "LC/2026/01/0001",
            'account_journal_id': self.company_data['default_journal_misc'].id,
            'picking_ids': [Command.set(picking.ids)],
            'cost_lines': [Command.create({
                'product_id': self.landed_cost_product.id,
                'price_unit': 250.0,
                'split_method': 'equal',
                'account_id': self.company_data['default_account_expense'].id,
            })],
        })
        landed_cost.compute_landed_cost()
        landed_cost.button_validate()

        # ==== Report 13.1 ====
        report = self.env['l10n_pe.stock.ple.wizard'].create({
            'date_from': '2026-01-01',
            'date_to': '2026-01-31',
        })

        report.get_ple_report_13_1()

        self.maxDiff = None
        report_lines = ['|'.join(element.split('|')[2:]) for element in report.report_data.decode().split('\n')]
        # The receipt line keeps the goods cost (2500). The landed cost is a
        # separate line (operation type 26) adding 250, so the running balance
        # closes at 2750 for an average unit cost of 550.
        self.assertSequenceEqual(
            report_lines,
            [
                'M1|0000|1|99|FURN9999|1||01/01/2026|01|FBILL202601|0001|02|product_order_no|NIU|1|5.00|500.00|2500.00|0.00|0.00|0.00|5.00|500.00|2500.00|1|',
                'M1|0000|1|99|FURN9999|1||01/01/2026|00|LC202601|0001|26|product_order_no|NIU|1|0.00|250.00|250.00|0.00|0.00|0.00|5.00|550.00|2750.00|1|',
                '',
            ]
        )

    @freeze_time('2026-01-01')
    def test_kardex_report_negative_landed_cost(self):
        """A negative landed cost (a rebate) lands in the salida columns.

        The receipt line keeps the goods cost (2500), the rebate shows 200 in
        the out columns and the running balance drops to 2300.
        """
        purchase = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [
                Command.create({
                    'name': self.company_data['product_order_no'].name,
                    'product_id': self.company_data['product_order_no'].id,
                    'product_qty': 5.0,
                    'uom_id': self.company_data['product_order_no'].uom_id.id,
                    'price_unit': 500.0,
                })],
        })
        purchase.button_confirm()

        picking = purchase.picking_ids
        picking.move_line_ids.write({'quantity': 5.0, 'picked': True})
        picking.button_validate()

        purchase.action_create_invoice()
        invoice = purchase.invoice_ids
        invoice.write({
            'invoice_date': '2026-01-01',
            'l10n_latam_document_type_id': self.env.ref("l10n_pe.document_type01").id,
            'l10n_latam_document_number': "BILL/2026/01/0001",
        })
        invoice.action_post()

        landed_cost = self.env['stock.landed.cost'].create({
            'name': "LC/2026/01/0001",
            'account_journal_id': self.company_data['default_journal_misc'].id,
            'picking_ids': [Command.set(picking.ids)],
            'cost_lines': [Command.create({
                'product_id': self.landed_cost_product.id,
                'price_unit': -200.0,
                'split_method': 'equal',
                'account_id': self.company_data['default_account_expense'].id,
            })],
        })
        landed_cost.compute_landed_cost()
        landed_cost.button_validate()

        report = self.env['l10n_pe.stock.ple.wizard'].create({
            'date_from': '2026-01-01',
            'date_to': '2026-01-31',
        })

        report.get_ple_report_13_1()

        self.maxDiff = None
        report_lines = ['|'.join(element.split('|')[2:]) for element in report.report_data.decode().split('\n')]
        self.assertSequenceEqual(
            report_lines,
            [
                'M1|0000|1|99|FURN9999|1||01/01/2026|01|FBILL202601|0001|02|product_order_no|NIU|1|5.00|500.00|2500.00|0.00|0.00|0.00|5.00|500.00|2500.00|1|',
                'M1|0000|1|99|FURN9999|1||01/01/2026|00|LC202601|0001|26|product_order_no|NIU|1|0.00|0.00|0.00|0.00|200.00|200.00|5.00|460.00|2300.00|1|',
                '',
            ]
        )
