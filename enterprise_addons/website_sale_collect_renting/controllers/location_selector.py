# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import route

from odoo.addons.sale_renting.controllers.utils import _convert_rental_dates
from odoo.addons.website_sale_collect.controllers.delivery import InStoreDelivery


class LocationSelector(InStoreDelivery):
    @route()
    def website_sale_get_pickup_locations(self, **kwargs):
        """Override of `website_sale_collect` to take the selected rental period into account."""
        _convert_rental_dates(kwargs)
        return super().website_sale_get_pickup_locations(**kwargs)
