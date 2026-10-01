# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import Form, tagged

from odoo.addons.website_sale.tests.common import MockRequest
from odoo.addons.website_sale_renting.tests.common import WebsiteSaleRentingCommon


@tagged("post_install", "-at_install")
class TestWebsiteSaleStockRenting(WebsiteSaleRentingCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.computer.is_storable = True
        cls.computer.allow_out_of_stock_order = False
        cls.computer.website_published = True

        cls.company.rental_resource_calendar_id = False
        cls.current_website = cls.env["website"].create({
            "name": "Website Sale Stock Renting",
            "company_id": cls.company.id,
        })

        cls.wh = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        quants = cls.env["stock.quant"].create({
            "product_id": cls.computer.id,
            "inventory_quantity": 5.0,
            "location_id": cls.wh.lot_stock_id.id,
        })
        quants.action_apply_inventory()
        cls.now = fields.Datetime.now()
        cls.so = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "company_id": cls.company.id,
            "warehouse_id": cls.wh.id,
            "website_id": cls.current_website.id,
            "rental_start_date": cls.now + relativedelta(days=1),
            "rental_return_date": cls.now + relativedelta(days=3),
        })
        cls.sol = cls.env["sale.order.line"].create({
            "order_id": cls.so.id,
            "product_id": cls.computer.id,
            "product_uom_qty": 3,
        })
        cls.user = (
            cls
            .env["res.users"]
            .with_company(cls.company.id)
            .create({"name": "Test User", "login": "test_user", "company_id": cls.company.id})
        )

    def test_available_and_rented_quantities_for_draft_so(self):
        from_date = self.now
        to_date = self.now + relativedelta(days=4)

        self._assert_rented_quantities(
            from_date,
            to_date,
            expected_rented_quantities={},
            expected_key_dates=[from_date, to_date],
        )
        self._assert_availabilities(
            from_date,
            to_date,
            expected_availabilities=[{"start": from_date, "end": to_date, "quantity_available": 5}],
        )
        self.so.update({"rental_start_date": from_date, "rental_return_date": to_date})
        self._assert_cart_and_free_qty(self.so, expected_cart_qty=3, expected_free_qty=5)

    def test_available_and_rented_quantities_for_sent_so(self):
        self.so.action_quotation_sent()
        from_date = self.now
        to_date = self.now + relativedelta(days=4)
        start_date = self.sol.start_date
        return_date = self.sol.return_date

        self._assert_rented_quantities(
            from_date,
            to_date,
            expected_rented_quantities={start_date: 3, return_date: -3},
            expected_key_dates=[from_date, start_date, return_date, to_date],
        )
        self._assert_availabilities(
            from_date,
            to_date,
            expected_availabilities=[
                {"start": from_date, "end": start_date, "quantity_available": 5},
                {"start": start_date, "end": return_date, "quantity_available": 2},
                {"start": return_date, "end": to_date, "quantity_available": 5},
            ],
        )
        self.so.update({"rental_start_date": from_date, "rental_return_date": to_date})
        self._assert_cart_and_free_qty(self.so, expected_cart_qty=3, expected_free_qty=2)

    def test_available_and_rented_quantities_for_confirmed_so(self):
        self.so.action_confirm()
        from_date = self.now
        to_date = self.now + relativedelta(days=4)
        start_date = self.sol.start_date
        return_date = self.sol.return_date

        self._assert_rented_quantities(
            from_date,
            to_date,
            expected_rented_quantities={start_date: 3, return_date: -3},
            expected_key_dates=[from_date, start_date, return_date, to_date],
        )
        self._assert_availabilities(
            from_date,
            to_date,
            expected_availabilities=[
                {"start": from_date, "end": start_date, "quantity_available": 5},
                {"start": start_date, "end": return_date, "quantity_available": 2},
                {"start": return_date, "end": to_date, "quantity_available": 5},
            ],
        )
        self.so.update({"rental_start_date": from_date, "rental_return_date": to_date})
        self._assert_cart_and_free_qty(self.so, expected_cart_qty=3, expected_free_qty=2)

    def test_available_and_rented_quantities_for_picked_up_so(self):
        self.so.action_confirm()
        self._pickup_so(self.so)
        from_date = self.now
        to_date = self.now + relativedelta(days=4)
        start_date = self.sol.start_date
        return_date = self.sol.return_date

        self._assert_rented_quantities(
            from_date,
            to_date,
            expected_rented_quantities={from_date: 3, start_date: 0, return_date: -3},
            expected_key_dates=[from_date, start_date, return_date, to_date],
        )
        self._assert_availabilities(
            from_date,
            to_date,
            expected_availabilities=[
                {"start": from_date, "end": start_date, "quantity_available": 2},
                {"start": start_date, "end": return_date, "quantity_available": 2},
                {"start": return_date, "end": to_date, "quantity_available": 5},
            ],
        )
        self.so.update({"rental_start_date": from_date, "rental_return_date": to_date})
        self._assert_cart_and_free_qty(self.so, expected_cart_qty=3, expected_free_qty=2)

    def test_available_and_rented_quantities_for_returned_so(self):
        self.so.action_confirm()
        self._pickup_so(self.so)
        self._return_so(self.so)
        from_date = self.now
        to_date = self.now + relativedelta(days=4)
        start_date = self.sol.start_date
        return_date = self.sol.return_date

        self._assert_rented_quantities(
            from_date,
            to_date,
            expected_rented_quantities={from_date: 0, start_date: 0, return_date: 0},
            expected_key_dates=[from_date, start_date, return_date, to_date],
        )
        self._assert_availabilities(
            from_date,
            to_date,
            expected_availabilities=[
                {"start": from_date, "end": start_date, "quantity_available": 5},
                {"start": start_date, "end": return_date, "quantity_available": 5},
                {"start": return_date, "end": to_date, "quantity_available": 5},
            ],
        )
        self.so.update({"rental_start_date": from_date, "rental_return_date": to_date})
        self._assert_cart_and_free_qty(self.so, expected_cart_qty=0, expected_free_qty=5)

    def test_available_and_rented_quantities_for_multiple_sos(self):
        self.so.action_confirm()
        so2 = self._create_so_with_sol(
            rental_start_date=self.now + relativedelta(days=1),
            rental_return_date=self.now + relativedelta(days=2),
            product_uom_qty=2,
        )
        so2.action_confirm()
        from_date = self.now
        to_date = self.now + relativedelta(days=4)
        start_date = self.sol.start_date
        return_date = self.sol.return_date
        return_date2 = so2.rental_return_date

        self._assert_rented_quantities(
            from_date,
            to_date,
            expected_rented_quantities={start_date: 5, return_date2: -2, return_date: -3},
            expected_key_dates=[from_date, start_date, return_date2, return_date, to_date],
        )
        self._assert_availabilities(
            from_date,
            to_date,
            expected_availabilities=[
                {"start": from_date, "end": start_date, "quantity_available": 5},
                {"start": start_date, "end": return_date2, "quantity_available": 0},
                {"start": return_date2, "end": return_date, "quantity_available": 2},
                {"start": return_date, "end": to_date, "quantity_available": 5},
            ],
        )
        self.so.update({"rental_start_date": from_date, "rental_return_date": to_date})
        self._assert_cart_and_free_qty(so2, expected_cart_qty=2, expected_free_qty=0)

    def test_available_and_rented_quantities_for_multiple_sos_with_one_picked_up(self):
        self.so.action_confirm()
        self._pickup_so(self.so)
        so2 = self._create_so_with_sol(
            rental_start_date=self.now + relativedelta(days=1),
            rental_return_date=self.now + relativedelta(days=2),
            product_uom_qty=2,
        )
        so2.action_confirm()
        from_date = self.now
        to_date = self.now + relativedelta(days=4)
        return_date = self.sol.return_date
        start_date2 = so2.rental_start_date
        return_date2 = so2.rental_return_date

        self._assert_rented_quantities(
            from_date,
            to_date,
            expected_rented_quantities={
                from_date: 3,
                start_date2: 2,
                return_date2: -2,
                return_date: -3,
            },
            expected_key_dates=[from_date, start_date2, return_date2, return_date, to_date],
        )
        self._assert_availabilities(
            from_date,
            to_date,
            expected_availabilities=[
                {"start": from_date, "end": start_date2, "quantity_available": 2},
                {"start": start_date2, "end": return_date2, "quantity_available": 0},
                {"start": return_date2, "end": return_date, "quantity_available": 2},
                {"start": return_date, "end": to_date, "quantity_available": 5},
            ],
        )
        self.so.update({"rental_start_date": from_date, "rental_return_date": to_date})
        self._assert_cart_and_free_qty(so2, expected_cart_qty=2, expected_free_qty=0)

    def test_add_max_quantity_to_cart(self):
        values = self.so._cart_update_line_quantity(line_id=self.sol.id, quantity=8)
        self.assertEqual(values["quantity"], 5)
        self.assertTrue(values["warning"])

    def test_add_picked_up_products_not_yet_returned_to_cart_before_return_date(self):
        self.so.action_confirm()
        self._pickup_so(self.so)
        website_so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "warehouse_id": self.wh.id,
        })

        from_date = self.sol.return_date + relativedelta(days=-1)
        to_date = self.sol.return_date + relativedelta(days=2)

        website_so.update({"rental_start_date": from_date, "rental_return_date": to_date})
        self._assert_cart_and_free_qty(website_so, expected_cart_qty=0, expected_free_qty=2)
        values = website_so._cart_add(
            product_id=self.computer.id, quantity=5, start_date=from_date, end_date=to_date
        )
        self.assertEqual(values["quantity"], 2)
        self.assertTrue(values["warning"])

    def test_add_picked_up_products_not_yet_returned_to_cart_after_return_date(self):
        self.so.action_confirm()
        self._pickup_so(self.so)
        website_so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "warehouse_id": self.wh.id,
        })

        from_date = self.sol.return_date + relativedelta(days=1)
        to_date = self.sol.return_date + relativedelta(days=2)

        website_so.update({"rental_start_date": from_date, "rental_return_date": to_date})
        self._assert_cart_and_free_qty(website_so, expected_cart_qty=0, expected_free_qty=5)
        values = website_so._cart_add(
            product_id=self.computer.id, quantity=5, start_date=from_date, end_date=to_date
        )
        self.assertEqual(values["quantity"], 5)
        self.assertFalse(values["warning"])

    def test_show_rental_product_that_will_be_available_in_future(self):
        """
        When you filter rental products on the /shop with the datepicker,
        you should be able to see rental products that would be available in the future,
        even if today the quantity on hand is 0 because it is being rented.
        """
        self.sol.product_uom_qty = 5
        self.so.action_confirm()
        self._pickup_so(self.so)
        from_date = self.sol.return_date + relativedelta(days=1)
        to_date = self.sol.return_date + relativedelta(days=2)

        product_template = self.sol.product_template_id.with_company(self.company).sudo()
        filtered_products_during_rental = product_template._filter_on_available_rental_products(
            self.sol.start_date, self.sol.return_date, self.wh.id
        )
        self.assertFalse(filtered_products_during_rental)
        filtered_products_after_rental = product_template._filter_on_available_rental_products(
            from_date, to_date, self.wh.id
        )
        self.assertTrue(filtered_products_after_rental)

    def test_rental_product_duration_with_same_start_and_end_period(self):
        """Test the rental product duration when the start and end periods are the same."""
        ctx = {
            "start_date": datetime.datetime(2026, 2, 7, 0, 0),
            "end_date": datetime.datetime(2026, 2, 7, 0, 0),
            "website_sale_stock_get_quantity": True,
        }

        with MockRequest(
            self.computer.product_tmpl_id.env, website=self.current_website
        ) as request:
            with self.assertRaisesRegex(
                UserError, "Please choose a return date that is after the pickup date."
            ):
                self.computer.product_tmpl_id.with_context(
                    dict(request.env.context, **ctx)
                )._get_combination_info()

    def test_out_of_stock_ribbon_is_not_applicable_for_rentals(self):
        out_of_stock_ribbon = self.env["product.ribbon"].search(
            [("assign", "=", "out_of_stock")], limit=1
        ) or self.env["product.ribbon"].create({"name": "Out of stock", "assign": "out_of_stock"})
        rental_product = self.env["product.product"].create({
            "name": "Rental Product",
            "rent_periodicity": "days",
            "is_storable": True,
            "allow_out_of_stock_order": False,
        })
        self.assertFalse(out_of_stock_ribbon._is_applicable_for(rental_product, {}))

    def test_serial_product_rental_available_quantities_in_multiple_warehouses(self):
        """
        A serial-tracked product with one unit in each of two warehouses should be
        rentable from either warehouse independently. Renting the unit from one
        warehouse should not affect the availability of the unit in the other.
        """

        if self.env['ir.module.module']._get('website_sale_collect').state != 'installed':
            self.skipTest("website_sale_collect not installed")

        serial_product = self.env['product.product'].create({
            'name': 'Serial Product',
            'is_storable': True,
            'tracking': 'serial',
            'rent_periodicity': 'days',
            'allow_out_of_stock_order': False,
        })
        wh2 = self.env['stock.warehouse'].create({
            'name': 'Second Warehouse',
            'code': 'WH2',
            'company_id': self.company.id,
        })

        for warehouse, lot_name in [(self.wh, 'SN001'), (wh2, 'SN002')]:
            lot = self.env['stock.lot'].create({
                'name': lot_name,
                'product_id': serial_product.id,
                'company_id': self.company.id,
            })
            quant = self.env['stock.quant'].create({
                'product_id': serial_product.id,
                'inventory_quantity': 1.0,
                'location_id': warehouse.lot_stock_id.id,
                'lot_id': lot.id,
            })
            quant.action_apply_inventory()

        rental_so = self._create_so_with_sol(
            rental_start_date=self.now,
            rental_return_date=self.now + relativedelta(days=1),
            product_id=serial_product.id,
        )
        rental_so.action_confirm()
        self._pickup_so(rental_so)

        in_store_carrier = self.env['delivery.carrier'].create({
            'name': 'In-Store Pickup',
            'delivery_type': 'in_store',
            'product_id': self.env['product.product'].create({
                'name': 'In-Store Pickup Delivery',
                'type': 'service',
            }).id,
        })

        wh2_so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'rental_start_date': self.now,
            'rental_return_date': self.now + relativedelta(days=1),
            'warehouse_id': wh2.id,
            'carrier_id': in_store_carrier.id
        })
        self._assert_cart_and_free_qty(wh2_so, 0.0, 1.0, serial_product)

    def _assert_rented_quantities(
        self, from_date, to_date, expected_rented_quantities, expected_key_dates
    ):
        with freeze_time(self.now):
            rented_quantities, key_dates = self.computer._get_rented_quantities(from_date, to_date)
        self.assertDictEqual(rented_quantities, expected_rented_quantities)
        self.assertListEqual(key_dates, expected_key_dates)

    def _assert_availabilities(self, from_date, to_date, expected_availabilities):
        with freeze_time(self.now):
            availabilities = self.computer._get_availabilities(from_date, to_date, self.wh.id)
        self.assertListEqual(availabilities, expected_availabilities)

    def _assert_cart_and_free_qty(self, so, expected_cart_qty, expected_free_qty, product=False):
        with freeze_time(self.now):
            cart_qty, free_qty = so._get_cart_and_free_qty(product=product or self.computer)
        self.assertEqual(cart_qty, expected_cart_qty)
        self.assertEqual(free_qty, expected_free_qty)

    def _create_so_with_sol(self, rental_start_date, rental_return_date, **sol_values):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "warehouse_id": self.wh.id,
            "rental_start_date": rental_start_date,
            "rental_return_date": rental_return_date,
            "order_line": [Command.create({"product_id": self.computer.id, **sol_values})],
        })

    def _pickup_so(self, so):
        pickup_action = so.action_open_pickup()
        Form(self.env["rental.order.wizard"].with_context(pickup_action["context"])).save().apply()

    def _return_so(self, so):
        return_action = so.action_open_return()
        Form(self.env["rental.order.wizard"].with_context(return_action["context"])).save().apply()
