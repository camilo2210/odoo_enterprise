# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class Website(models.Model):
    _inherit = 'website'

    def _get_breadcrumb_checkout_steps_domain(self, order_sudo):
        domain = super()._get_breadcrumb_checkout_steps_domain(order_sudo)
        if not (self.company_id.country_code == 'CL' and self.company_id.sale_automatic_invoice):
            domain &= Domain('step_href', '!=', '/shop/l10n_cl_invoicing_info')
        return domain
