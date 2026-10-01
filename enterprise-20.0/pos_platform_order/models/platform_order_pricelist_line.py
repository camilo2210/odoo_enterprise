from odoo import api, fields, models
from odoo.exceptions import UserError


class PlatformOrderPricelistLine(models.Model):
    _name = 'platform.order.pricelist.line'
    _description = 'Platform Order Pricelist Line'

    name = fields.Char(string='Name')
    external_key = fields.Char(string='External Key')
    store_id = fields.Many2one('platform.order.entity', string='Store', readonly=True, ondelete='cascade', index='btree_not_null')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, ondelete='restrict')

    @api.constrains('store_id', 'pricelist_id')
    def _check_currency(self):
        for line in self:
            if line.pricelist_id.currency_id != line.store_id.currency_id:
                raise UserError(self.env._("The pricelist currency must match the store currency."))
