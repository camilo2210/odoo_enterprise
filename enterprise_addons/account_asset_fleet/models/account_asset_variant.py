# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountAssetVariant(models.Model):
    _inherit = 'account.asset.variant'

    vehicle_id = fields.Many2one(related='asset_id.vehicle_id')
