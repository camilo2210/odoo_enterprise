# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

import requests

from odoo import fields, models
from odoo.exceptions import LockError, UserError

from odoo.addons.account_edi_proxy_client.models.account_edi_proxy_user import (
    AccountEdiProxyError,
)

_logger = logging.getLogger(__name__)
DEFAULT_IAP_ENDPOINT = 'https://account-avatax.api.odoo.com'
IAP_SERVICE_NAME = 'account_avatax_proxy'


class AccountEdiProxyClientUser(models.Model):
    _inherit = 'account_edi_proxy_client.user'

    proxy_type = fields.Selection(
        selection_add=[('avatax', 'AvaTax')],
        ondelete={'avatax': 'cascade'},
    )

    def _get_proxy_urls(self):
        urls = super()._get_proxy_urls()
        proxy_url = self.env['ir.config_parameter'].sudo().get_str(
            'account_avatax_iap.endpoint', DEFAULT_IAP_ENDPOINT)
        urls['avatax'] = {'prod': proxy_url}
        return urls

    def _get_proxy_identification(self, company, proxy_type):
        if proxy_type == 'avatax':
            return company.sudo().avalara_api_id or ''
        return super()._get_proxy_identification(company, proxy_type)

    def _call_avatax_proxy(self, endpoint, params=None):
        """Send an authenticated request to the AvaTax IAP proxy.

        Follows the standard Peppol pattern: wraps _make_request (JSON-RPC)
        with service-specific error handling.

        :param endpoint: The endpoint path (e.g. 'ping', 'create_transaction').
        :param params: Dict of parameters sent inside the JSON-RPC params.
        :returns: The response dict from the proxy.
        :raises UserError: On proxy or network errors.
        """
        self.ensure_one()
        try:
            return self._make_request(
                f'{self._get_server_url()}/api/account_avatax/1/{endpoint}',
                params=params,
            )
        except AccountEdiProxyError as e:
            raise UserError(e.message or e.code) from None

    def _renew_token(self):
        if self.proxy_type != 'avatax':
            super()._renew_token()
            return
        try:
            self.lock_for_update()
        except LockError:
            return
        response = self._make_request(self._get_server_url() + '/api/account_avatax/1/renew_token')
        if 'error' in response:
            _logger.error(response['error'])
            return
        self.sudo().refresh_token = response['refresh_token']

    def _register_avatax_proxy_user(self, company, endpoint, data):
        """Register with the AvaTax IAP proxy and create a proxy user record.

        Similar to the base _register_proxy_user but uses a custom registration
        endpoint since avatax account creation is handled server-side.

        :param company: The company to register for.
        :param endpoint: Registration endpoint ('connect_to_iap' or 'link_to_iap').
        :param data: Dict of registration parameters (Avalara-specific).
        :returns: The JSON response from the server.
        :raises UserError: On error responses from the server.
        """
        proxy_url = self._get_proxy_urls()['avatax']['prod']
        url = f'{proxy_url}/api/account_avatax/1/{endpoint}'

        private_key_sudo = self.env['certificate.key'].sudo()._generate_rsa_private_key(
            company, name=f"avatax_prod_{company.id}.key",
        )
        public_key_pem = private_key_sudo._get_public_key_bytes(encoding='pem').decode()

        iap_token = self.env['iap.account'].get(IAP_SERVICE_NAME).sudo().account_token
        db_uuid = self.env['ir.config_parameter'].sudo().get_str('database.uuid')

        data.update({
            'db_uuid': db_uuid,
            'company_id': company.id,
            'public_key': public_key_pem,
            'iap_token': iap_token,
        })

        try:
            response = requests.post(url, json=data, timeout=60).json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            private_key_sudo.unlink()
            raise UserError(self.env._(
                "Could not connect to the AvaTax proxy server. Please try again later.",
            )) from None

        error = self.env['account.external.tax.mixin']._handle_response(response, self.env._(
            "Odoo was unable to register with the AvaTax proxy for %(company)s",
            company=company.display_name,
        ))
        if error:
            private_key_sudo.unlink()
            raise UserError(error)

        self.create({
            'id_client': response['id_client'],
            'company_id': company.id,
            'proxy_type': 'avatax',
            'edi_mode': 'prod',
            'edi_identification': response.get('Avalara Account #', ''),
            'private_key_id': private_key_sudo.id,
            'refresh_token': response['refresh_token'],
        })

        company.avalara_connection_method = 'iap'
        company.avalara_iap_connected = True
        # Strip secrets before returning to the caller (shown in UI popup).
        response.pop('id_client', None)
        response.pop('refresh_token', None)
        return response
