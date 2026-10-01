from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_field_service_allow_maintenance_contract = fields.Boolean(
        'Maintenance Contracts',
        implied_group='planning_field_service_stock_subscription.group_field_service_allow_maintenance_contract',
        help='Track whether customer equipment is covered by a maintenance contract via subscriptions',
    )

    @api.onchange('group_field_service_allow_equipment')
    def _onchange_group_field_service_allow_equipment(self):
        super()._onchange_group_field_service_allow_equipment()
        if not self.group_field_service_allow_equipment:
            self.group_field_service_allow_maintenance_contract = False
