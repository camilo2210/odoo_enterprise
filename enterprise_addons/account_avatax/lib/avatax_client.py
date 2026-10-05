"""
AvaTax Software Development Kit for Python.

   Copyright 2019 Avalara, Inc.
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
@author     Robert Bronson
@author     Phil Werner
@author     Adrienne Karnoski
@author     Han Bao
@copyright  2019 Avalara, Inc.
@license    https://www.apache.org/licenses/LICENSE-2.0
@version    TBD
@link       https://github.com/avadev/AvaTax-REST-V2-Python-SDK
"""
# This is a stripped down version of the upstream Avatax library for Odoo. Changes were made to
# prevent arbitrary requests in case function references get leaked.

import logging
from datetime import datetime
from pprint import pformat

import requests
from requests.auth import HTTPBasicAuth

from odoo.exceptions import AccessError, RedirectWarning
from odoo.release import version

str_type = (str, type(None))
_logger = logging.getLogger(__name__)


class AvataxClient:
    @classmethod
    def _get_client(cls, company, skip_credentials_check=False):
        ExternalTaxMixin = company.env['account.external.tax.mixin']
        if not skip_credentials_check:
            company = ExternalTaxMixin._find_avatax_credentials_company(company)
        if not company:
            env = ExternalTaxMixin.env
            raise RedirectWarning(
                env._('Please add your AvaTax credentials or connect via Avalara Included'),
                env.ref('base_setup.action_general_configuration').id,
                env._("Go to the configuration panel"),
            )

        company_sudo = company.sudo()
        client = cls(
            company,
            app_name='Odoo SA',
            app_version=version,
        )
        client.add_credentials(
            company_sudo.avalara_api_id or '',
            company_sudo.avalara_api_key or '',
        )
        client.logger = lambda message: ExternalTaxMixin._log_external_tax_request(
            'Avatax US', 'account_avatax.log.end.date', message,
        )
        if company_sudo.avalara_connection_method == 'iap':
            client.proxy_user = company.account_edi_proxy_client_ids.filtered(
                lambda u: u.proxy_type == 'avatax' and u.active,
            )[:1]
        return client

    def __init__(self, company, app_name=None, app_version=None, machine_name=None,
                 timeout_limit=None):
        if not all(isinstance(i, str_type) for i in [app_name,
                                                     machine_name]):
            raise ValueError('Input(s) must be string or none type object')
        self.base_url = 'https://sandbox-rest.avatax.com'
        self.is_production = company.avalara_environment.lower() == 'production'
        if self.is_production:
            self.base_url = 'https://rest.avatax.com'
        self.auth = None
        self.app_name = app_name
        self.app_version = app_version
        self.machine_name = machine_name
        self.client_id = f'{app_name}; {app_version}; Python SDK; 18.5; {machine_name};'
        self.client_header = {'X-Avalara-Client': self.client_id}
        self.timeout_limit = timeout_limit or 120
        self.company = company
        self.connection_method = company.sudo().avalara_connection_method
        self.proxy_user = None

    def add_credentials(self, username=None, password=None):
        if not all(isinstance(i, str_type) for i in [username, password]):
            raise ValueError('Input(s) must be string or none type object')
        self.username = username
        if username and not password:
            self.client_header['Authorization'] = 'Bearer ' + username
        else:
            self.auth = HTTPBasicAuth(username, password)
        return self

    def iap_request(self, endpoint_path, **kwargs):
        """Send a request to the IAP proxy via the authenticated proxy user.

        Uses the standard account_edi_proxy_client _make_request (JSON-RPC)
        with OdooEdiProxyAuth HMAC signing, matching the Peppol pattern.

        :param endpoint_path: The IAP endpoint path (e.g. 'ping', 'create_transaction').
        :param kwargs: Endpoint-specific parameters forwarded inside JSON-RPC params.
        :raises odoo.exceptions.AccessError: on IAP-level errors.
        """
        start = datetime.utcnow()
        result = self.proxy_user._call_avatax_proxy(endpoint_path, params=kwargs)
        if hasattr(self, 'logger'):
            end = datetime.utcnow()
            self.logger(
                f"\nstart={start}\nend={end}\nendpoint={endpoint_path}\nkwargs={pformat(kwargs)}\n"
                f"response={pformat(result)}",
            )
        error = result.get('error')
        if not error:
            return result
        # IAP-level errors (INSUFFICIENT_CREDIT, AVATAX_ERROR) use a string code.
        # AvaTax API errors use a dict with 'code'/'details' - pass those through
        # to the caller so _handle_response can display the Avalara error message.
        if not isinstance(error, str):
            return result
        message = self.company.env._("An error occurred while reaching the AvaTax proxy. Please contact Odoo support if this error persists.")
        if error == 'INSUFFICIENT_CREDIT':
            message = self.company.env._("You do not have enough credits for this operation.")
        _logger.warning("iap request %s failed (%s): %s", endpoint_path, error, message)
        raise AccessError(message)

    def _dispatch(self, iap_endpoint, method, avatax_endpoint, params=None, json=None, **iap_kwargs):
        """Dispatch request to either IAP proxy or directly to AvaTax.

        :param iap_endpoint: IAP proxy endpoint path (used when connection_method == 'iap').
        :param method: HTTP method for direct AvaTax requests (GET, POST, etc.).
        :param avatax_endpoint: AvaTax API path for direct requests.
        :param params: Query parameters forwarded to AvaTax.
        :param json: JSON body forwarded to AvaTax.
        :param iap_kwargs: Additional endpoint-specific parameters for the IAP proxy.
        """
        if self.connection_method == 'iap':
            iap_payload = {k: v for k, v in {'params': params, 'json': json}.items() if v is not None}
            return self.iap_request(iap_endpoint, **iap_payload, **iap_kwargs)

        # Perform direct request to AvaTax API
        start = datetime.utcnow()
        url = f'{self.base_url}/api/v2/{avatax_endpoint}'
        response = requests.request(
            method, url,
            auth=self.auth,
            headers=self.client_header,
            timeout=self.timeout_limit,
            params=params,
            json=json,
        ).json()
        if hasattr(self, 'logger'):
            end = datetime.utcnow()
            self.logger(
                f"{method}\nstart={start}\nend={end}\nargs={pformat(url)}\nparams={pformat(params)}\njson={pformat(json)}\n"
                f"response={pformat(response)}",
            )
        return response

    def create_transaction(self, model, include=None):
        return self._dispatch(
            'create_transaction', 'POST', 'transactions/createoradjust',
            params=include, json={'createTransactionModel': model},
        )

    def uncommit_transaction(self, companyCode, transactionCode):
        return self._dispatch(
            'uncommit_transaction', 'POST',
            f'companies/{companyCode}/transactions/{transactionCode}/uncommit',
            company_code=companyCode or 'DEFAULT', transaction_code=transactionCode,
        )

    def void_transaction(self, companyCode, transactionCode):
        return self._dispatch(
            'void_transaction', 'POST',
            f'companies/{companyCode}/transactions/{transactionCode}/void',
            company_code=companyCode or 'DEFAULT', transaction_code=transactionCode,
            json={"code": "DocVoided"},
        )

    def ping(self):
        return self._dispatch('ping', 'GET', 'utilities/ping')

    def get_companies(self):
        return self._dispatch('get_companies', 'GET', 'companies')

    def list_nexus(self, company_id):
        return self._dispatch(
            'list_nexus', 'GET', f'companies/{company_id}/nexus',
            company_id=company_id,
        )

    def resolve_address(self, model=None):
        return self._dispatch('resolve_address', 'POST', 'addresses/resolve', json=model)

    def list_entity_use_codes(self, include=None):
        return self._dispatch('list_entity_use_codes', 'GET', 'definitions/entityusecodes', params=include)

    def list_parameters(self):
        return self._dispatch('list_parameters', 'GET', 'definitions/parameters')

    def list_unit_of_measurements(self):
        return self._dispatch('list_unit_of_measurements', 'GET', 'definitions/unitofmeasurements')
