# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.website_sale_subscription.controllers.cart import Cart
from odoo.addons.website_sale_subscription.tests.common import WebsiteSaleSubscriptionCommon


@tagged('post_install', '-at_install')
class TestWebsiteSaleSubscription(WebsiteSaleSubscriptionCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_cart_update_so_reccurence(self):
        self.env['product.pricelist'].sudo().search([('active', '=', True)]).action_archive()
        self.env['product.pricelist.item'].search([('plan_id', '!=', False)]).pricelist_id = False
        # Product not recurring
        product = self.env['product.template'].with_context(website_id=self.website.id).create({
            'name': 'Non-recurring Product',
            'list_price': 15,
            'type': 'service',
        })

        # Mocking to check if error raised on Website when adding
        # 2 subscription product with different recurrence
        with self.mock_request() as request:
            website = request.env.website
            so = website._create_cart()
            self.assertFalse(so.plan_id)
            so._cart_add(product_id=product.product_variant_ids.id, quantity=1)
            self.assertFalse(so.plan_id)
            so._cart_add(product_id=self.sub_product.product_variant_ids.id, quantity=1)
            self.assertEqual(so.plan_id, self.plan_week)
            with self.assertRaises(UserError, msg="You can't add a subscription product to a sale order with another recurrence."):
                # Must go through controller since _is_add_to_cart_allowed is checked there
                Cart().add_to_cart(
                    product_template_id=self.sub_product_2.id,
                    product_id=self.sub_product_2.product_variant_id.id,
                    quantity=1.0,
                )
            so._cart_update_line_quantity(
                line_id=so.order_line.filtered(
                    lambda sol: sol.product_id == self.sub_product.product_variant_id
                ).id,
                quantity=0,
            )
            self.assertFalse(so.plan_id)
            so._cart_add(product_id=self.sub_product_2.product_variant_ids.id, quantity=1)
            self.assertEqual(so.plan_id, self.plan_month)
            so._cart_update_line_quantity(
                line_id=so.order_line.filtered(
                    lambda sol: sol.product_id == self.sub_product_2.product_variant_id
                ).id,
                quantity=0,
            )
            self.assertFalse(so.plan_id)

    def test_combination_info_product(self):
        self.sub_product = self.sub_product.with_context(website_id=self.website.id)

        with self.mock_request() as request:
            self.assertEqual(request.pricelist, self.pricelist)
            combination_info = self.sub_product._get_combination_info()
            self.assertEqual(combination_info['price'], 5)
            self.assertTrue(combination_info['is_subscription'])
            self.assertEqual(combination_info['subscription_default_pricing_plan_id'], self.plan_week.id)
            self.assertEqual(combination_info['subscription_default_pricing_price'], 'Weekly: $ 5.00')

    def test_combination_info_variant_products(self):
        template = self.sub_with_variants.with_context(website_id=self.website.id)
        with self.mock_request() as request:
            self.assertEqual(request.pricelist, self.pricelist)
            combination_info = template.product_variant_ids[0]._get_combination_info_variant()
        self.assertEqual(combination_info['price'], 10)
        self.assertTrue(combination_info['is_subscription'])
        self.assertEqual(combination_info['subscription_default_pricing_plan_id'], self.plan_week.id)
        self.assertEqual(combination_info['subscription_default_pricing_price'], 'Weekly: $ 10.00')

        with self.mock_request() as request:
            self.assertEqual(request.pricelist, self.pricelist)
            combination_info_variant_2 = template.product_variant_ids[-1]._get_combination_info_variant()
        self.assertEqual(combination_info_variant_2['price'], 25)
        self.assertTrue(combination_info_variant_2['is_subscription'])
        self.assertEqual(combination_info_variant_2['subscription_default_pricing_plan_id'], self.plan_month.id)
        self.assertEqual(combination_info_variant_2['subscription_default_pricing_price'], 'Monthly: $ 25.00')

    def test_combination_info_multi_pricelist(self):
        product = self.sub_product_3.with_context(website_id=self.website.id)

        with self.mock_request(website_sale_current_pl=self.pricelist_111.id):
            combination_info = product._get_combination_info(only_template=True)
            self.assertEqual(combination_info['price'], 111)

        with self.mock_request(website_sale_current_pl=self.pricelist_222.id):
            combination_info = product._get_combination_info(only_template=True)
            self.assertEqual(combination_info['price'], 222)

    def test_cart_add_one_time_and_plan_product(self):
        one_time_product = self.one_time_sub_product

        # Case 1: Add to cart without a plan (one-time purchase)
        with self.mock_request() as request:
            website = request.env.website
            so = website._create_cart()
            self.assertFalse(so.plan_id)
            so._cart_add(product_id=one_time_product.product_variant_ids.id, quantity=1)

            # Check product in order line
            so.plan_id = False

            self.assertTrue(so.order_line)
            self.assertEqual(so.order_line.product_id, one_time_product.product_variant_ids)
            self.assertEqual(so.order_line.price_unit, one_time_product.list_price)

        # Case 2: Add to cart with a plan selected
        with self.mock_request() as request:
            website = request.env.website
            so = website._create_cart()
            so._cart_add(product_id=one_time_product.product_variant_ids.id, quantity=1)

            # Check product and price with plan applied

            self.assertTrue(so.order_line)
            self.assertEqual(so.order_line.product_id, one_time_product.product_variant_ids)
            self.assertEqual(so.plan_id, self.plan_month)

    def test_subscription_plan_discount_percentage(self):
        """Test discount percentage calculation"""
        # Case 1: Service subscription product
        product = self.env['product.template'].create({
            'name': 'Discounted Subscription', 'recurring_invoice': True, 'type': 'service',
        })
        self.env['product.pricelist.item'].create([
            {'plan_id': self.plan_week.id, 'fixed_price': 100.0, 'product_tmpl_id': product.id},
            {'plan_id': self.plan_month.id, 'fixed_price': 180.0, 'product_tmpl_id': product.id},
            {'plan_id': self.plan_year.id, 'fixed_price': 1000.0, 'product_tmpl_id': product.id},
        ])

        product = product.with_context(website_id=self.website.id)

        with self.mock_request(website=self.website):
            pricings = product._get_combination_info().get('pricings', [])

        weekly = next(p for p in pricings if p['plan_id'] == self.plan_week.id)
        monthly = next(p for p in pricings if p['plan_id'] == self.plan_month.id)
        yearly = next(p for p in pricings if p['plan_id'] == self.plan_year.id)
        self.assertEqual(weekly['discounted_price'], 0.0)  # Weekly plan no discount
        self.assertEqual(monthly['discounted_price'], 58)  # Monthly 10% discount
        self.assertEqual(yearly['discounted_price'], 80.0)  # Yearly 80% discount

        # Case 2: Consumable subscription product
        product.type = 'consu'
        with self.mock_request(website=self.website):
            pricings = product._get_combination_info().get('pricings', [])

        weekly = next(p for p in pricings if p['plan_id'] == self.plan_week.id)
        monthly = next(p for p in pricings if p['plan_id'] == self.plan_month.id)
        yearly = next(p for p in pricings if p['plan_id'] == self.plan_year.id)
        self.assertEqual(weekly['discounted_price'], 90.0)  # Weekly 90% cheaper than yearly
        self.assertEqual(monthly['discounted_price'], 82.0)  # Monthly 82% cheaper than yearly
        self.assertEqual(yearly['discounted_price'], 0.0)  # Yearly is base price

        # Case 3: One-time purchase + subscription
        product.list_price = 150  # One-time price
        product.allow_one_time_sale = True
        with self.mock_request():
            pricings = product._get_combination_info().get('pricings', [])

        weekly = next(p for p in pricings if p['plan_id'] == self.plan_week.id)
        monthly = next(p for p in pricings if p['plan_id'] == self.plan_month.id)
        yearly = next(p for p in pricings if p['plan_id'] == self.plan_year.id)
        self.assertEqual(weekly['discounted_price'], 33)    # (150-100)/150 = 33% cheaper than Buy Once
        self.assertEqual(monthly['discounted_price'], 0.0)  # 180 > 150 (Buy Once), no discount shown
        self.assertEqual(yearly['discounted_price'], 0.0)   # 1000 > 150 (Buy Once), no discount shown

    def test_cart_add_one_time_then_recurring_not_allowed(self):
        """
        Test that a cart cannot mix one-time and subscription products.
        Allows adding one-time, blocks adding subscription after it,
        but works once the one-time product is removed.
        """
        one_time_product = self.one_time_sub_product
        with self.mock_request() as request:
            website = request.env.website
            so = website._create_cart()

            # Add one-time product
            so._cart_add(product_id=one_time_product.product_variant_ids.id, quantity=1)
            so.plan_id = False

            with self.assertRaises(UserError, msg="You can't add a subscription product to a sale order with a one-time product."):
                Cart().add_to_cart(
                    product_template_id=self.sub_product.id,
                    product_id=self.sub_product.product_variant_id.id,
                    quantity=1.0,
                )

            so._cart_update_line_quantity(
                line_id=so.order_line.filtered(
                    lambda sol: sol.product_id == one_time_product.product_variant_id
                ).id,
                quantity=0,
            )
            self.assertFalse(so.plan_id)

            so._cart_add(product_id=self.sub_product.product_variant_ids.id, quantity=1)
            self.assertEqual(so.plan_id, self.plan_week)

    def test_combination_info_skips_archived_plan(self):
        # Archive the weekly subscription plan so the product has no active plan
        self.plan_week.action_archive()
        product = self.sub_product.with_context(website_id=self.website.id)

        with self.mock_request():
            combination_info = product._get_combination_info()
            self.assertTrue(combination_info['is_subscription'])
            self.assertEqual(combination_info['pricings'], [])

    def test_subscription_recompute_taxes_on_address_change(self):
        self.env.company.country_id = self.env.ref('base.us')
        domestic_fpos = self.env.company.domestic_fiscal_position_id
        fpos_be = self.env['account.fiscal.position'].create({
            'name': "Fiscal Position BE",
            'auto_apply': True,
            'country_id': self.country_be.id,
        })
        tax_15_excl, tax_0 = self.env['account.tax'].create([
            {
                'name': "15% excl",
                'amount': 15,
                'price_include_override': 'tax_excluded',
                'fiscal_position_ids': (fpos_be | domestic_fpos).ids,
            },
            {
                'name': "0%",
                'amount': 0,
                'fiscal_position_ids': fpos_be.ids,
            },
        ])
        tax_0.original_tax_ids = tax_15_excl
        self.sub_product.taxes_id = [Command.set(tax_15_excl.ids)]
        self.partner.country_id = self.country_be

        cart = self._create_so(order_line=[])
        cart._cart_add(product_id=self.sub_product.product_variant_ids.id, quantity=1)
        amount_untaxed = cart.amount_untaxed
        self.assertEqual(cart.fiscal_position_id, fpos_be)
        self.assertEqual(cart.order_line.tax_ids, tax_0)

        cart.action_confirm()
        self.assertEqual(cart.subscription_state, '3_progress')
        self.partner.country_id = self.env.company.country_id
        self.assertNotEqual(cart.fiscal_position_id, fpos_be)
        self.assertEqual(
            cart.order_line.tax_ids, tax_15_excl,
            "Tax should have been updated on running subscriptions",
        )
        self.assertEqual(cart.amount_untaxed, amount_untaxed, "Untaxed amount should not change")

        cart.set_close()
        self.partner.country_id = self.country_be
        self.assertNotEqual(cart.fiscal_position_id, fpos_be)
        self.assertEqual(
            cart.order_line.tax_ids, tax_15_excl,
            "Tax should not have been updated on churned subscriptions",
        )

        cart.set_open()
        self.assertEqual(cart.fiscal_position_id, fpos_be)
        self.assertEqual(
            cart.order_line.tax_ids, tax_0,
            "Tax should have been updated when reopening a subscription",
        )

    def test_zero_price_subscription_with_pricelist(self):
        """
        Enable the `prevent_sale` setting.
        Create a subscription product with a price of 0, except for a specific pricelist where it is
        priced at 20.0.
        Add the subscription product to the cart from the website as a user using that pricelist
        The product should be added and the sale order's monthly recurring revenue should be 20.0.
        """
        self.website.prevent_sale = True
        subscription = (
            self.env["product.product"]
            .with_context(website_id=self.website.id)
            .create(
                {
                    "name": "subscription",
                    "recurring_invoice": True,
                    "lst_price": 0,
                    "is_published": True,
                    "subscription_rule_ids": [
                        Command.create(
                            {
                                "plan_id": self.plan_month.id,
                                "fixed_price": 20,
                                "pricelist_id": self.pricelist.id,
                            }
                        )
                    ],
                }
            )
        )

        # website = self.website.with_user(self.public_user)
        with self.mock_request(user=self.public_user) as request:
            Cart().add_to_cart(
                product_template_id=subscription.product_tmpl_id.id,
                product_id=subscription.id,
                quantity=1,
                plan_id=self.plan_month.id,
            )
            sale_order = request.cart
        self.assertEqual(len(sale_order.order_line), 1)
        self.assertEqual(sale_order.order_line.product_id, subscription)
        self.assertEqual(sale_order.recurring_monthly, 20.0)

    def test_discount_percentage_when_no_unit_base_plan(self):
        """
        Test discounted price value when not having a unit base plan.
        (e.g. the minimum plan is 3 months)
        """

        subscription_product = self._create_product(
            type='service',
            subscription_rule_ids=[
                Command.create({'plan_id': self.plan_3_month.id, 'fixed_price': 30}),
                Command.create({'plan_id': self.plan_6_month.id, 'fixed_price': 55}),
                Command.create({'plan_id': self.plan_year.id, 'fixed_price': 100}),
            ],
        )
        with self.mock_request(website=self.website) as request:
            subscription_product = subscription_product.with_context(website_id=self.website.id)
            info = subscription_product.product_tmpl_id._get_additional_combination_info(
                subscription_product,
                quantity=1,
                uom=self.uom_unit,
                website=self.website,
                pricelist=request.pricelist,
                fiscal_position=request.fiscal_position,
            )
        pricing_data = info['pricings']
        self.assertEqual(pricing_data[0]['discounted_price'], 0, "The base plan should not be discounted")
        self.assertEqual(pricing_data[1]['discounted_price'], 8, "It should be the result of comparing this plan's unit price with\n"
                                                                 "10 -the base plan unit price- not 30 -the fixed price of the base plan")
        self.assertEqual(pricing_data[2]['discounted_price'], 16, "It should be the result of comparing this plan's unit price with\n"
                                                                 "10 -the base plan unit price- not 30 -the fixed price of the base plan")

    def test_shop_price_recurring_with_pricelist_discount(self):
        """On /shop, the pricelist discount must apply to the recurring price.

        The shop tile is rendered while the cart has no plan yet, so the
        recurring price used to be computed with `plan_id=False`. The
        percentage rule then fell back on the product's one-time `list_price`
        (5 -> 4.5) instead of the recurring price (10 -> 9).
        """
        product = self.env['product.template'].create({
            'name': 'One-time + Monthly',
            'recurring_invoice': True,
            'allow_one_time_sale': True,
            'type': 'consu',
            'list_price': 5.0,  # one-time sales price
            'taxes_id': False,
        })
        self.env['product.pricelist.item'].create({
            'plan_id': self.plan_month.id,
            'fixed_price': 10.0,  # recurring price: 10/month (global, no pricelist)
            'product_tmpl_id': product.id,
            'applied_on': '1_product',
            'pricelist_id': False,
        })
        # Advanced pricelist rule: 10% off the monthly recurring price.
        self.pricelist.item_ids = [Command.create({
            'plan_id': self.plan_month.id,
            'applied_on': '1_product',
            'product_tmpl_id': product.id,
            'compute_price': 'discount',
            'price_discount': 10.0,
        })]

        with self.mock_request() as request:
            self.assertEqual(request.pricelist, self.pricelist)
            self.assertFalse(request.cart.plan_id)
            prices = product._get_sales_prices(
                request.pricelist, request.fiscal_position, self.website
            )

        self.assertEqual(prices[product.id]['price_reduce'], 9.0)
