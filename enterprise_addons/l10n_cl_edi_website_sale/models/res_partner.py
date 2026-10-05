# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _check_billing_address(self, **kwargs):
        self.ensure_one()
        # In case of 'ticket' l10n_cl_document_type, the invoicing partner is a generic anonymous
        # one that cannot and shouldn't be edited by the customer.
        if self.id == self.env['ir.model.data']._xmlid_to_res_id('l10n_cl.par_cfa'):
            return True
        return super()._check_billing_address(**kwargs)

    def _get_mandatory_billing_address_fields(self, country_sudo, **kwargs):
        mandatory_fields = super()._get_mandatory_billing_address_fields(country_sudo, **kwargs)

        if self.env.company.country_code == country_sudo.code == "CL":
            mandatory_fields.add("vat")

        return mandatory_fields
