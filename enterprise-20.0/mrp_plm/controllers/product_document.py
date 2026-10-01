# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.product.controllers.product_document import ProductDocumentController


class ProductDocumentControllerECO(ProductDocumentController):
    def is_model_valid(self, res_model):
        return super().is_model_valid(res_model) or res_model == 'mrp.eco'
