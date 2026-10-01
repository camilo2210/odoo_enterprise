from odoo import models


class PosPrepDisplay(models.Model):
    _inherit = 'pos.prep.display'

    def get_preparation_display_orders_domain(self):
        domain = super().get_preparation_display_orders_domain()
        domain.append(('prep_order_id.pos_order_id.delivery_status', 'in', (False, 'acknowledged', 'food_ready', 'cancelled')))
        return domain

    def _load_preparation_data_models(self):
        res = super()._load_preparation_data_models()
        return res + ['pos.delivery.provider']

    def _get_preparation_display_order_additional_info(self, prep_lines):
        self.ensure_one()
        res = super()._get_preparation_display_order_additional_info(prep_lines)
        pos_order_ids = [order['id'] for order in res['pos.order']]
        pos_orders = self.env['pos.order'].browse(pos_order_ids)
        providers = pos_orders.delivery_provider_id
        res['pos.delivery.provider'] = providers.read(providers._load_pos_preparation_data_fields(), load=False)
        return res
