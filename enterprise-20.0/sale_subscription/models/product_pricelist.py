# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    def _compute_price_rule(self, products, quantity, *, plan_id=None, **kwargs):
        plan_id = plan_id or self.env.context.get("plan_id")
        return super()._compute_price_rule(products, quantity, plan_id=plan_id, **kwargs)

    def _get_applicable_rules(self, products, quantity, date, *, plan_id=None, **kwargs):
        if not self:
            return self.env['product.pricelist.item']

        self.ensure_one()

        recurring_rules = self.env['product.pricelist.item']
        if plan_id:
            # Prepend the recurring rules if a plan is given, as they are expected to take priority
            # over the standard rules.
            recurring_rules = self.env['product.pricelist.item'].with_context(active_test=False).search(
                self._get_applicable_rules_domain(products=products, date=date, plan_id=plan_id, quantity=quantity, **kwargs),
                order=self.env['product.pricelist.item']._get_recurring_rules_order(),
            ).with_context(self.env.context)

        # Do not give plan_id to super call
        return recurring_rules | super()._get_applicable_rules(products, quantity, date, **kwargs)

    def _get_applicable_rules_domain(self, *args, plan_id=None, any_plan=False, **kwargs):
        # Filter out subscription-rules targeting other products
        base_domain = super()._get_applicable_rules_domain(*args, plan_id=plan_id, **kwargs)

        if plan_id:
            # Only search recurring rules when a plan is given
            return Domain.AND([
                base_domain,
                [('plan_id', '=', plan_id)]
            ])

        if any_plan:
            # Specific use-case (website_sale_subscription), fetch all the recurring rules applying
            # to a given product.
            return Domain.AND([
                base_domain,
                [('plan_id', '!=', False)],
            ])

        # Do not return recurring rules if no plan was given
        return Domain.AND([
            base_domain,
            [('plan_id', '=', False)]
        ])
