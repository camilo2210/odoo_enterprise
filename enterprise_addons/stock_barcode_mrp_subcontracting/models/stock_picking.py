#  Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _subcontracted_produce(self, subcontract_details):
        if self.env.context.get('keep_subcontract_production'):
            subcontract_details = [(move, bom) for move, bom in subcontract_details if not move.move_orig_ids.production_id]
        return super()._subcontracted_produce(subcontract_details)
