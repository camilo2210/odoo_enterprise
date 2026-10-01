# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.const import REPORT_REASONS_MAPPING


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    @api.model
    def _is_tokenization_required(self, *, sale_order_id=None, **kwargs):
        """ Override of `payment` to force tokenization when paying for a subscription.

        :param int sale_order_id: The sales order to be paid, as a `sale.order` id.
        :return: Whether tokenization is required.
        :rtype: bool
        """
        if sale_order_id:
            sale_order = self.env['sale.order'].browse(sale_order_id).exists()
            if (sale_order.is_subscription or sale_order.subscription_id.is_subscription) and \
                    not kwargs.get('show_non_tokenize_provider'):
                return True
        return super()._is_tokenization_required(sale_order_id=sale_order_id, **kwargs)

    @api.model
    def _find_available_providers(
        self, *args, sale_order_id=None, website_id=None, report=None, **kwargs
    ):
        """Override of payment to exclude manually captured providers and providers whose minimum
        or maximum amount constraints are not met by the sales order total.

        :param int sale_order_id: The sale order to be paid, if any, as a `sale.order` id
        :param int website_id: The website on which the order is placed, if any, as a `website` id.
        :param dict report: The availability report.
        :return: The available providers
        :rtype: recordset of `payment.provider`
        """
        available_providers = super()._find_available_providers(
            *args, sale_order_id=sale_order_id, website_id=website_id, report=report, show_non_tokenize_provider=True, **kwargs
        )
        if sale_order_id:
            sale_order = self.env['sale.order'].browse(sale_order_id).exists()
            if sale_order.is_subscription or sale_order.subscription_id.is_subscription:
                manual_capture_providers = available_providers.filtered("capture_manually")
                available_providers -= manual_capture_providers
                payment_utils.add_to_report(
                    report,
                    manual_capture_providers,
                    available=False,
                    reason=REPORT_REASONS_MAPPING['manual_capture_not_supported'],
                )

                # This additional check for minimum and maximum amounts is necessary because,
                # without it, the minimum_amount and maximum_amount constraints on the payment
                # provider can be bypassed. For example, a user could navigate to a subscription and
                # click "Set Payment Method," causing the subscription to be charged using the
                # token regardless of the limits defined on the payment provider.
                unfiltered_providers = available_providers
                available_providers = available_providers.filtered(
                    lambda p: (
                        not p.minimum_amount
                        or p.main_currency_id.compare_amounts(
                            sale_order.amount_total, p.minimum_amount
                        )
                        == 1
                    )
                    and (
                        not p.maximum_amount
                        or p.main_currency_id.compare_amounts(
                            sale_order.amount_total, p.maximum_amount
                        )
                        == -1
                    )
                )
                payment_utils.add_to_report(
                    report,
                    unfiltered_providers - available_providers,
                    available=False,
                    reason=REPORT_REASONS_MAPPING['exceed_min_or_max_amount'],
                )
        return available_providers

    def _find_available_tokens(self, partner_id, *, is_subscription=False, **kwargs):
        """Override of `payment` to include the tokens of the commercial partner's children.

        :param int partner_id: The partner making the payment, as a `res.partner` id
        :param bool is_subscription: Whether the order is a subscription
        :return: The available tokens
        :rtype: payment.token
        """
        if not is_subscription:
            return super()._find_available_tokens(
                partner_id, is_subscription=is_subscription, **kwargs
            )

        partner = self.env['res.partner'].browse(partner_id)
        return self.env['payment.token'].sudo().search([
            ('provider_id', 'in', self.ids),
            ('partner_id', 'child_of', partner.commercial_partner_id.id),
        ])  # In sudo mode to read fields of the children of the commercial partner
