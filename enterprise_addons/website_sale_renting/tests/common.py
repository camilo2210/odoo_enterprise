# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.sale_renting.tests.common import SaleRentingCommon
from odoo.addons.website_sale.tests.common import WebsiteSaleCommon


class WebsiteSaleRentingCommon(SaleRentingCommon, WebsiteSaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # TODO: remove setUpClass and use `cls.projector` from sale_renting
        if "enforce_cities" in cls.env["res.country"]._fields:
            cls.company.country_id.enforce_cities = False

        cls.computer = cls._create_product(
            name="Computer", list_price=3.5, rent_periodicity="hours", is_storable=True
        )
        cls.rental_calendar = cls.env.ref("resource.resource_calendar_std")
