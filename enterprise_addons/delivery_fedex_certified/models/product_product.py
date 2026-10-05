from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = "product.product"

    manufacturer_product_id = fields.Char(string="NS-PID")
