# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route

from odoo.addons.website_sale_renting.controllers.main import WebsiteSaleRenting


class WebsiteSalePlanningRenting(WebsiteSaleRenting):
    @route()
    def renting_product_availabilities(self, product_id, min_date, max_date):
        product_sudo = request.env["product.product"].sudo().browse(product_id).exists()
        result = super().renting_product_availabilities(product_id, min_date, max_date)
        if renting_availabilities := product_sudo._renting_product_availabilities(
            min_date, max_date
        ):
            result["renting_availabilities"] = renting_availabilities
        return result
