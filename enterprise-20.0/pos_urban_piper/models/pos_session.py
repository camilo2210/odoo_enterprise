# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    def get_session_orders(self):
        """Exclude future delivery orders when computing draft orders at session closing"""
        orders = super().get_session_orders()
        return orders.filtered_domain([
            '|', '|',
            ('source', '!=', 'online'),
            ('preset_time', '!=', False),
            ('state', 'not in', ['draft', 'cancel']),
        ])

    @api.model
    def _load_pos_data_models(self, config):
        models = super()._load_pos_data_models(config)
        return models + ['pos.urbanpiper.store', 'urbanpiper.store.aggregator', 'pos.delivery.provider']

    def set_opening_control(self, cashbox_value, notes):
        super().set_opening_control(cashbox_value, notes)
        if self.state == 'opened' and (urbanpiper_store := self.config_id.urbanpiper_store_id):
            # Enable all delivery providers
            urbanpiper_store._change_aggregator_availability(active=True)

    def close_session_from_ui(self, payment_method_closing={}):
        result = super().close_session_from_ui(payment_method_closing)
        if result.get('successful') and (urbanpiper_store := self.config_id.urbanpiper_store_id):
            # Disable all delivery providers
            urbanpiper_store._change_aggregator_availability(active=False)
        return result

    def get_closing_control_data(self):
        data = super().get_closing_control_data()
        urbanpiper_store = self.config_id.urbanpiper_store_id
        if not urbanpiper_store or not data.get('non_cash_payment_methods'):
            return data
        orders = self._get_closed_orders()
        urbanpiper_payment_methods = urbanpiper_store.aggregator_lines.payment_method_id
        existing_non_cash_method_ids = [pm['id'] for pm in data['non_cash_payment_methods']]
        payment_summary_by_method = self.env['pos.payment']._read_group(
            domain=[
                ('pos_order_id', 'in', orders.ids),
                ('payment_method_id', 'in', urbanpiper_payment_methods.ids),
                ('payment_method_id', 'not in', existing_non_cash_method_ids),
            ],
            groupby=['payment_method_id'],
            aggregates=['__count', 'amount:sum'],
        )
        urbanpiper_non_cash_payment_methods = [
            {
                'name': pm.name,
                'amount': amount_sum,
                'number': count,
                'id': pm.id,
                'type': pm.type,
            }
            for pm, count, amount_sum in payment_summary_by_method
        ]
        data['non_cash_payment_methods'].extend(urbanpiper_non_cash_payment_methods)
        return data
