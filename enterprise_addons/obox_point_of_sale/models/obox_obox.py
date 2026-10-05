# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class OboxObox(models.Model):
    _name = 'obox.obox'
    _inherit = ['pos.load.mixin', 'obox.obox']

    @api.model
    def _load_pos_data_fields(self, config):
        return ['serial_number', 'name', 'local_ip']

    @api.model
    def _load_pos_data_domain(self, data):
        return [('id', 'in', data['pos.printer'].proxy_obox_id.ids)]

    def create_job(self, payload):
        self.ensure_one()
        job = self.env['obox.queue'].sudo().create({
            'obox_id': self.id,
            'payload': payload,
        })
        return [job.uuid]
