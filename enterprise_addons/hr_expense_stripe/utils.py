import hashlib
import logging
import re
from functools import lru_cache
from json import JSONDecodeError

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.tools import LazyTranslate, float_round

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)

STRIPE_VALID_JOURNAL_CURRENCIES = {
    'US': 'USD',
    'EU': 'EUR',
    'UK': 'GBP',
    'GB': 'GBP',
}

# List of countries that support Stripe Issuing
# See https://docs.stripe.com/issuing/global#local-issuing
# Note that US is not yet supported
STRIPE_SUPPORTED_COUNTRY_CODES = {
    'AT',
    'BE',
    'CY',
    'DE',
    'EE',
    'ES',
    'FI',
    'FR',
    'GB',
    'GR',
    'HR',
    'IE',
    'IT',
    'LT',
    'LU',
    'LV',
    'MT',
    'NL',
    'PT',
    'SI',
    'SK',
}

HANDLED_WEBHOOK_EVENTS = {
    ## Balance
    'balance.available',
    ## Authorization
    'issuing_authorization.created',
    'issuing_authorization.request',
    'issuing_authorization.updated',
    ## Cards
    # 'issuing_card.created',
    'issuing_card.updated',
    ## Cardholders
    # 'issuing_cardholder.updated',
    ## Disputes
    'issuing_dispute.created',
    'issuing_dispute.updated',
    'issuing_dispute.submitted',
    'issuing_dispute.closed',
    'issuing_dispute.funds_reinstated',
    'issuing_dispute.funds_rescinded',
    ## Capture transactions
    'issuing_transaction.created',
    'issuing_transaction.updated',
    # 'issuing_transaction.purchase_details_receipt_updated', TODO check if we want it
    ## Account top-ups
    # 'topup.created',
    # 'topup.updated',
    'topup.succeeded',
    # 'topup.reversed',
}

# Businesses in supported outlying territories should register for a Stripe account with the parent
# territory selected as the Country.
# See https://support.stripe.com/questions/stripe-availability-for-outlying-territories-of-supported-countries.
COUNTRY_MAPPING = {
    'MQ': 'FR',  # Martinique
    'GP': 'FR',  # Guadeloupe
    'GF': 'FR',  # French Guiana
    'RE': 'FR',  # Réunion
    'YT': 'FR',  # Mayotte
    'MF': 'FR',  # Saint-Martin
}

STRIPE_3D_SECURE_LOCALES = {
    'de',
    'en',
    'es',
    'fr',
    'it',
}

