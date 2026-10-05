# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields

from odoo.addons.website_sale_collect.tests.common import ClickAndCollectCommon
from odoo.addons.website_sale_renting.tests.common import WebsiteSaleRentingCommon


class ClickAndCollectRentingCommon(ClickAndCollectCommon, WebsiteSaleRentingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._add_product_qty_to_wh(cls.computer.id, 5.0, cls.warehouse.lot_stock_id.id)

    @classmethod
    def _create_in_store_delivery_order(cls, **values):
        now = fields.Datetime.now()
        values.setdefault("rental_start_date", now + relativedelta(days=1))
        values.setdefault("rental_return_date", now + relativedelta(weeks=1, days=1))
        return super()._create_in_store_delivery_order(**values)
