# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import secrets
from typing import Any

from requests.exceptions import RequestException

from odoo import Command, _, api, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.urls import urljoin

from odoo.addons.pos_platform_order import utils
from odoo.addons.pos_platform_order_gofood.utils import const
from odoo.addons.pos_platform_order_gofood.utils.gofood_request import GoFoodClient

_logger = logging.getLogger(__name__)

PROVIDER_CODE = 'gofood'

DAY_OF_WEEK = [
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday',
]


class PlatformOrderEntity(models.Model):
    _inherit = 'platform.order.entity'

    # region MENU SYNC
    # override
    def _sync_menu(self):
        gofood_stores = self.filtered(lambda e: e.provider_code == PROVIDER_CODE)
        if not gofood_stores:
            return super()._sync_menu()

        for store in gofood_stores:
            store.menu_sync_state = 'processing'
            try:
                client = GoFoodClient(store)
                client.request_sync_menu(store._prepare_gofood_menu_data())
                store._set_menu_sync_state_done()
            except RequestException as e:
                _logger.error("GoFood sync menu request failed: %s", e)
                store.menu_sync_state = 'failed'

        # Call the super method for non-GoFood stores
        super(PlatformOrderEntity, (self - gofood_stores))._sync_menu()
        return None

    def _prepare_gofood_menu_data(self):
        self.ensure_one()
        product_templates = self._get_menu_products()
        if not product_templates:
            raise UserError(_("No products found in the store."))

        return {
            'request_id': secrets.token_hex(16),
            'menus': self._prepare_gofood_categories_data(product_templates),
            'variant_categories': self._prepare_gofood_variant_categories_data(product_templates),
        }

    def _prepare_gofood_categories_data(self, product_templates) -> list:
        categories = product_templates.pos_categ_ids
        if self.available_categ_ids:
            categories = categories.filtered(lambda c: c in self.available_categ_ids)
        categories_list = []

        for category in categories:
            category_products = product_templates.filtered(lambda p: category in p.pos_categ_ids)
            if not category_products:
                continue

            menu_items = [self._prepare_gofood_menu_item(category, p) for p in category_products]
            categories_list.append({
                "name": category.name,
                "menu_items": menu_items,
            })
        return categories_list

    def _prepare_gofood_menu_item(self, category, product_template) -> dict[str, Any]:
        # We only consider the first pricelist line for GoFood menu item price
        pricelist = self.pricelist_line_ids[0].pricelist_id
        price_incl = product_template.taxes_id.filtered(
            lambda tax: tax.company_id == self.company_id,
        ).compute_all(
            pricelist._get_product_price(product_template, 1.0),
            pricelist.currency_id,
            1,
        )["total_included"]
        service_hours_id = self.service_hours_id
        if category.service_hours_id:
            service_hours_id = category.service_hours_id
        menu_item_data = {
            'description': product_template.description_sale or '',
            'external_id': utils._get_external_id(product_template),
            'image': urljoin(self.env.company.get_base_url(), f"/web/image/product.template/{product_template.id}/image_512/image.png?unique={int(product_template.write_date.timestamp())}"),
            'in_stock': product_template.platform_order_available,
            'name': product_template.name,
            'price': price_incl,
            "operational_hours": self._prepare_gofood_service_hours_data(service_hours_id),
        }
        if product_template.attribute_line_ids:
            menu_item_data['variant_category_external_ids'] = [
                utils._get_external_id(attribute_line) for attribute_line in product_template.attribute_line_ids
            ]
        return menu_item_data

    @api.model
    def _prepare_gofood_service_hours_data(self, service_hours_id) -> dict[str, list[dict]]:
        service_hours = {day: [] for day in DAY_OF_WEEK}
        for attendance in service_hours_id.attendance_ids:
            day_name = DAY_OF_WEEK[int(attendance.dayofweek)]
            hour_from = attendance.hour_from
            hour_to = min(attendance.hour_to, 23.99)
            service_hours[day_name].append({
                'start': f"{int(hour_from):02d}:{int((hour_from % 1) * 60):02d}",
                'end': f"{int(hour_to):02d}:{int((hour_to % 1) * 60):02d}",
            })
        return service_hours

    def _prepare_gofood_variant_categories_data(self, product_templates) -> list[dict[str, Any]]:
        """Prepares the list of variant categories (modifier groups) for the menu payload."""
        return [self._prepare_gofood_variant_category(line) for line in product_templates.attribute_line_ids]

    def _prepare_gofood_variant_category(self, attribute_line) -> dict[str, Any]:
        attribute = attribute_line.attribute_id
        is_multi_select = attribute.display_type == 'multi'
        return {
            'external_id': utils._get_external_id(attribute_line),
            'internal_name': f"{attribute_line.product_tmpl_id.name} - {attribute.name}",
            'name': attribute.name,
            'rules': {
                "selection": {
                    "min_quantity": 0 if is_multi_select else 1,
                    "max_quantity": None if is_multi_select else 1,
                },
            },
            'variants': [self._prepare_gofood_variant(val) for val in attribute_line.product_template_value_ids],
        }

    def _prepare_gofood_variant(self, attribute_value) -> dict[str, Any]:
        """Prepares the data for a single variant (modifier option)."""
        price_extra_incl = attribute_value.product_tmpl_id.taxes_id.filtered(
            lambda tax: tax.company_id == self.company_id,
        ).compute_all(attribute_value.price_extra, self.currency_id, 1)['total_included']
        return {
            'external_id': utils._get_external_id(attribute_value),
            'name': attribute_value.name,
            'price': self.currency_id.round(price_extra_incl),
            'in_stock': True,
        }

    # endregion

    # region FOOD ORDERING

    def _prepare_order_values_from_data(self, notification_data):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._prepare_order_values_from_data(notification_data)

        notification_order_data = notification_data.get('body', {}).get('order', {})

        return {
            'name': notification_order_data['order_number'],
            'floating_order_name': f"#{notification_order_data.get('order_number')}",
            'platform_order_ref': notification_order_data['order_number'],
            'platform_order_status': const.ORDER_STATUS_MAPPING[notification_order_data['status']],
            'platform_order_pin': notification_order_data.get('pin'),
            'general_customer_note': _("Cutlery Requested: %s", bool(notification_order_data.get('cutlery_requested'))),
            'order_type': const.SERVICE_TYPE_MAPPING.get(notification_data['body']['service_type']),
        }

    def _find_or_create_partners_from_data(self, order_data):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._find_or_create_partners_from_data(order_data)

        Partner = self.env['res.partner']
        customer_data = order_data.get('body', {}).get('customer', {})

        gofood_customer_id = customer_data.get('id')
        if not gofood_customer_id:
            return Partner

        customer = Partner.search([('gofood_customer_id', '=', gofood_customer_id)], limit=1)
        if not customer:
            customer = Partner.create({
                'name': customer_data.get('name', _("GoFood Customer %s", gofood_customer_id)),
                'gofood_customer_id': gofood_customer_id,
            })
        return customer

    def _prepare_order_lines_values_from_data(self, notification_data):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._prepare_order_lines_values_from_data(notification_data)

        order_lines_values = []
        lines_data = notification_data['body']['order']['order_items']
        for line_data in lines_data:
            product_tmpl_ids = utils._parse_external_ids(self.env, [line_data.get('external_id', [])])
            product_template = self.env["product.template"].browse(product_tmpl_ids)
            if not product_template:
                _logger.error("GoFood: Product not found for external_id %s", line_data.get('external_id'))
                raise ValidationError(_("GoFood: Product with external ID %s was not found.", line_data.get('external_id')))

            attribute_value_external_ids = [v.get('external_id') for v in line_data.get('variants', [])]
            attribute_value_ids = utils._parse_external_ids(self.env, attribute_value_external_ids)
            attribute_values = self.env["product.template.attribute.value"].browse(attribute_value_ids)
            product = product_template._create_product_variant(attribute_values)
            product = product or product_template.product_variant_id

            qty = int(line_data.get('quantity', 0))
            price_unit_incl = float(line_data.get('price', 0.0))
            # Recalculate tax-excluded price based on the tax-included price from the provider
            taxes = product.taxes_id.filtered(lambda tax: tax.company_id == self.company_id)
            price_info = taxes.with_context(force_price_include=True).compute_all(price_unit_incl, self.currency_id, qty)
            price_unit_excl = self.currency_id.round(price_info['total_excluded'] / qty) if qty else 0

            order_lines_value = {
                'attribute_value_ids': attribute_values,
                'customer_note': line_data.get('notes'),
                'full_product_name': product.name,
                'product_id': product.id,
                'qty': qty,
                'price_unit': price_unit_excl,
                'price_subtotal': self.currency_id.round(price_info['total_excluded']),
                'price_subtotal_incl': self.currency_id.round(price_info['total_included']),
                'tax_ids': [Command.set(taxes.ids)],
            }
            order_lines_values.append(order_lines_value)

        return order_lines_values
    # endregion

    # region COMMON METHODS
    # override
    def _find_store_from_data(self, provider_code, notification_data):
        if provider_code != PROVIDER_CODE:
            return super()._find_store_from_data(provider_code, notification_data)

        external_id = notification_data.get('body', {}).get('outlet', {}).get('id')
        if not external_id:
            raise ValidationError(_("GoFood: Received data with missing store ID %s.", external_id))

        store = self.search([('provider_code', '=', provider_code), ('external_id', '=', external_id)], limit=1)
        if not store:
            raise ValidationError(_("GoFood: No store found matching ID %s.", external_id))
        return store

    # override
    def _cancel_order_from_data(self, order_data, reason):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._cancel_order_from_data(order_data, reason)

        order_ref = order_data.get('body', {}).get('order', {}).get('order_number')

        try:
            client = GoFoodClient(self)
            client.reject_order(order_ref, cancel_reason_code="RESTAURANT_CLOSED", cancel_reason_description=reason)
        except RequestException as error:
            _logger.error("GoFood set food ready request failed for order %s: %s", order_ref, error)

    # override
    def _update_platform_order_menu(self, products):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._update_platform_order_menu(products)

        menu_items = [{
            "external_id": utils._get_external_id(product),
            "in_stock": product.platform_order_available,
        } for product in products]

        try:
            GoFoodClient(self).batch_update_menu(menu_items)
        except RequestException as error:
            _logger.error("GoFood update menu items request failed for store %s: %s", self.name, error)
            raise UserError(_("Failed to update menu items on GoFood: %s", str(error))) from error
    # endregion
