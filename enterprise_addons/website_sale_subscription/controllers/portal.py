# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import AccessError, MissingError
from odoo.http import request, route

from odoo.addons.sale_subscription.controllers.portal import SalePortal as SaleSubscriptionSalePortal
from odoo.addons.website_sale.controllers.sale import CustomerPortal as WebsiteSaleCustomerPortal


class CustomerPortal(SaleSubscriptionSalePortal, WebsiteSaleCustomerPortal):

    @route()
    def subscription(self, order_id, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            order_sudo = None

        if order_sudo and (website := order_sudo.assigned_website_id):
            request.update_context(website_id=website.id)
            website._force()

        return super().subscription(order_id, access_token=access_token, **kw)