# According to https://en.wikipedia.org/wiki/ISO_4217#Minor_unit_fractions
# Taken from payment
CURRENCY_MINOR_UNITS = {
    'ADF': 2,
    'ADP': 0,
    'AED': 2,
    'AFA': 2,
    'AFN': 2,
    'ALL': 2,
    'AMD': 2,
    'ANG': 2,
    'AOA': 2,
    'AOK': 0,
    'AON': 0,
    'AOR': 0,
    'ARA': 2,
    'ARL': 2,
    'ARP': 2,
    'ARS': 2,
    'ATS': 2,
    'AUD': 2,
    'AWG': 2,
    'AYM': 0,
    'AZM': 2,
    'AZN': 2,
    'BAD': 2,
    'BAM': 2,
    'BBD': 2,
    'BDS': 2,
    'BDT': 2,
    'BEF': 2,
    'BGL': 2,
    'BGN': 2,
    'BHD': 3,
    'BIF': 0,
    'BMD': 2,
    'BND': 2,
    'BOB': 2,
    'BOP': 2,
    'BOV': 2,
    'BRB': 2,
    'BRC': 2,
    'BRE': 2,
    'BRL': 2,
    'BRN': 2,
    'BRR': 2,
    'BSD': 2,
    'BTN': 2,
    'BWP': 2,
    'BYB': 2,
    'BYN': 2,
    'BYR': 0,
    'BZD': 2,
    'CAD': 2,
    'CDF': 2,
    'CHC': 2,
    'CHE': 2,
    'CHF': 2,
    'CHW': 2,
    'CLF': 4,
    'CLP': 0,
    'CNH': 2,
    'CNT': 2,
    'CNY': 2,
    'COP': 2,
    'COU': 2,
    'CRC': 2,
    'CSD': 2,
    'CUC': 2,
    'CUP': 2,
    'CVE': 2,
    'CYP': 2,
    'CZK': 2,
    'DEM': 2,
    'DJF': 0,
    'DKK': 2,
    'DOP': 2,
    'DZD': 2,
    'ECS': 0,
    'ECV': 2,
    'EEK': 2,
    'EGP': 2,
    'ERN': 2,
    'ESP': 0,
    'ETB': 2,
    'EUR': 2,
    'FIM': 2,
    'FJD': 2,
    'FKP': 2,
    'FRF': 2,
    'GBP': 2,
    'GEK': 0,
    'GEL': 2,
    'GGP': 2,
    'GHC': 2,
    'GHP': 2,
    'GHS': 2,
    'GIP': 2,
    'GMD': 2,
    'GNF': 0,
    'GTQ': 2,
    'GWP': 2,
    'GYD': 2,
    'HKD': 2,
    'HNL': 2,
    'HRD': 2,
    'HRK': 2,
    'HTG': 2,
    'HUF': 2,
    'IDR': 2,
    'IEP': 2,
    'ILR': 2,
    'ILS': 2,
    'IMP': 2,
    'INR': 2,
    'IQD': 3,
    'IRR': 2,
    'ISJ': 2,
    'ISK': 0,
    'ITL': 0,
    'JEP': 2,
    'JMD': 2,
    'JOD': 3,
    'JPY': 0,
    'KES': 2,
    'KGS': 2,
    'KHR': 2,
    'KID': 2,
    'KMF': 0,
    'KPW': 2,
    'KRW': 0,
    'KWD': 3,
    'KYD': 2,
    'KZT': 2,
    'LAK': 2,
    'LBP': 2,
    'LKR': 2,
    'LRD': 2,
    'LSL': 2,
    'LTL': 2,
    'LTT': 2,
    'LUF': 2,
    'LVL': 2,
    'LVR': 2,
    'LYD': 3,
    'MAD': 2,
    'MAF': 2,
    'MCF': 2,
    'MDL': 2,
    'MGA': 2,
    'MGF': 0,
    'MKD': 2,
    'MMK': 2,
    'MNT': 2,
    'MOP': 2,
    'MRO': 2,
    'MRU': 2,
    'MTL': 2,
    'MUR': 2,
    'MVR': 2,
    'MWK': 2,
    'MXN': 2,
    'MXV': 2,
    'MYR': 2,
    'MZE': 2,
    'MZM': 2,
    'MZN': 2,
    'NAD': 2,
    'NGN': 2,
    'NIC': 2,
    'NIO': 2,
    'NIS': 2,
    'NLG': 2,
    'NOK': 2,
    'NPR': 2,
    'NTD': 2,
    'NZD': 2,
    'OMR': 3,
    'PAB': 2,
    'PEN': 2,
    'PES': 2,
    'PGK': 2,
    'PHP': 2,
    'PKR': 2,
    'PLN': 2,
    'PLZ': 2,
    'PRB': 2,
    'PTE': 0,
    'PYG': 0,
    'QAR': 2,
    'RHD': 2,
    'RMB': 2,
    'ROL': 0,
    'RON': 2,
    'RSD': 2,
    'RUB': 2,
    'RUR': 2,
    'RWF': 0,
    'SAR': 2,
    'SBD': 2,
    'SCR': 2,
    'SDD': 2,
    'SDG': 2,
    'SEK': 2,
    'SGD': 2,
    'SHP': 2,
    'SIT': 2,
    'SKK': 2,
    'SLE': 2,
    'SLL': 2,
    'SLS': 2,
    'SML': 0,
    'SOS': 2,
    'SRD': 2,
    'SRG': 2,
    'SSP': 2,
    'STD': 2,
    'STG': 2,
    'STN': 2,
    'SVC': 2,
    'SYP': 2,
    'SZL': 2,
    'THB': 2,
    'TJR': 0,
    'TJS': 2,
    'TMM': 2,
    'TMT': 2,
    'TND': 3,
    'TOP': 2,
    'TPE': 0,
    'TRL': 0,
    'TRY': 2,
    'TTD': 2,
    'TVD': 2,
    'TWD': 2,
    'TZS': 2,
    'UAH': 2,
    'UAK': 2,
    'UGX': 0,
    'USD': 2,
    'USN': 2,
    'USS': 2,
    'UYI': 0,
    'UYN': 2,
    'UYU': 2,
    'UYW': 4,
    'UZS': 2,
    'VAL': 0,
    'VEB': 2,
    'VED': 2,
    'VEF': 2,
    'VES': 2,
    'VND': 0,
    'VUV': 0,
    'WST': 2,
    'XAF': 0,
    'XCD': 2,
    'XEU': 0,
    'XOF': 0,
    'XPF': 0,
    'YER': 2,
    'YUD': 2,
    'YUG': 2,
    'YUM': 2,
    'YUN': 2,
    'YUO': 2,
    'YUR': 2,
    'ZAL': 2,
    'ZAR': 2,
    'ZMK': 2,
    'ZMW': 2,
    'ZRN': 2,
    'ZRZ': 2,
    'ZWB': 2,
    'ZWC': 2,
    'ZWD': 2,
    'ZWL': 2,
    'ZWN': 2,
    'ZWR': 2
}

