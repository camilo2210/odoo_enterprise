# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def set_open(self):
        were_churned_subscriptions = self.filtered(lambda sub: sub.subscription_state == '6_churn')
        super().set_open()
        inprogress_subscriptions = self.filtered(lambda sub: sub.subscription_state == '3_progress')
        reopened_subscriptions = inprogress_subscriptions & were_churned_subscriptions
        # ensure fiscal position is up to date
        orders_by_fpos = reopened_subscriptions.grouped('fiscal_position_id')
        self.env.add_to_compute(reopened_subscriptions._fields['fiscal_position_id'], reopened_subscriptions)
        if fpos_changed := reopened_subscriptions.filtered(
            lambda so: so not in orders_by_fpos.get(so.fiscal_position_id, []),
        ):
            fpos_changed._recompute_taxes()

    def _cart_add(self, product_id, *args, plan_id=None, **kwargs):
        product = self.env['product.product'].browse(product_id)
        if product.recurring_invoice and not kwargs.get('allow_one_time_sale'):
            if plan_id and self.plan_id and self.plan_id.id != plan_id:
                raise UserError(_("You cannot mix different subscription plans in the same order."))

            if not self.plan_id:
                pricing = product.product_tmpl_id._get_recurring_pricing(
                    pricelist=self.pricelist_id, variant=product, plan_id=plan_id,
                )
                if pricing:
                    self.plan_id = pricing.plan_id
                elif not product.allow_one_time_sale:
                    raise UserError(_("No suitable subscription pricing found for this product."))

        return super()._cart_add(product_id, *args, plan_id=plan_id, **kwargs)

    def _verify_cart_after_update(self, *args, **kwargs):
        super()._verify_cart_after_update(*args, **kwargs)
        if not self.order_line.filtered(lambda sol: sol.product_id.recurring_invoice):
            self.plan_id = False

    def _has_one_time_sale(self):
        return (
            not self.plan_id
            and any(line.product_id.recurring_invoice for line in self.order_line)
        )
