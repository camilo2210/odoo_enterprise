from requests.exceptions import RequestException

from odoo import fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.hr_attendance_zkteco.models.utils import _notification


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    zkteco_server_url = fields.Char(related="company_id.zkteco_server_url", readonly=False)
    zkteco_email = fields.Char(related="company_id.zkteco_email", readonly=False)
    zkteco_password = fields.Char(related="company_id.zkteco_password", readonly=False)
    zkteco_company = fields.Char(related="company_id.zkteco_company", readonly=False)
    zkteco_checkout_lookback_days = fields.Integer(related="company_id.zkteco_checkout_lookback_days", readonly=False)
    zkteco_transaction_fetch_days = fields.Integer(related="company_id.zkteco_transaction_fetch_days", readonly=False)

    def action_test_zkteco_connection(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(self.env._("Only administrators can test the ZKTeco BioTime connection."))

        try:
            session = self.company_id.sudo()._get_zkteco_session()
        except RequestException:
            raise UserError(
                self.env._(
                    "Could not connect to the BioTime server. Please verify your configuration fields are set up correctly."
                )
            ) from None

        if not self.company_id.zkteco_initial_sync_done:
            self.company_id.zkteco_initial_sync_done = True
            self.env["zkteco.terminal"]._fetch_and_create_terminals(self.company_id, session)

            terminals = self.env["zkteco.terminal"].search([("company_id", "=", self.company_id.id)])
            employees_by_zkteco_id = dict(
                self.env["hr.employee"]._read_group(
                    [("zkteco_emp_id", "!=", False), ("company_id", "=", self.company_id.id)],
                    ["zkteco_emp_id"],
                    ["id:recordset"],
                )
            )

            self.env["zkteco.transactions"]._fetch_and_create_transactions(
                self.company_id,
                session,
                set(),
                terminals,
                employees_by_zkteco_id,
            )

        return _notification(
            self.env._("Connected successfully to the ZKTeco BioTime server."),
            title=self.env._("Success"),
            reload="reload",
        )
