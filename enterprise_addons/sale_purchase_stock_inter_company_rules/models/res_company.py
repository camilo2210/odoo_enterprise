# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    intercompany_sync_delivery_receipt = fields.Boolean(
        string="Synchronize Transfers",
        help="When confirming a Sale or Purchase Order with another company, will try to link the delivery/receipt with its corresponding receipt/delivery in the other company.",
        default=True,
    )
