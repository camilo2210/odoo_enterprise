# Part of Odoo. See LICENSE file for full copyright and licensing details.

import contextlib
import logging
import psycopg2

from odoo import SUPERUSER_ID, api, fields, models
from odoo.modules.registry import Registry

from ..utils.urbanpiper_connector import UrbanPiperConnector

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _default_payment_methods(self):
        """
        Override default payment methods to filter out delivery payment methods.
        """
        return super()._default_payment_methods().filtered(lambda pm: not pm.delivery_provider_id)

    urbanpiper_store_id = fields.Many2one(
        'pos.urbanpiper.store',
        string='UrbanPiper Store',
        check_company=True,
        help="UrbanPiper store linked to this point of sale for handling online delivery orders"
    )

    _urbanpiper_store_uniq = models.Constraint(
        'unique(urbanpiper_store_id)',
        'A food delivery store cannot be linked to more than one Point of Sale. Please assign a unique PoS to each store.',
    )

    def write(self, vals):
        product_packaging = self.env.ref('pos_urban_piper.product_packaging_charges', False)
        product_delivery = self.env.ref('pos_urban_piper.product_delivery_charges', False)
        product_other_charges = self.env.ref('pos_urban_piper.product_other_charges', False)
        if vals.get('module_pos_urban_piper'):
            if product_packaging and not product_packaging.product_tmpl_id.active:
                product_packaging.product_tmpl_id.active = True
            if product_delivery and not product_delivery.product_tmpl_id.active:
                product_delivery.product_tmpl_id.active = True
            if product_other_charges and not product_other_charges.product_tmpl_id.active:
                product_other_charges.product_tmpl_id.active = True
        if 'module_pos_urban_piper' in vals and not vals['module_pos_urban_piper']:
            vals['urbanpiper_store_id'] = False
        return super().write(vals)

    @api.model
    def _trigger_webhooks_refresh_cron(self):
        """
        This method must be triggered via a manual cron job to refresh the
        webhooks registered with UrbanPiper.

        NOTE: Don't use it directly in code
        """
        configs = self.env['pos.config'].search([
            ('module_pos_urban_piper', '=', True),
            ('urbanpiper_store_id', '!=', False),
            ('urbanpiper_store_id.is_webhook_register', '=', False),
        ])
        for store in configs.urbanpiper_store_id:
            UrbanPiperConnector(store).post_webhooks()

    def _notify_delivery_order(self, order_id=None):
        """
        Notify UrbanPiper delivery order to pos ui
        """
        self.ensure_one()
        if self.current_session_id:
            self._notify('URBANPIPER_DELIVERY_ORDER', order_id)

    @api.model
    def process_urbanpiper_store_action(self, data, urbanpiper_store):
        """
        # UrbanPiper Webhook Handler
        Send UrbanPiper store status updates (e.g., delivery aggregator enable/disable) to the POS UI.
        """
        if not urbanpiper_store.config_id:
            _logger.warning('UrbanPiper: No PoS config linked to store %s for processing store action', urbanpiper_store.name)
            return
        if urbanpiper_store.config_id.current_session_id:
            urbanpiper_store.config_id._notify('STORE_ACTION', data)

    def get_urbanpiper_order_data(self):
        """
        Fetch UrbanPiper delivery order counts for the POS UI.
        """
        self.ensure_one()
        delivery_order_count = self._get_urbanpiper_order_count()
        total_new_order = sum(
            provider_data.get('awaiting', 0)
            for provider_data in delivery_order_count.values()
        )
        return {
            'delivery_order_count': delivery_order_count,
            'total_new_order': total_new_order,
        }

    def _get_urbanpiper_order_count(self):
        """
        Compute the order status counts (awaiting, preparing, done) for each
        UrbanPiper delivery aggregators in the current session.
        """
        self.ensure_one()
        if not self.current_session_id:
            return {}
        order_count_data = {}
        status_map = {
            'placed': 'awaiting',
            'acknowledged': 'preparing',
            'food_ready': 'done',
            'dispatched': 'done',
            'completed': 'done',
        }
        for provider_name, delivery_status, count in self.env['pos.order']._read_group(
            domain=[
                ('source', '=', 'online'),
                ('session_id', '=', self.current_session_id.id),
                ('state', '!=', 'cancel'),
                ('delivery_status', '!=', 'cancelled'),
            ],
            groupby=['delivery_provider_id.technical_name', 'delivery_status'],
            aggregates=['__count'],
        ):
            order_count_data.setdefault(provider_name, {})
            order_count_data[provider_name][status_map[delivery_status]] = order_count_data[provider_name].get(status_map[delivery_status], 0) + count
        return order_count_data

    def get_urbanpiper_special_products(self):
        return [
            self.env.ref("pos_urban_piper.product_other_charges", raise_if_not_found=False),
            self.env.ref("pos_urban_piper.product_delivery_charges", raise_if_not_found=False),
            self.env.ref("pos_urban_piper.product_packaging_charges", raise_if_not_found=False),
        ]

    @api.model
    def log_urbanpiper(self, message, title, log_type='warning', **kwargs):
        # terminal logging
        logger = _logger.warning if log_type == 'warning' else _logger.info
        logger('UrbanPiper : ' + message)
        # log_xml - ir.logging
        if not kwargs.get('log_xml', True):
            return
        db_name = self.env.cr.dbname
        with contextlib.suppress(psycopg2.Error), Registry(db_name).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['ir.logging'].sudo().create({
                'name': title,
                'type': 'server',
                'dbname': db_name,
                'level': 'DEBUG',
                'message': message,
                'path': 'UrbanPiper',
                'func': kwargs.get('func', ''),
                'line': 1,
            })
