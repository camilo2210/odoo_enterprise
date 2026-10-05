from odoo import api, fields, models


class OboxQueue(models.TransientModel):
    _name = "obox.queue"
    _inherit = ["pos.load.mixin", "obox.queue"]

    pos_order_id = fields.Many2one('pos.order', string='POS Order', readonly=True)

    @api.model
    def check_job_status(self, job_uuid):
        job = self.search([("uuid", "=", job_uuid)])
        return job.read(self._load_pos_data_fields({}), load=False) if job else False

    @api.model
    def _load_pos_data_fields(self, config):
        return ['result', 'status', 'uuid', 'obox_id', 'retry']

    @api.model
    def _load_pos_data_domain(self, data):
        return False

    def handle_obox_response(self, result):
        # Testing purpose, we should not send a notification for every
        # action result in a real implementation
        self.ensure_one()
        data = super().handle_obox_response(result)

        if self.result:
            pos_config_ids = self.env['pos.config'].search([
                '|', ('preparation_printer_ids.proxy_obox_id', '!=', False),
                ('receipt_printer_ids.proxy_obox_id', '!=', False),
            ])
            payload = {
                'status': self.status,
                'result': self.result,
                'uuid': self.uuid,
            }
            for config in pos_config_ids:
                config._notify('OBOX', payload)

        return data
