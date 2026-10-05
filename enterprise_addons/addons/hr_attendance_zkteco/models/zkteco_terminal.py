import logging

from requests.exceptions import RequestException

from odoo import api, fields, models
from odoo.exceptions import AccessError, RedirectWarning, UserError

from odoo.addons.hr_attendance_zkteco.models.utils import _get_records_from_server, _notification

_logger = logging.getLogger(__name__)


class ZktecoTerminal(models.Model):
    _name = "zkteco.terminal"
    _description = "ZKTeco Terminal"

    name = fields.Char(required=True)
    location_id = fields.Many2one("hr.work.location")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    terminal_sn = fields.Char(
        string="Terminal ID",
        required=True,
        help="The ID of the terminal that is defined in the Biotime server",
    )

    _unique_terminal_sn_company = models.Constraint(
        "UNIQUE(terminal_sn, company_id)",
        "Terminal ID must be unique per company.",
    )

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (self.env.company.zkteco_initial_sync_done,)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        if not self.env.company.zkteco_initial_sync_done:
            raise RedirectWarning(
                message=self.env._(
                    "ZKTeco BioTime is not set up for %s yet. Configure the BioTime credentials in Settings to start syncing.",
                    self.env.company.name,
                ),
                action=self.env.ref("base_setup.action_general_configuration").id,
                button_text=self.env._("Go to Settings"),
            )
        return super()._get_view(view_id, view_type, **options)

    def action_fetch_terminals(self):
        if not self.env.user.has_groups("base.group_system,hr_attendance.group_hr_attendance_manager"):
            raise AccessError(self.env._("Only attendance managers can fetch terminals from the ZKTeco BioTime server."))

        company = self.env.company
        try:
            session = company.sudo()._get_zkteco_session()
        except RequestException as e:
            raise UserError(self.env._("Could not connect to the ZKTeco BioTime server: %s", e)) from None

        try:
            self._fetch_and_create_terminals(company, session)
        except RequestException as e:
            raise UserError(self.env._("Failed to fetch terminals from BioTime server: %s", e)) from None

        return _notification(self.env._("Terminals have been fetched from the BioTime server."))

    @api.model
    def _fetch_and_create_terminals(self, company, session):
        existing_sns = {r["terminal_sn"] for r in self.search_read([("company_id", "=", company.id)], ["terminal_sn"])}
        new_terminals = []

        for terminal in _get_records_from_server(session, "/iclock/api/terminals/"):
            sn = terminal.get("sn")
            if not sn or sn in existing_sns:
                continue

            new_terminals.append({"name": terminal.get("alias") or sn, "terminal_sn": sn, "company_id": company.id})
            existing_sns.add(sn)

        self.create(new_terminals)
        _logger.info("Created %d terminal records from ZKTeco BioTime server", len(new_terminals))
