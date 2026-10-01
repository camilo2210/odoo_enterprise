from odoo import api, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.onchange('group_stock_production_lot')
    def _onchange_group_stock_production_lot(self):
        super()._onchange_group_stock_production_lot()
        if not self.group_stock_production_lot:
            self.group_field_service_allow_equipment = False

    @api.onchange('group_field_service_allow_equipment')
    def _onchange_group_field_service_allow_equipment(self):
        if self.group_field_service_allow_equipment:
            self.group_stock_production_lot = True

    def set_values(self):
        super().set_values()
        if self.group_field_service_allow_equipment:
            slots = self.env['planning.slot'].search([('partner_id', '!=', False), ('lot_ids', '=', False), ('state', '=', '1_draft')])
            slots._compute_lot_ids()