STRIPE_EXCEPTIONS_CURRENCY_MINOR_UNITS = {
    'ISK': 2,
    'HUF': 2,
    'TWD': 2,
    'UGX': 2,
}

STRIPE_CURRENCY_MINOR_UNITS = {**CURRENCY_MINOR_UNITS, **STRIPE_EXCEPTIONS_CURRENCY_MINOR_UNITS}

STRIPE_SAFE_SIMPLE_ROUTES = {
    'accounts',
    'account_links',
    'cardholders',
    'cards',
    'disputes',
    'ephemeral_keys',
    'files',
    'funding_instructions',
    'send_verification_code',
    'test_helpers/authorizations',
    'test_helpers/issuing/cards',
    'test_helpers/fund_balance',
    'test_helpers/transactions/create_force_capture',
    'test_helpers/account_verify',
    'topups',
}

STRIPE_REQUEST_REFUSED_REASONS = {
    'account_disabled': _lt("Your Stripe account is disabled."),
    'card_active': _lt("The card is active, and there was no control setup on your Stripe account."),  # SHOULD NEVER HAPPEN
    'card_canceled': _lt("The card used was blocked."),
    'card_expired': _lt("The card has expired."),
    'card_inactive': _lt("The card is currently inactive, please activate it first."),
    'cardholder_blocked': _lt("The cardholder was blocked."),
    'cardholder_inactive': _lt("The cardholder is currently inactive."),
    'cardholder_verification_required': _lt("The cardholder is still under verification."),
    'insecure_authorization_method': _lt("An insecure authorization method was used."),
    'insufficient_funds': _lt("There is insufficient funds on your Stripe account, please top-up your account first."),
    'network_fallback': _lt("Stripe timed-out or encountered an error when communicating with the card network."),
    'not_allowed': _lt("The charge is not allowed on the Stripe network, possibly because it is an ATM withdrawal or cash advance."),
    'pin_blocked': _lt("The card's PIN is blocked."),
    'authorization_controls': _lt("Transaction amount exceeded the card daily/transaction hard limit of 50,000 €."),
    'spending_controls': _lt("The card was declined because of the Stripe spending controls."),
    'suspected_fraud': _lt("The authorization was suspected as fraudulent by Stripe's risk controls."),
    'verification_failed': _lt("The authorization failed required verification checks."),
    'webhook_approved': _lt("The authorization was approved by your Odoo database."),
    'webhook_declined': _lt("The authorization was refused by your Odoo database."),
    'webhook_error': _lt("There was an error in your Odoo database and Stripe received an invalid response."),
    'webhook_timeout': _lt("Your Odoo database failed to respond to Stripe in time, and the authorization was refused by default.")
}

