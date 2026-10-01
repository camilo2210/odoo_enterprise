# Part of Odoo. See LICENSE file for full copyright and licensing details.

from math import floor

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import format_amount


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.constrains('optional_product_ids')
    def _constraints_optional_product_ids(self):
        for template in self:
            if not template.recurring_invoice:
                continue
            plan_ids = set(template.pricelist_rule_ids.plan_id.ids)
            for optional_template in template.optional_product_ids:
                if not optional_template.recurring_invoice:
                    continue
                optional_plan_ids = optional_template.pricelist_rule_ids.plan_id.ids
                if not plan_ids.intersection(optional_plan_ids):
                    raise UserError(_('You cannot have an optional product that has a no common pricing\'s plan.'))

    def _is_donation(self):
        return super()._is_donation() or self.id == self.env["ir.model.data"]._xmlid_to_res_id(
            "website_sale_subscription.product_recurring_donation"
        )

    def _is_purchasable(self, product=None) -> bool:
        # Override of `website_sale` to handle recurring products
        if not super()._is_purchasable(product):
            return False

        if not self.recurring_invoice:
            return True

        if request.cart._has_one_time_sale() and not self.allow_one_time_sale:
            return False

        if self.allow_one_time_sale and not request.cart.plan_id:
            return True

        has_pricing = bool(
            self._get_recurring_pricing(
                pricelist=request.pricelist,
                variant=product,
                plan_id=request.cart.plan_id.id,
            )
        )
        if not has_pricing and not product:
            # If pricings are only defined by variant, there are no pricing applicable to the
            # template itself. In this situation, we need to search for a pricing on a variant
            # otherwise customers wouldn't be able to add the product to their cart.
            has_pricing = bool(
                self._get_recurring_pricing(
                    pricelist=request.pricelist,
                    variant=self.product_variant_id,
                    plan_id=request.cart.plan_id.id,
                )
            )

        return has_pricing

    def _get_additional_combination_info(
        self, product_or_template, quantity, uom, website, pricelist, fiscal_position, **kwargs
    ):
        res = super()._get_additional_combination_info(
            product_or_template, quantity, uom, website, pricelist, fiscal_position, **kwargs
        )

        if not product_or_template.recurring_invoice:
            return res

        product = (product_or_template.is_product_variant and product_or_template) or self.env['product.product']
        cart = request.cart if (request and hasattr(request, 'cart')) else self.env['sale.order'].sudo()
        pricings = self._get_recurring_pricings(pricelist=pricelist, variant=product, quantity=quantity)

        original_list_price = res['list_price']
        res['list_price'] = res['price']  # No pricelist discount for subscription prices
        res['original_list_price'] = (
            original_list_price
            if self.allow_one_time_sale and res.get('has_discounted_price')
            else None
        )

        if not pricings:
            res.update({
                'is_subscription': True,
                'is_plan_possible': False,
                'pricings': [],
                'allow_one_time_sale': not cart.plan_id and self.allow_one_time_sale,
            })
            return res

        to_year = {'year': 1, 'month': 12, 'week': 52}
        translation_mapping = {
            'year': _('year'),
            'month': _('month'),
            'week': _('week'),
        }

        # Find the plan with the shortest billing period to use as base for comparison
        base_plan = min(pricings.sudo().plan_id, key=lambda x: 1 / to_year[x.billing_period_unit])
        minimum_period = base_plan.billing_period_unit

        # Compute base period price and max price for discount calculation
        base_plan_pricings = pricings.filtered(lambda pr: pr.plan_id == base_plan)
        base_period_price = min(base_plan_pricings.mapped('fixed_price'), default=0.0) / base_plan.billing_period_value
        max_price = max(pricings.mapped('fixed_price'), default=0.0)

        currency = website.currency_id
        requested_plan = request and request.params.get('plan_id')
        requested_plan_id = requested_plan and requested_plan.isdigit() and int(requested_plan)
        requested_plan_id = requested_plan_id or cart.plan_id.id
        if requested_plan_id:
            chosen_pricing = pricings.filtered(lambda pricing: pricing.plan_id.id == requested_plan_id) or pricings[0]
        else:
            chosen_pricing = pricings[0]

        sales_price = res['price']

        def _get_pricing_data(pricing):
            if not pricing:
                return {}

            price = pricing._compute_price(
                product=product_or_template,
                quantity=quantity or 1.0,
                uom=product_or_template.uom_id,
                currency=currency,
                plan_id=pricing.plan_id.id,
            )

            if res.get('product_taxes', False):
                price = product_or_template._apply_taxes_to_price(
                    price, currency, product_taxes=res['product_taxes'], taxes=res['taxes'],
                )

            price_format = format_amount(self.env, amount=price, currency=currency)
            pricing_plan_sudo = pricing.plan_id.sudo()  # Not accessible to public users
            price_in_minimum_period = (
                price
                / pricing_plan_sudo.billing_period_value
                * to_year[pricing_plan_sudo.billing_period_unit]
                / to_year[minimum_period]
            )

            if product_or_template.type == 'consu':
                # For consumable products, use delivery period (e.g., "Deliver every 3 months") instead of plan name
                table_name = pricing.plan_id.delivery_period_display
            else:
                # For non-consumable products, use plan name with non-breaking spaces
                table_name = pricing.plan_id.name.replace(" ", "\u00A0")

            pricing_data = {
                'plan_id': pricing_plan_sudo.id,
                'price': f"{pricing.plan_id.name}: {price_format}",
                'price_value': price,
                'table_price': price_format,
                'table_name': table_name,
                'to_minimum_billing_period': f'{format_amount(self.env, amount=price_in_minimum_period, currency=currency)}'
                                             f' / {translation_mapping.get(minimum_period, minimum_period)}',
                'can_be_added': cart.plan_id.id in (pricing_plan_sudo.id, False),
            }

            original_price = None
            if pricing.compute_price != 'fixed':
                original_price = pricing._compute_price_before_discount(
                    product=product_or_template,
                    quantity=quantity or 1.0,
                    uom=product_or_template.uom_id,
                    date=fields.Datetime.now(),
                    currency=currency,
                    plan_id=pricing.plan_id.id,
                )
            # Calculate discount percentage
            reference_price = current_plan_price = 0.0
            if product_or_template.allow_one_time_sale:
                # Compare against the Buy Once(sales_price) price to show the benefit of subscribing.
                reference_price, current_plan_price = sales_price, price
            elif product_or_template.type == 'consu':
                # Compare against the most expensive plan to show savings on cheaper delivery options.
                reference_price, current_plan_price = max_price, price
            elif 0 < price_in_minimum_period < base_period_price:
                # Compare against the shortest billing period to show savings across subscription terms.
                reference_price, current_plan_price = base_period_price, price_in_minimum_period

            discount = 0.0
            if pricing.is_plain_discount:  # Plain discount: use the value directly
                discount = pricing.price_discount
            elif 0 < current_plan_price < reference_price:
                discount = ((reference_price - current_plan_price) * 100) / reference_price

            pricing_data['discounted_price'] = floor(discount)
            pricing_data['original_plan_price'] = (
                format_amount(self.env, amount=original_price, currency=currency)
                if original_price and original_price > 0 and original_price > price
                else None
            )
            return pricing_data

        default_pricing_data = _get_pricing_data(chosen_pricing)

        pricing_details = [
            _get_pricing_data(pricing)
            for pricing in pricings
        ]

        unit_price = default_pricing_data.get('price_value', 0)
        return {
            **res,
            'is_subscription': True,
            'pricings': pricing_details,
            'is_plan_possible': bool(chosen_pricing),
            'price': unit_price,
            'subscription_default_pricing_price': default_pricing_data.get('price', ''),
            'subscription_default_pricing_plan_id': default_pricing_data.get('plan_id', False),
            'subscription_pricing_select': (product_or_template.allow_one_time_sale or len(pricings) > 1) and not cart.plan_id,
            'prevent_sale': website._prevent_product_sale(
                product_or_template,
                currency.is_zero(unit_price),
            ),
            'allow_one_time_sale': not cart.plan_id and self.allow_one_time_sale,
            'allow_recurring': not cart._has_one_time_sale(),
            'product_type': product_or_template.type,  # Used to change pricing text in template based on product type
            "temporal_unit_display": chosen_pricing.plan_id.sudo().billing_period_display_sentence if chosen_pricing else "",
        }

    # Search bar
    def _search_render_results_prices(self, mapping, combination_info):
        if not combination_info.get('is_subscription'):
            return super()._search_render_results_prices(mapping, combination_info)

        if not combination_info['is_plan_possible']:
            return ''

        website = self.env.website
        return website._render_template(
            'website_sale_subscription.subscription_search_result_price',
            values={
                'subscription_default_pricing_price': combination_info['subscription_default_pricing_price'],
            }
        )

    def _get_sales_prices(self, pricelist_sudo, fiscal_position_sudo, website):
        prices = super()._get_sales_prices(pricelist_sudo, fiscal_position_sudo, website)

        ProductPricelistItem = self.env['product.pricelist.item'].sudo()

        for template in self:
            if not template.recurring_invoice:
                continue

            prices[template.id]['is_subscription'] = True

            pricelist_item_id = prices[template.id]['pricelist_rule_id']
            pricelist_item_sudo = ProductPricelistItem.browse(pricelist_item_id)

            pricing_sudo = ProductPricelistItem
            if pricelist_item_sudo.plan_id:
                # If the pricelist rule considered by the base price computation logic has a plan
                # then it's a recurring pricing. This only happens when a plan is given through the
                # context, meaning that the cart already has a plan and recurring products.
                pricing_sudo = pricelist_item_sudo

            if not pricing_sudo:
                # If no pricelist item was found, it means that the pricing applied (if any) is
                # a generic one, not restricted to a specific pricelist.
                if not self.env.context.get('plan_id'):
                    pricing_sudo = template.sudo()._get_recurring_pricing(pricelist=pricelist_sudo)
                else:
                    # If there was a matching recurring pricing in the current pricelist, it would
                    # have been found by the super call. As none was found, the only pricing that
                    # could still work is a generic one without pricelist
                    pricing_sudo = template.sudo()._get_recurring_pricing(pricelist=pricelist_sudo.browse())
                prices[template.id]['pricelist_rule_id'] = pricing_sudo.id

                if pricing_sudo:
                    # If a recurring pricing was found, the price displayed on the shop page should
                    # be its recurring price, and not its sales price.
                    currency = (pricelist_sudo or website).currency_id
                    unit_price = pricing_sudo._compute_price(
                        product=template,
                        quantity=1.0,
                        uom=template.uom_id,
                        currency=currency,
                        plan_id=pricing_sudo.plan_id.id,
                    )
                    prices[template.id]['price_reduce'] = template._apply_taxes_to_price(
                        unit_price, currency
                    )

            if not pricing_sudo:
                prices[template.id]['is_plan_possible'] = False
                continue

            prices[template.id].update({
                'is_plan_possible': True,  # The plan can only be valid at this point
                'temporal_unit_display': pricing_sudo.plan_id.billing_period_display_sentence,
            })

        return prices

    def _get_recurring_pricing(self, pricelist, variant=None, plan_id=None, quantity=1.0):
        return super()._get_recurring_pricing(
            pricelist,
            variant=variant,
            plan_id=plan_id or self.env.context.get('plan_id'),
            quantity=quantity,
        )
