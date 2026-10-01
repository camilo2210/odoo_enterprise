# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class WebsiteCheckoutStep(models.Model):
    _inherit = 'website.checkout.step'

    def _validate_completion(self, order_sudo, **kwargs):
        if self.step_href == '/shop/l10n_cl_invoicing_info':
            return self._check_l10n_cl_invoicing_info_completion(order_sudo, **kwargs)
        return super()._validate_completion(order_sudo, **kwargs)

    def _check_l10n_cl_invoicing_info_completion(self, order_sudo, **_kwargs):
        company = self.website_id.company_id
        if (
            company.country_code == 'CL'
            and company.sale_automatic_invoice
            and not order_sudo.partner_invoice_id.l10n_cl_sii_taxpayer_type
        ):
            return '/shop/l10n_cl_invoicing_info'