KiB = 1024
MiB = 1024 * KiB
# see https://docs.stripe.com/file-upload
STRIPE_FILE_UPLOAD_CONFIG = {
    'account_requirement': {
        'mimetypes': ['application/pdf', 'image/jpeg', 'image/png'],
        'max_size': 64 * MiB,
        'supported_models': [],
        # 'downloadable': False,
    },
    'business_icon': {
        'mimetypes': ['image/jpeg', 'image/png', 'image/gif'],
        'max_size': 512 * KiB,
        'supported_models': [],
        # 'downloadable': True,
    },
    'business_logo': {
        'mimetypes': ['image/jpeg', 'image/png', 'image/gif'],
        'max_size': 512 * KiB,
        'supported_models': [],
        # 'downloadable': True,
    },
    'customer_signature': {
        'mimetypes': ['image/jpeg', 'image/png', 'image/svg+xml'],
        'max_size': 4 * MiB,
        'supported_models': [],
        # 'downloadable': True,
    },
    'dispute_evidence': {
        'mimetypes': ['application/pdf', 'image/jpeg', 'image/png'],
        'max_size': 5 * MiB,
        'supported_models': ['hr.expense.stripe.dispute'],
        # 'downloadable': True,
    },
    'platform_terms_of_service': {
        'mimetypes': ['application/pdf', 'text/plain', 'text/markdown'],
        'max_size': 64 * MiB,
        'supported_models': [],
        # 'downloadable': False,
    },
    'issuing_regulatory_reporting': {
        'mimetypes': ['application/json'],
        'max_size': 256 * KiB,
        'supported_models': [],
        # 'downloadable': True,
    },
    'pci_document': {
        'mimetypes': ['application/pdf'],
        'max_size': 16 * MiB,
        'supported_models': [],
        # 'downloadable': True,
    },
    'tax_document_user_upload': {
        'mimetypes': [
            'application/pdf',
            'text/csv',
            'image/jpeg',
            'image/png',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ],
        'max_size': 16 * MiB,
        'supported_models': [],
        # 'downloadable': True,
    },
    'additional_verification': {
        'mimetypes': ['application/pdf', 'image/jpeg', 'image/png'],
        'max_size': 16 * MiB,
        'supported_models': [],
        # 'downloadable': False,
    },
    'terminal_android_apk': {
        'mimetypes': ['application/vnd.android.package-archive'],
        'max_size': 200 * MiB,
        'supported_models': [],
        # 'downloadable': True,
    },
    'terminal_reader_splashscreen': {
        'mimetypes': ['image/png', 'image/jpeg', 'image/gif'],
        'max_size': 4 * MiB,
        'supported_models': [],
        # 'downloadable': True,
    },
    'identity_document': {
        'mimetypes': ['application/pdf', 'image/jpeg', 'image/png'],
        'max_size': 32 * MiB,
        'supported_models': [],
        # 'downloadable': True,
    },
}


class StripeIssuingDatabaseError:
    """ Enum class to handle errors, returning the error status """

    DB_WRONG_SIGNATURE = 462  # The signature found in the request is incorrect
    DB_ERROR = 550  # A Generic error, that occurred on the database side
    DB_WRONG_WEBHOOK = 551  # A wrong webhook was accessed


