# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import product

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestRentalUi(HttpCase):
    def test_rental_flow(self):
        self.env.ref("base.user_admin").write({"email": "mitchell.admin@example.com"})
        self.env.company.rental_resource_calendar_id = False

        # somehow, the name_create and onchange of the partner_id
        # in a quotation trigger a re-rendering that loses
        # the focus of some fields, preventing the tour to
        # run successfully if a partner is created during the flow
        # create it in advance here instead
        self.env["res.partner"].name_create("Agrolait")
        self.start_tour("/odoo", "rental_tour", login="admin")

    def test_product_displayed_on_rental_only(self):
        """
        This test will check that product are diplayed in the correct app.
        In the rental app: sale_ok product and no products without rent_periodicity.
        In the sale app: sale_ok product and no product with rent_periodicity.
        """
        if self.env["ir.module.module"]._get("sale_management").state != "installed":
            self.skipTest(
                "If the 'sale_management' module isn't installed, we can't test wether products"
                " appear in the sale app!"
            )

        self.env["product.product"].create([
            {
                "name": f"product:{sale_ok=},{bool(rent_periodicity)=}",
                "type": "consu",
                "sale_ok": sale_ok,
                "rent_periodicity": rent_periodicity,
            }
            for sale_ok, rent_periodicity in product([True, False], [False, "hours"])
        ])

        self.start_tour("/odoo", "sale_renting_product_display", login="admin")
        self.start_tour("/odoo", "sale_product_display", login="admin")
