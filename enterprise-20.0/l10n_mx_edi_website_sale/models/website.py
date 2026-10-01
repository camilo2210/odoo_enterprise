# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class Website(models.Model):
    _inherit = 'website'

    def _require_mx_invoicing_details(self, order_sudo):  # noqa: ARG002
        """Provide a hook for internal purposes (where cart company != website company)."""
        return self.company_id.country_code == 'MX'

    def _get_breadcrumb_checkout_steps_domain(self, order_sudo):
        domain = super()._get_breadcrumb_checkout_steps_domain(order_sudo)
        if not self._require_mx_invoicing_details(order_sudo):
            domain &= Domain('step_href', '!=', '/shop/l10n_mx_invoicing_info')
        return domain
