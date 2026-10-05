from odoo import api, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    @api.model
    def default_get(self, fields):
        vals = super().default_get(fields)

        if default_name := self.env.context.get('default_name'):
            vals['license_plate'] = default_name

        return vals
