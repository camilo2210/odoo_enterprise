from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    manufacturer_product_id = fields.Char(string="NS-PID", compute='_compute_manufacturer_product_id', inverse='_inverse_manufacturer_product_id')

    def _compute_manufacturer_product_id(self):
        for template in self:
            template.manufacturer_product_id = template.product_variant_count == 1 and template.product_variant_id.manufacturer_product_id

    def _inverse_manufacturer_product_id(self):
        for template in self:
            template.product_variant_id.manufacturer_product_id = template.manufacturer_product_id
