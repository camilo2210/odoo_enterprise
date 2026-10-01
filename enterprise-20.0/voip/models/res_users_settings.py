import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.mail.tools.discuss import Store

from .pbx_service import (
    PBX_USER_FORWARD_DESTINATION_KINDS,
    PBX_USER_FORWARD_DESTINATION_MODELS,
    PBX_USER_FORWARD_DESTINATION_TYPES,
)
from .voip_extension import EXTENSION_NUMBER_RE

LABEL_EXTERNAL_DEVICE = "Call via desk/mobile"
HELP_EXTERNAL_DEVICE = "Enter the number of another device (desk phone or mobile). Calls placed in Odoo Phone will ring that device and then connect you to the recipient."
LABEL_RING_CONCURRENT_CALLS = "Ring Concurrent Calls"
HELP_RING_CONCURRENT_CALLS = (
    "If checked, incoming calls received during an ongoing call will ring. "
    "If unchecked, they will be forwarded according to the On Busy rule or "
    "they will return a busy tone."
)
PBX_SYNC_FIELDS = {
    "voip_ring_concurrent_calls",
    "voip_no_answer_destination_ref",
    "voip_no_answer_destination_type",
    "voip_no_answer_destination_kind",
    "voip_no_answer_immediate_destination",
    "voip_no_answer_outcall_number",
    "voip_busy_destination_ref",
    "voip_busy_destination_type",
    "voip_busy_destination_kind",
    "voip_busy_outcall_number",
    "voip_disconnected_destination_ref",
    "voip_disconnected_destination_type",
    "voip_disconnected_destination_kind",
    "voip_disconnected_outcall_number",
    "voip_no_answer_timeout",
}
PBX_CONCURRENT_CALLS_LIMIT = 5
PBX_SINGLE_CALL_LIMIT = 1
VOIP_CONFIG_FIELDS = {
    "voip_provider_id",
    "voip_username",
    "voip_secret",
}
E164_NUMBER_RE = re.compile(r"^\+[1-9]\d{1,14}$")
PROVISIONED_NO_ANSWER_TIMEOUT = 20


