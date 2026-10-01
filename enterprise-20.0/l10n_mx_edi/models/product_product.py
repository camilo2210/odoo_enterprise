from odoo import models
from odoo.fields import Domain


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _l10n_mx_edi_get_bill_retrieval_product_search_plan(self):
        return [
            (11, self._l10n_mx_edi_import_retrieve_product_from_variant_seller_product_code),
            (16, self._l10n_mx_edi_import_retrieve_product_from_variant_seller_product_name),
        ]

    def _l10n_mx_edi_import_retrieve_product_from_variant_seller_product_code(self, product_values):
        if not product_values.get('default_code'):
            return
        seller_domain = Domain('product_code', '=', product_values['default_code'])
        if product_values.get('partner_id'):
            seller_domain &= Domain('partner_id', '=', product_values['partner_id'])

        return {'criteria': [{'domain': Domain('variant_seller_ids', 'any', seller_domain)}]}

    def _l10n_mx_edi_import_retrieve_product_from_variant_seller_product_name(self, product_values):
        if not product_values.get('name'):
            return
        seller_domain = Domain('product_name', 'ilike', product_values['name'])
        if product_values.get('partner_id'):
            seller_domain &= Domain('partner_id', '=', product_values['partner_id'])

        return {'criteria': [{'domain': Domain('variant_seller_ids', 'any', seller_domain)}]}
