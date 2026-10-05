# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    intercompany_sync_delivery_receipt = fields.Boolean(
        related='company_id.intercompany_sync_delivery_receipt',
        string="Synchronize Transfers",
        readonly=False,
    )
