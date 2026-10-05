# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    urbanpiper_tax_liability = fields.Selection(
        string='UrbanPiper Tax Liability',
        selection=[
            ('aggregator', 'Aggregator'),
            ('merchant', 'Merchant')
        ],
        readonly=True,
        help="Indicates whether the aggregator or the merchant is responsible for paying taxes for this online delivery order line."
    )
