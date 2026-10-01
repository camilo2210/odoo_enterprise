# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_rental_stock_picking = fields.Boolean(
        "Rental pickings", implied_group='sale_stock_renting.group_rental_stock_picking'
    )

    def set_values(self):
        rental_group_before = self.default_get(['group_rental_stock_picking']).get(
            'group_rental_stock_picking'
        )
        super().set_values()
        if rental_group_before and not self.group_rental_stock_picking:
            self.env['stock.warehouse'].update_rental_rules()
        elif not rental_group_before and self.group_rental_stock_picking:
            self.env['res.company'].create_missing_rental_location()
            self.env['stock.warehouse'].update_rental_rules()