def interpret_error_code(response):
    """ Return readable error message from the response status sent by the IAP proxy server

        :param requests.Response response: The response from the IAP proxy server
        :return: The lazy translation of the error message
        :rtype: LazyTranslate
    """
    code = response.status_code
    try:
        reason = response.json().get('message', 'Unknown Error')
    except JSONDecodeError:
        reason = response.reason or _lt("Unexpected error")
        if isinstance(reason, bytes):
            try:
                reason = reason.decode('utf-8')
            except UnicodeDecodeError:
                reason = reason.decode('iso-8859-1')
    iap_errors = {
        # Stripe specific
        401: _lt("We received the following error from Stripe: %(reason)s", reason=reason),  # Unauthorized
        402: _lt("We received the following error from Stripe: %(reason)s", reason=reason),  # Request Failed
        413: _lt("We received the following error from Stripe: %(reason)s", reason=reason),  # Forbidden
        414: _lt("We received the following error from Stripe: %(reason)s", reason=reason),  # Not found (because a 404 is a IAP not found)
        409: _lt("We received the following error from Stripe: %(reason)s", reason=reason),  # Conflict (idempotency)
        410: _lt("We received the following error from Stripe: %(reason)s", reason=reason),  # Bad Request code from Stripe
        429: _lt("We received the following error from Stripe: %(reason)s", reason=reason),  # Too Many Requests
        501: _lt("We received the following error from Stripe: %(reason)s", reason=reason),  # Stripe Server Error

        # IAP specific
        400: _lt("Invalid request sent to the Odoo IAP proxy server: %(reason)s", reason=reason),  # Unauthorized
        403: _lt("Forbidden access to the IAP proxy server"),
        404: _lt("We were unable to reach Odoo IAP proxy server"),
        451: _lt("Missing Cardholder on IAP proxy server"),
        452: _lt("Wrong or Expired validation code"),
        453: _lt("The sms service is currently experiencing a lot of request. Please try again in a few minutes."),  # Rate limit reached for sending SMS
        454: _lt("Stripe Issuing with Odoo is not yet implemented for the US customers."),
        455: _lt("The Stripe account specified in the request wasn't found. Please check your configuration"),
        456: _lt("No signature found in the request. Please check your configuration"),
        457: _lt("Invalid or expired signature found in the request. Please check your configuration"),
        459: _lt("Your account balance isn't zero, please use any remaining funds or contact support to close your account."),
        460: _lt("The creation rate limit for this type of cards has been reached. Please try again later."),  # Rate limit reached for creating cards
        461: _lt("Only licenses databases can use Odoo Stripe Issuing services."),
        463: _lt("There was an error when sending the SMS, please try again later. If the problem persists, please contact the support."),
        464: _lt("The country of the phone number is not supported for SMS."),
        465: _lt("There was an error when sending the email, please try again later. If the problem persists, please contact the support."),
        467: _lt("Your dispute creation rate limit has been reached. Please try again later."),  # Rate limit for creating disputes
        500: _lt("There was an unexpected error on Odoo IAP proxy server"),
        503: _lt("We received the following error from Odoo IAP proxy server:\n- Missing account secret"),
        504: _lt("We received the following error from Odoo IAP proxy server:\n- Missing account webhook"),
        505: _lt("We received the following error from Odoo IAP proxy server:\n- Wrong platform setup/route is restricted"),
        False: _lt("Unknown Error Code"),
    }
    error_message = iap_errors.get(code) or iap_errors[False]
    return error_message


def to_major_currency_units(minor_amount, currency, arbitrary_decimal_number=None):
    """ Return the amount converted to the major units of its currency.

    The conversion is done by dividing the amount by 10^k where k is the number of decimals of the
    currency as per the ISO 4217 norm.
    To force a different number of decimals, set it as the value of the `arbitrary_decimal_number`
    argument.

    :param float minor_amount: The amount in minor units, to convert in major units
    :param recordset currency: The currency of the amount, as a `res.currency` record
    :param int arbitrary_decimal_number: The number of decimals to use instead of that of ISO 4217
    :return: The amount in major units of its currency
    :rtype: int
    """
    # Taken from payment
    if arbitrary_decimal_number is None:
        currency.ensure_one()
        decimal_number = CURRENCY_MINOR_UNITS.get(currency.name, currency.decimal_places)
    else:
        decimal_number = arbitrary_decimal_number
    return float_round(minor_amount, precision_digits=0) / (10**decimal_number)


