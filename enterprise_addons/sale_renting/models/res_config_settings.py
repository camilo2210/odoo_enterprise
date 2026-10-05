# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_sale_management_renting = fields.Boolean()
    rental_resource_calendar_id = fields.Many2one(
        related="company_id.rental_resource_calendar_id", readonly=False
    )
