# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    quality_check_count = fields.Integer(
        related='partner_id.quality_check_count', groups='quality.group_quality_user')
    quality_rate = fields.Float(
        related='partner_id.quality_rate', groups='quality.group_quality_user')

    def action_see_quality_rate(self):
        self.ensure_one()
        return self.partner_id.action_see_quality_rate()
