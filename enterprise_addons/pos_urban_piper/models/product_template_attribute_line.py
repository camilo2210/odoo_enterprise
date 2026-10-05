# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplateAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    urbanpiper_min_qty = fields.Integer(
        string="UrbanPiper Min Qty",
        default=0,
        help="Minimum quantity allowed for product modifier on UrbanPiper (0 = no limit). To configure, the Attribute's display type should be Multi-checkbox"
    )
    urbanpiper_max_qty = fields.Integer(
        string="UrbanPiper Max Qty",
        default=-1,
        help="Maximum quantity allowed for product modifier on UrbanPiper (-1 = no limit). To configure, the Attribute's display type should be Multi-checkbox"
    )
    display_type = fields.Selection(related='attribute_id.display_type')
    is_urbanpiper_multi_modifiers = fields.Boolean(
        string="UrbanPiper Multi-Modifiers",
        help="Enable or disable support for multiple modifiers in UrbanPiper."
    )

    @api.constrains('urbanpiper_min_qty', 'urbanpiper_max_qty')
    def _check_urbanpiper_min_max_qty(self):
        for record in self:
            if record.urbanpiper_min_qty < 0:
                raise ValidationError(_("Minimum quantity cannot be less than 0"))

            if record.urbanpiper_max_qty != -1 and record.urbanpiper_min_qty > record.urbanpiper_max_qty:
                raise ValidationError(_("Minimum quantity cannot be greater than maximum quantity."))
