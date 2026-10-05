# Part of Odoo. See LICENSE file for full copyright and licensing details.
import odoo.tests
from unittest.mock import patch

from odoo import http
from odoo.fields import Command
from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest
from odoo.addons.point_of_sale.controllers.main import PosController


@odoo.tests.tagged("post_install", "-at_install")
class TestFrontendMobile(SelfOrderCommonTest):
    def setUp(self):
        super().setUp()
        self.obox = self.env['obox.obox'].create({
            'name': 'Test Obox',
            'serial_number': '1234567890',
            'state': '02_paired',
            'token': 'dummy',
        })

        self.env['product.template'].search([]).write({
            'list_price': 0,
        })
        self.env['product.product'].search([]).write({
            'lst_price': 0,
        })
        self.env['product.product'].search([('name', '=', 'Fanta')]).write({
            'lst_price': 5,
        })
        printer = self.env['pos.printer'].create({
            'name': 'Printer',
            'printer_type': 'epson_epos',
            'printer_ip': self.pos_config.get_base_url(),
            'proxy_obox_id': self.obox.id,
            'use_type': 'preparation',
            'product_categories_ids': [Command.set(self.env['pos.category'].search([]).ids)],
        })

        self.pos_config.write({
            'self_ordering_default_user_id': self.pos_admin.id,
            'self_ordering_mode': 'mobile',
            'self_ordering_pay_after': 'each',
            'self_ordering_service_mode': 'counter',
            'available_preset_ids': [(5, 0)],
            'preparation_printer_ids': [Command.set([printer.id])],
        })

    def test_obox_request_and_callback_mobile_each(self):
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()

        def has_valid_self_payment_method_patch(self):
            return True

        # Force the has_valid_self_payment_method to return True to simulate a valid payment method for the test
        with patch.object(self.env.registry.models['pos.config'], "has_valid_self_payment_method", has_valid_self_payment_method_patch):
            self.start_tour(self_route, 'test_obox_request_and_callback_mobile_each')

        obox_jobs = self.env['obox.queue'].search([
            ('obox_id', '=', self.obox.id),
        ])
        paid_order = self.pos_config.current_session_id.order_ids.filtered_domain([
            ('state', '=', 'paid')
        ])
        self.assertEqual(len(obox_jobs), 1, "Only one OBOX job should have been created.")
        product_name = paid_order.prep_order_ids.prep_line_ids.product_id.name
        self.assertEqual(len(paid_order.prep_order_ids.prep_line_ids), 1, "Only one prep line should have been created.")
        self.assertEqual(product_name, "Coca-Cola")

    def test_obox_request_and_callback_mobile_meal(self):
        self.pos_config.write({
            'self_ordering_mode': 'mobile',
            'self_ordering_service_mode': 'table',
            'self_ordering_pay_after': 'meal',
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route(table_id=self.pos_table_1.id)
        self.start_tour(self_route, 'test_obox_request_and_callback_mobile_meal')
        obox_jobs = self.env['obox.queue'].search([
            ('obox_id', '=', self.obox.id),
        ])
        self.assertEqual(len(obox_jobs), 2, "Only one OBOX job should have been created.")
        order = self.pos_config.current_session_id.order_ids
        product_names = order.prep_order_ids.prep_line_ids.product_id.mapped('name')
        product_qty = order.prep_order_ids.prep_line_ids.mapped('quantity')
        self.assertEqual(product_names, ["Coca-Cola", "Fanta"])
        self.assertEqual(product_qty, [1.0, 1.0, 1.0, 1.0])

    def _create_receipt_printer(self, proxy_obox_id=False):
        return self.env['pos.printer'].create({
            'name': 'Receipt Printer',
            'printer_type': 'epson_epos',
            'printer_ip': '127.0.0.1',
            'proxy_obox_id': proxy_obox_id,
            'use_type': 'receipt',
        })

    def _create_paid_mobile_order(self, pos_reference='Order Obox Receipt 0001'):
        return self.env['pos.order'].create({
            'config_id': self.pos_config.id,
            'session_id': self.pos_config.current_session_id.id,
            'company_id': self.pos_config.company_id.id,
            'amount_total': 2.2,
            'amount_paid': 2.2,
            'amount_tax': 0.0,
            'amount_return': 0.0,
            'to_invoice': False,
            'partner_id': False,
            'pos_reference': pos_reference,
            'name': pos_reference,
            'state': 'paid',
            'source': 'mobile',
            'lines': [(0, 0, {
                'name': 'Line 0001',
                'product_id': self.cola.id,
                'price_unit': 2.2,
                'discount': 0,
                'qty': 1,
                'tax_ids': False,
                'price_subtotal': 2.2,
                'price_subtotal_incl': 2.2,
            })],
            'payment_ids': [(0, 0, {
                'amount': 2.2,
                'payment_date': '2024-01-01 12:00:00',
                'payment_method_id': self.pos_config.payment_method_ids[0].id,
                'pos_order_id': 1,
            })],
        })

    def _setup_receipt_printing(self, printer_ids, iface_print_auto=True):
        self.pos_config.write({
            'iface_print_auto': iface_print_auto,
            'receipt_printer_ids': [Command.set(printer_ids)],
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")

    def test_send_self_order_receipt_creates_obox_print_job(self):
        printer = self._create_receipt_printer(proxy_obox_id=self.obox.id)
        self._setup_receipt_printing([printer.id])

        order = self._create_paid_mobile_order()
        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', self.obox.id)]))
        order._send_self_order_receipt()

        obox_jobs = self.env['obox.queue'].search([('obox_id', '=', self.obox.id)])
        self.assertEqual(len(obox_jobs), 1, "One OBOX print job should have been created.")
        self.assertEqual(obox_jobs.payload['method'], 'POST')
        self.assertIn(printer.printer_ip, obox_jobs.payload['url'])
        self.assertIn('epos-print', obox_jobs.payload['payload'])
        self.assertEqual(order.nb_print, 1)

    def test_send_self_order_receipt_not_printed_twice(self):
        printer = self._create_receipt_printer(proxy_obox_id=self.obox.id)
        self._setup_receipt_printing([printer.id])

        order = self._create_paid_mobile_order()
        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', self.obox.id)]))
        order._send_self_order_receipt()
        order._send_self_order_receipt()

        obox_jobs = self.env['obox.queue'].search([('obox_id', '=', self.obox.id)])
        self.assertEqual(len(obox_jobs), 1, "The receipt should only be printed once.")
        self.assertEqual(order.nb_print, 1)

    def test_send_self_order_receipt_requires_iface_print_auto(self):
        printer = self._create_receipt_printer(proxy_obox_id=self.obox.id)
        self._setup_receipt_printing([printer.id], iface_print_auto=False)

        order = self._create_paid_mobile_order()
        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', self.obox.id)]))
        order._send_self_order_receipt()

        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', self.obox.id)]))
        self.assertEqual(order.nb_print, 0)

    def test_send_self_order_receipt_ignores_printer_without_proxy_obox(self):
        printer = self._create_receipt_printer(proxy_obox_id=False)
        self._setup_receipt_printing([printer.id])

        order = self._create_paid_mobile_order()
        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', self.obox.id)]))
        order._send_self_order_receipt()

        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', self.obox.id)]))
        self.assertEqual(order.nb_print, 0)

    def test_send_self_order_receipt_requires_mobile_source(self):
        printer = self._create_receipt_printer(proxy_obox_id=self.obox.id)
        self._setup_receipt_printing([printer.id])

        order = self._create_paid_mobile_order()
        order.source = 'pos'
        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', self.obox.id)]))
        order._send_self_order_receipt()

        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', self.obox.id)]))
        self.assertEqual(order.nb_print, 0)

    def test_send_self_order_receipt_only_obox_printers_receive_job(self):
        printer_without_obox = self._create_receipt_printer(proxy_obox_id=False)
        printer_with_obox = self._create_receipt_printer(proxy_obox_id=self.obox.id)
        self._setup_receipt_printing([printer_without_obox.id, printer_with_obox.id])

        order = self._create_paid_mobile_order()
        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', self.obox.id)]))
        order._send_self_order_receipt()

        obox_jobs = self.env['obox.queue'].search([('obox_id', '=', self.obox.id)])
        self.assertEqual(len(obox_jobs), 1, "Only the printer linked to an OBOX proxy should receive a job.")
        self.assertEqual(order.nb_print, 1)

    def test_send_self_order_receipt_tour_creates_obox_print_job(self):
        # Use a dedicated OBOX for the receipt printer so its jobs can be told
        # apart from the prep-ticket job created by the preparation printer set up above.
        receipt_obox = self.env['obox.obox'].create({
            'name': 'Test Receipt Obox',
            'serial_number': '0987654321',
            'state': '02_paired',
            'token': 'dummy',
        })
        printer = self._create_receipt_printer(proxy_obox_id=receipt_obox.id)
        self._setup_receipt_printing([printer.id])

        # A 0-amount order is paid directly by the self-order controller, without going
        # through a payment screen, which is what triggers _send_self_order_receipt().
        self.cola.list_price = 0
        self.assertFalse(self.env['obox.queue'].search([('obox_id', '=', receipt_obox.id)]))
        self_route = self.pos_config._get_self_order_route()
        self.start_tour(self_route, 'test_pos_self_order_preparation_each')

        obox_jobs = self.env['obox.queue'].search([('obox_id', '=', receipt_obox.id)])
        self.assertEqual(len(obox_jobs), 1, "The self order receipt should have been printed through OBOX.")
        order = self.pos_config.current_session_id.order_ids[:1]
        self.assertEqual(order.state, 'paid')
        self.assertEqual(order.nb_print, 1)

    def test_preparation_ticket_language(self):
        self.env['res.lang']._activate_lang('fr_FR')
        self.env['res.lang']._activate_lang('en_US')
        all_categories = self.env['pos.category'].search([])
        printer = self.env['pos.printer'].search([
            ('product_categories_ids', '!=', False)
        ], limit=1)
        printer.product_categories_ids = all_categories
        self.pos_config.write({
            'self_ordering_pay_after': 'each',
            'preparation_printer_ids': [Command.set([printer.id])],
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")

        def create_order():
            return self.env['pos.order'].create({
                'config_id': self.pos_config.id,
                'session_id': self.pos_config.current_session_id.id,
                'company_id': self.pos_config.company_id.id,
                'amount_total': 2.2,
                'amount_paid': 2.2,
                'amount_tax': 0.0,
                'amount_return': 0.0,
                'to_invoice': False,
                'partner_id': False,
                'pos_reference': '1000-004-00002',
                'name': 'Order 0002',
                'state': 'paid',
                'source': 'mobile',
                'lines': [(0, 0, {
                    'name': 'Line 0001',
                    'product_id': self.cola.id,
                    'price_unit': 2.2,
                    'discount': 0,
                    'qty': 1,
                    'tax_ids': False,
                    'price_subtotal': 2.2,
                    'price_subtotal_incl': 2.2,
                })],
                'payment_ids': [(0, 0, {
                    'amount': 10.0,
                    'payment_date': '2024-01-01 12:00:00',
                    'payment_method_id': self.pos_config.payment_method_ids[0].id,
                    'pos_order_id': 1,
                })],
            })

        self.cola.update_field_translations("name", {
            'fr_FR': "French Coca-Cola",
            'en_US': "English Coca-Cola",
        })
        order_1 = create_order()
        self.pos_config.self_ordering_default_user_id.write({'lang': 'fr_FR'})
        data_1 = order_1._order_change_receipts_generate_html()
        text = str(next(iter(data_1.values()))[0])
        self.assertTrue("French Coca-Cola" in text)

        order_2 = create_order()
        self.pos_config.self_ordering_default_user_id.write({'lang': 'en_US'})
        data_2 = order_2._order_change_receipts_generate_html()
        text = str(next(iter(data_2.values()))[0])
        self.assertTrue("English Coca-Cola" in text)

    def test_pos_self_order_preparation(self):
        """
        Behavior of the self-ordering preparation process depending on the payment
        status and the configuration of the PoS.

        Self Order mobile (always printed via OBOX):
        - EACH PAID: If an order is created and paid, it should create a prep order directly from the
          Self Order (via OBOX or preparation display)
        - EACH UNPAID: If an order is created and unpaid, it should also create a prep order directly
          from the Self Order if there is NO available payment method (via OBOX or preparation display)
        - MEAL PAID: If an order is created and paid, it should create a prep order directly from the
          Self Order (via OBOX or preparation display)
        - MEAL UNPAID: If an order is created and unpaid, it should also create a prep order directly
          from the Self Order (via OBOX or preparation display)

        Self Order kiosk:
        - EACH PAID: If an order is created and paid, it should create a prep order directly from the
          Self Order (via local IP or preparation display)
        - EACH UNPAID: If an order is created and unpaid, it should create a prep order directly only
          if there is NO available payment method (via local IP or preparation display)

        !!!! DO NOT UPDATE THIS TEST WITHOUT ASKING THE POS TEAM !!!!
        """
        self._set_browser_size('mobile')
        self.cola.list_price = 100
        self.pos_config.with_user(self.pos_user).open_ui()
        current_session = self.pos_config.current_session_id
        current_session.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()
        printed = self._install_fake_epos_printer()
        self.pos_config.preparation_printer_ids.write({
            'printer_ip': self.base_url().removeprefix('http://') + '/fake_printer',
            'use_lna': True,
        })

        # ##########################################
        # # MOBILE area
        # ##########################################
        self.pos_config.write({
            'self_ordering_mode': 'mobile',
            'self_ordering_pay_after': 'each',
            'self_ordering_service_mode': 'counter',
        })

        # EACH PAID case (use zero amount to simulate a paid order)
        self.cola.list_price = 0
        obox_queue_len = self.env['obox.queue'].search_count([])
        self.start_tour(self_route, 'test_pos_self_order_preparation_each')
        order = current_session.order_ids[:1]
        obox_queue_len_after = self.env['obox.queue'].search_count([])
        self.assertEqual(obox_queue_len + 1, obox_queue_len_after, "An OBOX job should have been created for a paid self order")
        self.assertEqual(order.source, 'mobile')
        self.assertEqual(order.state, 'paid')
        self.assertTrue(order.prep_order_ids, "A prep order should have been created for a paid self order")

        # EACH UNPAID case with no available payment method should create a prep
        # order directly from the Self Order
        self.cola.list_price = 100
        obox_queue_len = self.env['obox.queue'].search_count([])
        with patch.object(self.env.registry.models['pos.config'], "has_valid_self_payment_method", lambda self: False):
            self.start_tour(self_route, 'test_pos_self_order_preparation_each')
        order = current_session.order_ids[:1]
        obox_queue_len_after = self.env['obox.queue'].search_count([])
        self.assertEqual(obox_queue_len + 1, obox_queue_len_after, "An OBOX job should have been created for a paid self order")
        self.assertEqual(order.source, 'mobile')
        self.assertEqual(order.state, 'draft')
        self.assertTrue(order.prep_order_ids, "A prep order should have been created for a paid self order")
        order.state = 'cancel'  # Cancel to avoid noises

        # EACH UNPAID case with an available payment method should not create a prep
        # order until it is paid from the PoS.
        self.cola.list_price = 100  # Readability, but already set above
        obox_queue_len = self.env['obox.queue'].search_count([])
        with patch.object(self.env.registry.models['pos.config'], "has_valid_self_payment_method", lambda self: True):
            self.start_tour(self_route, 'test_pos_self_order_preparation_each')
        order = current_session.order_ids[:1]
        obox_queue_len_after = self.env['obox.queue'].search_count([])
        self.assertEqual(obox_queue_len, obox_queue_len_after, "No new OBOX job should have been created for an unpaid self order")
        self.assertEqual(order.source, 'mobile')
        self.assertEqual(order.state, 'draft')
        self.assertFalse(order.prep_order_ids, "No prep order should have been created for an unpaid self order")
        self._set_browser_size('desktop')
        self.start_tour('/pos/ui?config_id=%d' % self.pos_config.id, 'test_pos_self_order_preparation_pos', login='pos_user')
        self.assertEqual(obox_queue_len, self.env['obox.queue'].search_count([]))
        self.assertEqual(order.state, 'paid')
        self.assertEqual(order.source, 'pos')
        self.assertEqual(len(printed), 1, "The order was printed from the PoS")
        printed.pop()  # Remove the printed order to avoid noise for the next test

        # Prepare the PoS to use MEAL and COUNTER for the self-ordering mode
        self.pos_config.write({
            'self_ordering_mode': 'mobile',
            'self_ordering_pay_after': 'meal',
            'self_ordering_service_mode': 'table',
        })

        # MEAL PAID case (use zero amount to simulate a paid order)
        self.cola.list_price = 0
        obox_queue_len = self.env['obox.queue'].search_count([])
        self.start_tour(self_route, 'test_pos_self_order_preparation_meal')
        order = current_session.order_ids[:1]
        obox_queue_len_after = self.env['obox.queue'].search_count([])
        self.assertEqual(obox_queue_len + 1, obox_queue_len_after, "An OBOX job should have been created for a paid self order")
        self.assertEqual(order.source, 'mobile')
        self.assertEqual(order.state, 'paid')
        self.assertTrue(order.prep_order_ids, "A prep order should have been created for a paid self order")

        # MEAL UNPAID case with no available payment method should create a prep
        self.cola.list_price = 100
        obox_queue_len = self.env['obox.queue'].search_count([])
        with patch.object(self.env.registry.models['pos.config'], "has_valid_self_payment_method", lambda self: False):
            self.start_tour(self_route, 'test_pos_self_order_preparation_meal')
        order = current_session.order_ids[:1]
        obox_queue_len_after = self.env['obox.queue'].search_count([])
        self.assertEqual(obox_queue_len + 1, obox_queue_len_after, "An OBOX job should have been created for an unpaid self order with no available payment method")
        self.assertEqual(order.source, 'mobile')
        self.assertEqual(order.state, 'draft')
        self.assertTrue(order.prep_order_ids, "A prep order should have been created for an unpaid self order with no available payment method")
        order.state = 'cancel'  # Cancel to avoid noises

        # MEAL UNPAID case with an available payment method should create a prep order directly from the Self Order
        self.cola.list_price = 100
        obox_queue_len = self.env['obox.queue'].search_count([])
        with patch.object(self.env.registry.models['pos.config'], "has_valid_self_payment_method", lambda self: True):
            self.start_tour(self_route, 'test_pos_self_order_preparation_meal')
        order = current_session.order_ids[:1]
        obox_queue_len_after = self.env['obox.queue'].search_count([])
        self.assertEqual(obox_queue_len + 1, obox_queue_len_after, "An OBOX job should have been created for an unpaid self order with an available payment method")
        self.assertEqual(order.source, 'mobile')
        self.assertEqual(order.state, 'draft')
        self.assertTrue(order.prep_order_ids, "A prep order should have been created for an unpaid self order with an available payment method")
        order.state = 'cancel'  # Cancel to avoid noises

        # ##########################################
        # # KIOSK area
        # ##########################################
        self.pos_config.write({
            'self_ordering_mode': 'kiosk',
            'self_ordering_pay_after': 'each',
            'self_ordering_service_mode': 'counter',
        })

        # # EACH PAID case (use zero amount to simulate a paid order)
        self.cola.list_price = 0
        obox_queue_len = self.env['obox.queue'].search_count([])
        self.start_tour(self_route, 'test_pos_self_order_preparation_kiosk')
        order = current_session.order_ids[:1]
        obox_queue_len_after = self.env['obox.queue'].search_count([])
        self.assertEqual(obox_queue_len, obox_queue_len_after, "Obox isn't used for kiosk")
        self.assertEqual(order.source, 'kiosk')
        self.assertEqual(order.state, 'paid')
        self.assertTrue(order.prep_order_ids, "A prep order should have been created for a paid kiosk order")
        self.assertEqual(len(printed), 1, "The order was printed from the PoS")
        printed.pop()  # Remove the printed order to avoid noise for the next test

        # EACH UNPAID case with an available payment method
        self.cola.list_price = 100
        obox_queue_len = self.env['obox.queue'].search_count([])
        with patch.object(self.env.registry.models['pos.config'], "has_valid_self_payment_method", lambda self: True):
            self.start_tour(self_route, 'test_pos_self_order_preparation_kiosk')
        order = current_session.order_ids[:1]
        obox_queue_len_after = self.env['obox.queue'].search_count([])
        self.assertEqual(obox_queue_len, obox_queue_len_after, "Obox isn't used for kiosk")
        self.assertEqual(order.source, 'kiosk')
        self.assertEqual(order.state, 'draft')
        self.assertFalse(order.prep_order_ids, "A prep order should not have been created for an unpaid kiosk order with an available payment method")

        # Normally the kiosk shouldn't print any changes but since we are using a fake payment method,
        # the frontend think there is no available payment method and will print the order.
        self.assertEqual(len(printed), 1, "The order was printed from the Self")
        printed.pop()  # Remove the printed order to avoid noise for the next test

        # EACH UNPAID case with no available payment method should create a prep order directly from the Self Order
        self.cola.list_price = 100
        obox_queue_len = self.env['obox.queue'].search_count([])
        with patch.object(self.env.registry.models['pos.config'], "has_valid_self_payment_method", lambda self: False):
            self.start_tour(self_route, 'test_pos_self_order_preparation_kiosk')
        order = current_session.order_ids[:1]
        obox_queue_len_after = self.env['obox.queue'].search_count([])
        self.assertEqual(obox_queue_len, obox_queue_len_after, "Obox isn't used for kiosk")
        self.assertEqual(order.source, 'kiosk')
        self.assertEqual(order.state, 'draft')
        self.assertTrue(order.prep_order_ids, "A prep order should have been created for an unpaid kiosk order with no available payment method")
        self.assertEqual(len(printed), 1, "The order was printed from the PoS")
        printed.pop()  # Remove the printed order to avoid noise for the next test

    def _set_browser_size(self, size='desktop'):
        if size == 'desktop':
            self.browser_size = '1366x768'
        elif size == 'mobile':
            self.browser_size = '375x667'

    def _install_fake_epos_printer(self):
        """Serve /fake_printer/cgi-bin/epos/service.cgi and record what is printed."""
        printed = []

        def fake_epos_printer(self, **kwargs):
            printed.append(True)
            return http.Response(
                '<response success="true" code="" status="0"/>',
                content_type="application/xml",
            )
        self.env.transaction.invalidate_ormcache('routing')

        PosController.fake_epos_printer = http.route(
            "/fake_printer/cgi-bin/epos/service.cgi",
            type="http",
            auth="public",
            methods=["POST"],
            csrf=False,
        )(fake_epos_printer)

        @self.addCleanup
        def _uninstall_fake_epos_printer():
            del PosController.fake_epos_printer
            self.env.transaction.invalidate_ormcache('routing')

        return printed
