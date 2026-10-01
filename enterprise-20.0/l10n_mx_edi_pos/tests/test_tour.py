# -*- coding: utf-8 -*-
from .common import TestMxEdiPosCommon
import odoo
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization
from odoo.tools import mute_logger


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestUi(TestMxEdiPosCommon, TestPointOfSaleHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_mx.write({
            "name": "Arturo Garcia",
            "l10n_mx_edi_usage": "I01",
        })

    def test_mx_pos_invoice_order_and_refund(self):
        self.start_tour("/odoo", "l10n_mx_edi_pos.test_mx_pos_invoice_order_and_refund", login=self.env.user.login)

    def test_mx_pos_invoice_order_default_usage(self):
        self.start_tour("/odoo", "l10n_mx_edi_pos.tour_invoice_order_default_usage", login=self.env.user.login)

    def test_mx_pos_invoice_previous_order(self):
        self.start_tour("/odoo", "l10n_mx_edi_pos.tour_invoice_previous_order", login=self.env.user.login)
        invoice = self.env['account.move'].search([('move_type', '=', 'out_invoice')], order='id desc', limit=1)
        self.assertRecordValues(invoice, [{
            'partner_id': self.partner_mx.id,
            'l10n_mx_edi_usage': "G03",
            'l10n_mx_edi_cfdi_to_public': False,
        }])

    def test_mx_pos_invoice_previous_order_default_usage(self):
        self.start_tour("/odoo", "l10n_mx_edi_pos.tour_invoice_previous_order_default_usage", login=self.env.user.login)
        invoice = self.env['account.move'].search([('move_type', '=', 'out_invoice')], order='id desc', limit=1)
        self.assertRecordValues(invoice, [{
            'partner_id': self.partner_mx.id,
            'l10n_mx_edi_usage': "I01",
            'l10n_mx_edi_cfdi_to_public': True,
        }])

    def test_mx_pos_refund_discount_order(self):
        self.product1 = self.env['product.product'].create({
            'name': 'Test Product 1',
            'is_storable': True,
            'list_price': 10.0,
            'taxes_id': False,
        })
        self.product_discount = self.env['product.product'].create({
            'name': 'Test Discount',
            'is_storable': False,
            'list_price': -0.10,
            'taxes_id': False,
        })
        self.main_pos_config.open_ui()
        self.main_pos_config.current_session_id.set_opening_control(0, "")
        self.pos_order = self.env['pos.order'].create({
            "name": "Order 0001",
            "pos_reference": "Order 12345-123-1234",
            'company_id': self.env.company.id,
            'session_id': self.main_pos_config.current_session_id.id,
            'partner_id': self.partner_mx.id,
            'access_token': '1234567890',
            'lines': [odoo.Command.create({
                'name': "OL/0001",
                'product_id': self.product1.id,
                'price_unit': 10,
                'discount': 0.0,
                'qty': 1.0,
                'tax_ids': False,
                'price_subtotal': 10,
                'price_subtotal_incl': 10,
            }),
            odoo.Command.create({
                'name': "OL/0002",
                'product_id': self.product_discount.id,
                'price_unit': -0.10,
                'discount': 0.0,
                'qty': 1.0,
                'tax_ids': False,
                'price_subtotal': -0.10,
                'price_subtotal_incl': -0.10,
            })],
            'amount_tax': 0,
            'amount_total': 9.90,
            'amount_paid': 9.90,
            'amount_return': 0,
        })
        self.make_payment(self.pos_order, self.main_pos_config.payment_method_ids[0], 9.90)
        self.main_pos_config.current_session_id.close_session_from_ui()
        self.start_tour("/odoo", "l10n_mx_edi_pos.tour_refund_discount_order", login=self.env.user.login)

    def test_qr_code_receipt_mx(self):
        """
        This test ensures that no user is created when a partner is set on the PoS order.
        It also ensures that the invoice has the correct default values when created through
        self-invoicing with a public user and a partner set on the order.
        """
        self.authenticate(None, None)
        self.new_partner = self.env['res.partner'].create({
            'name': 'AAA Partner',
            'zip': '12345',
            'state_id': self.env.ref('base.state_mx_ags').id,
            'country_id': self.env.company.country_id.id,
        })
        self.product1 = self.env['product.product'].create({
            'name': 'Test Product 1',
            'is_storable': True,
            'list_price': 10.0,
            'taxes_id': False,
        })
        self.main_pos_config.open_ui()
        self.pos_order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': self.main_pos_config.current_session_id.id,
            'partner_id': self.new_partner.id,
            'access_token': '1234567890',
            'lines': [(0, 0, {
                'name': "OL/0001",
                'product_id': self.product1.id,
                'price_unit': 10,
                'discount': 0.0,
                'qty': 1.0,
                'tax_ids': False,
                'price_subtotal': 10,
                'price_subtotal_incl': 10,
            })],
            'amount_tax': 10,
            'amount_total': 10,
            'amount_paid': 10.0,
            'amount_return': 10.0,
        })
        self.main_pos_config.current_session_id.close_session_from_ui()
        self.url_open(f'/pos/ticket/validate?access_token={self.pos_order.access_token}')
        self.assertEqual(self.env['res.partner'].sudo().search_count([('name', '=', 'AAA Partner')]), 1)
        self.assertTrue(self.pos_order.is_singly_invoiced, "The pos order should have an invoice")
        self.assertEqual(self.pos_order.account_move.l10n_mx_edi_usage, 'G03', 'Invoice has default value for l10n_mx_edi_usage')
        self.assertEqual(self.new_partner.l10n_mx_edi_fiscal_regime, '601', 'Partner has default value for l10n_mx_edi_fiscal_regime')

    def test_qr_code_receipt_mx_without_order_partner(self):
        """
        This test ensures that when no partner is set on the order and partner data is provided for self-invoicing,
        a new partner is created and the corresponding values are set on the invoice based on the provided data.
        """
        self.authenticate(None, None)
        self.product1 = self.env['product.product'].create({
            'name': 'Test Product 1',
            'is_storable': True,
            'list_price': 10.0,
            'taxes_id': False,
        })
        self.main_pos_config.open_ui()
        self.pos_order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': self.main_pos_config.current_session_id.id,
            'access_token': '1234567890',
            'lines': [(0, 0, {
                'name': "OL/0001",
                'product_id': self.product1.id,
                'price_unit': 10,
                'discount': 0.0,
                'qty': 1.0,
                'tax_ids': False,
                'price_subtotal': 10,
                'price_subtotal_incl': 10,
            })],
            'amount_tax': 10,
            'amount_total': 10,
            'amount_paid': 10.0,
            'amount_return': 10.0,
        })
        self.main_pos_config.current_session_id.close_session_from_ui()
        get_invoice_data = {
            'access_token': self.pos_order.access_token,
            'name': 'AAA Partner',
            'email': "test@test.com",
            'street': "Test street",
            'city': "Test City",
            'zipcode': '12345',
            'country_id': self.env.company.country_id.id,
            'state_id': self.env.company.country_id.state_ids[0].id,
            'phone': "123456789",
            'vat': 'GODE561231GR8',
            'invoice_l10n_mx_edi_usage': 'D10',
            'partner_l10n_mx_edi_fiscal_regime': '624',
            'csrf_token': self.csrf_token()
        }
        self.url_open(f'/pos/ticket/validate?access_token={self.pos_order.access_token}', data=get_invoice_data)
        self.assertEqual(self.env['res.partner'].sudo().search_count([('name', '=', 'AAA Partner')]), 1)
        self.assertTrue(self.pos_order.is_singly_invoiced, "The pos order should have an invoice")
        self.assertEqual(self.pos_order.account_move.l10n_mx_edi_usage, 'D10', 'Invoice values not saved')
        self.assertEqual(self.pos_order.partner_id.l10n_mx_edi_fiscal_regime, '624', 'Partner values not saved')

    def test_pos_settle_due_main(self):
        """
        As tour are very energy consuming, we will only write one test
        in which we will test the main flow of settling a due invoice

        Testing behavior:
        - Create an order with customer account and check that the due
        amount is correct on the partner
        - Deposit money from the partner list and check that the due
        amount is updated on the partner
        - Settle an open invoice from the partner list and check that
        the due amount is updated on the partner
        """
        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'type': 'pay_later',
        })
        self.main_pos_config.write({
            'payment_method_ids': [
                (4, self.customer_account_payment_method.id),
            ]
        })
        moda = self.env['res.partner'].create({
            'name': 'AAA - Moda',
            'country_id': self.env.ref('base.mx').id,
        })
        invoice = self.env['account.move'].create({
            'partner_id': moda.id,
            'date': '2025-02-17',
            'invoice_date': '2025-02-17',
            'move_type': 'out_invoice',
            'invoice_line_ids': [
                (0, 0, {'name': 'test', 'price_unit': 200})
            ],
        })
        invoice.action_post()
        self.assertEqual(moda.total_due, 200)

        self.main_pos_config.open_ui()
        self.start_pos_tour('test_pos_settle_due_main', login='accountman')

        # Check partner due amount, should be 80000 deposit minus 10
        # from partially paid order created in the tour
        self.assertEqual(moda.total_due, -79990.0)

        pos_invoice = moda.invoice_ids[0]
        self.assertEqual(pos_invoice.amount_residual, 10)
        self.env['account.payment.register'].with_context(
            active_ids=pos_invoice.ids,
            active_model='account.move'
        ).create({
            'payment_date': pos_invoice.date,
            'amount': 10,
        })._create_payments()

        self.assertEqual(pos_invoice.amount_residual, 0)

    def test_usage_mx_pos_invoice_order(self):
        self.main_pos_config.open_ui()

        self.product_a = self.env['product.product'].create({
            'name': 'Test Product 1',
            'is_storable': True,
            'list_price': 10.0,
            'taxes_id': False,
        })
        order_data = {
            "amount_paid": 10,
            "amount_tax": 0,
            "amount_return": 0,
            "amount_total": 10,
            "date_order": fields.Datetime.to_string(fields.Datetime.now()),
            "fiscal_position_id": False,
            "lines": [
                Command.create({
                    "discount": 0,
                    "price_unit": 10.0,
                    "product_id": self.product_a.id,
                    "price_subtotal": 10.0,
                    "price_subtotal_incl": 10.0,
                    "tax_ids": [[6, False, []]],
                    "qty": 1,
                }),
            ],
            "name": "Order 12345-123-1234",
            "partner_id": self.partner_a.id,
            "session_id": self.main_pos_config.current_session_id.id,
            "sequence_number": 2,
            "payment_ids": [
                    Command.create({
                        "amount": 10,
                        "name": fields.Datetime.now(),
                        "payment_method_id": self.bank_payment_method.id,
                    }),
            ],
            "uuid": "12345-123-1234",
            "user_id": self.env.uid,
            "to_invoice": False,
            "l10n_mx_edi_usage": False,
        }

        order = self.env["pos.order"].sync_from_ui([order_data])["pos.order"][0]
        self.assertTrue(order, "No POS order was created during the tour.")

        usage = order['l10n_mx_edi_usage']
        self.assertTrue(usage, "The invoice has no usage set.")
        self.assertEqual(usage, "G03", f"Expected CFDI usage to be 'G03', got '{usage}' instead.")

    def test_refund_with_gift_card_mx(self):
        """
        Tests that in the case of a refund with a gift card involved, the customer can
        still pay for the order, and that the points will go up on the gift card, depending
        on how much the refunded product was worth.
        """
        self.ensure_installed('pos_loyalty')

        self.main_pos_config.with_user(self.pos_user).open_ui()
        LoyaltyProgram = self.env['loyalty.program']
        (LoyaltyProgram.search([])).write({'pos_ok': False})
        self.env.ref('loyalty.gift_card_product_50').write({'active': True})

        program_id = LoyaltyProgram.create_from_template('gift_card')['res_id']
        gift_card_program = LoyaltyProgram.browse(program_id)
        gift_card_program.write({'name': 'Test Gift Card Program'})
        self.env["loyalty.generate.wizard"].with_context(
            {"active_id": gift_card_program.id}
        ).create({"coupon_qty": 1, 'points_granted': 1}).generate_coupons()
        gift_card_program.coupon_ids.code = '043123456'

        self.start_tour("/pos/ui?config_id=%d" % self.main_pos_config.id, 'test_refund_with_gift_card_mx', login="pos_user")
        self.assertEqual(gift_card_program.coupon_ids.points, 4.2)

    def test_usage_mx_pos_partner(self):
        """This test makes sure that if usage is set on the partner, it is taken into account instead of the default one."""
        self.main_pos_config.open_ui()

        self.product_a = self.env['product.product'].create({
            'name': 'Test Product 1',
            'is_storable': True,
            'list_price': 10.0,
            'taxes_id': False,
        })

        self.partner_a.l10n_mx_edi_usage = 'D10'

        order_data = {
            "amount_paid": 10,
            "amount_tax": 0,
            "amount_return": 0,
            "amount_total": 10,
            "date_order": fields.Datetime.to_string(fields.Datetime.now()),
            "fiscal_position_id": False,
            "lines": [
                Command.create({
                    "discount": 0,
                    "price_unit": 10.0,
                    "product_id": self.product_a.id,
                    "price_subtotal": 10.0,
                    "price_subtotal_incl": 10.0,
                    "tax_ids": [[6, False, []]],
                    "qty": 1,
                }),
            ],
            "name": "Order 12345-123-1234",
            "partner_id": self.partner_a.id,
            "session_id": self.main_pos_config.current_session_id.id,
            "sequence_number": 2,
            "payment_ids": [
                    Command.create({
                        "amount": 10,
                        "name": fields.Datetime.now(),
                        "payment_method_id": self.bank_payment_method.id,
                    }),
            ],
            "uuid": "12345-123-1234",
            "user_id": self.env.uid,
            "to_invoice": False,
            "l10n_mx_edi_usage": False,
        }

        order = self.env["pos.order"].sync_from_ui([order_data])["pos.order"][0]
        usage = order['l10n_mx_edi_usage']
        self.assertEqual(usage, "D10")

    def test_refund_with_discount(self):
        """
        Tests that when a refund is processed it's total amount does not exceed the original order total.
        """
        if self.env['ir.module.module']._get('pos_discount').state != 'installed':
            self.skipTest("pos_discount needs to be installed")

        self.main_pos_config.module_pos_discount = True
        self.main_pos_config.discount_product_id = self.env.ref("pos_discount.product_product_consumable", raise_if_not_found=False)
        self.main_pos_config.with_user(self.pos_user).open_ui()

        self.start_tour("/pos/ui?config_id=%d" % self.main_pos_config.id, 'test_refund_with_discount', login="pos_user")

    @mute_logger('odoo.http')
    def test_invoice_to_general_public(self):
        self.no_address_partner = self.env['res.partner'].create({
            'name': 'Homeless Customer',
        })
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_tour("/pos/ui?config_id=%d" % self.main_pos_config.id, "tour_invoice_to_general_public", login="pos_user")


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericMX(TestGenericLocalization):

    _pos_partner_pos_form_fields = ['l10n_mx_edi_fiscal_regime', 'l10n_mx_edi_usage']
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('mx')
    def setUpClass(cls):
        super().setUpClass()
