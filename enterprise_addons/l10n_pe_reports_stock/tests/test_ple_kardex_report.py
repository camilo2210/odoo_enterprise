from freezegun import freeze_time

from odoo.addons.sale.tests.common import TestSaleCommon
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo import Command
from odoo.tests import Form, tagged
from odoo.tools import mute_logger


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestPleKardexReport(TestSaleCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data["company"].country_id = cls.env.ref("base.pe")
        cls.company_data["company"].vat = "20512528458"
        cls.partner_a.write({"country_id": cls.env.ref("base.pe").id, "vat": "20557912879"})
        cls.company_data['product_order_no'].categ_id.property_cost_method = "average"
        cls.company_data['product_order_no'].is_storable = True
        cls.company_data['product_delivery_no'].is_storable = True

    def test_kardex_report(self):
        """Ensure that the Kardex report is generated correctly using both a Sale Order and a Purchase Order.
            Steps:
            1. Create a Purchase Order to bring products into inventory.
            2. Create a Sale Order to move products out of inventory.
            3. Generate the 12.1 report.
            4. Generate the 13.1 report.
            5. Create another Sale Order in a new period.
            6. Generate the 13.1 report again to verify that historical quantities are properly considered.
        """
        with freeze_time('2024-01-01'):
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

            # First picking and invoice
            picking = purchase.picking_ids
            picking.move_line_ids.write({'quantity': 3.0, 'picked': True})
            action_data = picking.button_validate()
            backorder_wizard = Form(self.env['stock.backorder.confirmation'].with_context(action_data['context'])).save()
            backorder_wizard.process()

            move_form = Form(self.env['account.move'].with_context(default_move_type='in_invoice'))
            move_form.partner_id = self.partner_a
            with mute_logger('odoo.tests.form.onchange'):  # Mute "x PO lines added to the bill" notification
                move_form.purchase_vendor_bill_id = self.env['purchase.bill.union'].browse(-purchase.id)
            move_form.invoice_date = '2024-01-01'
            move_form.l10n_latam_document_type_id = self.env.ref("l10n_pe.document_type01")
            move_form.l10n_latam_document_number = "BILL/2024/01/0001"
            invoice = move_form.save()
            invoice.action_post()

            # Second picking and invoice
            picking = self.env['stock.picking'].search([('backorder_id', '=', picking.id)])
            picking.move_line_ids.write({'quantity': 2.0, 'picked': True})
            picking.button_validate()

            move_form = Form(self.env['account.move'].with_context(default_move_type='in_invoice'))
            move_form.partner_id = self.partner_a
            with mute_logger('odoo.tests.form.onchange'):  # Mute "x PO lines added to the bill" notification
                move_form.purchase_vendor_bill_id = self.env['purchase.bill.union'].browse(-purchase.id)
            move_form.invoice_date = '2024-01-02'
            move_form.l10n_latam_document_type_id = self.env.ref("l10n_pe.document_type01")
            move_form.l10n_latam_document_number = "BILL/2024/01/0002"
            invoice = move_form.save()
            invoice.action_post()

            # Sale order
            sale = self.env['sale.order'].create({
                'partner_id': self.partner_a.id,
                'partner_invoice_id': self.partner_a.id,
                'partner_shipping_id': self.partner_a.id,
                'order_line': [
                    Command.create({
                        'name': p.name,
                        'product_id': p.id,
                        'product_uom_qty': 2,
                        'price_unit': p.list_price,
                        'tax_ids': [Command.set(self.env.ref(f"account.{self.env.company.id}_sale_tax_igv_18").ids)],
                    }) for p in (
                        self.company_data['product_order_no'],
                        self.company_data['product_service_delivery'],
                        self.company_data['product_service_order'],
                        self.company_data['product_delivery_no'],
                    )],
                'picking_policy': 'direct',
            })

            # confirm our standard so, check the picking
            sale.action_confirm()
            self.assertTrue(sale.picking_ids, 'Sale Stock: no picking created for "invoice on delivery" storable products')

            # Process picking
            pick = sale.picking_ids
            pick.move_ids.write({'quantity': 2, 'picked': True})
            pick.button_validate()

            # invoice on order
            sale._create_invoices()
            sale.invoice_ids.action_post()

            # ==== Report 12.1 ====
            wizard_form = Form(self.env['l10n_pe.stock.ple.wizard'])
            wizard_form.date_from = '2024-01-01'
            wizard_form.date_to = '2024-01-31'
            report = wizard_form.save()

            report.get_ple_report_12_1()

            self.maxDiff = None
            report_lines = ['|'.join(element.split('|')[2:]) for element in report.report_data.decode().split('\n')]
            # In 19.0, order is by product_id (name), date, id.
            # product_delivery_no sorts before product_order_no alphabetically.
            # Both PO moves share the same purchase_line_id so both show bill 0001
            # (first-created, via .sorted('id')[:1]).
            self.assertSequenceEqual(
                report_lines,
                [
                    'M1|0000|1|99|FURN7777|1||01/01/2024|01|FFFI|00000001|01|product_delivery_no|NIU|0.00|-2.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/01/2024|01|FBILL202401|0001|02|product_order_no|NIU|3.00|0.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/01/2024|01|FBILL202401|0001|02|product_order_no|NIU|2.00|0.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/01/2024|01|FFFI|00000001|01|product_order_no|NIU|0.00|-2.00|1|',
                    '',
                ]
            )

            # ==== Report 13.1 ====
            wizard_form = Form(self.env['l10n_pe.stock.ple.wizard'])
            wizard_form.date_from = '2024-01-01'
            wizard_form.date_to = '2024-01-31'
            report = wizard_form.save()

            report.get_ple_report_13_1()

            report_lines_131 = ['|'.join(element.split('|')[2:]) for element in report.report_data.decode().split('\n')]
            # Same product ordering as 12.1. Running balances accumulate per product.
            self.assertSequenceEqual(
                report_lines_131,
                [
                    'M1|0000|1|99|FURN7777|1||01/01/2024|01|FFFI|00000001|01|product_delivery_no|NIU|1|0.00|0.00|0.00|-2.00|55.00|-110.00|-2.00|55.00|-110.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/01/2024|01|FBILL202401|0001|02|product_order_no|NIU|1|3.00|500.00|1500.00|0.00|0.00|0.00|3.00|500.00|1500.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/01/2024|01|FBILL202401|0001|02|product_order_no|NIU|1|2.00|500.00|1000.00|0.00|0.00|0.00|5.00|500.00|2500.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/01/2024|01|FFFI|00000001|01|product_order_no|NIU|1|0.00|0.00|0.00|-2.00|500.00|-1000.00|3.00|500.00|1500.00|1|',
                    '',
                ]
            )

        with freeze_time('2024-02-01'):
            # ==== Report 13.1 Initial lines ====
            # Sale order
            sale = self.env['sale.order'].create({
                'partner_id': self.partner_a.id,
                'partner_invoice_id': self.partner_a.id,
                'partner_shipping_id': self.partner_a.id,
                'order_line': [
                    Command.create({
                        'name': p.name,
                        'product_id': p.id,
                        'product_uom_qty': 2,
                        'price_unit': p.list_price,
                        'tax_ids': [Command.set(self.env.ref(f"account.{self.env.company.id}_sale_tax_igv_18").ids)],
                    }) for p in (
                        self.company_data['product_order_no'],
                        self.company_data['product_service_delivery'],
                        self.company_data['product_service_order'],
                        self.company_data['product_delivery_no'],
                    )],
                'picking_policy': 'direct',
            })

            # confirm our standard so, check the picking
            sale.action_confirm()
            self.assertTrue(sale.picking_ids, 'Sale Stock: no picking created for "invoice on delivery" storable products')

            # Process picking
            pick = sale.picking_ids
            pick.move_ids.write({'quantity': 2, 'picked': True})
            pick.button_validate()

            # invoice on order
            sale._create_invoices()
            sale.invoice_ids.action_post()

            # Create a reversal picking
            picking = pick._create_return()
            picking.move_ids.product_uom_qty = 2.0
            picking.move_ids.picked = True
            picking.button_validate()

            wizard_form = Form(self.env['l10n_pe.stock.ple.wizard'])
            wizard_form.date_from = '2024-02-01'
            wizard_form.date_to = '2024-02-28'
            report = wizard_form.save()

            report.get_ple_report_13_1()

            report_lines_feb = ['|'.join(element.split('|')[2:]) for element in report.report_data.decode().split('\n')]
            # In 19.0, product_delivery_no sorts before product_order_no by name.
            # Opening balances (A1/16) + Feb movements + returns (operation_type 24).
            # All values match 18.0, only product ordering differs.
            self.assertSequenceEqual(
                report_lines_feb,
                [
                    'A1|0000|1|99|FURN7777|1||01/02/2024|00|0|0|16|product_delivery_no|NIU|1|0.00|55.00|0.00|-2.00|55.00|-110.00|-2.00|55.00|-110.00|1|',
                    'M1|0000|1|99|FURN7777|1||01/02/2024|01|FFFI|00000002|01|product_delivery_no|NIU|1|0.00|0.00|0.00|-2.00|55.00|-110.00|-4.00|55.00|-220.00|1|',
                    'M1|0000|1|99|FURN7777|1||01/02/2024|01|FFFI|00000002|24|product_delivery_no|NIU|1|2.00|55.00|110.00|0.00|0.00|0.00|-2.00|55.00|-110.00|1|',
                    'A1|0000|1|99|FURN9999|1||01/02/2024|00|0|0|16|product_order_no|NIU|1|3.00|500.00|1500.00|0.00|0.00|0.00|3.00|500.00|1500.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/02/2024|01|FFFI|00000002|01|product_order_no|NIU|1|0.00|0.00|0.00|-2.00|500.00|-1000.00|1.00|500.00|500.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/02/2024|01|FFFI|00000002|24|product_order_no|NIU|1|2.00|500.00|1000.00|0.00|0.00|0.00|3.00|500.00|1500.00|1|',
                    '',
                ]
            )

        with freeze_time('2024-03-01'):
            # Purchase at a different price to shift the average cost
            purchase_mar = self.env['purchase.order'].create({
                'partner_id': self.partner_a.id,
                'order_line': [
                    Command.create({
                        'name': self.company_data['product_order_no'].name,
                        'product_id': self.company_data['product_order_no'].id,
                        'product_qty': 7.0,
                        'uom_id': self.company_data['product_order_no'].uom_id.id,
                        'price_unit': 333.33,
                    })],
            })
            purchase_mar.button_confirm()
            picking = purchase_mar.picking_ids
            picking.move_line_ids.write({'quantity': 7.0, 'picked': True})
            picking.button_validate()

            move_form = Form(self.env['account.move'].with_context(default_move_type='in_invoice'))
            move_form.partner_id = self.partner_a
            with mute_logger('odoo.tests.form.onchange'):  # Mute "x PO lines added to the bill" notification
                move_form.purchase_vendor_bill_id = self.env['purchase.bill.union'].browse(-purchase_mar.id)
            move_form.invoice_date = '2024-03-01'
            move_form.l10n_latam_document_type_id = self.env.ref("l10n_pe.document_type01")
            move_form.l10n_latam_document_number = "BILL/2024/03/0001"
            invoice = move_form.save()
            invoice.action_post()

            product_order = self.company_data['product_order_no']
            self.assertNotAlmostEqual(product_order.standard_price, 500.0, places=2)

            # Re-generate Feb report: opening balance must not be
            # affected by the March purchase that changed standard_price
            wizard_form = Form(self.env['l10n_pe.stock.ple.wizard'])
            wizard_form.date_from = '2024-02-01'
            wizard_form.date_to = '2024-02-28'
            report = wizard_form.save()
            report.get_ple_report_13_1()

            report_lines_feb2 = [
                '|'.join(element.split('|')[2:])
                for element in report.report_data.decode().split('\n')
            ]
            self.assertSequenceEqual(
                report_lines_feb2,
                [
                    'A1|0000|1|99|FURN7777|1||01/02/2024|00|0|0|16|product_delivery_no|NIU|1|0.00|55.00|0.00|-2.00|55.00|-110.00|-2.00|55.00|-110.00|1|',
                    'M1|0000|1|99|FURN7777|1||01/02/2024|01|FFFI|00000002|01|product_delivery_no|NIU|1|0.00|0.00|0.00|-2.00|55.00|-110.00|-4.00|55.00|-220.00|1|',
                    'M1|0000|1|99|FURN7777|1||01/02/2024|01|FFFI|00000002|24|product_delivery_no|NIU|1|2.00|55.00|110.00|0.00|0.00|0.00|-2.00|55.00|-110.00|1|',
                    'A1|0000|1|99|FURN9999|1||01/02/2024|00|0|0|16|product_order_no|NIU|1|3.00|500.00|1500.00|0.00|0.00|0.00|3.00|500.00|1500.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/02/2024|01|FFFI|00000002|01|product_order_no|NIU|1|0.00|0.00|0.00|-2.00|500.00|-1000.00|1.00|500.00|500.00|1|',
                    'M1|0000|1|99|FURN9999|1||01/02/2024|01|FFFI|00000002|24|product_order_no|NIU|1|2.00|500.00|1000.00|0.00|0.00|0.00|3.00|500.00|1500.00|1|',
                    '',
                ]
            )

    def _receive_in_uom(self, product, uom, qty, unit_cost):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        move = self.env['stock.move'].create({
            'product_id': product.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': warehouse.lot_stock_id.id,
            'uom_id': uom.id,
            'product_uom_qty': qty,
            'price_unit': unit_cost,
            'picking_type_id': warehouse.in_type_id.id,
        })
        move._action_confirm()
        move._action_assign()
        move.move_line_ids.quantity = qty
        move.picked = True
        move._action_done()
        return move

    def test_kardex_report_opening_balance_no_period_moves(self):
        """A period with stock but no movements still reports opening balances.

        The stock is recorded in dozens, so the opening line must also convert
        the quantity to the product's reference unit (24 units, not 2 dozen).
        """
        dozen = self.env.ref('uom.product_uom_dozen')
        self.company_data['product_order_no'].standard_price = 100.0
        with freeze_time('2024-01-15'):
            self._receive_in_uom(self.company_data['product_order_no'], dozen, 2.0, 100.0)

        with freeze_time('2024-02-01'):
            wizard_form = Form(self.env['l10n_pe.stock.ple.wizard'])
            wizard_form.date_from = '2024-02-01'
            wizard_form.date_to = '2024-02-28'
            report = wizard_form.save()
            report.get_ple_report_13_1()

            self.maxDiff = None
            report_lines = ['|'.join(element.split('|')[2:]) for element in report.report_data.decode().split('\n')]
            # 2 dozen at 100 per unit -> 24 units worth 2400.
            self.assertSequenceEqual(
                report_lines,
                [
                    'A1|0000|1|99|FURN9999|1||01/02/2024|00|0|0|16|product_order_no|NIU|1|24.00|100.00|2400.00|0.00|0.00|0.00|24.00|100.00|2400.00|1|',
                    '',
                ]
            )
