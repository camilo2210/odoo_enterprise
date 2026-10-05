# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    platform_order_available = fields.Boolean(
        string="Available for Platform Orders",
        help="If this product is available for platform orders.",
        default=True,
    )

    def write(self, vals):
        """
        Override write to trigger a menu update on relevant platforms
        when a product's availability or price changes.
        """
        res = super().write(vals)

        # Check if any of the fields that require a sync have been modified.
        fields_to_check = ['platform_order_available', 'list_price', 'name', 'description_sale', 'pos_sequence']
        if any(field in vals for field in fields_to_check):
            self._post_update_platform_order_menu_hook()

        return res

    def _post_update_platform_order_menu_hook(self):
        """
        Finds all platform entities affected by this product update and
        triggers their respective menu update methods.

        An entity is considered affected if its linked Point of Sale
        configuration includes the categories of the updated products.
        """
        relevant_configs = self.env['pos.config'].sudo().search([
            '|', ('limit_categories', '=', False),
            ('iface_available_categ_ids', 'in', self.pos_categ_ids.ids)
        ])
        if not relevant_configs:
            return

        stores = self.env['platform.order.entity'].sudo().search([
            ('config_id', 'in', relevant_configs.ids),
            ('menu_sync_state', '=', 'done'),
        ])
        for store in stores:
            # Determine which of the updated products are actually sold by this store.
            store_products = self.filtered(lambda p: p.id in store._get_menu_products().ids)
            # Only call the update method if there are relevant products to send.
            if store_products:
                store._update_platform_order_menu(store_products)
