from .common import TestEcEdiPosCommon

import lxml
from freezegun import freeze_time

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import file_open


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEcPos(TestEcEdiPosCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config.default_partner_id.write({
            'vat': '24ABCPM8965E1ZE',
            'state_id': cls.env.ref("base.state_in_gj").id,
            'country_id': cls.env.ref("base.in").id,
        })

    @freeze_time('2024-01-01')
    def test_pos_multi_payments_invoice_xml_1(self):
        """Asserts that invoices created from orders with two or more payments have the correct XML payment data."""
        with self.with_pos_session() as _session:
            multi_payments_order = self._create_order({
                'pos_order_lines_ui_args': [(self.product_a, 1)],
                'payments': [(self.cash_pm1, 575.0), (self.bank_pm1, 575.0)],
                'customer': self.partner_a,
            })
            multi_payments_order.action_pos_order_invoice()
            self.assertEqual(multi_payments_order.account_move.l10n_ec_sri_payment_id.code, "mpm", "PoS orders with multiple payments should have Multiple Payment Methods (PoS) as their SRI payment method.")

            invoice = multi_payments_order.account_move
            generated_file, errors = self.env['account.edi.format']._l10n_ec_generate_xml(invoice)
            self.assertFalse(errors)
            self.assertTrue(generated_file)
            with file_open('l10n_ec_edi_pos/tests/data/expected_document.xml', 'rt') as f:
                expected_xml = lxml.etree.fromstring(f.read().encode())
            self.assertXmlTreeEqual(lxml.etree.fromstring(generated_file.encode()), expected_xml)

    @freeze_time('2024-01-01')
    def test_pos_multi_payments_invoice_xml_2(self):
        """Asserts that invoices created from orders with mixed payments and change have the correct XML payment data."""
        with self.with_pos_session() as _session:
            multi_payments_order = self._create_order({
                'pos_order_lines_ui_args': [(self.product_a, 1)],
                'payments': [(self.cash_pm1, -5.0), (self.cash_pm1, 580.0), (self.bank_pm1, 575.0)],
                'customer': self.partner_a,
            })
            multi_payments_order.action_pos_order_invoice()
            invoice = multi_payments_order.account_move
            generated_file = self.env['account.edi.format']._l10n_ec_generate_xml(invoice)[0]
            with file_open('l10n_ec_edi_pos/tests/data/expected_document.xml', 'rt') as f:
                expected_xml = lxml.etree.fromstring(f.read().encode())
            self.assertXmlTreeEqual(lxml.etree.fromstring(generated_file.encode()), expected_xml)

    def test_max_consumer_final_limit_before_invoice_creation(self):
        """
            Asserts that invoices should not be created for the final consumer with,
            the total order amount higher than the limit set in the config.
        """
        with self.with_pos_session() as _session:

            # =======================================================
            # Invoice creation validation from 'pos.order' form view.
            # =======================================================
            order_higher_than_limit = self._create_order({
                'pos_order_lines_ui_args': [(self.product_a, 1)],
                'payments': [(self.cash_pm1, 1150.0)],
                'customer': self.env.ref('l10n_ec.ec_final_consumer'),
            })
            # The default limit for 'Final Consumer' set in the config is 50.0, and the above order is higher than that;
            # therefore, the invoice creation should be blocked.
            with self.assertRaises(UserError):
                order_higher_than_limit.action_pos_order_invoice()

            order_lower_than_limit = self._create_order({
                'pos_order_lines_ui_args': [(self._create_product(lst_price=30.0), 1)],
                'customer': self.env.ref('l10n_ec.ec_final_consumer'),
                'is_invoiced': True,
            })
            # This order is lower than the limit, therefore invoice creation should not be blocked.
            order_lower_than_limit.action_pos_order_invoice()

            # ==========================================================================
            # Invoice creation validation from 'Multiple order invoice creation' wizard.
            # ==========================================================================
            multiple_orders = self._create_order({
                'pos_order_lines_ui_args': [(self._create_product(lst_price=30.0), 1)],
                'customer': self.env.ref('l10n_ec.ec_final_consumer'),
            })
            multiple_orders |= self._create_order({
                'pos_order_lines_ui_args': [(self._create_product(lst_price=35.0), 1)],
                'customer': self.env.ref('l10n_ec.ec_final_consumer'),
            })
            multiple_orders |= self._create_order({
                'pos_order_lines_ui_args': [(self._create_product(lst_price=25.0), 1)],
                'customer': self.env.ref('l10n_ec.ec_final_consumer'),
            })

            consolidated_billing_wizard = self.env['pos.make.invoice'].with_context(active_ids=multiple_orders.ids).create([{}])
            # Consolidated bill for 'Final Consumer' with all the multiple_orders will have a higher total amount than the limit set in config;
            # therefore, the invoice creation should be blocked.
            with self.assertRaises(UserError):
                consolidated_billing_wizard.action_create_invoices()

            single_billing_wizard = self.env['pos.make.invoice'].with_context(active_ids=multiple_orders.ids).create([{
                'consolidated_billing': False,
            }])
            single_billing_wizard.action_create_invoices()

    @freeze_time('2024-01-01')
    def test_pos_free_order_invoice(self):
        """Simulate a free order that would be paid with a gift card and try to invoice it"""
        with self.with_pos_session() as _session:
            free_product = self.env['product.product'].create({
                'name': 'Free Product',
                'type': 'consu',
                'list_price': 0.0,
            })
            no_payment_order = self._create_order({
                'pos_order_lines_ui_args': [(free_product, 1)],
                'payments': [],
                'customer': self.partner_a,
            })
            no_payment_order.action_pos_order_invoice()
            invoice = no_payment_order.account_move
            self.assertEqual(invoice.l10n_ec_sri_payment_id.code, "01", "Order without payments should fallback to the No use of the financiel system SRI payment method. (Code 01)")


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestUI(TestEcEdiPosCommon, TestPointOfSaleHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_ec_pos_order_refund(self):
        self.main_pos_config.open_ui()
        self.start_pos_tour('test_ec_pos_order_refund', login="accountman")

    def test_max_consumer_final_limit_validation_from_frontend(self):
        self.main_pos_config.open_ui()
        self.start_pos_tour('test_max_consumer_final_limit_validation_from_frontend', login="pos_user")
