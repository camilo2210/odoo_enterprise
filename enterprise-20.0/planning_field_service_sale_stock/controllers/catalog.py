# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.planning_field_service_sale_timesheet.controllers.catalog import CatalogControllerFieldService


class CatalogControllerFieldServiceStock(CatalogControllerFieldService):

    def _get_fsm_catalog_update_info(self, order_line):
        return {
            **super()._get_fsm_catalog_update_info(order_line),
            'min_quantity': (
                order_line.product_id.fsm_quantity - order_line.product_id.quantity_decreasable_sum
            )
        }
