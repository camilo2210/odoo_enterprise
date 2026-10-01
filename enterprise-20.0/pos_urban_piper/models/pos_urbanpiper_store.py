# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import BinaryBytes, consteq, file_open

from ..utils.urbanpiper_connector import UrbanPiperConnector

logger = logging.getLogger(__name__)


class PosUrbanPiperStore(models.Model):
    _name = 'pos.urbanpiper.store'
    _description = 'PoS UrbanPiper Store'
    _inherit = ['pos.load.mixin', 'mail.thread']

    def _default_tax_type(self):
        """
        Default tax type that determines whether prices should be synced as tax-inclusive or tax-exclusive.
        NOTE: Currently, for brands outside India, prices must be synced explicitly as tax-inclusive.
        """
        return 'total_included'

    def _default_urbanpiper_credentials(self, field_name='urbanpiper_username'):
        """
        Return the value of the most recently created UrbanPiper credential.

        :param str field_name: Credential field to fetch.
            Supported values are `urbanpiper_apikey` and `urbanpiper_username`.
        :return: Credential value if found, otherwise `False`.
        """
        store = self.sudo().search_read(
            [
                *self._check_company_domain(self.env.company),
                ('urbanpiper_username', '!=', False),
                ('urbanpiper_apikey', '!=', False),
            ],
            [field_name],
            limit=1,
        )
        return store[0].get(field_name) if store else False

    def _default_store_timings(self):
        return [{'weekday': day} for day in
            ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']]

    def _default_preset_id(self):
        """Return the 'Online Delivery' preset as default if available."""
        return (
            self.env.ref('pos_urban_piper.pos_online_preset', raise_if_not_found=False)
            or self.env['pos.preset'].search([('identification', '=', 'online')], limit=1)
        )

    def _default_order_notification_sound(self):
        audio_url = 'point_of_sale/static/src/sounds/order-receive-tone.mp3'
        try:
            with file_open(audio_url, 'rb') as audio_file:
                return BinaryBytes(audio_file.read())
        except (FileNotFoundError, ValueError):
            logger.exception('UrbanPiper: Failed to load local default audio %s', audio_url)
            return False

    def _pos_config_domain(self):
        """Return the domain restricting selectable PoS config for the UrbanPiper store."""
        return Domain('urbanpiper_store_id', '=', False)

    name = fields.Char('Name', translate=True, required=True)
    config_id = fields.Many2one(
        'pos.config',
        string='Point of Sale',
        domain=lambda self: self._pos_config_domain(),
        copy=False,
        tracking=True,
        compute='_compute_config_id',
        inverse='_inverse_config_id',
        check_company=True,
        help="Point of Sale used to manage online food delivery orders for this UrbanPiper store."
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        index=True
    )
    city = fields.Char('City', default=lambda self: self.env.company.city, required=True)
    country_id = fields.Many2one(related='company_id.country_id')
    country_code = fields.Char(related='company_id.country_code')
    tax_type = fields.Selection(
        string='Tax Type',
        selection=[
            ('total_included', 'Inclusive'),
            ('total_excluded', 'Exclusive')
        ],
        default=_default_tax_type,
        tracking=True,
        help=(
            "Specify whether taxes are included in the price or added separately for UrbanPiper orders.\n"
            "- Inclusive: Tax collection by Merchant\n"
            "- Exclusive: Tax collection by Aggregator"
        ),
    )
    store_identifier = fields.Char(
        string='POS Store ID',
        default=lambda self: secrets.token_hex(),
        copy=False,
        required=True,
        tracking=True,
        help="Unique POS store ID for UrbanPiper (Atlas) integration."
    )
    preset_id = fields.Many2one(
        'pos.preset',
        string='Preset',
        domain=[('identification', '=', 'online')],
        default=_default_preset_id,
        index='btree_not_null',
        help=(
            "Preset used for food delivery orders.\n"
            "The following properties are applied from the preset:\n"
            " - Pricelist (used as the store's global pricelist)\n"
            " - Fiscal Position\n"
            " - Schedule (store timings)\n"
        ),
    )
    pricelist_id = fields.Many2one(related='preset_id.pricelist_id')
    aggregator_lines = fields.One2many(
        'urbanpiper.store.aggregator',
        'store_id',
        string='Store Aggregators',
        help="Delivery aggregators and their configurations for online orders."
    )
    delivery_provider_ids = fields.Many2many(
        'pos.delivery.provider',
        compute='_compute_delivery_providers',
        string='Aggregators',
        help="Delivery providers associated with this UrbanPiper store.",
    )
    order_notification_sound = fields.Binary(
        string='Order Notification Sound',
        default=_default_order_notification_sound,
        help="Custom MP3 sound to play when a new online delivery order is received."
    )
    order_notification_filename = fields.Char('Filename for Order Notification Sound', default='order-receive-tone.mp3')
    urbanpiper_username = fields.Char(
        string='Username',
        default=_default_urbanpiper_credentials,
        required=True,
        groups='base.group_system',
        help="The username of the UrbanPiper API account."
    )
    urbanpiper_apikey = fields.Char(
        string='API Key',
        default=lambda self: self._default_urbanpiper_credentials('urbanpiper_apikey'),
        required=True,
        groups='base.group_system',
        help="API key for accessing the UrbanPiper services.",
    )
    is_webhook_register = fields.Boolean(
        string='Is Webhook Registered?',
        copy=False,
        readonly=True,
        help="Indicates if the webhook registered or refresh cron job needs to be run for this store.",
    )
    urbanpiper_synced_json = fields.Json(
        string='UrbanPiper Sync Metadata',
        help="To keep track of synced urbanpiper menu like products, options etc.)",
    )
    minimum_preparation_time = fields.Integer(
        string='Minimum Preparation Time (Minutes)',
        default=20,
        required=True,
        help="The minimum amount of time the customer must wait for the order to be prepared.",
    )
    store_order_count = fields.Integer(compute='_compute_store_counts')
    store_product_count = fields.Integer(compute='_compute_store_counts')
    use_test_mode = fields.Boolean(
        string='Test Mode',
        help="Enable test mode to synchronize the store with UrbanPiper's test environment (Atlas)."
    )

    _urbanpiper_store_identifier_uniq = models.Constraint(
        'unique(store_identifier)',
        "Store ID must be unique to configure the Online Food Delivery Store.",
    )

    def _compute_config_id(self):
        for store in self:
            store.config_id = self.env['pos.config'].search(
                [('urbanpiper_store_id', 'in', store.ids)],
                limit=1,
            )

    def _inverse_config_id(self):
        """Update the PoS config linked to each UrbanPiper store.

        Ensures that a store remains linked to at most one PoS config by
        clearing any existing association before assigning the new one.
        """
        for store in self:
            if old_config := self.env['pos.config'].search([('urbanpiper_store_id', '=', store.id)], limit=1):
                # Remove the existing store association before reassigning it.
                old_config.urbanpiper_store_id = False
                old_config.module_pos_urban_piper = False

            if new_config := store.config_id:
                # Link the selected PoS config to this store and enable
                # the UrbanPiper integration for it.
                new_config.module_pos_urban_piper = True
                new_config.urbanpiper_store_id = store

    @api.depends('aggregator_lines.delivery_provider_id')
    def _compute_delivery_providers(self):
        for store in self:
            store.delivery_provider_ids = store.aggregator_lines.delivery_provider_id

    def _compute_store_counts(self):
        # Orders count grouped by config
        orders_data = self.env['pos.order']._read_group(
            domain=[('config_id', 'in', self.config_id.ids), ('source', '=', 'online')],
            groupby=['config_id'],
            aggregates=['__count']
        )
        order_count_by_config = {config.id: count for config, count in orders_data}
        # Products count grouped by store
        products_data = self.env['product.template']._read_group(
            domain=[('urbanpiper_store_ids', 'in', self.ids)],
            groupby=['urbanpiper_store_ids'],
            aggregates=['__count']
        )
        product_count_by_store = {store.id: count for store, count in products_data}

        for store in self:
            store.store_order_count = order_count_by_config.get(store.config_id.id, 0)
            store.store_product_count = product_count_by_store.get(store.id, 0)

    def write(self, vals):
        if 'config_id' in vals and any(store.is_webhook_register and store.config_id.has_active_session for store in self):
            raise UserError(_(
                "You cannot change the Point of Sale while a store session is still open and the store has already been synchronized"
                "Please close the active session first."
            ))
        if {'urbanpiper_apikey', 'urbanpiper_username', 'use_test_mode'} & vals.keys():
            vals['is_webhook_register'] = False
            self._clear_store_webhooks()
        res = super().write(vals)
        if 'preset_id' in vals:
            self._assign_default_pricelist_to_aggregators()
        return res

    @api.model
    def _get_by_identifier(self, identifier):
        if not identifier:
            raise ValueError("Token must be provided")
        return next((
            store for store in self.sudo().search([('store_identifier', '!=', False)])
            if consteq(store.store_identifier, identifier)
        ), None)

    @api.ondelete(at_uninstall=False)
    def _unlink_pos_urbanpiper_store(self):
        if any(store.is_webhook_register and store.config_id.has_active_session for store in self):
            raise UserError(_(
                "You cannot delete this store while its session is still open.\n"
                "Please close the active session first."
            ))

    @api.model
    def _load_pos_data_fields(self, config):
        return ['name', 'config_id', 'delivery_provider_ids', 'aggregator_lines', 'order_notification_sound']

    @api.model
    def _load_pos_data_domain(self, data):
        return [('id', '=', data['pos.config'].urbanpiper_store_id.id)]

    def _assign_default_pricelist_to_aggregators(self):
        """Assign the store preset pricelist to aggregator lines."""
        for store in self:
            if pricelist := store.preset_id.pricelist_id:
                store.aggregator_lines.filtered(
                    lambda line: not line.pricelist_id
                ).pricelist_id = pricelist

    def _clear_store_webhooks(self):
        """
        Delete all webhooks associated with the current stores.

        This is typically triggered when UrbanPiper credentials change,
        forcing webhook re-registration with updated authentication.
        """
        self.env['pos.urban.piper.webhook'].search([
            ('store_id', 'in', self.ids)
        ]).unlink()

    def _update_urbanpiper_synced_json(self, products):
        """Update UrbanPiper sync state by updating synced product and option ids."""
        self.ensure_one()
        prev_products = set((self.urbanpiper_synced_json or {}).get('synced_product_ids', []))
        prev_options = set((self.urbanpiper_synced_json or {}).get('synced_option_ids', []))
        new_ptav_ids = set(products.attribute_line_ids.product_template_value_ids.filtered(lambda ptav: ptav.ptav_active).ids)
        self.urbanpiper_synced_json = {
            'synced_product_ids': list(prev_products | set(products.ids)),
            'synced_option_ids': list(prev_options | new_ptav_ids),
        }

    def _reset_urbanpiper_synced_json(self):
        """Clear all UrbanPiper sync-related metadata, usually performed before triggering a flush."""
        self.ensure_one()
        self.urbanpiper_synced_json = {
            'synced_product_ids': [],
            'synced_option_ids': []
        }

    def _change_aggregator_availability(self, active=False):
        """
        Change the availability of all linked delivery providers for this UrbanPiper store,
        typically when a POS session is opened or closed.
        """
        self.ensure_one()
        self.aggregator_lines.is_online = active

    def _check_required_request_params(self):
        self.ensure_one()
        msg = ''
        if not self.sudo().urbanpiper_username:
            msg += _('Username is required.\n')
        if not self.sudo().urbanpiper_apikey:
            msg += _('API Key is required.\n')
        if not self.config_id:
            msg += _('Point of Sale is required.\n')
        if msg:
            raise UserError(msg)

    def action_update_store(self):
        """Create/update the store in UrbanPiper."""
        self.ensure_one()
        self._check_required_request_params()
        if not self.is_webhook_register:
            self.action_refresh_webhooks()
        response_json = UrbanPiperConnector(self).post_stores()
        if response_json.get('status') == 'success':
            self.message_post(body=_('The store has been successfully updated on UrbanPiper.'))
        return self._urbanpiper_handle_response(response_json)

    def action_sync_menu(self, flush=False):
        """
        Sync the menu with UrbanPiper.
        This will update the menu items and categories in UrbanPiper.
        """
        self.ensure_one()
        self._check_required_request_params()
        if not self.is_webhook_register:
            self.action_refresh_webhooks()
        response = UrbanPiperConnector(self).post_location_inventory(flush)
        return self._urbanpiper_handle_response(response)

    def action_refresh_webhooks(self):
        """
        If a webhook already exists on Atlas, refresh it; otherwise, create a new one.
        """
        self._check_required_request_params()
        self.is_webhook_register = False
        self.env.ref('pos_urban_piper.cron_update_urban_piper_webhook_urls')._trigger()

    def action_view_store_products(self):
        synced_product_ids = (self.urbanpiper_synced_json or {}).get('synced_product_ids', [])
        store_ids = self.ids
        return {
            'name': _('Store Products'),
            'res_model': 'product.template',
            'view_mode': 'list,kanban,form',
            'views': [
                (self.env.ref('pos_urban_piper.urbanpiper_store_product_template_list_view').id, 'list'),
                (self.env.ref('product.product_template_kanban_view').id, 'kanban'),
                (self.env.ref('product.product_template_only_form_view').id, 'form'),
            ],
            'type': 'ir.actions.act_window',
            'context': {
                'synced_products': synced_product_ids,
                'store_id': store_ids,
                'search_default_urbanpiper_store_ids': store_ids,
                'default_urbanpiper_store_ids': store_ids,
                'default_available_in_pos': True,
            },
            'search_view_id': (self.env.ref('pos_urban_piper.pos_urbanpiper_store_product_search_view').id, 'search'),
        }

    def action_view_store_orders(self):
        return {
            'name': _('Store Orders'),
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('pos_urban_piper.view_pos_order_list_inherit_pos_urban_piper').id, 'list'),
                (self.env.ref('point_of_sale.view_pos_pos_form').id, 'form'),
            ],
            'type': 'ir.actions.act_window',
            'domain': [('config_id', 'in', self.config_id.ids), ('source', 'in', 'online')],
        }

    def action_open_urbanpiper_signup_form(self):
        """Open the UrbanPiper signup form in a new browser tab."""
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://www.odoo.com/survey/start/f13956e4-0104-48a0-967e-e5b6ffedd45d',
            'target': 'new',
        }

    def action_flush_and_sync_menu(self):
        """Resets all existing UrbanPiper product linkages and performs a fresh menu sync."""
        self.ensure_one()
        self._reset_urbanpiper_synced_json()
        return self.action_sync_menu(flush=True)

    def _urbanpiper_handle_response(self, response_json, raise_exception=False):
        """Handle response from UrbanPiper"""
        title, message = _('UrbanPiper'), ''
        if response_json.get('errors'):
            title, message = next(iter(response_json.get('errors').items()))
        else:
            message = response_json.get('message') or response_json.get('error_message')
        if not message:
            return
        if response_json.get('status') == 'success':
            message = message.split('.')[0]
        elif response_json.get('status') == 'error' and raise_exception:
            raise ValidationError(message)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': 'success' if response_json.get('status') == 'success' else 'danger',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},  # force a form reload
            }
        }