def to_minor_currency_units(major_amount, currency, arbitrary_decimal_number=None):
    """ Return the amount converted to the minor units of its currency.

    The conversion is done by multiplying the amount by 10^k where k is the number of decimals of
    the currency as per the ISO 4217 norm.
    To force a different number of decimals, set it as the value of the `arbitrary_decimal_number`
    argument.

    Note: currency.ensure_one() if arbitrary_decimal_number is not provided

    :param float major_amount: The amount in major units, to convert in minor units
    :param recordset currency: The currency of the amount, as a `res.currency` record
    :param int arbitrary_decimal_number: The number of decimals to use instead of that of ISO 4217
    :return: The amount in minor units of its currency
    :rtype: int
    """
    # Taken from payment
    if arbitrary_decimal_number is None:
        currency.ensure_one()
        decimal_number = CURRENCY_MINOR_UNITS.get(currency.name, currency.decimal_places)
    else:
        decimal_number = arbitrary_decimal_number
    return int(
        float_round(major_amount * (10**decimal_number), precision_digits=0, rounding_method='DOWN')
    )


def format_amount_from_stripe(amount, currency):
    """ Helper to convert currencies according to stripe formatting which is the amount in the currency's minor unit with exceptions  """
    return to_major_currency_units(amount, currency, arbitrary_decimal_number=STRIPE_EXCEPTIONS_CURRENCY_MINOR_UNITS.get(currency.name))


def format_amount_to_stripe(amount, currency):
    """ Helper to convert currencies according from stripe formatting which is the amount in the currency's minor unit with exceptions  """
    return to_minor_currency_units(amount, currency, arbitrary_decimal_number=STRIPE_EXCEPTIONS_CURRENCY_MINOR_UNITS.get(currency.name))


def convert_dict_to_url_encoded_forms(dict_vals, level=0):
    """
    Convert python dict into url encoded forms
    """
    new_dict = {}

    for key, item in dict_vals.items():
        dict_key = f'{key}' if level == 0 else f'[{key}]'
        if isinstance(item, dict):
            new_sub_dict = convert_dict_to_url_encoded_forms(item, level + 1)
            # Add sub dict to this dict
            for sub_dict_key, sub_dict_item in new_sub_dict.items():
                new_dict[f'{dict_key}{sub_dict_key}'] = sub_dict_item
        elif isinstance(item, (tuple, list, set)):
            for idx, sub_item in enumerate(item):
                if isinstance(sub_item, dict):
                    sub_item = convert_dict_to_url_encoded_forms(item, level + 1)
                    # Add sub dict to this dict
                    for sub_dict_key, sub_dict_item in new_sub_dict.items():
                        new_dict[f'{dict_key}[{idx}]{sub_dict_key}'] = sub_dict_item
                else:
                    new_dict[f'{dict_key}[{idx}]'] = sub_item
        else:
            new_dict[dict_key] = item
    # Conversion is important else the signed payload received by IAP will be different from the one we signed
    return {key: str(value) for key, value in new_dict.items()}


def _create_signature(signature_key, payload_data):
    """ Create the signature for IAP to authenticate the payload. We need to canonicalize the payload data because some parameters
    will be found in the route """
    timestamp = str(int(fields.Datetime.now().timestamp()))
    canonical_payload_str = str({key: payload_data[key] for key in sorted(payload_data)})
    signed_message = f'{timestamp}.{canonical_payload_str}'.encode()
    signature = signature_key._sign(signed_message, formatting='base64').decode()
    return f'v1={signature},t={timestamp}'


