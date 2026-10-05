from odoo import models
from odoo.fields import Domain


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def action_fsm_add_product_from_barcode(self, barcode):
        self.ensure_one()

        materials_domain = self._get_available_product_materials_domain()
        product = self.env['product.product'].search(
            materials_domain & Domain('barcode', '=', barcode), limit=1,
        )
        added_qty = 1.0
        if not product:
            packaging = self.env['product.uom'].search([
                ('barcode', '=', barcode),
                ('product_id', 'any', materials_domain),
            ], limit=1)
            if packaging:
                product = packaging.product_id
                added_qty = packaging.uom_id._compute_quantity(1, product.uom_id)
        if not product:
            return {
                'type': 'warning',
                'message': self.env._('No product matches the barcode %s.', barcode),
            }

        old_quantity, old_subtotal = self._get_fsm_catalog_quantity_and_subtotal(product)
        result, lines = self._update_fsm_catalog_quantity(product, added_qty + old_quantity)
        if not result:
            return {
                'type': 'warning',
                'message': self.env._("You can't edit this product in the catalog."),
            }

        new_quantity, new_subtotal = self._get_fsm_catalog_quantity_and_subtotal(product, lines=lines)
        if isinstance(result, dict):
            return {
                'action': result,
                'product_id': product.id,
                'quantity': new_quantity,
            }

        return {
            **self._prepare_fsm_barcode_notification(product, new_quantity),
            'subtotal_delta': new_subtotal - old_subtotal,
        }

    def get_fsm_barcode_notification(self, product_id):
        self.ensure_one()
        product = self.env['product.product'].browse(product_id)
        quantity, _subtotal = self._get_fsm_catalog_quantity_and_subtotal(product)
        return self._prepare_fsm_barcode_notification(product, quantity)

    def _prepare_fsm_barcode_notification(self, product, quantity):
        return {
            'type': 'success',
            'product_id': product.id,
            'quantity': quantity,
            'message': self.env._(
                '[%(name)s] quantity updated to %(quantity)g', name=product.display_name, quantity=quantity,
            ),
        }

    def _get_fsm_catalog_quantity_and_subtotal(self, product, lines=None):
        lines = self._get_fsm_catalog_lines(product) if lines is None else lines
        data = lines._get_product_catalog_lines_data(self.sale_order_id.sudo()) if lines else {}
        return data.get('quantity', 0), data.get('subtotal', 0)
