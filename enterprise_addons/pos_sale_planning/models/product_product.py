from odoo import api, models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_tax_product = fields.Boolean(string="Is a tax product", readonly=True)

    @api.model
    def _get_pos_product_for_account(self, account_id):
        """ In POS, we want to link the tax to a product, in order to be able to display it on the receipt.
        So we need to find a product that has the same tax as the one of the order line.
        """
        product = self.search([
            ('property_account_income_id', '=', account_id.id),
            ('is_tax_product', '=', True)
        ], limit=1)
        if not product:
            # If no product is found, we create one.
            # The product is created with the good property_account_income_id.
            product_name = self.env._('PoS Miscellaneous (%(account_name)s)', account_name=account_id.name)
            product = self.create([{
                'name': product_name,
                'type': 'service',
                'is_tax_product': True,
                'taxes_id': [],
                'property_account_income_id': account_id.id,
            }])
        return product or None
