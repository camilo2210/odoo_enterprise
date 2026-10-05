import logging
import requests

_logger = logging.getLogger(__name__)


def get_barcode_lookup_key(self):
    '''
    Get the Barcode Lookup API Key from the system.
    '''
    return self.env['ir.config_parameter'].sudo().get_str('product_barcodelookup.api_key') or False


def barcode_lookup_request(url, params={}):
    '''
    Make a request to the given URL and return the response.
    '''
    response = requests.get(url, params, timeout=15)
    if response.status_code != 200:
        _logger.warning('Status code: %s with the given URL: %s', response.status_code, url)

    return response
