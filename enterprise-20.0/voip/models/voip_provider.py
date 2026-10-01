from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, UserError

# Keep these values aligned with the seeded XML data for the special Odoo provider.
ODOO_PROVIDER_VALS = {
    "name": "Odoo Phone Service",
    "ws_server": "wss://sip.odoo.com:7443",
    "pbx_ip": "sip.odoo.com",
    "mode": "prod",
    "voicemail_code": "*98",
    "company_id": False,
    "sequence": 0,
}


class VoipProvider(models.Model):
    """VoIP provider configuration record used by users and PBX provisioning."""

    _name = "voip.provider"
    _description = "VoIP Provider"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    is_odoo_provider = fields.Boolean(compute="_compute_is_odoo_provider")
    company_id = fields.Many2one("res.company", string="Company")
    ws_server = fields.Char(
        "WebSocket",
        help="The URL of your WebSocket",
        default="ws://localhost",
        groups="base.group_system",
    )
    pbx_ip = fields.Char(
        "PBX Server IP",
        help="The IP address of your PBX Server",
        default="localhost",
        groups="base.group_system",
    )
    mode = fields.Selection(
        [
            ("demo", "Demo"),
            ("prod", "Production"),
        ],
        string="VoIP Environment",
        help=(
            "Demo: Calls are simulated and no device rings. "
            "Production: Phone-number links use Odoo Phone when the provider and current user "
            "are configured for calling. Otherwise, they open the device's calling app through "
            "a tel: link."
        ),
        default="demo",
        required=True,
    )
    recording_enabled = fields.Boolean(default=False, export_string_translation=False)
    recording_policy_option = fields.Selection(
        [
            ("always", "Force recording of all calls. Users can't disable it."),
            ("user", "Let users decide when to record."),
        ],
        default="always",
        export_string_translation=False,
    )
    recording_policy = fields.Selection(
        [
            ("always", "Force for all users"),
            ("user", "Let users decide"),
            ("disabled", "Disabled"),
        ],
        compute="_compute_recording_policy",
        inverse="_inverse_recording_policy",
    )
    voicemail_code = fields.Char(
        "Mailbox Code",
        help="The phone number or short code used to dial into the mailbox system."
    )
    cloud_storage_provider = fields.Char(compute="_compute_cloud_storage_provider")

    def _cloud_storage_provider(self):
        return self.env["ir.config_parameter"].sudo().get_str("cloud_storage_provider")

    @api.constrains("recording_enabled", "mode")
    def _check_recording_enabled(self):
        cloud_storage_module = self.env["ir.module.module"].sudo().search_fetch(
            [("name", "=", "cloud_storage")], ["state"], limit=1
        )
        is_cloud_storage_installed = cloud_storage_module and cloud_storage_module.state == "installed"

        for provider in self:
            if provider.recording_enabled and not self._cloud_storage_provider() and provider.mode == "prod":
                if not is_cloud_storage_installed:
                    action = self.env.ref("voip.cloud_storage_error_apps_action")
                    raise RedirectWarning(
                        self.env._(
                            "Cloud storage is not installed. Call recording cannot be enabled. "
                            "Please install the cloud storage module first."
                        ),
                        action.id,
                        self.env._("Install Cloud Storage")
                    )
                else:
                    action = self.env.ref("voip.cloud_storage_error_settings_action")
                    raise RedirectWarning(
                        self.env._(
                            "Cloud storage is not configured. Call recording cannot be enabled. "
                            "Please configure a cloud storage provider first."
                        ),
                        action.id,
                        self.env._("Go to General Settings")
                    )

    def _compute_is_odoo_provider(self):
        odoo_provider = self.get_or_create_odoo_provider()
        for provider in self:
            provider.is_odoo_provider = provider == odoo_provider

    @api.model
    def get_or_create_odoo_provider(self):
        """Return the Odoo VoIP provider record, recreating it if deleted."""
        provider = self.env.ref("voip.odoo_provider", raise_if_not_found=False)
        if provider:
            return provider
        provider_sudo = self.sudo().create(ODOO_PROVIDER_VALS)
        self.env["ir.model.data"].sudo().create({
            "name": "odoo_provider",
            "module": "voip",
            "model": "voip.provider",
            "res_id": provider_sudo.id,
            "noupdate": True,
        })
        return provider_sudo.sudo(False)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_odoo_provider(self):
        odoo_provider = self.env.ref("voip.odoo_provider", raise_if_not_found=False)
        if odoo_provider and odoo_provider in self:
            raise UserError(self.env._("You cannot delete Odoo Phone Service."))

    def _compute_cloud_storage_provider(self):
        cloud_storage_provider = self._cloud_storage_provider()
        for provider in self:
            provider.cloud_storage_provider = cloud_storage_provider

    @api.depends("recording_enabled", "recording_policy_option", "mode")
    def _compute_recording_policy(self):
        cloud_storage_provider = self._cloud_storage_provider()
        for provider in self:
            if not provider.recording_enabled or (provider.mode == "prod" and not cloud_storage_provider):
                provider.recording_policy = "disabled"
            else:
                provider.recording_policy = provider.recording_policy_option

    def _inverse_recording_policy(self):
        for provider in self:
            if provider.recording_policy == "disabled":
                provider.recording_enabled = False
            else:
                provider.recording_enabled = True
                provider.recording_policy_option = provider.recording_policy
