# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.fields import Domain


class PlanningSlot(models.Model):
    _inherit = "planning.slot"

    def action_view_material(self):
        res = super().action_view_material()
        res['domain'] = Domain.AND([res['domain'], ['|', ('recurring_invoice', '=', False), ('allow_one_time_sale', '=', True)]])
        return res
