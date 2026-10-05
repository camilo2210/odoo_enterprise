# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    preparation_time = fields.Float(
        string="Padding Time",
        help="Temporarily make this product unavailable before pickup.",
        company_dependent=True,
    )

    @api.constrains('rent_periodicity', 'tracking')
    def _lot_not_supported_rental(self):
        for template in self:
            if template.rent_periodicity and template.tracking == 'lot':
                raise ValidationError(
                    template.env._(
                        "Tracking by lots isn't supported for rental products."
                        "\nYou should rather change the tracking mode to unique serial numbers."
                    )
                )

    def _compute_show_qty_status_button(self):
        super()._compute_show_qty_status_button()
        for template in self:
            if template.rent_periodicity and not template.sale_ok:
                template.show_forecasted_qty_status_button = False

    def _get_default_start_delta(self):
        """Override to take the padding time into account."""
        delta = super()._get_default_start_delta()
        if self.rent_periodicity == "hours":
            # Ensure we have enough time to prepare
            delta = max(delta, timedelta(hours=self.preparation_time))
        return delta
