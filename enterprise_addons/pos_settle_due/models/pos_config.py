from odoo import models, api


class PosConfig(models.Model):
    _inherit = 'pos.config'
    _name = 'pos.config'

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if read_records:
            read_records[0]['_pos_settle_due_due_account_move_list_view_id'] = self.env.ref('pos_settle_due.due_account_move_list_view').id
        return read_records
