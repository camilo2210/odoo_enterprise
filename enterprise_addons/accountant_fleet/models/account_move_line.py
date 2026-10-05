from odoo import models
from odoo.tools import SQL


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _predictive_field_getter(self):
        getters = super()._predictive_field_getter()
        getters.append(('vehicle_id', self.env['fleet.vehicle'].browse, SQL("vehicle_id")))
        return getters
