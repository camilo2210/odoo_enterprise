import logging

import requests
from requests.exceptions import RequestException

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.urls import urljoin

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    zkteco_email = fields.Char(groups="base.group_system")
    zkteco_server_url = fields.Char(groups="base.group_system")
    zkteco_password = fields.Char(groups="base.group_system")
    zkteco_company = fields.Char(groups="base.group_system")
    zkteco_initial_sync_done = fields.Boolean()
    zkteco_checkout_lookback_days = fields.Integer(default=2)
    zkteco_transaction_fetch_days = fields.Integer(default=2)

    def write(self, vals):
        res = super().write(vals)
        if "zkteco_initial_sync_done" in vals:
            self.env.transaction.invalidate_ormcache("default")
        return res

    def _get_zkteco_credentials(self):
        self.ensure_one()
        return {
            "server_url": self.zkteco_server_url,
            "email": self.zkteco_email,
            "password": self.zkteco_password,
            "company": self.zkteco_company,
        }

    def _get_zkteco_session(self):
        self.ensure_one()
        credentials = self._get_zkteco_credentials()

        missing_credentials = []
        if not credentials.get("server_url"):
            missing_credentials.append(self.env._("Server URL"))
        if not credentials.get("email"):
            missing_credentials.append(self.env._("Email"))
        if not credentials.get("password"):
            missing_credentials.append(self.env._("Password"))
        if not credentials.get("company"):
            missing_credentials.append(self.env._("Company Name"))
        if missing_credentials:
            warning_message = self.env._("ZKTeco BioTime company settings are incomplete. Please configure the following fields:\n")
            raise UserError(warning_message + "\n -".join(missing_credentials))

        try:
            response = requests.post(
                urljoin(credentials["server_url"], "/jwt-api-token-auth/"),
                json={"email": credentials["email"], "password": credentials["password"], "company": credentials["company"]},
                timeout=30,
            )
            response.raise_for_status()
            token = response.json().get("token")
        except RequestException:
            _logger.warning("ZKTeco BioTime auth failed for %s", credentials["server_url"], exc_info=True)
            raise

        if not token:
            raise UserError(self.env._("ZKTeco BioTime authentication failed: no token in server response."))

        session = requests.Session()
        session.headers["Authorization"] = f"JWT {token}"
        session.base_url = credentials["server_url"]
        return session
