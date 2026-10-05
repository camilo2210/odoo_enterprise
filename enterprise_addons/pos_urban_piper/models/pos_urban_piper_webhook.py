# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PosUrbanPiperWebhook(models.Model):
    _name = 'pos.urban.piper.webhook'
    _description = 'UrbanPiper Webhook'

    webhook_id = fields.Char(string='UrbanPiper Webhook ID', copy=False, readonly=True)
    webhook_url = fields.Char(string='UrbanPiper Webhook URL', copy=False, readonly=True)
    event_name = fields.Char(string='UrbanPiper Event Name', copy=False, readonly=True)
    store_id = fields.Many2one('pos.urbanpiper.store', string='UrbanPiper Store', readonly=True, required=True)