class ResUsersSettings(models.Model):
    _inherit = "res.users.settings"

    voip_provider_id = fields.Many2one(
        "voip.provider",
        string="VoIP Provider",
    )
    uses_odoo_provider = fields.Boolean(related="voip_provider_id.is_odoo_provider")
    pbx_extension_number = fields.Char(
        compute="_compute_pbx_extension_number",
        inverse="_inverse_pbx_extension_number",
        readonly=False,
        string="Extension",
    )
    has_assigned_did_number = fields.Boolean(compute="_compute_has_assigned_did_number")
    can_manage_pbx_extension = fields.Boolean(compute="_compute_can_manage_pbx_extension")

    should_call_from_another_device = fields.Boolean(
        "Use Another Device",
        help=HELP_EXTERNAL_DEVICE,
    )
    external_device_number = fields.Char(
        LABEL_EXTERNAL_DEVICE,
        help=HELP_EXTERNAL_DEVICE,
    )
    how_to_call_on_mobile = fields.Selection(
        [("ask", "Always Ask"), ("voip", "Odoo Phone"), ("phone", "Phone's Default App")],
        default="ask",
        string="Default phone app",
        help="""Choose which app to open when clicking on a phone number in the Odoo Mobile app.""",
        required=True,
    )

    voip_username = fields.Char(
        "VoIP username",
        help="The username that will be used to register with the PBX server.",
    )
    voip_secret = fields.Char(
        "VoIP secret",
        help="The password that will be used to register with the PBX server.",
    )
    voip_linphone_provisioning_serial = fields.Integer(
        "Linphone provisioning serial",
        copy=False,
        help="Bumped every time a Linphone bootstrap document is served, "
             "which invalidates every QR code issued before.",
    )
    voip_linphone_provisioning_key_hashes = fields.Json(
        "Linphone provisioning key digests",
        groups=fields.NO_ACCESS,
        copy=False,
        help="Keyed digests of the keys provisioned phones send back on every "
             "configuration refresh, oldest first. One entry per phone; "
             "consuming a QR code appends one and drops the oldest beyond the cap.",
    )

    do_not_disturb_until_dt = fields.Datetime(
        string="Do Not Disturb until",
        help="If set, Odoo Phone will be in Do Not Disturb mode until this time.",
    )
    voip_no_answer_timeout = fields.Integer(
        string="No answer after",
        help="Set to 0 to forward the call immediately.",
    )
    voip_no_answer_destination_type = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_TYPES,
        string="No Answer Destination",
    )
    voip_no_answer_destination_kind = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_KINDS,
        string="No Answer Destination Kind",
    )
    voip_no_answer_destination_ref = fields.Reference(
        selection=PBX_USER_FORWARD_DESTINATION_MODELS,
        string="No Answer Internal Destination",
    )
    voip_no_answer_outcall_number = fields.Char(string="No Answer External Number")
    voip_no_answer_immediate_destination = fields.Char(
        string="Immediate Forward Destination",
        help="Enter an internal extension or an external number in E.164 format.",
    )
    voip_busy_destination_type = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_TYPES,
        string="Busy Destination",
    )
    voip_busy_destination_kind = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_KINDS,
        string="Busy Destination Kind",
    )
    voip_busy_destination_ref = fields.Reference(
        selection=PBX_USER_FORWARD_DESTINATION_MODELS,
        string="Busy Internal Destination",
    )
    voip_busy_outcall_number = fields.Char(string="Busy External Number")
    voip_disconnected_destination_type = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_TYPES,
        string="Disconnected Destination",
    )
    voip_disconnected_destination_kind = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_KINDS,
        string="Disconnected Destination Kind",
    )
    voip_disconnected_destination_ref = fields.Reference(
        selection=PBX_USER_FORWARD_DESTINATION_MODELS,
        string="Disconnected Internal Destination",
    )
    voip_disconnected_outcall_number = fields.Char(string="Disconnected External Number")
    voip_ring_concurrent_calls = fields.Boolean(
        string=LABEL_RING_CONCURRENT_CALLS,
        help=HELP_RING_CONCURRENT_CALLS,
    )

    def _compute_can_manage_pbx_extension(self):
        can_manage_pbx_extension = self.env.user.has_group("voip.group_voip_admin")
        for settings in self:
            settings.can_manage_pbx_extension = can_manage_pbx_extension

    @api.depends("user_id")
    def _compute_has_assigned_did_number(self):
        users_with_did = self.env["voip.did.number"].sudo().search([
            ("user_id", "in", self.user_id.ids),
            ("state", "in", ("ordering", "pending", "active", "suspended")),
        ]).user_id
        for settings in self:
            settings.has_assigned_did_number = settings.user_id in users_with_did

    @api.constrains("voip_provider_id")
    def _check_demo_provider_access(self):
        if (
            not self.env.user.has_group("voip.group_voip_admin")
            and any(settings.voip_provider_id.mode == "demo" for settings in self)
        ):
            raise AccessError(_("Only VoIP administrators can select demo providers."))

    def _sync_odoo_extension(self):
        self.user_id.sudo().routing_extension_id._sync_pbx()

    @api.model
    def _get_user_from_voip_username(self, username, provider=None):
        """Return the (sudo) user registering with `username`, restricted to
        `provider` when one is given (pass an empty provider to require none)."""
        if not username:
            return self.env["res.users"]
        domain = [("voip_username", "=", username)]
        if provider is not None:
            domain.append(("voip_provider_id", "=", provider.id))
        return self.sudo().search(domain, limit=1).user_id

    @api.depends("user_id")
    def _compute_pbx_extension_number(self):
        extensions_by_user_id = {
            extension.destination_ref.id: extension
            for extension in self.user_id.sudo().routing_extension_id
        }
        for settings in self:
            extension = extensions_by_user_id.get(settings.user_id.id)
            settings.pbx_extension_number = extension.number if extension else False

    def _inverse_pbx_extension_number(self):
        if not self.env.user.has_group("voip.group_voip_admin"):
            raise AccessError(_("Only VoIP administrators can assign PBX extensions."))
        Extension = self.env["voip.extension"]
        for settings in self:
            if not settings.user_id:
                continue
            extension_number = settings.pbx_extension_number and settings.pbx_extension_number.strip()
            assigned_extension = settings.user_id.sudo().routing_extension_id
            if not extension_number:
                assigned_extension.unlink()
                continue
            if not EXTENSION_NUMBER_RE.fullmatch(extension_number):
                raise ValidationError(_("Enter an extension number from 100 to 9999."))
            destination_ref = f"res.users,{settings.user_id.id}"
            if assigned_extension:
                assigned_extension.write({"number": extension_number})
            else:
                Extension.create({
                    "number": extension_number,
                    "destination_ref": destination_ref,
                })

    @api.constrains("voip_no_answer_timeout")
    def _check_voip_no_answer_timeout(self):
        for settings in self:
            if settings.voip_no_answer_timeout < 0:
                raise ValidationError(_("The no answer timeout must be positive."))

    @api.constrains(
        "voip_no_answer_destination_type",
        "voip_no_answer_destination_kind",
        "voip_no_answer_destination_ref",
        "voip_no_answer_immediate_destination",
        "voip_no_answer_outcall_number",
        "voip_busy_destination_type",
        "voip_busy_destination_kind",
        "voip_busy_destination_ref",
        "voip_busy_outcall_number",
        "voip_disconnected_destination_type",
        "voip_disconnected_destination_kind",
        "voip_disconnected_destination_ref",
        "voip_disconnected_outcall_number",
    )
    def _check_voip_user_destinations(self):
        for settings in self:
            for fallback in ("no_answer", "busy", "disconnected"):
                destination_type = settings[f"voip_{fallback}_destination_type"]
                if (
                    fallback == "no_answer"
                    and destination_type == "forward"
                    and settings.voip_no_answer_timeout == 0
                ):
                    destination = (settings.voip_no_answer_immediate_destination or "").strip()
                    if not (
                        EXTENSION_NUMBER_RE.fullmatch(destination)
                        or E164_NUMBER_RE.fullmatch(destination)
                    ):
                        raise ValidationError(_(
                            "Enter an internal extension or an external number in E.164 format.",
                        ))
                    continue
                if destination_type != "forward":
                    continue
                kind = settings[f"voip_{fallback}_destination_kind"]
                destination_ref = settings[f"voip_{fallback}_destination_ref"]
                if kind == "external":
                    number = (settings[f"voip_{fallback}_outcall_number"] or "").strip()
                    if not E164_NUMBER_RE.fullmatch(number):
                        raise ValidationError(_(
                            "Enter an external number in E.164 format, for example +32471234567.",
                        ))
                elif not kind or not destination_ref:
                    raise ValidationError(_("Select a destination."))
                elif destination_ref._name != kind:
                    raise ValidationError(_(
                        "The selected destination does not match the destination kind.",
                    ))

    def write(self, vals):
        notify_voip_config_users = self.env["res.users"]
        if VOIP_CONFIG_FIELDS & vals.keys():
            notify_voip_config_users = self.user_id
        sync_odoo_extension_settings = self.env["res.users.settings"]
        if vals.get("voip_provider_id") and not self.env.context.get("voip_skip_pbx_sync"):
            odoo_provider = self.env["voip.pbx.service"].voip_provider
            if vals["voip_provider_id"] == odoo_provider.id:
                sync_odoo_extension_settings = self.filtered(
                    lambda settings: settings.voip_provider_id != odoo_provider,
                )
        res = super().write(vals)
        if sync_odoo_extension_settings:
            sync_odoo_extension_settings._sync_odoo_extension()
        if PBX_SYNC_FIELDS & vals.keys() and not self.env.context.get("voip_skip_pbx_sync"):
            self._voip_sync_pbx()
        if notify_voip_config_users and not self.env.context.get("voip_skip_config_bus"):
            notify_voip_config_users._bus_send("voip.config/updated", {})
        return res

    def _voip_sync_pbx(self):
        if not self.env.context.get("voip_skip_pbx_sync"):
            for settings in self.sudo():
                user = settings.user_id
                if not user.voip_pbx_user_id:
                    continue
                always_destination = None
                if (
                    settings.voip_no_answer_destination_type == "forward"
                    and settings.voip_no_answer_timeout == 0
                ):
                    always_destination = settings.voip_no_answer_immediate_destination
                    no_answer_destination = None
                else:
                    no_answer_destination = settings._get_pbx_user_destination("no_answer")
                settings.env["voip.pbx.service"]._update_user_routing(
                    user_id=user.voip_pbx_user_id,
                    no_answer_destination=no_answer_destination,
                    busy_destination=settings._get_pbx_user_destination("busy"),
                    fail_destination=settings._get_pbx_user_destination("disconnected"),
                    always_destination=always_destination,
                    no_answer_timeout=settings.voip_no_answer_timeout,
                    simultaneous_calls=settings._get_pbx_simultaneous_calls(),
                )

    def _get_pbx_simultaneous_calls(self):
        self.ensure_one()
        return (
            PBX_CONCURRENT_CALLS_LIMIT
            if self.voip_ring_concurrent_calls
            else PBX_SINGLE_CALL_LIMIT
        )

    def _get_pbx_user_destination(self, fallback):
        """Build the typed Wazo destination selected for a user fallback."""
        self.ensure_one()
        service = self.env["voip.pbx.service"]
        if self[f"voip_{fallback}_destination_type"] != "forward":
            if fallback == "busy":
                return service._get_default_user_busy_destination()
            return None
        if self[f"voip_{fallback}_destination_kind"] == "external":
            number = self[f"voip_{fallback}_outcall_number"]
            return {
                "type": "outcall",
                "exten": number.strip().removeprefix("+"),
            }
        return service._get_pbx_destination(
            self[f"voip_{fallback}_destination_ref"],
        )

    def _voip_store_sip_username(self, sip_username):
        self.ensure_one()
        if not sip_username or sip_username == self.voip_username:
            return
        self.with_context(
            voip_skip_config_bus=True,
            voip_skip_pbx_sync=True,
        ).voip_username = sip_username
        if not self.env.context.get("voip_skip_config_bus"):
            self.user_id._bus_send("voip.config/updated", {})

    def _get_fields_blacklist(self):
        return [
            *super()._get_fields_blacklist(),
            "voip_no_answer_timeout",
            "voip_no_answer_destination_type",
            "voip_no_answer_destination_kind",
            "voip_no_answer_destination_ref",
            "voip_no_answer_immediate_destination",
            "voip_no_answer_outcall_number",
            "voip_busy_destination_type",
            "voip_busy_destination_kind",
            "voip_busy_destination_ref",
            "voip_busy_outcall_number",
            "voip_linphone_provisioning_serial",
            "voip_linphone_provisioning_key_hashes",
            "voip_disconnected_destination_type",
            "voip_disconnected_destination_kind",
            "voip_disconnected_destination_ref",
            "voip_disconnected_outcall_number",
        ]

    def _store_settings_fields(self, res: Store.FieldList):
        super()._store_settings_fields(res)
        res.extend([
            "do_not_disturb_until_dt",
            "external_device_number",
            "how_to_call_on_mobile",
            "should_call_from_another_device",
            "voip_secret",
            "voip_username",
        ])

    def _format_settings(self, fields_to_format):
        res = super()._format_settings(fields_to_format)
        if "do_not_disturb_until_dt" in fields_to_format:
            res["do_not_disturb_until_dt"] = fields.Datetime.to_string(
                self.do_not_disturb_until_dt,
            )
        return res

    # ------------------------------------------------------------------
    # Deprovisioning
    # ------------------------------------------------------------------

    def _clear_sip_credentials(self):
        self.sudo().write({
            "voip_provider_id": False,
            "voip_username": False,
            "voip_secret": False,
        })
