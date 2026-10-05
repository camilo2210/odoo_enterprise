from odoo import api, models


class IrUiView(models.Model):
    _name = 'ir.ui.view'
    _inherit = ['ir.ui.view', 'pos.load.mixin']

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return [('key', 'in', self._get_enterprise_xml_ids_to_load())]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['key']

    @api.model
    def _load_pos_preparation_data_read(self, data):
        read_records = super()._load_pos_preparation_data_read(data)

        for key in self._get_enterprise_xml_ids_to_load():
            read_records.append({
                'key': key,
                '_template': self.env['ir.qweb']._get_template(key)[1],
            })

        return read_records

    @api.model
    def _get_enterprise_xml_ids_to_load(self):
        return [
            'point_of_sale.pos_order_receipt_style',
            'pos_enterprise.pos_order_change_receipt',
            'point_of_sale.pos_order_change_receipt_line',
        ]
