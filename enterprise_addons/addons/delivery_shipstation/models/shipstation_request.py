# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
from base64 import b64decode

import requests
from markupsafe import Markup

from odoo.exceptions import UserError
from odoo.tools import format_list
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)


class ShipStation:
    def __init__(self, carrier, debug_logger):
        self.url = "https://api.shipstation.com/"
        self.__session = requests.Session()
        self.__session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'API-Key': carrier.sudo().shipstation_production_api_key,
        })
        self.carrier = carrier
        self.debug_logger = debug_logger
        self._currency_cache = {}

    def __make_api_request(self, method, endpoint, data=None, params=None):
        access_url = self.url + endpoint
        try:
            response = self.__session.request(method=method, url=access_url, json=data, params=params, timeout=30)
        except requests.exceptions.RequestException as error:
            _logger.warning('Request Error: %s with the given URL: %s', error, access_url)
            return {'errors': [{'message': "Cannot reach the server. Please try again later."}]}

        try:
            response_json = response.json()
        except ValueError as error:
            _logger.warning('Malformed ShipStation response (HTTP %s): %s', response.status_code, error)
            response_json = {}

        # Log the details for debugging purposes
        self.debug_logger(
            f"{access_url} ({method}) {response.status_code}\n\n"
            f"request={json.dumps(data, indent=2)}\n\n"
            f"response={json.dumps(response_json, indent=2)}\n\n"
            f"response_headers={json.dumps(dict(response.headers), indent=2)}\n",
            f"__make_api_request ({endpoint})",
        )

        # Auth failures answer with an empty or HTML body, so map the status instead.
        if response.status_code in (401, 403):
            return {'errors': [{'message': self.carrier.env._(
                "ShipStation refused the API key. Make sure it is an active V2 production key:"
                " V1 keys are not supported.",
            )}]}
        # Rating reports its errors inside 'rate_response' instead of at the top level.
        payload_errors = response_json.get('errors') or response_json.get('rate_response', {}).get('errors')
        if not response.ok and not payload_errors:
            return {'errors': [{'message': self.carrier.env._(
                "ShipStation returned an unexpected error (HTTP %(status_code)s).",
                status_code=response.status_code,
            )}]}
        if not response_json:
            return {'errors': [{'message': self.carrier.env._("ShipStation returned an unreadable response.")}]}
        return response_json

    def _parse_error_messages(self, response_json):
        request_id = response_json.get('request_id', 'N/A')
        messages = []

        errors = response_json.get('errors', [])
        if errors:
            messages.append(self.carrier.env._(
                "There was an error in your ShipStation request. (Reference ID: %(request_id)s)",
                request_id=request_id,
            ))
            for error in errors:
                message = error.get('message', 'Unknown error')
                messages.append(self.carrier.env._(
                    "ShipStation Error: %(message)s", message=message,
                ))

        # Unlike 'errors' above, the keys below come verbatim from the ShipStation payload.
        for warning in response_json.get('warning_messages', []):
            messages.append(self.carrier.env._(
                "ShipStation Warning: %(message)s", message=warning,
            ))

        for invalid in response_json.get('invalid_rates', []):
            for message in invalid.get('error_messages', []):
                messages.append(self.carrier.env._(
                    "ShipStation Error: %(message)s", message=message,
                ))

        full_message = "\n".join(messages)
        if "insufficient funds" in full_message.lower():
            full_message += "\n" + self.carrier.env._(
                "Top up your ShipStation account in your ShipStation portal to continue creating labels.",
            )
        return full_message

    # -------------------------------------------------------------------------
    # API CALLS
    # -------------------------------------------------------------------------

    def _fetch_shipstation_carriers(self):
        """ Import all available carriers
        url: v2/carriers
        """
        carrier_json = self.__make_api_request("GET", "v2/carriers")
        carrier_data = carrier_json.get('carriers')
        if carrier_json.get('errors'):
            return {'error': self._parse_error_messages(carrier_json)}
        return {'carriers': carrier_data}

    def _get_label_from_tracking_number(self, tracking_number):
        labels_response = self.__make_api_request('GET', 'v2/labels', params={'tracking_number': tracking_number})
        if labels_response.get('errors') or labels_response.get('total', 0) == 0:
            return None
        return labels_response['labels'][0]

    def _rate_request(self, order):
        """ Returns the dictionary of shipment rate from ShipStation
        url: v2/rates
        """
        recipient = order.partner_shipping_id
        shipper = order.warehouse_id.partner_id or order.warehouse_id.company_id.partner_id

        if not order:
            raise UserError(self.carrier.env._("Sale Order is required to get rate."))
        self._check_products(order.order_line.product_id)

        default_package = self.carrier.shipstation_default_package_type_id
        packages = self.carrier._get_packages_from_order(order, default_package)
        package_groups = self._group_packages(packages)

        total_price = 0.0
        warning_messages = []
        no_rate_message = order.env._("ShipStation returned no rates for this shipment.")
        # Base rate_shipment interprets the returned price in the company currency
        # (and converts to the order currency itself), using this company precedence.
        target_currency = (self.carrier.company_id or order.company_id or self.carrier.env.company).currency_id
        if len(package_groups) > 1:
            warning_messages.append(order.env._(
                "The carrier does not support multi-package shipments."
                " The packages were split into %(count)s separate shipments.",
                count=len(package_groups),
            ))
        for group in package_groups:
            package_data, item_data = self._prepare_package_information(group)
            data = {
                'rate_options': {
                    'carrier_ids': [self.carrier.shipstation_carrier_code],
                    'service_codes': [self.carrier.shipstation_service_code],
                },
                'shipment': {
                    'validate_address': 'no_validation',
                    'ship_to': self._prepare_address_values(recipient),
                    'ship_from': self._prepare_address_values(shipper),
                    'insurance_provider': self.carrier.shipstation_insurance_provider or 'none',
                    'confirmation': self.carrier.shipstation_confirmation_type or 'none',
                    'packages': package_data,
                    'items': item_data,
                },
            }
            if self.carrier.shipstation_additional_handling:
                data['shipment']['advanced_options'] = {
                    'additional_handling': True,
                }

            rate_json = self.__make_api_request("POST", "v2/rates", data=data)

            error_source = None
            if not rate_json or rate_json.get('errors'):
                error_source = rate_json
            elif not rate_json['rate_response']['rates']:
                error_source = rate_json['rate_response']
            if error_source is not None:
                error_message = self._parse_error_messages(error_source) or no_rate_message
                if warning_messages:
                    error_message = '\n'.join(warning_messages) + '\n' + error_message
                return {'error_found': error_message}

            rate = rate_json['rate_response']['rates'][0]
            for price_fields in ['shipping', 'insurance', 'confirmation', 'other']:
                total_price += self._convert_amount(rate.get(f'{price_fields}_amount') or {}, target_currency)
            if rate.get('warning_messages'):
                warning_messages.append(self._parse_error_messages(rate))

        return_data = {'price': total_price}
        if warning_messages:
            return_data['warning_message'] = '\n'.join(warning_messages)
        return return_data

    def _send_shipping(self, recipient, shipper, picking):
        """ Returns a dictionary containing:
        - Price of the shipment
        - All tracking numbers for each package
        - Label IDs to use for returns and cancellation.
        url: v2/labels
        """
        self._check_products(picking.move_line_ids.product_id)
        default_package = self.carrier.shipstation_default_package_type_id
        packages = self.carrier._get_packages_from_picking(picking, default_package)
        package_groups = self._group_packages(packages)

        tracking_numbers = []
        label_urls = []
        label_ids = []
        total_price = 0.0
        order_currency = picking.sale_id.currency_id or picking.company_id.currency_id

        for group in package_groups:
            label_json = self._create_shipment_label(recipient, shipper, picking, group)
            total_price += self._sum_label_costs(label_json, order_currency)
            label_ids.append(label_json['label_id'])
            for package in label_json.get('packages', []):
                tracking_number = package.get('tracking_number')
                if not tracking_number:
                    continue
                tracking_numbers.append(tracking_number)
                label_urls.append(self._build_label_attachment(
                    package['label_download'], self.carrier._get_delivery_label_prefix(), tracking_number,
                ))

        logmessage = Markup(
            "{header}<br/><b>{tracking_header}</b> {tracking_numbers}<br/>",
        ).format(
            header=picking.env._("Shipment created into ShipStation:"),
            tracking_header=picking.env._("Tracking Numbers:"),
            tracking_numbers=format_list(picking.env, tracking_numbers),
        )

        picking.message_post(body=logmessage, attachments=label_urls)

        return {
            'exact_price': total_price,
            'tracking_number': ','.join(tracking_numbers),
            'label_ids': ','.join(label_ids),
        }

    def _create_shipment_label(self, recipient, shipper, picking, packages):
        """ Performs the actual sending of the package to ShipStation.
        url: v2/labels
        """
        package_data, item_data = self._prepare_package_information(packages)
        shipping_data = {
            'shipment': {
                'create_sales_order': True,
                'external_shipment_id': picking.sale_id.name or picking.name,
                'carrier_id': self.carrier.shipstation_carrier_code,
                'service_code': self.carrier.shipstation_service_code,
                'ship_to': self._prepare_address_values(recipient),
                'ship_from': self._prepare_address_values(shipper),
                'insurance_provider': self.carrier.shipstation_insurance_provider or 'none',
                'confirmation': self.carrier.shipstation_confirmation_type or 'none',
                'packages': package_data,
                'items': item_data,
            },
            'is_return_label': False,
            'validate_address': 'no_validation',
            'label_download_type': 'inline',
            'label_format': self.carrier.shipstation_label_file_type.lower(),
            'display_scheme': 'label',
            'label_layout': self.carrier.shipstation_label_layout,
        }
        if self.carrier.shipstation_additional_handling:
            shipping_data['shipment']['advanced_options'] = {
                'additional_handling': True,
            }

        if shipper.country_id != recipient.country_id:
            shipping_data['shipment']['customs'] = {
                'contents': 'merchandise',
                'non_delivery': 'return_to_sender',
            }

        label_json = self.__make_api_request("POST", "v2/labels", data=shipping_data)
        if not label_json or label_json.get('errors'):
            raise UserError(self._parse_error_messages(label_json))
        return label_json

    def _cancel_shipment(self, picking):
        """ Cancels the individual picking and all orders attached.
        For multi-package shipments ShipStation cascades the void to sibling labels,
        but rather than trusting that cascade silently we void each label and treat
        an "already refunded/voided" response as success.
        url: v2/labels/{label_id}/void
        """
        if not picking.shipstation_label_ref:
            raise UserError(picking.env._("No label reference found on the picking. Unable to cancel shipment."))
        label_ids = picking.shipstation_label_ref.split(',')
        tracking_numbers = (picking.carrier_tracking_ref or '').split(',')
        # A label can cover several packages, so pair them only when the counts match.
        all_trackings = picking.carrier_tracking_ref or ''
        paired = len(label_ids) == len(tracking_numbers)
        warnings = {}

        for index, label_id in enumerate(label_ids):
            tracking_number = tracking_numbers[index] if paired else all_trackings
            void_response = self.__make_api_request('PUT', f'v2/labels/{label_id}/void')
            errors = void_response.get('errors') or []
            top_message = void_response.get('message') or ''
            already_voided = 'already' in top_message.lower() and (
                'refunded' in top_message.lower() or 'voided' in top_message.lower()
            )
            if (errors or not void_response.get('approved')) and not already_voided:
                parts = [e.get('message') for e in errors if e.get('message')]
                if top_message:
                    parts.append(top_message)
                warnings[label_id] = {
                    'message': '\n'.join(parts) or self.carrier.env._(
                        "Unable to cancel for an unknown reason. Please try again or investigate in your ShipStation portal.",
                    ),
                    'tracking_number': tracking_number,
                }
        return warnings

    def _return_shipment(self, picking, log_picking=None):
        """ Generates a return label when requested. As this can charge on label
        creation, we notify the price to the user in the chatter.

        :param picking: the outgoing delivery that holds the ShipStation label
            reference the return is built from.
        :param log_picking: the picking the return label and chatter are attached
            to (the return picking on the manual flow). Defaults to ``picking``.
        url: v2/labels/{label_id}/return
        """
        log_picking = log_picking or picking
        if not picking.shipstation_label_ref:
            raise UserError(picking.env._("No label reference found on the picking. Unable to create return shipment."))

        original_label_ids = picking.shipstation_label_ref
        payload = {
            'charge_event': 'carrier_default',
            'label_download_type': 'inline',
            'label_format': self.carrier.shipstation_label_file_type.lower(),
            'display_scheme': 'label',
            'label_layout': self.carrier.shipstation_label_layout,
        }
        order_currency = log_picking.sale_id.currency_id or log_picking.company_id.currency_id
        tracking_numbers = []
        label_urls = []
        label_ids = []
        total_price = 0.0
        for label_id in original_label_ids.split(','):
            return_json = self.__make_api_request('POST', f'v2/labels/{label_id}/return', data=payload)
            if not return_json or return_json.get('errors'):
                raise UserError(self._parse_error_messages(return_json))

            total_price += self._sum_label_costs(return_json, order_currency)
            label_ids.append(return_json['label_id'])
            tracking_number = return_json.get('tracking_number')
            if not tracking_number:
                continue
            tracking_numbers.append(tracking_number)
            label_urls.append(self._build_label_attachment(
                return_json['label_download'], self.carrier.get_return_label_prefix(), tracking_number,
            ))

        logmessage = Markup(
            "{header}<br/><b>{tracking_header}</b> {tracking_numbers}<br/>{return_cost}",
        ).format(
            header=log_picking.env._("Return shipment(s) created into ShipStation:"),
            tracking_header=log_picking.env._("Tracking Numbers:"),
            tracking_numbers=format_list(log_picking.env, tracking_numbers),
            return_cost=log_picking.env._("Cost: %(price).2f %(currency)s", price=total_price, currency=order_currency.name),
        )

        log_picking.message_post(body=logmessage, attachments=label_urls)

        return {
            'exact_price': total_price,
            'tracking_number': ','.join(tracking_numbers),
            'label_ids': ','.join(label_ids),
        }

    # -------------------------------------------------------------------------
    # API HELPERS
    # -------------------------------------------------------------------------

    def _group_packages(self, packages):
        """Group packages for shipment based on multi-package support."""
        if self.carrier.shipstation_supports_multipackage or len(packages) <= 1:
            return [packages]
        return [[pkg] for pkg in packages]

    def _convert_amount(self, amount_data, target_currency):
        """Convert a ShipStation ``{'currency': ..., 'amount': ...}`` payload into
        ``target_currency``. ShipStation quotes in its account currency (e.g. USD),
        which is not necessarily the Odoo company/order currency."""
        amount = amount_data.get('amount') or 0.0
        currency_name = (amount_data.get('currency') or '').upper()
        if not amount or not currency_name or not target_currency:
            return amount
        if currency_name not in self._currency_cache:
            self._currency_cache[currency_name] = self.carrier.env['res.currency'].with_context(
                active_test=False,
            ).search([('name', '=', currency_name)], limit=1)
        source_currency = self._currency_cache[currency_name]
        if not source_currency or source_currency == target_currency:
            return amount
        company = self.carrier.company_id or self.carrier.env.company
        return source_currency._convert(amount, target_currency, company)

    def _sum_label_costs(self, response, target_currency):
        """Sum a label/return response's shipment and insurance costs, each converted
        from its own ShipStation currency into ``target_currency``."""
        return sum(
            self._convert_amount(response[f'{key}_cost'], target_currency)
            for key in ('shipment', 'insurance')
        )

    def _build_label_attachment(self, label_download, prefix, tracking_number):
        """Decode an inline base64 label into a ``(filename, bytes)`` attachment tuple."""
        label_data = b64decode(label_download['href'].split(',')[1])
        filename = '%s-%s.%s' % (prefix, tracking_number, self.carrier.shipstation_label_file_type.lower())
        return (filename, label_data)

    def _get_products_from_package(self, package, original_weight_uom, target_weight_uom):
        return [{
                'description': comm.product_id.name,
                'quantity': int(comm.qty),
                'value': {
                    'currency': package.currency_id.name,
                    'amount': comm.monetary_value,
                },
                'weight': {
                    'value': original_weight_uom._compute_quantity(comm.product_id.weight, target_weight_uom),
                    'unit': 'pound',
                },
                'harmonized_tariff_code': comm.product_id.hs_code or '',
                'country_of_origin': comm.country_of_origin or '',
                'sku': comm.product_id.default_code or '',
            } for comm in package.commodities]

    def _prepare_package_information(self, packages):
        original_weight_uom = self.carrier.env['product.template'].sudo()._get_weight_uom_id_from_ir_config_parameter()
        target_weight_uom = self.carrier.env.ref('uom.product_uom_lb')
        original_length_uom = self.carrier.env['product.template'].sudo()._get_length_uom_id_from_ir_config_parameter()
        target_length_uom = self.carrier.env.ref('uom.product_uom_inch')
        packages_data = []
        items_data = []
        for package in packages:
            if any(dim <= 0 for dim in (package.dimension['length'], package.dimension['width'], package.dimension['height'])):
                raise UserError(self.carrier.env._('Length, Width, and Height is necessary for a ShipStation Package.'))
            weight = package.weight
            weight_data = {
                'value': original_weight_uom._compute_quantity(weight, target_weight_uom),
                'unit': 'pound',
            }
            # Convert dimensions to inches
            dimensions = {
                'unit': 'inch',
                'length': original_length_uom._compute_quantity(package.dimension['length'], target_length_uom),
                'width': original_length_uom._compute_quantity(package.dimension['width'], target_length_uom),
                'height': original_length_uom._compute_quantity(package.dimension['height'], target_length_uom),
            }

            products = self._get_products_from_package(package, original_weight_uom, target_weight_uom)

            # Compute cost of package
            value = sum(comm.monetary_value * comm.qty for comm in package.commodities)
            insurance = float_round(value * self.carrier.shipping_insurance / 100, 2)
            packages_data.append({
                'package_code': package.packaging_type,
                'weight': weight_data,
                'dimensions': dimensions,
                'insured_value': {'currency': package.currency_id.name, 'amount': insurance},
                'products': products,
            })
            items_data.extend({
                'name': product['description'],
                'sku': product['sku'],
                'quantity': product['quantity'],
                'weight': product['weight'],
                'value': product['value'],
            } for product in products)
        return packages_data, items_data

    def _prepare_address_values(self, partner):
        if not partner:
            raise UserError(self.carrier.env._("Partner information is required to get rate."))
        return {
            'name': partner.name,
            'phone': partner.phone,
            'email': partner.email,
            'address_line1': partner.street,
            'address_line2': partner.street2 or '',
            'city_locality': partner.city,
            'state_province': partner.state_id.code if partner.state_id else '',
            'postal_code': partner.zip,
            'country_code': partner.country_id.code,
        }

    def _check_products(self, products):
        bad_products = products.filtered(lambda prod: not prod.weight and prod.type == 'consu').mapped('name')
        if bad_products:
            raise UserError(products.env._(
                "ShipStation Error: The following products don't have weights set: %(product_names)s",
                product_names=bad_products,
            ))
