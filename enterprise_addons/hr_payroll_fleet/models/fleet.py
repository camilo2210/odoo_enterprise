from odoo import models, fields


class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    can_be_requested = fields.Boolean(
        string="Can be requested", company_dependent=True,
        tracking=True,
        help="Can be requested on a contract as a new vehicle")
    default_car_value = fields.Float(string="Catalog Value (VAT Incl.)", tracking=True)
