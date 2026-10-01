from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_uy_edi_is_non_billable = fields.Boolean(
        string="Non-Billable",
        help="Products with indicator 6 and 7 for EDI.",
    )

    @api.constrains("l10n_uy_edi_is_non_billable", "taxes_id")
    def _l10n_uy_edi_check_non_billable_taxes(self):
        for product in self:
            if product.l10n_uy_edi_is_non_billable and product.taxes_id.filtered(lambda t: t.country_code == "UY"):
                raise ValidationError(product.env._(
                    "A non-billable product cannot have sales taxes. Please remove the taxes from"
                    " product '%(product_name)s' to continue.",
                    product_name=product.display_name,
                ))

    @api.onchange("l10n_uy_edi_is_non_billable")
    def _onchange_l10n_uy_edi_is_non_billable(self):
        if self.l10n_uy_edi_is_non_billable:
            # Only drop the UY taxes, keep taxes belonging to other companies (multi-company).
            self.taxes_id = self.taxes_id.filtered(lambda t: t.country_code != "UY")
