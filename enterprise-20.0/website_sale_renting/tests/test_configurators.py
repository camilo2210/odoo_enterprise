# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.website_sale_renting.tests.common import WebsiteSaleRentingCommon


@tagged("post_install", "-at_install")
class TestWebsiteSaleRentingConfigurators(HttpCase, WebsiteSaleRentingCommon):
    def test_website_sale_renting_product_configurator(self):
        optional_product = self._create_product(
            name="Optional product",
            website_published=True,
            rent_periodicity="hours",
            list_price=6.0,
        )
        self._create_product(
            name="Main product",
            optional_product_ids=[Command.set(optional_product.product_tmpl_id.ids)],
            rent_periodicity="hours",
            list_price=5.0,
            website_published=True,
        )
        self.start_tour("/shop?search=Main product", "website_sale_renting_product_configurator")

    def test_website_sale_renting_combo_configurator(self):
        combo = (
            self
            .env["product.combo"]
            .sudo()
            .create({
                "name": "Test combo",
                "combo_item_ids": [
                    Command.create({
                        "product_id": self._create_product(
                            website_published=True, rent_periodicity="hours"
                        ).id
                    }),
                    Command.create({
                        "product_id": self._create_product(
                            website_published=True, rent_periodicity="hours"
                        ).id
                    }),
                ],
            })
        )
        self._create_product(
            name="Combo product",
            type="combo",
            combo_ids=[Command.link(combo.id)],
            rent_periodicity="hours",
            list_price=5.0,
            website_published=True,
        )
        self.start_tour("/shop?search=Combo product", "website_sale_renting_combo_configurator")
