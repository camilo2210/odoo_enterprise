from odoo import Command
from odoo.addons.l10n_ke_edi_oscu_pos.tests.common import CommonPosKeEdiTest
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.l10n_ke_edi_oscu.tests.common import TestKeEdiCommon
from odoo.addons.l10n_ke_edi_oscu.tests.test_live import TestKeEdi
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEtimsPos(TestKeEdiCommon, CommonPosKeEdiTest):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestKeEdi.setup_country('ke')
    def setUpClass(self):
        super().setUpClass()
        self.company.l10n_ke_server_mode = 'demo'

    def test_etims_post_order(self):
        """Testing the pos order process to make sure everything is correctly sends to eTIMS
        """
        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id
            },
            'line_data': [
                {'product_id': self.twenty_dollars_with_10_incl.product_variant_id.id}
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id}
            ]
        })

        order.action_post_order()
        self.assertEqual(order.l10n_ke_oscu_internal_data, 'GRKJVWYCFBPTYQ225X2UEYONVE')
        self.assertEqual(order.l10n_ke_oscu_signature, '123456789ODOOGR3')
        self.assertEqual(order.l10n_ke_oscu_receipt_number, 169)

        # Send stock move to eTIMS
        with self.enter_registry_test_mode():
            self.env.ref('l10n_ke_edi_oscu_stock.ir_cron_send_stock_moves').method_direct_trigger()
        self.assertEqual(order.picking_ids.l10n_ke_oscu_sar_number, 1)

    def test_combo_line_excluded_from_etims(self):
        """
        A combo adds a "0 price" parent line in the PoS, with the chosen combo item as a
        child line. Only the combo item must be sent to eTIMS, not the combo parent line.
        """
        self.pos_config_usd.open_ui()
        product = self.twenty_dollars_with_10_incl.product_variant_id
        combo = self.env['product.combo'].create({
            'name': 'Drinks Combo',
            'combo_item_ids': [Command.create({'product_id': product.id})],
        })
        combo_product = self.env['product.product'].create({
            'name': 'Burger Combo',
            'type': 'combo',
            'combo_ids': [Command.set(combo.ids)],
        })
        pos_order = self.env['pos.order'].create({
            'session_id': self.pos_config_usd.current_session_id.id,
            'partner_id': self.partner_moda.id,
            'amount_tax': 0.0,
            'amount_total': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
        })
        combo_line = self.env['pos.order.line'].create({
            'order_id': pos_order.id,
            'product_id': combo_product.id,
            'qty': 1,
            'price_subtotal': 0,
            'price_subtotal_incl': 0,
        })
        combo_item_line = self.env['pos.order.line'].create({
            'order_id': pos_order.id,
            'product_id': product.id,
            'qty': 1,
            'price_unit': 100,
            'price_subtotal': 100,
            'price_subtotal_incl': 110,
            'tax_ids': product.taxes_id.ids,
            'combo_item_id': combo.combo_item_ids.id,
            'combo_parent_id': combo_line.id,
        })

        line_items = pos_order._l10n_ke_oscu_get_json_from_order_lines()
        self.assertEqual(len(line_items), 1, "the combo parent line must not be sent to eTIMS")
        self.assertEqual(line_items[0]['itemNm'], combo_item_line.name, "only the combo item line should be sent")

    def test_invoice_order(self):
        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id,
                'to_invoice': True,
            },
            'line_data': [
                {'product_id': self.twenty_dollars_with_10_incl.product_variant_id.id}
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id}
            ]
        })

        order.action_post_order()

        # As the etims call is send in the pos order, we just copy the values from pos order to invoice
        # to avoid duplicate calls
        self.assertEqual(order.l10n_ke_oscu_internal_data, order.account_move.l10n_ke_oscu_internal_data)
        self.assertEqual(order.l10n_ke_oscu_signature, order.account_move.l10n_ke_oscu_signature)
        self.assertEqual(order.l10n_ke_oscu_receipt_number, order.account_move.l10n_ke_oscu_receipt_number)

    def test_cant_send_order_with_product_out_of_stock(self):
        order, _ = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id,
            },
            'line_data': [
                {'product_id': self.twenty_dollars_with_10_incl.product_variant_id.id, 'qty': 100}
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id}
            ]
        })

        # Send order to eTIMS, should raise an error
        with self.assertRaises(UserError):
            order.action_post_order()

    def test_refund_pos_order(self):
        order, refund = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.partner_moda.id,
                'to_invoice': True,
            },
            'line_data': [
                {'product_id': self.twenty_dollars_with_10_incl.product_variant_id.id}
            ],
            'payment_data': [
                {'payment_method_id': self.bank_payment_method.id}
            ],
            'refund_data': [
                {'payment_method_id': self.cash_payment_method.id}
            ]
        })

        order.action_post_order()
        refund.action_post_order()
        self.assertEqual(refund.l10n_ke_oscu_internal_data, 'GRKJVWYCFBPTYQ225X2UEYONVE')
        self.assertEqual(refund.l10n_ke_oscu_signature, '123456789ODOOGR3')
        self.assertEqual(refund.l10n_ke_oscu_receipt_number, 169)

        # The refund must reference the KRA invoice number of the order it refunds, not its own order number.
        self.assertEqual(refund.l10n_ke_order_json['orgInvcNo'], order.l10n_ke_oscu_order_number)
        self.assertNotEqual(refund.l10n_ke_order_json['orgInvcNo'], refund.sequence_number)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEtimsComboTour(TestKeEdiCommon, TestPointOfSaleHttpCommon):

    @classmethod
    @TestKeEdi.setup_country('ke')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.l10n_ke_server_mode = 'demo'
        cls.main_pos_config.payment_method_ids = [Command.link(cls.bank_payment_method.id)]

        drink = cls.env['product.product'].create({
            'name': 'Registered Drink',
            'available_in_pos': True,
            'standard_price': 30,
            'taxes_id': cls.tax_sale_a.ids,
            'l10n_ke_product_type_code': '2',
            'l10n_ke_packaging_unit_id': cls.env['l10n_ke_edi_oscu.code'].search([('code', '=', 'BA')], limit=1).id,
            'unspsc_code_id': cls.env['product.unspsc.code'].search([('code', '=', '52161557')], limit=1).id,
            'l10n_ke_origin_country_id': cls.env.ref('base.be').id,
        })
        combo = cls.env['product.combo'].create({
            'name': 'Drinks Combo',
            'combo_item_ids': [Command.create({'product_id': drink.id})],
        })
        cls.env['product.product'].create({
            'name': 'Non-registered Combo',
            'type': 'combo',
            'available_in_pos': True,
            'list_price': 10,
            'taxes_id': False,
            'combo_ids': [Command.set(combo.ids)],
        })

    def test_etims_combo(self):
        """
        A combo whose components are registered can be validated without registering the
        combo itself, and no eTIMS warning should be shown.
        """
        self.main_pos_config.open_ui()
        self.start_pos_tour('l10n_ke_edi_pos_combo_registered', login="accountman")
