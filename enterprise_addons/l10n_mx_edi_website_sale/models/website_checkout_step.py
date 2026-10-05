# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class WebsiteCheckoutStep(models.Model):
    _inherit = 'website.checkout.step'

    def _validate_completion(self, order_sudo, **kwargs):
        if self.step_href == '/shop/l10n_mx_invoicing_info':
            return self._check_l10n_mx_invoicing_info_completion(order_sudo, **kwargs)
        return super()._validate_completion(order_sudo, **kwargs)

    def _check_l10n_mx_invoicing_info_completion(self, order_sudo, **_kwargs):
        if self.website_id._require_mx_invoicing_details(order_sudo) and not (
            order_sudo.l10n_mx_edi_cfdi_to_public
            or (
                order_sudo.partner_id.vat
                and order_sudo.partner_id.l10n_mx_edi_fiscal_regime
                and order_sudo.l10n_mx_edi_usage
            )
        ):
            return '/shop/l10n_mx_invoicing_info'
