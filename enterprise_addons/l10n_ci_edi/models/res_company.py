import logging
import requests
from requests.exceptions import RequestException
from json.decoder import JSONDecodeError

from odoo import api, fields, models, _
from odoo.tools.urls import urljoin
from odoo.tools import frozendict

_logger = logging.getLogger(__name__)

FNE_BASE_URLS = frozendict({
    'production': "https://www.services.fne.dgi.gouv.ci/ws",
    'test': "http://54.247.95.108/ws",
})


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ci_edi_server_mode = fields.Selection(
        selection=[
            ('production', "Production"),
            ('test', "Test"),
        ],
        string="FNE Server Mode",
        help="""
            - Production: Connection to the DGI FNE system in production mode.
            - Test: Connection to the DGI FNE system in test mode.
        """,
        groups='base.group_system',
    )
    l10n_ci_edi_fne_api_token = fields.Char(
        string="FNE API Token",
        help="Authentication token provided by the DGI for API access.",
        groups='base.group_system',
    )
    l10n_ci_edi_is_active = fields.Boolean(compute='_compute_l10n_ci_edi_is_active', compute_sudo=True)

    @api.depends('l10n_ci_edi_server_mode', 'l10n_ci_edi_fne_api_token')
    def _compute_l10n_ci_edi_is_active(self):
        for company in self:
            company.l10n_ci_edi_is_active = bool(
                company.l10n_ci_edi_server_mode
                and company.l10n_ci_edi_fne_api_token
            )

    def _l10n_ci_edi_api_call(self, endpoint, payload):
        """Make an API call to the FNE system.

        :param endpoint: API endpoint
        :param payload: Dictionary with request body
        :returns: tuple (response_data, error)
        """
        self.ensure_one()
        base_url = FNE_BASE_URLS.get(self.sudo().l10n_ci_edi_server_mode, FNE_BASE_URLS['test'])
        url = urljoin(base_url, endpoint)
        headers = {
            'Authorization': f'Bearer {self.sudo().l10n_ci_edi_fne_api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
        except RequestException as e:
            _logger.error("FNE API connection error: %s", e)
            return None, {
                'code': 'CONNECTION_ERROR',
                'message': self.env._("Error connecting to the FNE server. Please try again later."),
            }

        try:
            response_data = response.json()
        except (JSONDecodeError, ValueError):
            # An error response (e.g. a 502 from a gateway)
            if not response.ok:
                _logger.error("FNE API error (HTTP %s): %s", response.status_code, response.text[:500])
                return None, {
                    'code': str(response.status_code),
                    'message': self.env._("Unknown error"),
                }
            _logger.error("FNE API response decode error: %s", response.text[:500])
            return None, {
                'code': 'DECODE_ERROR',
                'message': self.env._("Error decoding response from the FNE server."),
            }

        # Check for API-level errors
        if not response.ok:
            error_msg = response_data.get('message', self.env._("Unknown error"))
            if errors := response_data.get('errors'):
                # errors is a nested dict like {'field': {'rule': 'message'}}
                error_details = [
                    f"{field}: {detail}"
                    for field, rules in errors.items()
                    for detail in (rules.values() if isinstance(rules, dict) else [rules])
                ]
                if error_details:
                    error_msg += '\n' + '\n'.join(error_details)
            _logger.error("FNE API error (HTTP %s): %s", response.status_code, error_msg)
            return None, {
                'code': str(response.status_code),
                'message': error_msg,
            }

        # Check for errors in response
        if status := response_data.get('statusCode'):
            error_msg = (response_data.get('error') or _('Error')) + ' : ' + (response_data.get('message') or '')
            return None, {
                'code': str(status),
                'message': error_msg,
            }

        return response_data, None
