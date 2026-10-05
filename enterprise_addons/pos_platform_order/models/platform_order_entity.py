# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from typing import Any

from odoo import api, fields, models
from odoo.fields import Command, Domain

_logger = logging.getLogger(__name__)


class PlatformOrderEntity(models.Model):
    _name = 'platform.order.entity'
    _description = 'Platform Order Entity'

    name = fields.Char(string='Name', required=True)
    provider_id = fields.Many2one('platform.order.provider', string='Provider',
                                  required=True, domain="[('state', '!=', 'disabled')]")
    external_id = fields.Char(
        string='External ID', help="External ID used in the provider's system", required=True, index=True, copy=False)
    company_id = fields.Many2one(related='provider_id.company_id', store=True)
    currency_id = fields.Many2one(related='provider_id.default_pricelist_id.currency_id')

    # -- Point of Sale Configuration --
    config_id = fields.Many2one('pos.config', string='Point of Sale', domain="['|', ('company_id', '=', False), ('company_id', 'child_of', company_id)]")
    payment_method_id = fields.Many2one('pos.payment.method', string='Payment Method', domain="['|', ('company_id', '=', False), ('company_id', 'child_of', company_id)]")
    available_categ_ids = fields.Many2many(string='Available Product Categories', comodel_name='pos.category')
    service_hours_id = fields.Many2one('resource.calendar', string='Service Hours', groups="base.group_system",
                                       default=lambda self: self.env.ref('pos_restaurant.pos_resource_preset', raise_if_not_found=False))
    pricelist_line_ids = fields.One2many('platform.order.pricelist.line', 'store_id', string='Pricelist Lines',
                                         store=True, readonly=False, help="List of pricelist configurations for this entity.")

    # -- Presets Configuration --
    delivery_preset_id = fields.Many2one(
        'pos.preset', string='Delivery Preset', default=lambda self: self.env.ref('pos_restaurant.pos_delivery_preset', raise_if_not_found=False))
    pickup_preset_id = fields.Many2one(
        'pos.preset', string='Pickup Preset', default=lambda self: self.env.ref('pos_restaurant.pos_takeout_preset', raise_if_not_found=False))
    dinein_preset_id = fields.Many2one(
        'pos.preset', string='Dine-in Preset', default=lambda self: self.env.ref('pos_restaurant.pos_takein_preset', raise_if_not_found=False))

    # -- Menu Synchronization --
    menu_sync_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('queuing', 'Queuing'),
            ('processing', 'Processing'),
            ('done', 'Done'),
            ('failed', 'Failed')],
        string='Menu Sync Status', default='draft', readonly=True)
    last_menu_synced = fields.Datetime(
        string='Last Menu Synced', readonly=True)

    # -- Technical Fields (Related, for internal use) --
    provider_code = fields.Selection(related='provider_id.code')
    available_categ_ids_domain = fields.Char(
        compute='_compute_available_categ_ids_domain')

    # -- Constraints --
    _entity_id_uniq = models.Constraint(
        'UNIQUE(external_id, provider_id)',
        'A store with the same external ID already exists for this provider.',
    )

    @api.depends('provider_id.name', 'name')
    def _compute_display_name(self):
        for record in self:
            name_parts = [
                record.provider_id.name,
                record.name or None
            ]
            record.display_name = "/".join(filter(None, name_parts))

    @api.depends('config_id.iface_available_categ_ids', 'config_id.limit_categories')
    def _compute_available_categ_ids_domain(self):
        for record in self:
            if record.config_id.limit_categories:
                record.available_categ_ids_domain = str(Domain('id', 'child_of',
                    record.config_id.iface_available_categ_ids.ids))
            else:
                record.available_categ_ids_domain = Domain(True)

    @api.onchange('provider_id')
    def _onchange_provider_id(self):
        if self.provider_id:
            self.payment_method_id = self.provider_id.default_payment_method_id
            self.pricelist_line_ids = [Command.clear()] + [Command.create(
                vals) for vals in self._prepare_pricelist_line_vals()]
        else:
            self.payment_method_id = False
            self.pricelist_line_ids = [Command.clear()]

    def _set_menu_sync_state_done(self):
        self.menu_sync_state = 'done'
        self.last_menu_synced = fields.Datetime.now()

    def _prepare_pricelist_line_vals(self):
        self.ensure_one()
        return [{
            'name': 'Default Pricelist',
            'external_key': 'default',
            'pricelist_id': self.provider_id.default_pricelist_id.id,
            'store_id': self.id,
        }]

    # region MENU SYNCHRONIZATION
    def action_sync_menu(self):
        """
        This method is called to synchronize the menu for the entity.
        It checks the provider code and calls the appropriate method for synchronization.
        """
        self._sync_menu()
        return True

    # To be overridden
    def _sync_menu(self):
        """
        This method should be overridden in the specific provider classes
        to implement the actual menu synchronization logic.
        """
        if self:
            raise NotImplementedError("This method should be overridden in the specific provider classes.")

    def _get_menu_products(self):
        self.ensure_one()
        domain = Domain.AND([Domain('available_in_pos', '=', True), Domain('sale_ok', '=', True)])
        if not self.provider_id.support_combo:
            domain = Domain.AND([domain, Domain('type', '!=', 'combo')])
        if self.config_id.limit_categories:
            domain = Domain.AND([domain, Domain('pos_categ_ids', 'child_of', self.config_id.iface_available_categ_ids.ids)])
        if self.available_categ_ids:
            domain = Domain.AND([domain, Domain('pos_categ_ids', 'child_of', self.available_categ_ids.ids)])
        return self.env['product.template'].search(domain)
    # endregion

    # region FOOD ORDERING
    def _create_order_from_data(self, order_data: dict):
        self.ensure_one()

        order_vals = self._prepare_order_values_from_data(order_data)

        if not self.config_id.current_session_id:
            return self._cancel_order_from_data(order_data, self.env._("Shop is closed."))

        order_lines_values = self._prepare_order_lines_values_from_data(order_data)
        order_vals = self._convert_to_order_values(**order_vals)
        order_vals['lines'] = [Command.create(order_line_value) for order_line_value in order_lines_values]

        order_id = self.env['pos.order']._process_order(order_vals, False)
        order = self.env['pos.order'].browse(order_id)
        order._compute_prices()

        self.config_id.notify_platform_order_synchronisation(order, is_new_order=True)
        return order

    # To be overridden
    def _prepare_order_values_from_data(self, data: dict) -> dict[str, Any]:
        """
        This method should be overridden in the specific provider classes
        to implement the logic for preparing order values from notification data.
        This method will call _convert_to_order_values to get the final order values.

        :return: A dictionary representing the order values:
            - `name` (str): Order name
            - `floating_order_name` (str): Floating order name
            - `platform_order_ref` (str): Platform order reference
            - `platform_order_status` (str): Platform order status
            - `platform_order_pin` (str): Platform order PIN
            - `general_customer_note` (str, optional): General customer note
            - `order_type` (str): Order type
        """
        self.ensure_one()
        msg = "This method should be overridden in the specific provider classes."
        raise NotImplementedError(msg)

    def _convert_to_order_values(self, **kwargs):
        """
        Helper method to return common order values.
        :return: dict of order values
        """
        session = self.config_id.current_session_id
        pos_reference, tracking_number = self.config_id._get_next_order_refs()
        default_pricelist_id = self.pricelist_line_ids[:1].pricelist_id.id

        partner = self._find_or_create_partners_from_data(kwargs)
        preset = self.env['pos.preset']
        order_type = kwargs.get('order_type', 'delivery')
        if self.config_id.use_presets:
            match order_type:
                case 'delivery':
                    preset = self.delivery_preset_id
                case 'pickup':
                    preset = self.pickup_preset_id
                case 'dine_in':
                    preset = self.dinein_preset_id

        return {
            'state': 'draft',
            'name': kwargs.get('name', '/'),
            'source': 'platform_order',
            'pos_reference': pos_reference,
            'tracking_number': tracking_number,
            'floating_order_name': kwargs.get('floating_order_name', ''),
            'session_id': session.id,
            'company_id': self.config_id.company_id.id,
            'user_id': session.user_id.id,
            'partner_id': partner.id,
            'pricelist_id': kwargs.get('pricelist_id', default_pricelist_id),
            'preset_id': preset.id,
            'preset_time': kwargs.get('preset_time'),
            'platform_order_store_id': self.id,
            'platform_order_type': kwargs.get('order_type', 'delivery'),
            'platform_order_ref': kwargs.get('platform_order_ref'),
            'platform_order_status': kwargs.get('platform_order_status', 'new'),
            'platform_order_pin': kwargs.get('platform_order_pin'),
            'general_customer_note': kwargs.get('general_customer_note', ''),
            'amount_paid': 0.0,
            'amount_total': 0.0,
            'amount_tax': 0.0,
            'amount_return': 0.0,
        }

    # To be overridden
    def _find_or_create_partners_from_data(self, order_data):
        """
        This method should be overridden in the specific provider classes
        to implement the logic for finding or creating a customer from notification data.
        """
        self.ensure_one()
        raise NotImplementedError(
            "This method should be overridden in the specific provider classes.")

    # To be overridden
    def _prepare_order_lines_values_from_data(self, order_data):
        """
        This method should be overridden in the specific provider classes
        to implement the logic for preparing order line values from notification data.
        :return: list of order line values
        """
        self.ensure_one()
        _logger.info(
            "Order line preparation not implemented for this provider. Skipping.")
        return []
    # endregion

    # region COMMON METHODS
    # To be overridden
    @api.model
    def _find_store_from_data(self, provider_code, order_data):
        """
        This method retrieves the store based on the order data.
        It checks if the store ID is present in the order data.
        """
        msg = "This method should be overridden in the specific provider classes."
        raise NotImplementedError(msg)

    # To be overridden
    def _cancel_order_from_data(self, data: dict, reason: str):
        self.ensure_one()
        msg = "This method should be overridden in the specific provider classes."
        raise NotImplementedError(msg)

    # To be overridden
    def _update_platform_order_menu(self, products):
        """
        This method should be overridden in the specific provider classes
        to implement the actual availability status sending logic.
        """
        self.ensure_one()
        msg = "This method should be overridden in the specific provider classes."
        raise NotImplementedError(
            msg)
    # endregion
