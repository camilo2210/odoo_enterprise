import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.urls import urljoin as url_join

GOSI_API_URLS = {"test": "https://sandbox-api.gosi.gov.sa", "prod": "https://api.gosi.gov.sa"}


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_sa_gosi_registration_number = fields.Char(string="GOSI Registration Number", groups="base.group_system")
    l10n_sa_gosi_api_key = fields.Char(string="GOSI API Key", groups="base.group_system")
    l10n_sa_gosi_client_id = fields.Char(string="GOSI Client ID", groups="base.group_system")
    l10n_sa_gosi_client_secret = fields.Char(string="GOSI Client Secret", groups="base.group_system")
    l10n_sa_gosi_dpop_private_key_id = fields.Many2one(string="GOSI DPoP Key", comodel_name="certificate.key", groups="base.group_system")
    l10n_sa_gosi_dpop_private_key_value = fields.Text(
        compute="_compute_l10n_sa_gosi_dpop_private_key_value",
        inverse="_inverse_l10n_sa_gosi_dpop_private_key_value",
        store=True,
        groups="base.group_system",
    )
    l10n_sa_gosi_api_mode = fields.Selection(
        selection=[("inactive", "Inactive"), ("test", "Testing"), ("prod", "Production")],
        string="GOSI Api Mode", required=True, default="prod", groups="base.group_system",
    )
    l10n_sa_gosi_api_is_available = fields.Boolean(
        compute="_compute_l10n_sa_gosi_api_is_available",
        search="_search_l10n_sa_gosi_api_is_available",
        compute_sudo=True,
    )

    @api.model
    def _search_l10n_sa_gosi_api_is_available(self, operator, value):
        if operator not in ("in", "not in"):
            raise NotImplementedError

        available_companies = self.search([
            ("partner_id.country_id.code", "=", 'SA'),
            ("l10n_sa_gosi_api_key", "!=", False),
            ("l10n_sa_gosi_client_id", "!=", False),
            ("l10n_sa_gosi_client_secret", "!=", False),
            ("l10n_sa_gosi_dpop_private_key_id", "!=", False),
            ("l10n_sa_gosi_api_mode", "!=", "inactive"),
        ])

        if operator == "in":
            return [("id", "in" if value else "not in", available_companies.ids)]

        return [("id", "not in" if value else "in", available_companies.ids)]

    @api.depends(
        "l10n_sa_gosi_registration_number",
        "l10n_sa_gosi_api_key",
        "l10n_sa_gosi_client_id",
        "l10n_sa_gosi_client_secret",
        "l10n_sa_gosi_dpop_private_key_id",
        "l10n_sa_gosi_api_mode",
    )
    def _compute_l10n_sa_gosi_api_is_available(self):
        for record in self:
            record.l10n_sa_gosi_api_is_available = (
                record.l10n_sa_gosi_registration_number
                and record.l10n_sa_gosi_api_key
                and record.l10n_sa_gosi_client_id
                and record.l10n_sa_gosi_client_secret
                and record.l10n_sa_gosi_dpop_private_key_id
                and record.l10n_sa_gosi_api_mode != "inactive"
                and record.country_code == "SA"
            )

    @api.depends("l10n_sa_gosi_dpop_private_key_id.content")
    def _compute_l10n_sa_gosi_dpop_private_key_value(self):
        for record in self:
            record.l10n_sa_gosi_dpop_private_key_value = \
                record.l10n_sa_gosi_dpop_private_key_id.pem_key.to_base64()

    def _inverse_l10n_sa_gosi_dpop_private_key_value(self):
        self.l10n_sa_gosi_dpop_private_key_id.content = False
        for record in self.filtered("l10n_sa_gosi_dpop_private_key_value"):
            key_content = record.l10n_sa_gosi_dpop_private_key_value
            if present_key := record.l10n_sa_gosi_dpop_private_key_id:
                present_key.content = key_content
            else:
                record.l10n_sa_gosi_dpop_private_key_id = self.env["certificate.key"].create({
                    "content": key_content,
                    "name": "GOSI DPoP Private Key",
                })

    def _l10n_sa_gosi_get_base_url(self):
        self.ensure_one()
        return GOSI_API_URLS.get(self.l10n_sa_gosi_api_mode)

    def _l10n_sa_gosi_get_access_token(self) -> dict:
        self.ensure_one()
        data = {}
        try:
            url = url_join(self._l10n_sa_gosi_get_base_url(),
                          f"/v1/establishment/{self.l10n_sa_gosi_registration_number}/access-token")
            dpop = self.l10n_sa_gosi_dpop_private_key_id._l10n_sa_gosi_generate_dpop_jwt("POST", url)
            headers = {"x-apikey": self.l10n_sa_gosi_api_key, "dpop": dpop}
            payload = {"client_id": self.l10n_sa_gosi_client_id, "client_secret": self.l10n_sa_gosi_client_secret}
            response = requests.request("POST", url, json=payload, headers=headers, timeout=10)
            data = response.json()
            response.raise_for_status()
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout, ValueError, ValidationError):
            return False

        return data.get('access_token')
