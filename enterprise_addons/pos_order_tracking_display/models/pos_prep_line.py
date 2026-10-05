from odoo import models


class PosPrepLine(models.Model):
    _inherit = 'pos.prep.line'

    def change_prep_line_stage(self, prep_display_id, direction=1):
        res = super().change_prep_line_stage(prep_display_id, direction)
        self.env['pos.prep.display'].browse(int(prep_display_id))._send_orders_to_customer_display()
        return res
