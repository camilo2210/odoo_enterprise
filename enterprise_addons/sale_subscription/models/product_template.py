# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    recurring_invoice = fields.Boolean(
        string="Subscription Product",
        help="If set, confirming a sale order with this product will create a subscription",
    )
    allow_one_time_sale = fields.Boolean(
        string="Accept One-Time",
        help="Define if the subscription product can also be bought as a one-time.",
    )
    allow_prorated_price = fields.Boolean(
        string="Prorated Price",
        help="Define if price must be prorated or not for incomplete periods (upsell, calendar alignment, etc.)",
        compute="_compute_allow_prorated_price",
        store=True,
        readonly=False,
    )

    subscription_rule_ids = fields.One2many(
        comodel_name='product.pricelist.item',
        inverse_name='product_tmpl_id',
        string="Subscription Pricings",
        domain=lambda self: self._domain_subscription_rule_ids(),
        bypass_search_access=True,
        copy=False,
        groups='sales_team.group_sale_salesman',
    )
    display_subscription_pricing = fields.Char(
        string='Display Price', compute='_compute_display_subscription_pricing',
    )

    def write(self, vals):
        if self.env.context.get('import_file') and 'recurring_invoice' in vals:
            confirmed_lines = self._get_confirmed_order_lines()
            updated_product = self.filtered(lambda p: p.recurring_invoice != vals['recurring_invoice'])
            if confirmed_lines and updated_product:
                problematic_products = confirmed_lines.product_template_id & updated_product
                raise UserError(_("You can not change the recurring property of this product because it has been sold already (%s)", ", ".join(problematic_products.mapped('display_name'))))
        res = super().write(vals)
        return res

    @api.model
    def _domain_subscription_rule_ids(self):
        return self._domain_pricelist_rule_ids() & Domain('plan_id', '!=', False)

    @api.depends('recurring_invoice')
    def _compute_show_sales_price_page(self):
        super()._compute_show_sales_price_page()
        for template in self:
            template.show_sales_price_page |= template.recurring_invoice

    @api.model
    def _get_incompatible_types(self):
        return ['recurring_invoice'] + super()._get_incompatible_types()

    @api.onchange('recurring_invoice')
    def _onchange_recurring_invoice(self):
        """
        Raise a warning if the user has checked 'Subscription Product'
        while the product has already been sold.
        In this case, the 'Subscription Product' field is automatically
        unchecked.
        """
        confirmed_lines = self.env['sale.order.line'].search([
            ('product_template_id', 'in', self.ids),
            ('state', '=', 'sale')])
        if confirmed_lines:
            self.recurring_invoice = self._origin.recurring_invoice
            return {'warning': {
                'title': _("Warning"),
                'message': _(
                    "You can not change the recurring property of this product because it has been sold already.")
            }}

    @api.depends('type', 'recurring_invoice', 'invoice_policy')
    def _compute_allow_prorated_price(self):
        for template in self:
            if template.recurring_invoice and template.type == 'service' and template.invoice_policy != 'delivery':
                template.allow_prorated_price = True
            else:
                template.allow_prorated_price = False

    @api.depends('subscription_rule_ids')
    def _compute_display_subscription_pricing(self):
        self.display_subscription_pricing = False
        for template in self:
            template.display_subscription_pricing = template._get_recurring_pricing(
                pricelist=template.env['product.pricelist']
            ).price

    @api.constrains('type', 'combo_ids', 'recurring_invoice')
    def _check_subscription_combo_ids(self):
        for template in self:
            if (
                template.type == 'combo'
                and template.recurring_invoice
                and any(
                    not product.recurring_invoice
                    for product in template.combo_ids.combo_item_ids.product_id
                )
            ):
                raise ValidationError(
                    _("A subscription combo product can only contain subscription products.")
                )

    @api.model
    def _get_configurator_price(
        self, product_or_template, quantity, date, currency, pricelist, *, plan_id=None, **kwargs
    ):
        """Override of `sale` to compute the subscription price.

        :param product.product|product.template product_or_template: The product for which to get
            the price.
        :param int quantity: The quantity of the product.
        :param datetime date: The date to use to compute the price.
        :param res.currency currency: The currency to use to compute the price.
        :param product.pricelist pricelist: The pricelist to use to compute the price.
        :param int|None plan_id: The subscription plan of the product, as a `sale.subscription.plan`
            id.
        :param dict kwargs: Locally unused data passed to `super`.
        :rtype: float
        :return: The specified product's price.
        """
        # When no plan is selected and the user opted for a one time purchase on the website, skip recurring pricing.
        # allow_one_time_sale is passed via kwargs from the website add-to-cart request and is only relevant for this one time purchase case.
        if product_or_template.recurring_invoice and not plan_id and not (kwargs.get('allow_one_time_sale') and product_or_template.allow_one_time_sale):
            if product_or_template.is_product_variant:
                template, variant = product_or_template.product_tmpl_id, product_or_template
            else:
                template, variant = product_or_template, None

            # get the default pricing and plan since the plan has not yet been chosen
            pricing = template._get_recurring_pricing(
                pricelist=pricelist, variant=variant, quantity=quantity,
            )
            if pricing:
                return (
                    pricing._compute_price(
                        product_or_template,
                        quantity,
                        uom=product_or_template.uom_id,
                        date=date,
                        currency=currency,
                    ),
                    pricing.id
                )

        return super()._get_configurator_price(
            product_or_template, quantity, date, currency, pricelist, plan_id=plan_id, **kwargs
        )

    @api.model
    def _get_additional_configurator_data(
        self, product_or_template, date, currency, pricelist, *, quantity=1.0, plan_id=None, **kwargs
    ):
        """Override of `sale` to append subscription data.

        :param product.product|product.template product_or_template: The product for which to get
            additional data.
        :param datetime date: The date to use to compute prices.
        :param res.currency currency: The currency to use to compute prices.
        :param product.pricelist pricelist: The pricelist to use to compute prices.
        :param int|None plan_id: The subscription plan of the product, as a `sale.subscription.plan`
            id.
        :param dict kwargs: Locally unused data passed to `super`.
        :rtype: dict
        :return: A dict containing additional data about the specified product.
        """
        data = super()._get_additional_configurator_data(
            product_or_template, date, currency, pricelist, plan_id=plan_id, **kwargs
        )

        # If the user chooses one time purchase on the website, return data without
        # the recurring price label since this product is being sold as a one time purchase.
        if kwargs.get('allow_one_time_sale') and product_or_template.allow_one_time_sale:
            return data

        if product_or_template.recurring_invoice:
            if product_or_template.is_product_variant:
                template, variant = product_or_template.product_tmpl_id, product_or_template
            else:
                template, variant = product_or_template, None

            pricing = template._get_recurring_pricing(
                pricelist=pricelist, variant=variant, plan_id=plan_id, quantity=quantity,
            )
            if pricing:
                data['price_info'] = pricing.plan_id.sudo().billing_period_display_sentence

            pricings = template._get_recurring_pricings(pricelist=pricelist, variant=variant, quantity=quantity)
            data['subscription_plans'] = [
                {
                    'id': p.plan_id.id,
                    'display_name': p.plan_id.sudo().name,
                }
                for p in pricings
            ]

        return data

    def _get_recurring_pricing(self, pricelist, variant=None, plan_id=None, quantity=1.0):
        self.ensure_one()
        product_or_template = variant or self
        domain = pricelist._get_applicable_rules_domain(
            products=product_or_template,
            date=fields.Datetime.now(),
            plan_id=plan_id,
            quantity=quantity,
            # If no plan is given, return the first one with a plan, to be used as default pricing
            any_plan=True,
        )
        order = self.env['product.pricelist.item']._get_recurring_rules_order()
        pricing = self.env['product.pricelist.item'].search(domain, order=order).filtered(
            lambda ppi: ppi._is_applicable_for(
                product=product_or_template,
                # No need for uom conversion since multi-uom is not supported for recurring
                # products atm.
                quantity=quantity,
            )
        )[:1]

        if pricing or not pricelist:
            return pricing

        # If the current pricelist has no recurring rules, the recurring price (and plans) will be
        # decided by the recurring rules not linked to a specific pricelist.
        domain = self.env['product.pricelist']._get_applicable_rules_domain(
            products=variant or self,
            date=fields.Datetime.now(),
            quantity=quantity,
            plan_id=plan_id,
            # If no plan is given, return the first one with a plan, to be used as default pricing
            any_plan=True,
        )
        return self.env['product.pricelist.item'].search(domain, order=order).filtered(
            lambda ppi: ppi._is_applicable_for(
                product=product_or_template,
                # No need for uom conversion since multi-uom is not supported for recurring
                # products atm.
                quantity=quantity,
            )
        )[:1]

    def _get_recurring_pricings(self, pricelist, variant=None, quantity=1.0):
        """Return the first pricing applicable for each of the available subscription plans."""
        self.ensure_one()

        pricings = self.env['product.pricelist.item']
        domain = pricelist._get_applicable_rules_domain(
            products=variant or self,
            date=fields.Datetime.now(),
            quantity=quantity,
            any_plan=True,
        )

        all_pricings = self.env['product.pricelist.item'].search(
            domain, order=self.env['product.pricelist.item']._get_recurring_rules_order()
        )
        if pricelist:
            # Add the rules not restricted to a specific pricelist, only for the plans that had no
            # rule for the current pricelist.
            domain = self.env['product.pricelist']._get_applicable_rules_domain(
                products=variant or self,
                date=fields.Datetime.now(),
                quantity=quantity,
                any_plan=True,
            )
            all_pricings |= self.env['product.pricelist.item'].search(
                Domain.AND([domain, [('plan_id', 'not in', all_pricings.plan_id.ids)]]),
                order=self.env['product.pricelist.item']._get_recurring_rules_order()
            )

        found_plan_ids = set()
        for pricing in all_pricings:
            if (
                pricing.plan_id.sudo().active
                and (plan_id := pricing.plan_id.id) not in found_plan_ids
                # No need for uom conversion since multi-uom is not supported for recurring
                # products atm.
                and pricing._is_applicable_for(product=variant or self, quantity=quantity)
            ):
                found_plan_ids.add(plan_id)
                pricings |= pricing

        return pricings

    def _has_multiple_uoms(self):
        # multi-uoms doesn't work with subscription (for now)
        if self.recurring_invoice:
            return False
        return super()._has_multiple_uoms()

    def _prepare_invoicing_tooltip(self):
        if self.recurring_invoice:
            if self.invoice_policy == 'delivery':
                return self.env._("Recurring order with this product will be invoiced at the end of the period.")
            elif self.invoice_policy == 'order':
                return self.env._("Recurring order with this product will be invoiced at the beginning of the period.")
        return super()._prepare_invoicing_tooltip()

    def _get_confirmed_order_lines(self):
        return self.env['sale.order.line'].search([
            ('product_template_id', 'in', self.ids),
            ('state', '=', 'sale')
        ])
