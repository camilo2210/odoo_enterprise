from odoo import models


class PosPrepDisplay(models.Model):
    _inherit = 'pos.prep.display'

    def _load_preparation_data_models(self):
        preparation_data_models = super()._load_preparation_data_models()
        preparation_data_models.append('pos.pack.operation.lot')
        return preparation_data_models

    def _get_preparation_display_order_additional_info(self, prep_lines):
        additional_info = super()._get_preparation_display_order_additional_info(prep_lines)
        additional_info['pos.pack.operation.lot'] = prep_lines.pos_order_line_id.pack_lot_ids.read(
            prep_lines.pos_order_line_id.pack_lot_ids._load_pos_preparation_data_fields(), load=False)
        return additional_info
