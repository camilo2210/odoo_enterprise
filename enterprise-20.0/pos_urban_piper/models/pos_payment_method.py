# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    delivery_provider_id = fields.Many2one(
        'pos.delivery.provider',
        string='Delivery Provider',
        readonly=True,
        help='Responsible delivery provider for online order, e.g., UberEats, Zomato.'
    )
