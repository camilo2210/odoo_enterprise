# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosPreset(models.Model):
    _inherit = 'pos.preset'

    whatsapp_receipt_template_id = fields.Many2one(
        comodel_name='whatsapp.template',
        string="WhatsApp Receipt template",
        domain=[('model', '=', 'pos.order'), ('status', '=', 'approved')],
        help="WhatsApp template used to send the order receipt to the customer after a successful self order.",
    )

    @api.model
    def _load_pos_self_data_fields(self, config):
        return super()._load_pos_self_data_fields(config) + ['whatsapp_receipt_template_id']
