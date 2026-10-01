from odoo import models


class PosPrepDisplay(models.Model):
    _inherit = "pos.prep.display"

    def _load_preparation_data_models(self):
        res = super()._load_preparation_data_models()
        return res + ['restaurant.table', 'restaurant.order.course', 'restaurant.floor']

    def _get_preparation_display_order_additional_info(self, prep_lines):
        self.ensure_one()
        res = super()._get_preparation_display_order_additional_info(prep_lines)
        pos_orderline_ids = [line['id'] for line in res['pos.order.line']]
        pos_orderlines = self.env['pos.order.line'].browse(pos_orderline_ids)
        res['restaurant.order.course'] = pos_orderlines.course_id.read(pos_orderlines.course_id._load_pos_preparation_data_fields(), load=False)
        return res
