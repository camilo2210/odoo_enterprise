# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import json
from json import JSONDecodeError

import re

import requests
from requests import RequestException

from odoo import _, fields
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_repr, remove_accents

FEDEX_API_PROD_URL = 'https://apis.fedex.com/'
FEDEX_API_TEST_URL = 'https://apis-sandbox.fedex.com/'

IAP_PATH = 'api/fedex_rest/1/send/'

ENDPOINT_ACCOUNT_REGISTRATION = re.compile(r'registration\/v2\/(?:(?:address|invoice|pin)\/keys|customerkeys\/pin)generation')

# Why using standardized ISO codes? It's way more fun to use made up codes...
# https://developer.fedex.com/api/en-us/guides/api-reference.html#currencycodes
FEDEX_CURR_MATCH = {
    'XCD': 'ECD',
    'MXN': 'NMP',
    'KYD': 'CID',
    'CHF': 'SFR',
    'DOP': 'RDD',
    'JPY': 'JYE',
    'KRW': 'WON',
    'SGD': 'SID',
    'CLP': 'CHP',
    'JMD': 'JAD',
    'KWD': 'KUD',
    'AED': 'DHS',
    'TWD': 'NTD',
    'ARS': 'ARN',
    'VES': 'VEF',
    # 'LVL': 'EUR',
    # 'UYU': 'UYP',
    'GBP': 'UKL',
    # 'IDR': 'RPA',
}

FEDEX_MX_STATE_MATCH = {
    'AGU': 'AG',
    'BCN': 'BC',
    'BCS': 'BS',
    'CAM': 'CM',
    'CHH': 'CH',
    'CHP': 'CS',
    'CMX': 'DF',
    'COA': 'CO',
    'COL': 'CL',
    'DUR': 'DG',
    'GRO': 'GR',
    'GUA': 'GT',
    'HID': 'HG',
    'JAL': 'JA',
    'MEX': 'EM',
    'MIC': 'MI',
    'MOR': 'MO',
    'NAY': 'NA',
    'NLE': 'NL',
    'OAX': 'OA',
    'PUE': 'PU',
    'QUE': 'QE',
    'ROO': 'QR',
    'SIN': 'SI',
    'SLP': 'SL',
    'SON': 'SO',
    'TAB': 'TB',
    'TAM': 'TM',
    'TLA': 'TL',
    'VER': 'VE',
    'YUC': 'YU',
    'ZAC': 'ZA'
}

FEDEX_AE_STATE_MATCH = {
    'AZ': 'AB',
    'AJ': 'AJ',
    'DU': 'DU',
    'FU': 'FU',
    'RK': 'RA',
    'SH': 'SH',
    'UQ': 'UM',
}

FEDEX_STOCK_TYPE_MATCH = {
    'PAPER_4X6.75': 'PAPER_4X675',
    'PAPER_7X4.75': 'PAPER_7X475',
    'PAPER_8.5X11_BOTTOM_HALF_LABEL': 'PAPER_85X11_BOTTOM_HALF_LABEL',
    'PAPER_8.5X11_TOP_HALF_LABEL': 'PAPER_85X11_TOP_HALF_LABEL',
    'STOCK_4X6.75': 'STOCK_4X675',
    'STOCK_4X6.75_LEADING_DOC_TAB': 'STOCK_4X675_LEADING_DOC_TAB',
    'STOCK_4X6.75_TRAILING_DOC_TAB': 'STOCK_4X675_TRAILING_DOC_TAB',
}


