# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo.fields import Command
from odoo.tests import tagged

from .common import ClickAndCollectRentingCommon


@tagged("post_install", "-at_install")
class TestDeliveryCarrier(ClickAndCollectRentingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a partner for a warehouse.
        cls.wh_address_partner = cls.env["res.partner"].create({
            **cls.dummy_partner_address_values,
            "name": "Shop 1",
            "partner_latitude": 1.0,
            "partner_longitude": 2.0,
        })
        cls.warehouse.partner_id = cls.wh_address_partner.id
        cls.warehouse.opening_hours = cls.env["resource.calendar"].create({
            "name": "Opening hours",
            "attendance_ids": [
                Command.create({"dayofweek": "0", "hour_from": 8, "hour_to": 12}),
                Command.create({"dayofweek": "0", "hour_from": 13, "hour_to": 17}),
            ],
        })

    def test_in_store_get_close_locations_rental_product_not_available(self):
        so = self._create_in_store_delivery_order(
            order_line=[Command.create({"product_id": self.computer.id, "product_uom_qty": 5.0})]
        )
        so.action_confirm()

        with (
            patch.object(self.registry["res.partner"], "geo_localize", return_value=True),
            self.mock_request(sale_order_id=so.id),
        ):
            locations = self.in_store_dm.sudo()._in_store_get_close_locations(
                self.wh_address_partner,
                product_id=self.computer.id,
                start_date=so.rental_start_date,
                end_date=so.rental_return_date,
            )
            self.assertEqual(
                locations["pickup_location_data"][0]["additional_data"],
                {
                    "in_store_stock_data": {
                        "in_stock": False,
                        "uom_name": "Units",
                        "show_quantity": False,
                        "quantity": 0,
                    }
                },
            )

    def test_in_store_get_close_locations_rental_product_available(self):
        so = self._create_in_store_delivery_order(
            order_line=[Command.create({"product_id": self.computer.id, "product_uom_qty": 5.0})]
        )
        so.action_confirm()

        with (
            patch.object(self.registry["res.partner"], "geo_localize", return_value=True),
            self.mock_request(sale_order_id=so.id),
        ):
            locations = self.in_store_dm.sudo()._in_store_get_close_locations(
                self.wh_address_partner,
                product_id=self.computer.id,
                start_date=so.rental_return_date + relativedelta(weeks=1),
                end_date=so.rental_return_date + relativedelta(weeks=2),
            )
            self.assertEqual(
                locations["pickup_location_data"][0]["additional_data"],
                {
                    "in_store_stock_data": {
                        "in_stock": True,
                        "uom_name": "Units",
                        "show_quantity": False,
                        "quantity": 5.0,
                    }
                },
            )
