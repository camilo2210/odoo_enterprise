# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest import skip

from freezegun import freeze_time

from odoo.fields import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.website_sale_renting.tests.common import WebsiteSaleRentingCommon


@tagged("-at_install", "post_install")
class TestUi(HttpCase, WebsiteSaleRentingCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_website_sale_renting_ui(self):
        self.env.ref("base.user_admin").write({
            "name": "Mitchell Admin",
            "email": "mitchell.admin@example.com",
            "street": "215 Vine St",
            "phone": "+1 555-555-5555",
            "city": "Scranton",
            "zip": "18503",
            "country_id": self.env.ref("base.us").id,
            "state_id": self.env.ref("base.state_us_39").id,
        })
        self.start_tour("/shop", "shop_buy_rental_product", login="admin")

    def test_add_accessory_rental_product(self):
        parent_product, accessory_product = self.env["product.product"].create([
            {
                "name": "Parent product",
                "list_price": 1000,
                "sale_ok": True,
                "rent_periodicity": "hours",
                "is_published": True,
            },
            {
                "name": "Accessory product",
                "list_price": 1000,
                "sale_ok": True,
                "rent_periodicity": "hours",
                "is_published": True,
            },
        ])
        parent_product.accessory_product_ids = accessory_product
        self.start_tour("/shop", "shop_buy_accessory_rental_product", login="admin")

    @skip("TODO: `freeze_time` should affect `luxon.DateTime.now()`")
    def test_website_sale_renting_default_range(self):
        with freeze_time("2023-12-04 08:00"):
            self.start_tour(
                "/shop?start_date=2023-12-17+23%3A00%3A00&end_date=2023-12-22+22%3A59%3A59",
                "website_sale_renting_default_duration_from_default_range",
                login="admin",
            )

    def test_website_sale_update_rental_duration(self):
        self.start_tour("/shop", "rental_cart_update_duration")

    def test_website_sale_update_rental_duration_days(self):
        self.computer.write({
            "list_price": 20.0,
            "rent_periodicity": "days",
            "pickup_time": 9,
            "return_time": 18,
        })
        self.start_tour("/shop", "date_based_rental_duration")

    def test_website_sale_renting_select_wrong_period(self):
        self.start_tour("/shop?search=Computer", "website_sale_renting_select_wrong_period")

    def test_website_sale_renting_wishlist_ui(self):
        self.env.ref("base.user_admin").write({
            "name": "Mitchell Admin",
            "street": "215 Vine St",
            "phone": "+1 555-555-5555",
            "city": "Scranton",
            "zip": "18503",
            "country_id": self.env.ref("base.us").id,
            "state_id": self.env.ref("base.state_us_39").id,
            "email": "mitchell.admin@example.com",
        })
        self.start_tour("/shop?search=Computer", "shop_buy_rental_product_wishlist", login="admin")

    def test_website_sale_renting_comparison_ui(self):
        # Checkout process in the tour assumes partner information is set.
        self.env.ref("base.user_admin").partner_id.write({
            "country_id": self.env.ref("base.be").id,
            "street": "StreetName 3",
            "email": "mitchell.admin@openerp.com",
            "city": "Louvain-La-Neuve",
            "zip": "1348",
            "phone": "+32 2 290 34 90",
        })
        attribute = self.env["product.attribute"].create({
            "name": "Color",
            "sequence": 10,
            "display_type": "color",
            "value_ids": [Command.create({"name": "Red"}), Command.create({"name": "Pink"})],
        })
        self.env["product.template"].create({
            "name": "Color T-Shirt",
            "list_price": 20.0,
            "website_sequence": 9980,
            "is_published": True,
            "type": "service",
            "invoice_policy": "delivery",
            "attribute_line_ids": [
                Command.create({"attribute_id": attribute.id, "value_ids": attribute.value_ids})
            ],
        })
        self.attribute_processor = self.env["product.attribute"].create({
            "name": "Processor",
            "sequence": 1,
        })
        self.values_processor = self.env["product.attribute.value"].create([
            {"name": name, "attribute_id": self.attribute_processor.id, "sequence": i}
            for i, name in enumerate(["i3", "i5", "i7"])
        ])
        self.attribute_line_processor = self.env["product.template.attribute.line"].create([
            {
                "product_tmpl_id": self.computer.product_tmpl_id.id,
                "attribute_id": self.attribute_processor.id,
                "value_ids": [Command.set(v.ids)],
            }
            for v in self.values_processor
        ])
        self.assertTrue(self.computer.valid_product_template_attribute_line_ids)

        # Make sure comparison button is enabled on /shop page (of any website, as it seems
        # self.website is not the website used by the tour)
        for website in self.env["website"].search([]):
            website.write({
                "shop_opt_products_design_classes": self.website.shop_opt_products_design_classes
                + " o_wsale_products_opt_has_comparison"
            })
        self.start_tour(
            "/shop?search=Computer", "shop_buy_rental_product_comparison", login="admin"
        )