class FedexRequest:
    def __init__(self, carrier):
        ICP = carrier.env['ir.config_parameter'].sudo()

        self.carrier = carrier.sudo()
        iap_url = ICP.get_str(
            "delivery_fedex_certified.fedex_iap_prod_url" if self.carrier.prod_environment
            else "delivery_fedex_certified.fedex_iap_test_url"
        )
        self.iap_url = iap_url + IAP_PATH if iap_url else False
        self.base_url = FEDEX_API_PROD_URL if self.carrier.prod_environment else FEDEX_API_TEST_URL
        self._dbuuid = ICP.get_str('database.uuid')

        # Used for local testing + delete iap ir.config_parameter
        self._integrator_key = ICP.get_str("delivery_fedex_certified.integrator_key")
        self._integrator_secret = ICP.get_str("delivery_fedex_certified.integrator_secret")

        self.session = requests.Session()

    def _send_fedex_request(self, endpoint, json_data=None, method='POST', headers=None):
        endpoint = endpoint.lstrip('/')
        is_account_registration = bool(ENDPOINT_ACCOUNT_REGISTRATION.fullmatch(endpoint))
        is_oauth = endpoint == 'oauth/token'
        is_authenticated_call = not is_account_registration and not is_oauth

        if is_authenticated_call and not self.carrier.fedex_certified_account_id._is_eula_agreed():
            raise ValidationError(_('You cannot proceed with the FedEx API until you have fully agreed to the terms of the FedEx End User Licence Agreement (EULA).'))

        request_headers = {**(headers or {})}
        if is_authenticated_call:
            request_headers['Authorization'] = f"Bearer {self._get_access_token()}"
        url = self.base_url + endpoint
        params = None

        # Redirect oauth call to iap proxy
        if not is_authenticated_call and not self._integrator_key and self.iap_url:
            url = self.iap_url + endpoint
            params = {'dbuuid': self._dbuuid}

        self.carrier.log_xml("%s %s\n%s\n\n%s" % (
            method,
            url,
            '\n'.join(f'{k}: {v}' for k, v in request_headers.items()),
            json.dumps(json_data),
        ), 'fedex_certified_request')

        try:
            response = self.session.request(method, url, headers=request_headers, json=json_data, params=params, timeout=15)
        except RequestException as e:
            self.carrier.log_xml(f"RequestException: {e}", 'fedex_certified_response')
            raise ValidationError(_('Something went wrong, please try again later')) from None

        self.carrier.log_xml("%s %s\n%s\n\n%s" % (
            response.status_code,
            response.reason,
            '\n'.join(f'{k}: {v}' for k, v in response.headers.items()),
            response.text,
        ), 'fedex_certified_response')

        try:
            response_data = response.json()
        except JSONDecodeError:
            raise ValidationError(_('Could not decode response')) from None

        if 'errors' in response_data or 'error' in response_data:
            raise ValidationError(self._process_errors(response_data))

        return response_data

    def _process_errors(self, res_body):
        errors = res_body.get('errors', [])
        if res_body.get('error'):
            errors += res_body.get('error')
        if isinstance(errors, dict):  # For ETD : Thanks to FedEx for the inconsistency between their doc and actual response
            errors = [errors]
        err_msgs = []
        for err in errors:
            if isinstance(err, dict) and 'message' in err:
                error = err['message']
                if 'code' in err:
                    error += f' ({err["code"]})'
                err_msgs.append(error)
            else:
                err_msgs.append(f"{err}")
        return ','.join(err_msgs)

    def _process_alerts(self, response):
        messages = []
        alerts = response.get('alerts', [])
        if 'rateReplyDetails' in response:
            alerts += response['rateReplyDetails'][0].get('customerMessages', [])
        for alert in alerts:
            messages.append(f"{alert['message']} ({alert['code']})")

        return '\n'.join(messages)

    def _get_access_token(self):
        if self.carrier.fedex_certified_account_id._get_valid_token():
            return self.carrier.fedex_certified_account_id._get_valid_token()

        if not self._integrator_key and (not self.carrier.fedex_certified_account_id.child_key or not self.carrier.fedex_certified_account_id.child_secret):
            raise ValidationError(_('You must select or register your FedEx account on the carrier first'))

        payload = {
            'grant_type': 'client_credentials' if not self.carrier.fedex_certified_account_id.child_key else 'csp_credentials',
        }
        if self.carrier.fedex_certified_account_id.child_key and self.carrier.fedex_certified_account_id.child_secret:
            payload['child_Key'] = self.carrier.fedex_certified_account_id.child_key
            payload['child_secret'] = self.carrier.fedex_certified_account_id.child_secret
        if self._integrator_key and self._integrator_secret:
            payload['client_id'] = self._integrator_key
            payload['client_secret'] = self._integrator_secret

        response_data = self._send_fedex_request("/oauth/token", payload)
        # Only store specific customer account oauth
        if self.carrier.fedex_certified_account_id.child_key and self.carrier.fedex_certified_account_id.child_secret:
            self.carrier.fedex_certified_account_id._set_token(response_data['access_token'], response_data.get('expires_in', 3599))
        return response_data['access_token']

    def _account_registration(self, registration_type, data, account_auth_token=None):
        """
        Register an account with FedEx using the specified registration type.
        This method constructs the appropriate endpoint based on the registration type
        and sends a registration request to FedEx's registration API.

        :param str registration_type: The type of registration to perform.
            Valid values are:

            * ``"address"``: Address Validation - Mandatory first step and used for technical support validation
            * ``"invoice"``: Invoice Validation
            * ``"pin_generation"``: PIN Generation
            * ``"pin"``: PIN Validation

        :param dict data: The registration data to be sent to FedEx.

        :returns dict: The response from the FedEx registration API.
        :raises UserError: If the registration_type is invalid.
        :raises ValidationError: If the registration request fails or if the response cannot be decoded.
        """
        if registration_type not in ["address", "invoice", "pin_generation", "pin"]:
            raise ValidationError(_('Invalid registration type'))

        endpoint = "/registration/v2/"
        if registration_type == 'pin_generation':
            endpoint += "customerkeys/pingeneration"
        else:
            endpoint += f"{registration_type}/keysgeneration"

        headers = {}
        if account_auth_token:
            headers['accountAuthToken'] = account_auth_token
        if self._integrator_key:
            headers['Authorization'] = f"Bearer {self._get_access_token()}"
        return self._send_fedex_request(endpoint, data, headers=headers)['output']

    def _parse_state_code(self, state_code, country_code):
        if country_code == 'CH':
            # For Switzerland, keep the part before the hyphen
            return state_code.split('-')[0]
        else:
            # For other countries, keep the part after the hyphen
            split_code = state_code.split('-')
            if split_code[0] == country_code and len(split_code) > 1:
                return split_code[1]
            else:
                return state_code

    def _get_location_from_partner(self, partner, check_residential=False):
        res = {'countryCode': partner.country_id.code}
        if partner.city:
            res['city'] = remove_accents(partner.city)
        if partner.zip:
            res['postalCode'] = partner.zip
        if partner.state_id:
            state_code = self._parse_state_code(partner.state_id.code, partner.country_id.code)
        # need to adhere to two character length state code
            if partner.country_id.code == 'MX':
                state_code = FEDEX_MX_STATE_MATCH[state_code]
            if partner.country_id.code == 'AE':
                state_code = FEDEX_AE_STATE_MATCH.get(state_code, state_code)
            if partner.country_id.code == 'IN' and partner.state_id.code == 'UK':
                state_code = 'UT'
            if len(state_code) <= 2:
                res['stateOrProvinceCode'] = state_code
        if check_residential:
            setting = self.carrier.fedex_certified_residential_address
            if setting == 'always' or (setting == 'check' and self._check_residential_address({**res, 'streetLines': [partner.street, partner.street2]})):
                res['residential'] = True
        return res

    def _check_residential_address(self, address):
        if not address['streetLines'][1]:
            del address['streetLines'][1]
        result = self._send_fedex_request('/address/v1/addresses/resolve', {
            'addressesToValidate': [{'address': address}]
        })
        return result['output']['resolvedAddresses'][0]['classification'] != 'BUSINESS'  # We assume residential until proven otherwise

    def _get_address_from_partner(self, partner, check_residential=False):
        res = self._get_location_from_partner(partner, check_residential)
        res['streetLines'] = [remove_accents(partner.street)]
        if partner.street2:
            res['streetLines'].append(remove_accents(partner.street2))
        return res

    def _get_contact_from_partner(self, partner, company_partner=False):
        res = {'phoneNumber': partner.phone}
        if company_partner and not res['phoneNumber']:
            # Fallback to phone on the company if none on the WH
            res['phoneNumber'] = company_partner.phone
        if company_partner:
            # WH partner: personName is the WH partner's name. companyName is the
            # parent company's name when the WH partner is a sub-contact (a person
            # at the warehouse); otherwise fall back to the WH partner's own name
            # (legacy single-partner-per-company setups).
            res['personName'] = partner.name[:70]
            if partner != company_partner and partner.parent_id:
                res['companyName'] = partner.parent_id.name[:35]
            else:
                res['companyName'] = partner.name[:35]
        elif partner.is_company:
            res['companyName'] = partner.name[:35]
            res['personName'] = partner.name[:70]
        else:
            res['personName'] = partner.name[:70]
            if partner.parent_id:
                res['companyName'] = partner.parent_id.name[:35]
            elif partner.parent_name:
                res['companyName'] = partner.parent_name[:35]
        if partner.email:
            res['emailAddress'] = partner.email
        elif company_partner and company_partner.email:
            res['emailAddress'] = company_partner.email
        return res

    def _get_package_info(self, package):
        res = {
            'weight': {
                'units': self.carrier.fedex_certified_weight_unit,
                'value': self.carrier._fedex_certified_convert_weight(package.weight)
            },
            'customerReferences': [],
        }
        if int(package.dimension['length']) or int(package.dimension['width']) or int(package.dimension['height']):
            # FedEx will raise a warning when mixing imperial and metric units (MIXED.MEASURING.UNITS.INCLUDED).
            # So we force the dimension unit based on the selected weight unit on the delivery method.
            res['dimensions'] = {
                'units': 'IN' if self.carrier.fedex_certified_weight_unit == 'LB' else 'CM',
                'length': int(package.dimension['length']),
                'width': int(package.dimension['width']),
                'height': int(package.dimension['height']),
            }
        if self.carrier.shipping_insurance:
            res['declaredValue'] = {
                'amount': float_repr(package.total_cost * self.carrier.shipping_insurance / 100, 2),
                'currency': FEDEX_CURR_MATCH.get(package.currency_id.name, package.currency_id.name),
            }
        return res

    def _get_detailed_package_info(self, package, customPackaging, order_no=False):
        res = self._get_package_info(package)
        if customPackaging:
            res['subPackagingType'] = 'PACKAGE'
        description = ', '.join([c.product_id.name for c in package.commodities])
        res['itemDescription'] = description[:50]
        res['itemDescriptionForClearance'] = description
        if package.picking_id:
            res['customerReferences'].append({
                'customerReferenceType': 'CUSTOMER_REFERENCE',
                'value': package.picking_id.name,
            })
        if order_no:
            res['customerReferences'].append({
                'customerReferenceType': 'P_O_NUMBER',
                'value': order_no
            })
        return res

    def _get_commodities_info(self, commodity, currency):
        res = {
            'description': commodity.product_id.name[:450],
            'customsValue': ({'amount': commodity.monetary_value * commodity.qty, 'currency': currency}),
            'unitPrice': ({'amount': commodity.monetary_value, 'currency': currency}),
            'countryOfManufacture': commodity.country_of_origin,
            'weight': {
                'units': self.carrier.fedex_certified_weight_unit,
                'value': self.carrier._fedex_certified_convert_weight(commodity.product_id.weight),
            },
            'quantity': commodity.qty,
            'quantityUnits': commodity.product_id.uom_id.fedex_code,
            'numberOfPieces': 1,
        }
        if commodity.product_id.hs_code:
            res['harmonizedCode'] = commodity.product_id.hs_code
        return res

    def _get_tins_from_partner(self, partner, custom_vat=False):
        def _transform_vat_to_fedex_format(vat_number):
            if not vat_number:
                return ''
            if len(vat_number) > 18:
                return re.sub(r'[^A-Za-z0-9 ]', '', vat_number)
            return vat_number

        res = []
        if custom_vat:
            res.append({
                'number': _transform_vat_to_fedex_format(self.carrier.fedex_certified_override_shipper_vat),
                'tinType': 'BUSINESS_UNION'
            })
        if partner.vat and partner.is_company:
            res.append({'number': _transform_vat_to_fedex_format(partner.vat), 'tinType': 'BUSINESS_NATIONAL'})
        elif partner.parent_id and partner.parent_id.vat and partner.parent_id.is_company:
            res.append({'number': _transform_vat_to_fedex_format(partner.parent_id.vat), 'tinType': 'BUSINESS_NATIONAL'})
        return res

    def _get_shipping_price(self, ship_from, ship_to, packages, currency):
        fedex_currency = FEDEX_CURR_MATCH.get(currency, currency)
        request_data = {
            'accountNumber': {'value': self.carrier.fedex_certified_account_number},
            'requestedShipment': {
                'rateRequestType': ['PREFERRED'],
                'preferredCurrency': fedex_currency,
                'pickupType': self.carrier.fedex_certified_droppoff_type,
                'serviceType': self.carrier.fedex_certified_service_type,
                'packagingType': packages[0].packaging_type,
                'shipper': {'address': self._get_location_from_partner(ship_from)},
                'recipient': {'address': self._get_location_from_partner(ship_to, True)},
                'requestedPackageLineItems': [self._get_package_info(p) for p in packages],
                'customsClearanceDetail': {
                    'commercialInvoice': {'shipmentPurpose': 'SOLD'},
                    'commodities': [self._get_commodities_info(c, fedex_currency) for pkg in packages for c in pkg.commodities],
                    'freightOnValue': 'CARRIER_RISK' if self.carrier.shipping_insurance == 100 else 'OWN_RISK',
                    'dutiesPayment': {'paymentType': 'SENDER'}  # Only allowed value...
                }
            }
        }
        self._add_extra_data_to_request(request_data, 'rate')
        res = self._send_fedex_request("/rate/v1/comprehensiverates/quotes", request_data)['output']

        # Always take the first rated shipment FedEx returns. When the request
        # carries both a `preferredCurrency` AND a `rateRequestType` mix, FedEx
        # may return several entries (ACCOUNT, LIST, PREFERRED_CURRENCY, …) —
        # we want a deterministic pick + a known source currency to convert
        # from. The first entry's `currency` is what we trust.
        rate = res['rateReplyDetails'][0]['ratedShipmentDetails'][0]
        price = rate.get('totalNetChargeWithDutiesAndTaxes') or rate.get('totalNetCharge', 0.0)

        # Convert from the rate's currency (may be FedEx's invented code like
        # JYE, UKL, SFR…) back into the sale order's currency. Skip when
        # source and target match.
        extra_alerts = []
        curr_fdx = rate.get('currency') or fedex_currency
        curr_match = [k for k, v in FEDEX_CURR_MATCH.items() if v == curr_fdx]
        rate_currency_code = curr_match[0] if curr_match else curr_fdx
        if rate_currency_code != currency:
            env = self.carrier.env
            # active_test=False so we can distinguish "missing" from "inactive"
            # and surface a useful alert instead of silently returning the price
            # in the wrong currency.
            currencies = env['res.currency'].with_context(active_test=False).search(
                [('name', 'in', [rate_currency_code, currency])])
            rate_currency = currencies.filtered(lambda c: c.name == rate_currency_code)
            so_currency = currencies.filtered(lambda c: c.name == currency)
            for label, code, curr in (('rate', rate_currency_code, rate_currency),
                                      ('order', currency, so_currency)):
                if not curr:
                    extra_alerts.append(_(
                        "Currency %(code)s (FedEx %(label)s currency) is not "
                        "registered in this database; the price is returned "
                        "as-is in %(rate_code)s.",
                        code=code, label=label, rate_code=rate_currency_code,
                    ))
                elif not curr.active:
                    extra_alerts.append(_(
                        "Currency %(code)s (FedEx %(label)s currency) is "
                        "inactive — activate it in Settings → Currencies "
                        "so the rate can be converted to the sale order currency.",
                        code=code, label=label,
                    ))
            if (rate_currency and rate_currency.active
                    and so_currency and so_currency.active
                    and rate_currency != so_currency):
                price = rate_currency._convert(
                    price, so_currency, self.carrier.company_id, fields.Date.today(),
                )

        alert_message = self._process_alerts(res)
        if extra_alerts:
            extra = '\n'.join(extra_alerts)
            alert_message = (alert_message + '\n' + extra) if alert_message else extra

        return {
            'price': price,
            'alert_message': alert_message,
        }

    def _ship_package(self, ship_from_wh, ship_from_company, ship_to, sold_to, packages, currency, order_no, customer_ref, picking_no, incoterms, freight_charge):
        fedex_currency = FEDEX_CURR_MATCH.get(currency, currency)
        package_type = packages[0].packaging_type
        label_stock_type = FEDEX_STOCK_TYPE_MATCH.get(self.carrier.fedex_certified_label_stock_type, self.carrier.fedex_certified_label_stock_type)
        request_data = {
            'accountNumber': {'value': self.carrier.fedex_certified_account_number},
            'labelResponseOptions': 'LABEL',
            'requestedShipment': {
                'rateRequestType': ['PREFERRED'],
                'preferredCurrency': fedex_currency,
                'pickupType': self.carrier.fedex_certified_droppoff_type,
                'serviceType': self.carrier.fedex_certified_service_type,
                'packagingType': package_type,
                'shippingChargesPayment': {'paymentType': 'SENDER'},
                'labelSpecification': {'labelStockType': label_stock_type, 'imageType': self.carrier.fedex_certified_label_file_type},
                'shipper': {
                    'address': self._get_address_from_partner(ship_from_wh),
                    'contact': self._get_contact_from_partner(ship_from_wh, ship_from_company),
                    'tins': self._get_tins_from_partner(ship_from_company, self.carrier.fedex_certified_override_shipper_vat),
                },
                'recipients': [{
                    'address': self._get_address_from_partner(ship_to, True),
                    'contact': self._get_contact_from_partner(ship_to),
                    'tins': self._get_tins_from_partner(ship_to),
                }],
                'requestedPackageLineItems': [self._get_detailed_package_info(p, package_type == 'YOUR_PACKAGING', order_no) for p in packages],
                'customsClearanceDetail': {
                    'dutiesPayment': {'paymentType': self.carrier.fedex_certified_duty_payment},
                    'commodities': [self._get_commodities_info(c, fedex_currency) for pkg in packages for c in pkg.commodities],
                    'commercialInvoice': {
                        'shipmentPurpose': 'SOLD',
                        'originatorName': ship_from_company.name,
                        'comments': ['', picking_no],  # First one is special instructions
                    },
                }
            }
        }
        if freight_charge:
            request_data['requestedShipment']['customsClearanceDetail']['commercialInvoice']['freightCharge'] = {
                'amount': freight_charge,
                'currency': fedex_currency,
            }
        if incoterms:
            request_data['requestedShipment']['customsClearanceDetail']['commercialInvoice']['termsOfSale'] = incoterms
        if customer_ref:
            request_data['requestedShipment']['customsClearanceDetail']['commercialInvoice']['customerReferences'] = [{
                'customerReferenceType': 'CUSTOMER_REFERENCE',
                'value': customer_ref,
            }]
        if request_data['requestedShipment']['shipper']['address']['countryCode'] == 'IN' and request_data['requestedShipment']['recipients'][0]['address']['countryCode'] == 'IN':
            request_data['requestedShipment']['customsClearanceDetail']['freightOnValue'] = 'CARRIER_RISK' if self.carrier.shipping_insurance == 100 else 'OWN_RISK'
        if (sold_to and sold_to != ship_to
                and sold_to.street and sold_to.city and sold_to.country_id):
            request_data['requestedShipment']['soldTo'] = {
                'address': self._get_address_from_partner(sold_to),
                'contact': self._get_contact_from_partner(sold_to),
                'tins': self._get_tins_from_partner(sold_to),
            }
            request_data['requestedShipment']['customsClearanceDetail']['importerOfRecord'] = {
                'address': self._get_address_from_partner(sold_to),
                'contact': self._get_contact_from_partner(sold_to),
                'tins': self._get_tins_from_partner(sold_to),
            }
        if ship_to.vat or ship_to.parent_id.vat:
            request_data['requestedShipment']['customsClearanceDetail']['recipientCustomsId'] = {
                'type': 'COMPANY',
                'value': ship_to.vat or ship_to.parent_id.vat,
            }
        if self.carrier.fedex_certified_email_notifications and ship_to.email:
            request_data['requestedShipment']['emailNotificationDetail'] = {
                'aggregationType': 'PER_PACKAGE',
                'emailNotificationRecipients': [{
                    'emailNotificationRecipientType': 'RECIPIENT',
                    'emailAddress': ship_to.email,
                    'name': ship_to.name,
                    'notificationFormatType': 'HTML',
                    'notificationType': 'EMAIL',
                    'notificationEventType': ['ON_DELIVERY', 'ON_EXCEPTION', 'ON_SHIPMENT', 'ON_TENDER', 'ON_ESTIMATED_DELIVERY']
                }]
            }
        if self.carrier.fedex_certified_documentation_type != 'none':
            request_data['requestedShipment']['shippingDocumentSpecification'] = {
                'shippingDocumentTypes': ['COMMERCIAL_INVOICE'],
                'commercialInvoiceDetail': {
                    'documentFormat': {'stockType': 'PAPER_LETTER', 'docType': 'PDF'}
                }
            }
        if self.carrier.fedex_certified_documentation_type == 'etd':
            request_data['requestedShipment']['shipmentSpecialServices'] = {
                "specialServiceTypes": [
                    "ELECTRONIC_TRADE_DOCUMENTS"
                ],
                "etdDetail": {
                    "requestedDocumentTypes": [
                        "COMMERCIAL_INVOICE"
                    ]
                }
            }

        self._add_extra_data_to_request(request_data, 'ship')
        res = self._send_fedex_request("/ship/v1/shipments", request_data)['output']

        try:
            shipment = res['transactionShipments'][0]
            details = shipment['completedShipmentDetail']
            pieces = shipment['pieceResponses']
            # Sometimes the shipment might be created but no pricing calculated, we just set to 0.
            price = self._decode_pricing(details['shipmentRating'], fedex_currency) if 'shipmentRating' in details else 0.0
        except KeyError:
            raise ValidationError(_('Could not decode response')) from None

        return {
            'service_info': f"{details.get('carrierCode', '')} > {details.get('serviceDescription', {}).get('description', '')} > {details.get('packagingDescription', '')}",
            'tracking_numbers': ','.join([
                t.get('trackingNumber', '')
                for pkg in details.get('completedPackageDetails', [])
                for t in pkg.get('trackingIds', [])
            ]),
            # All package-level docs (LABEL, AUXILIARY, …) for every piece +
            # every shipment-level doc (COMMERCIAL_INVOICE, …). Pre-decoded
            # and named so the caller can feed them straight into
            # `message_post(attachments=[…])`.
            'attachments': self._collect_response_attachments(shipment, pieces),
            # Legacy keys — kept so any caller still expecting them stays
            # working. Both derive from the same source as `attachments`.
            'labels': [
                (
                    p.get('trackingNumber', ''),
                    next(filter(lambda d: d.get('contentType', '') == 'LABEL', p.get('packageDocuments') or []), {}).get('encodedLabel')
                )
                for p in pieces
            ],
            'invoice': next(filter(
                lambda d: d.get('contentType', '') == 'COMMERCIAL_INVOICE',
                shipment.get('shipmentDocuments') or []
            ), {}).get('encodedLabel', ''),
            'price': price,
            'documents': ', '.join([
                f"{d.get('minimumCopiesRequired')}x {d.get('type', '')}"
                for d in details.get('documentRequirements', {}).get('generationDetails', {})
                if d.get('minimumCopiesRequired', 0)
            ]),
            'alert_message': self._process_alerts(shipment),
            'date': shipment.get('shipDatestamp', ''),
        }

    def _collect_response_attachments(self, shipment, pieces):
        """Return ``[(filename, raw_bytes), …]`` for every encoded document in
        the FedEx ship response — both per-piece ``packageDocuments`` (LABEL,
        AUXILIARY, customs slips, …) and shipment-level ``shipmentDocuments``
        (COMMERCIAL_INVOICE, PRO_FORMA_INVOICE, …).

        The earlier implementation only kept the first LABEL per piece and a
        single COMMERCIAL_INVOICE — every other document FedEx returned was
        silently dropped, which left the picking chatter missing the customs
        copies you needed for AWB printing.
        """
        attachments = []
        label_prefix = 'LabelShipping-fedex'
        doc_prefix = 'ShippingDoc-fedex'
        for p in pieces:
            tracking = p.get('trackingNumber', '')
            for d in p.get('packageDocuments') or []:
                encoded = d.get('encodedLabel')
                if not encoded:
                    continue
                content_type = d.get('contentType') or 'DOCUMENT'
                ext = (d.get('docType') or self.carrier.fedex_certified_label_file_type or 'pdf').lower()
                name = f"{label_prefix}-{content_type}-{tracking}.{ext}"
                attachments.append((name, base64.b64decode(encoded)))
        for d in shipment.get('shipmentDocuments') or []:
            encoded = d.get('encodedLabel')
            if not encoded:
                continue
            content_type = d.get('contentType') or 'DOCUMENT'
            ext = (d.get('docType') or 'pdf').lower()
            name = f"{doc_prefix}-{content_type}.{ext}"
            attachments.append((name, base64.b64decode(encoded)))
        return attachments

    def _return_package(self, ship_from, ship_to_company, ship_to_wh, packages, currency, tracking, date):
        fedex_currency = FEDEX_CURR_MATCH.get(currency, currency)
        package_type = packages[0].packaging_type
        label_stock_type = FEDEX_STOCK_TYPE_MATCH.get(self.carrier.fedex_certified_label_stock_type, self.carrier.fedex_certified_label_stock_type)
        request_data = {
            'accountNumber': {'value': self.carrier.fedex_certified_account_number},
            'labelResponseOptions': 'LABEL',
            'requestedShipment': {
                'rateRequestType': ['PREFERRED'],
                'preferredCurrency': fedex_currency,
                'pickupType': self.carrier.fedex_certified_droppoff_type,
                'serviceType': self.carrier.fedex_certified_service_type,
                'packagingType': package_type,
                'shippingChargesPayment': {'paymentType': 'SENDER'},
                'shipmentSpecialServices': {
                    'specialServiceTypes': ['RETURN_SHIPMENT'],
                    'returnShipmentDetail': {
                        'returnType': 'PRINT_RETURN_LABEL',
                        'returnAssociationDetail': {'trackingNumber': tracking, 'shipDatestamp': date},
                    }
                },
                'labelSpecification': {'labelStockType': label_stock_type, 'imageType': self.carrier.fedex_certified_label_file_type},
                'shipper': {
                    'address': self._get_address_from_partner(ship_from),
                    'contact': self._get_contact_from_partner(ship_from),
                    'tins': self._get_tins_from_partner(ship_from),
                },
                'recipients': [{
                    'address': self._get_address_from_partner(ship_to_wh, True),
                    'contact': self._get_contact_from_partner(ship_to_wh, ship_to_company),
                    'tins': self._get_tins_from_partner(ship_to_company, self.carrier.fedex_certified_override_shipper_vat),
                }],
                'requestedPackageLineItems': [self._get_detailed_package_info(p, package_type == 'YOUR_PACKAGING') for p in packages],
                'customsClearanceDetail': {
                    'dutiesPayment': {'paymentType': 'SENDER'},  # Only allowed value for returns
                    'commodities': [self._get_commodities_info(c, fedex_currency) for pkg in packages for c in pkg.commodities],
                    'customsOption': {'type': 'REJECTED'},
                }
            }
        }
        if request_data['requestedShipment']['shipper']['address']['countryCode'] == 'IN' and request_data['requestedShipment']['recipients'][0]['address']['countryCode'] == 'IN':
            request_data['requestedShipment']['customsClearanceDetail']['freightOnValue'] = 'CARRIER_RISK' if self.carrier.shipping_insurance == 100 else 'OWN_RISK'
        if self.carrier.fedex_certified_override_shipper_vat or ship_to_company.vat:
            request_data['requestedShipment']['customsClearanceDetail']['recipientCustomsId'] = {
                'type': 'COMPANY',
                'value': self.carrier.fedex_certified_override_shipper_vat or ship_to_company.vat,
            }

        self._add_extra_data_to_request(request_data, 'return')
        res = self._send_fedex_request("/ship/v1/shipments", request_data)['output']

        try:
            shipment = res['transactionShipments'][0]
            details = shipment['completedShipmentDetail']
            pieces = shipment['pieceResponses']
        except KeyError:
            raise ValidationError(_('Could not decode response')) from None

        return {
            'tracking_numbers': ','.join([
                t.get('trackingNumber', '')
                for pkg in details.get('completedPackageDetails', [])
                for t in pkg.get('trackingIds', [])
            ]),
            'attachments': self._collect_response_attachments(shipment, pieces),
            'labels': [
                (
                    p.get('trackingNumber', ''),
                    next(filter(lambda d: d.get('contentType', '') == 'LABEL', p.get('packageDocuments') or []), {}).get('encodedLabel')
                )
                for p in pieces
            ],
            'documents': ', '.join([
                f"{d.get('minimumCopiesRequired')}x {d.get('type', '')}"
                for d in details.get('documentRequirements', {}).get('generationDetails', {})
                if d.get('minimumCopiesRequired', 0)
            ]),
            'alert_message': self._process_alerts(shipment),
        }

    def _decode_pricing(self, rating_result, request_currency=False):
        actual = next(filter(
            lambda d:
                d['rateType'] in [rating_result['actualRateType'], rating_result['actualRateType'].replace("PAYOR", "PREFERRED").replace("RATED", "PREFERRED")] and
                (not request_currency or d['currency'] == request_currency),
            rating_result['shipmentRateDetails']
        ), {})
        if actual.get('totalNetChargeWithDutiesAndTaxes', False):
            return actual['totalNetChargeWithDutiesAndTaxes']
        return actual['totalNetCharge']

    def cancel_shipment(self, tracking_nr):
        res = self._send_fedex_request('/ship/v1/shipments/cancel', {
            'accountNumber': {'value': self.carrier.fedex_certified_account_number},
            'deletionControl': 'DELETE_ALL_PACKAGES',  # Cancel the entire shipment, not only the individual package.
            'trackingNumber': tracking_nr,
        }, method='PUT')['output']
        if not res.get('cancelledShipment', False):
            return {
                'delete_success': False,
                'errors_message': res.get('message', 'Cancel shipment failed. Reason unknown.'),
            }
        return {
            'delete_success': True,
            'alert_message': self._process_alerts(res),
        }

    def _add_extra_data_to_request(self, request, request_type):
        """Adds the extra data to the request.
        When there are multiple items in a list, they will all be affected by
        the change.
        """
        extra_data_input = {
            'rate': self.carrier.fedex_certified_extra_data_rate_request,
            'ship': self.carrier.fedex_certified_extra_data_ship_request,
            'return': self.carrier.fedex_certified_extra_data_return_request,
        }.get(request_type) or ''
        try:
            extra_data = json.loads('{' + extra_data_input + '}')
        except SyntaxError:
            raise UserError(_('Invalid syntax for FedEx extra data.')) from None

        def extra_data_to_request(request, extra_data):
            """Recursively merge extra_data into request.

            - dict + dict → recurse so existing nested keys are preserved
              (e.g. extra_ship's `shippingChargesPayment.payor.…` adds to
              the connector's `shippingChargesPayment.paymentType` instead
              of wiping it).
            - list + dict → apply the dict to EVERY item in the list. This
              is the documented pattern for `requestedPackageLineItems`
              and `recipients`. Without this branch a `requestedPackageLineItems:
              {packageSpecialServices: …}` in extra_ship would replace the
              connector's full list of packages with a malformed single
              dict, and FedEx returns the vague `INVALID.INPUT.EXCEPTION`
              because `requestedPackageLineItems` MUST be an array with
              `weight` per item.
            - anything else (scalar override, list-into-list, dict-into-None,
              …) → assign the new value.
            """
            for key, new_value in extra_data.items():
                current_value = request.get(key)
                if isinstance(current_value, list) and isinstance(new_value, dict):
                    for item in current_value:
                        extra_data_to_request(item, new_value)
                elif isinstance(new_value, dict) and isinstance(current_value, dict):
                    extra_data_to_request(current_value, new_value)
                else:
                    request[key] = new_value

        extra_data_to_request(request, extra_data)