@lru_cache(maxsize=1)
def _get_route_re_pattern(safe_simple_routes):
    # Check if the route is a formatted route e.g. 'test_helpers/authorizations/ich_1MsKAB2eZvKYlo2C3eZ2BdvK/capture'
    simple_routes_pattern = '|'.join(safe_simple_routes)
    return re.compile(
        rf'(?:{simple_routes_pattern})/'  # base route part
        r'[a-z]{2,5}(?:_[a-z]{2,4})?_'  # Prefix part (e.g. 'sk_test_', 'ich_', etc.)
        r'[a-zA-Z0-9]{16,24}'  # Stripe ID part (alphanumeric characters)
        r'(?:/capture'  # Optional capture part (e.g. in the case of test authorizations)
        r'|/shipping/(?:submit|ship|deliver|return|fail)'  # Optional shipping part (e.g. in the case of test shippings)
        r'|/submit'  # when submitting disputes
        r'|/contents'  # for file contents
        r')?$'
    )


def _validate_route(route):
    """ Check that the route is in the proper whitelist """
    if route in STRIPE_SAFE_SIMPLE_ROUTES:
        return None

    if _get_route_re_pattern(tuple(STRIPE_SAFE_SIMPLE_ROUTES)).fullmatch(route):
        return None

    return _lt("The route '%(route)s' is not allowed to be called from the Stripe IAP proxy server.", route=route)


def make_request_stripe_proxy(company, route, route_params=None, payload=None, method="POST", headers=None, files=None, raw=False):
    """ Main helper to make requests to the Stripe IAP proxy server.

    :param :class:`~odoo.addons.base.models.res_company.ResCompany` company: The company for which the request is made
    :param str route: The route endpoint to call on the IAP proxy server
    :param dict route_params: The parameters to format the route with (needed that way to include it in the signature)
    :param dict payload: The payload to send in the request
    :param str method: The HTTP method to use for the request (default: "POST")
    :param dict headers: Additional headers to send with the request
    :param dict files: The files to send, used for `requests`
    :return: The response content from the IAP proxy server
    :rtype: dict | tuple[str, bytes]
    """
    if not headers:
        headers = {}
    match company.env['ir.config_parameter'].get_str('hr_expense_stripe.stripe_mode') or 'live':
        case 'live':
            proxy_server = 'https://iap-services.odoo.com'
        case 'test':
            proxy_server = 'https://iap-services-test.odoo.com'
        case _:
            raise UserError(company.env._("Stripe Issuing configuration invalid, please set it as 'live' or 'test' in the configurations."))
    payload = convert_dict_to_url_encoded_forms(payload or {})
    signature_key = company.stripe_issuing_db_private_key_id

    if signature_key:
        payload_data = {**(route_params or {}), **payload}
        if files:
            file_name, file_content, file_type = files['file']
            payload_data.update({
                'file_name': file_name,
                'file_type': file_type,
                'file_sha256': hashlib.sha256(file_content).hexdigest(),
            })
        headers['Db-Signature'] = _create_signature(signature_key, payload_data)
    if route_params:
        route = route.format(**route_params)

    error_msg = _validate_route(route)
    if error_msg:
        raise UserError(company.env._(error_msg))  # pylint: disable=gettext-variable

    url = f"{proxy_server}/api/stripe_issuing/v1/{route}"
    _logger.info(
        '[STRIPE ISSUING] %(method)s call to %(url)s for %(company)s (%(company_id)s) by %(user)s (%(user_id)s)',
        {
            'method': method,
            'url': url,
            'company': company.name,
            'company_id': company.id,
            'user': company.env.user.name,
            'user_id': company.env.user.id,
        },
    )

    response = requests.request(
        method,
        url,
        params=payload if method == 'GET' else None,
        data=payload if method != 'GET' else None,
        headers=headers,
        timeout=(5, 30 if files else 10),
        files=files,
    )
    if not response.ok:
        raise UserError(company.env._(interpret_error_code(response)))  # pylint: disable=gettext-variable
    if raw:
        return response.headers.get('Content-Type', 'application/octet-stream'), response.content
    response_content = response.json()
    response_content['session_id'] = response.cookies.get('session_id', False)

    return response_content
