# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import logging
from collections import defaultdict

import dateutil
from requests.exceptions import RequestException

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools.urls import urljoin

from odoo.addons.pos_platform_order import utils
from odoo.addons.pos_platform_order_grabfood.utils import const
from odoo.addons.pos_platform_order_grabfood.utils.grabfood_request import (
    GrabFoodClient,
)

_logger = logging.getLogger(__name__)

PROVIDER_CODE = 'grabfood'
DAY_OF_WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class PlatformOrderEntity(models.Model):
    _inherit = 'platform.order.entity'

    # override
    def _prepare_pricelist_line_vals(self):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._prepare_pricelist_line_vals()

        pricelist_id = self.provider_id.default_pricelist_id.id
        return [
            {'name': 'Delivery On-Demand', 'external_key': 'Delivery_OnDemand_GrabApp', 'store_id': self.id, 'pricelist_id': pricelist_id},
            {'name': 'Delivery Scheduled', 'external_key': 'Delivery_Scheduled_GrabApp', 'store_id': self.id, 'pricelist_id': pricelist_id},
            {'name': 'Self-Pickup On-Demand', 'external_key': 'SelfPickUp_OnDemand_GrabApp', 'store_id': self.id, 'pricelist_id': pricelist_id},
            {'name': 'Dine-In On-Demand', 'external_key': 'DineIn_OnDemand_GrabApp', 'store_id': self.id, 'pricelist_id': pricelist_id},
        ]

    # region MENU SYNCHRONIZATION
    # override
    def _sync_menu(self):
        grabfood_stores = self.filtered(lambda e: e.provider_code == PROVIDER_CODE)
        if not grabfood_stores:
            return super()._sync_menu()

        stores_without_external_id = grabfood_stores.filtered(lambda e: not e.external_id)
        if stores_without_external_id:
            raise UserError(_("External ID is not set for one or more GrabFood stores: %s", stores_without_external_id))

        for store in grabfood_stores:
            client = GrabFoodClient(store)
            client.request_sync_menu()
            client.update_store_delivery_hours(store._prepare_grabfood_service_hours_val())

        grabfood_stores.menu_sync_state = 'queuing'

        # Call super for non-GrabFood stores
        super(PlatformOrderEntity, (self - grabfood_stores))._sync_menu()
        return None

    def _prepare_grabfood_menu_data(self):
        self.ensure_one()
        company_self = self.with_company(self.company_id)
        product_templates = company_self._get_menu_products()
        categories = product_templates.pos_categ_ids
        if self.available_categ_ids:
            categories = categories.filtered(lambda c: c in self.available_categ_ids)

        return {
            'currency': company_self._prepare_grabfood_currency_val(),
            'sellingTimes': company_self._prepare_grabfood_store_selling_times_data(categories.service_hours_id),
            'categories': company_self._prepare_grabfood_store_categories_data(categories, product_templates),
        }

    def _prepare_grabfood_currency_val(self):
        self.ensure_one()
        return {
            "code": self.currency_id.name,
            "symbol": self.currency_id.symbol,
            "exponent": const.COUNTRIES_CURRENCY_EXPONENT.get(self.provider_id.country_code, self.currency_id.decimal_places),
        }

    def _prepare_grabfood_service_hours_val(self):
        self.ensure_one()
        service_hours = {day: [] for day in DAY_OF_WEEK}
        for attendance in self.service_hours_id.attendance_ids:
            day = DAY_OF_WEEK[int(attendance.dayofweek)]
            hour_from = attendance.hour_from
            hour_to = min(attendance.hour_to, 23.99)  # Cap at 23:59
            service_hours[day].append({
                "startTime": f"{int(hour_from):02d}:{int((hour_from % 1) * 60):02d}",
                "endTime": f"{int(hour_to):02d}:{int((hour_to % 1) * 60):02d}",
            })
        return service_hours

    def _prepare_grabfood_store_selling_times_data(self, service_hours_records) -> list:
        if not service_hours_records:
            raise UserError(_("No selling times found for this entity."))

        result = []
        for service_hour in service_hours_records:
            periods_by_day = defaultdict(list)
            for attendance in service_hour.attendance_ids:
                day_str = DAY_OF_WEEK[int(attendance.dayofweek)]
                periods_by_day[day_str].append({
                    "startTime": f"{int(attendance.hour_from):02d}:{int((attendance.hour_from % 1) * 60):02d}",
                    "endTime": f"{int(attendance.hour_to):02d}:{int((attendance.hour_to % 1) * 60):02d}",
                })

            service_hours_val = {
                day: {"openPeriodType": "OpenPeriod", "periods": periods_by_day[day]} if periods_by_day.get(day) else {"openPeriodType": "CloseAllDay"}
                for day in DAY_OF_WEEK
            }

            result.append({
                "id": utils._get_external_id(service_hour),
                "name": service_hour.name,
                "serviceHours": service_hours_val,
                "startTime": "1970-01-01 00:00:00",
                "endTime": "9999-12-31 23:59:59",
            })

        return result

    def _prepare_grabfood_store_categories_data(self, categories, product_templates) -> list:
        """Formats product categories and their items for the GrabFood menu."""
        menu_categories = []
        for category in categories:
            if not category.service_hours_id:
                continue

            category_products = product_templates.filtered(lambda p: category in p.pos_categ_ids)
            if not category_products:
                continue

            items_data = [self._prepare_grabfood_item_data(p) for p in category_products]
            menu_categories.append({
                "id": utils._get_external_id(category),
                "name": category.name,
                "sequence": category.sequence,
                "availableStatus": "AVAILABLE",
                "items": items_data,
                "sellingTimeID": utils._get_external_id(category.service_hours_id),
            })
        return menu_categories

    def _get_grabfood_price_field(self):
        self.ensure_one()
        if self.provider_id.country_code in const.MENU_PRICE_TAX_INCLUSIVE_COUNTRIES:
            return "total_included"
        return "total_excluded"

    def _prepare_grabfood_item_data(self, product):
        """Prepares the data for a single menu item (product)."""
        status = "AVAILABLE" if product.platform_order_available else "UNAVAILABLE"
        advanced_pricing = {}
        for pricelist_line in self.pricelist_line_ids:
            pricelist = pricelist_line.pricelist_id
            price_tax_excluded = product.taxes_id.filtered(
                lambda tax: tax.company_id == self.company_id,
            ).compute_all(
                pricelist._get_product_price(product, 1.0),
                pricelist.currency_id, 1)[self._get_grabfood_price_field()]
            advanced_pricing[pricelist_line.external_key] = self._format_grabfood_price(
                price_tax_excluded, pricelist.currency_id.decimal_places)

        item_data = {
            "id": utils._get_external_id(product),
            "name": product.name,
            "description": product.description_sale or '',
            "sequence": product.pos_sequence,
            "availableStatus": status,
            "photos": [urljoin(self.env.company.get_base_url(), f"/web/image/product.template/{product.id}/image_512/image.png?unique={int(product.write_date.timestamp())}")],
            "advancedPricing": advanced_pricing,
        }
        if product.attribute_line_ids:
            item_data["modifierGroups"] = [self._prepare_grabfood_modifier_group(line) for line in product.attribute_line_ids]
        return item_data

    def _prepare_grabfood_modifier_group(self, attribute_line):
        """Prepares the data for a modifier group (product attribute line)."""
        is_multi_select = attribute_line.attribute_id.display_type == 'multi'
        return {
            "id": utils._get_external_id(attribute_line),
            "name": attribute_line.attribute_id.name,
            "sequence": attribute_line.sequence,
            "availableStatus": "AVAILABLE",
            "selectionRangeMin": 1 if not is_multi_select else 0,
            "selectionRangeMax": 1 if not is_multi_select else len(attribute_line.product_template_value_ids),
            "modifiers": [self._prepare_grabfood_modifier(value) for value in attribute_line.product_template_value_ids],
        }

    def _prepare_grabfood_modifier(self, value):
        """Prepares the data for a single modifier (product attribute value)."""
        price_extra_tax_excluded = self.env['product.template'].taxes_id.filtered(
            lambda tax: tax.company_id == self.company_id,
        ).compute_all(value.price_extra, self.currency_id, 1)[self._get_grabfood_price_field()]

        return {
            "id": utils._get_external_id(value),
            "name": value.name,
            "sequence": value.product_attribute_value_id.sequence,
            "availableStatus": "AVAILABLE",
            "price": self._format_grabfood_price(price_extra_tax_excluded, self.currency_id.decimal_places),
        }

    # endregion

    # region FOOD ORDERING
    # override
    def _prepare_order_values_from_data(self, notification_data):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._prepare_order_values_from_data(notification_data)

        est_ready_time = None
        est_ready_time_str = notification_data.get('orderReadyEstimation', {}).get('estimatedOrderReadyTime')
        if est_ready_time_str:
            try:
                est_ready_time = dateutil.parser.parse(est_ready_time_str)
            except dateutil.parser.ParserError:
                _logger.warning(
                    "Could not parse estimated order ready time: %s", est_ready_time_str)

        order_vals = {
            'name': notification_data['orderID'],
            'floating_order_name': f"#{notification_data.get('shortOrderNumber')}",
            'platform_order_ref': notification_data['orderID'],
            'platform_order_status': const.ORDER_ACCEPTANCE_TYPE_START_STATUS.get(notification_data.get('featureFlags', {}).get('orderAcceptedType')),
            'platform_order_pin': notification_data['shortOrderNumber'],
            'general_customer_note': _("Cutlery Requested: %s", bool(notification_data.get('cutlery'))),
            'order_type': const.SERVICE_TYPE_MAPPING.get(notification_data.get('featureFlags', {}).get('orderType'), 'delivery'),
        }

        if notification_data.get('scheduledTime') and self.config_id.use_presets and est_ready_time:
            # Convert to UTC and remove timezone info for Odoo's DateTime field
            order_vals['preset_time'] = est_ready_time.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        return order_vals

    # override
    def _find_or_create_partners_from_data(self, order_data):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._find_or_create_partners_from_data(order_data)

        Partner = self.env['res.partner']

        customer_data = order_data.get('receiver', {})
        name = customer_data.get('name')
        phone = customer_data.get('virtualContact', {}).get('phoneNumber')

        if not name or not phone:
            return Partner

        name = name.strip().replace('%', r'\%').replace('_', r'\_')
        partner = Partner.search([('name', '=like', f'%{name}%'), ('phone', '=', phone)], limit=1)
        if not partner:
            partner = Partner.create({'name': name, 'phone': phone})
        return partner

    # Override
    def _prepare_order_lines_values_from_data(self, notification_data):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._prepare_order_lines_values_from_data(notification_data)

        order_lines_values = []
        exponent = notification_data['currency']['exponent']
        for line_data in notification_data['items']:
            price_extra = 0.0

            attribute_value_external_ids = []
            modifiers = line_data.get('modifiers') or []
            for variant in modifiers:
                price_extra += self._parse_grabfood_price(variant.get('price', 0), exponent)
                attribute_value_external_ids.append(variant.get('id'))

            product_tmpl_ids = utils._parse_external_ids(self.env, line_data['id'])
            product_template = self.env["product.template"].browse(product_tmpl_ids)
            if not product_template:
                _logger.error("Product template not found for ID: %s", line_data['id'])
                raise ValidationError(_("Product template not found for ID: %s", line_data['id']))

            attribute_value_ids = utils._parse_external_ids(self.env, attribute_value_external_ids)
            attribute_values = self.env["product.template.attribute.value"].browse(attribute_value_ids)
            product = product_template._create_product_variant(attribute_values)
            product = product or product_template.product_variant_id
            taxes = product.taxes_id.filtered(lambda t: t.company_id == self.company_id)

            qty = int(line_data['quantity'])
            amount_tax = self._parse_grabfood_price(line_data['tax'], exponent)
            price_unit = self._parse_grabfood_price((line_data['price']), exponent) - amount_tax
            computed_price = taxes.compute_all(price_unit, self.currency_id, qty)

            order_lines_value = {
                'attribute_value_ids': [Command.set(attribute_value_ids)],
                'customer_note': line_data.get('specifications'),
                'full_product_name': product.name,
                'product_id': product.id,
                'qty': qty,
                'price_extra': price_extra,
                'price_unit': price_unit,
                'price_subtotal': computed_price['total_excluded'],
                'price_subtotal_incl': computed_price['total_included'],
                'tax_ids': [Command.set(taxes.ids)],
            }
            order_lines_values.append(order_lines_value)

        return order_lines_values
    # endregion

    # region COMMON METHODS
    # override
    def _find_store_from_data(self, provider_code, order_data):
        """Finds the store based on GrabFood's `merchantID` from notification data."""
        if provider_code != PROVIDER_CODE:
            return super()._find_store_from_data(provider_code, order_data)

        merchant_id = order_data.get('merchantID')
        if not merchant_id:
            raise ValidationError(_("GrabFood: Received data with missing merchant ID."))

        store = self.search([('provider_code', '=', provider_code), ('external_id', '=', merchant_id)], limit=1)
        if not store:
            raise ValidationError(_("GrabFood: No store found matching merchant ID %s.", merchant_id))
        return store

    # override
    def _cancel_order_from_data(self, order_data, reason):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._cancel_order_from_data(order_data, reason)

        platform_order_ref = order_data.get('orderID')
        try:
            client = GrabFoodClient(self)
            client.cancel_order(platform_order_ref, 1003)
        except RequestException as error:
            _logger.error("Failed to reject GrabFood order %s: %s", platform_order_ref, error)

    # override
    def _update_platform_order_menu(self, products):
        self.ensure_one()
        if self.provider_code != PROVIDER_CODE:
            return super()._update_platform_order_menu(products)

        menu_items = []
        for product in products:
            advanced_pricings = []
            for pricelist_line in self.pricelist_line_ids:
                pricelist = pricelist_line.pricelist_id
                price_tax_excluded = product.taxes_id.filtered(
                    lambda tax: tax.company_id == self.company_id,
                ).compute_all(
                    pricelist._get_product_price(product, 1.0),
                    pricelist.currency_id, 1)[self._get_grabfood_price_field()]
                advanced_pricings.append({
                    "key": pricelist_line.external_key,
                    "price": self._format_grabfood_price(price_tax_excluded, pricelist.currency_id.decimal_places),
                })

            menu_items.append({
                "id": utils._get_external_id(product),
                "availableStatus": "AVAILABLE" if product.platform_order_available else "UNAVAILABLE",
                "advancedPricings": advanced_pricings,
            })

        try:
            GrabFoodClient(self).batch_update_menu(menu_items)
        except RequestException as error:
            _logger.error("Failed to update menu items on GrabFood for store %s: %s", self.name, error)
            raise UserError(_("Failed to update menu items on GrabFood: %s", str(error))) from error
    # endregion

    # region NOTIFICATION HANDLERS
    def _grabfood_handle_menu_sync_notification(self, notification_data):
        self.ensure_one()
        menu_status_key = notification_data.get('status')
        menu_status = const.MENU_STATUS_MAPPING.get(menu_status_key)
        if not menu_status:
            _logger.warning("GrabFood: Received unknown menu status: %s", menu_status_key)
            return

        state_rank = {
            'queuing': 1,
            'processing': 2,
            'done': 3,
            'failed': 3,
        }

        current_state_rank = state_rank.get(self.menu_sync_state, 0)
        new_state_rank = state_rank.get(menu_status, 0)
        if new_state_rank < current_state_rank:
            _logger.info("GrabFood: Ignoring menu sync status downgrade from %s to %s", self.menu_sync_state, menu_status)
            return

        if menu_status == 'done':
            self._set_menu_sync_state_done()
        else:
            self.menu_sync_state = menu_status

    def _grabfood_handle_edit_order_notification(self, notification_data):
        self.ensure_one()
        pos_order = self.env['pos.order']._find_order_from_data(PROVIDER_CODE, notification_data)
        if not pos_order:
            _logger.error("GrabFood: Order not found for notification data: %s", notification_data)
            raise ValidationError(_("Order not found for notification data."))

        orderlines_values = self._prepare_order_lines_values_from_data(notification_data)
        pos_order.write({
            'lines': [Command.clear()] + [Command.create(line_vals) for line_vals in orderlines_values],
        })
        pos_order._compute_prices()
        self.config_id.notify_platform_order_synchronisation(pos_order)
    # endregion

    @api.model
    def _format_grabfood_price(self, price: float, exponent: int) -> int:
        """Converts a float price to GrabFood's integer format."""
        return int(price * (10 ** exponent))

    @api.model
    def _parse_grabfood_price(self, price: int, exponent: int) -> float:
        """Converts GrabFood's integer price format to a float."""
        return float(price / (10 ** exponent))
