# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route

from odoo.addons.product.controllers.catalog import ProductCatalogController


class CatalogControllerFieldService(ProductCatalogController):

    @route()
    def product_catalog_get_order_lines_info(self, res_model, order_id, product_ids, **kwargs):
        if intervention_id := kwargs.get('intervention_id'):
            intervention = request.env['planning.slot'].browse(intervention_id)
            if not order_id:
                order_id = intervention.sale_order_id.id

            request.update_context(intervention_id=intervention_id)
            if intervention_company := intervention.company_id:
                request.update_context(allowed_company_ids=intervention_company.ids)

        return super().product_catalog_get_order_lines_info(
            res_model, order_id, product_ids, **kwargs
        )

    @route()
    def product_catalog_update_order_line_info(
        self, res_model, order_id, product_id, quantity=0, uom_id=False, **kwargs
    ):
        # Return additional info for field service flow
        if not (intervention_id := kwargs.get('intervention_id')):
            return super().product_catalog_update_order_line_info(
                res_model, order_id, product_id, quantity, uom_id, **kwargs
            )

        request.update_context(
            child_field=kwargs.get('child_field'),
            intervention_id=intervention_id,
            section_id=kwargs.get('section_id'),
        )
        intervention = request.env['planning.slot'].browse(intervention_id)
        product = request.env['product.product'].browse(product_id)
        wizard, lines = intervention._update_fsm_catalog_quantity(product, quantity)
        return {"action": wizard, **self._get_fsm_catalog_update_info(lines[:1])}

    def _get_fsm_catalog_update_info(self, order_line):
        return {
            "price": order_line.price_unit if order_line else False,
            "subtotal": order_line.price_subtotal if order_line else False,
        }
