# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError

from odoo.addons.website_sale.controllers import delivery, main


class WebsiteSaleExternalTaxCalculation(main.WebsiteSale):

    def _get_shop_payment_values(self, order, **kwargs):
        res = super()._get_shop_payment_values(order, **kwargs)
        res['on_payment_step'] = True
        return res


class WebsiteSaleDelivery(delivery.Delivery):

    def _order_summary_values(self, order, **post):
        res = super()._order_summary_values(order, **post)
        try:
            order._get_and_set_external_taxes_on_eligible_records()
        except UserError as e:
            res['external_tax_error'] = str(e)
        return res
