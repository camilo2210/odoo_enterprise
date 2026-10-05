from odoo import api, models


class IrUiView(models.Model):
    _name = 'ir.ui.view'
    _inherit = 'ir.ui.view'

    @api.model
    def _get_xml_ids_to_load(self):
        res = super()._get_xml_ids_to_load()
        res += ['pos_iot_six.pos_six_balance_receipt']
        return res
