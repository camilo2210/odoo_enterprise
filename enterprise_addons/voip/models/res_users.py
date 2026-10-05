# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import hash_sign
from odoo.tools.image import image_data_uri

from odoo.addons.mail.tools.discuss import Store
from odoo.addons.voip.models.pbx_service import (
    PBX_USER_FORWARD_DESTINATION_KINDS,
    PBX_USER_FORWARD_DESTINATION_MODELS,
    PBX_USER_FORWARD_DESTINATION_TYPES,
    SHARED_DESTINATION_TYPE_BY_MODEL,
)
from odoo.addons.voip.models.phone_service_api import get_buy_credits_action
from odoo.addons.voip.models.res_users_settings import (
    E164_NUMBER_RE,
    HELP_EXTERNAL_DEVICE,
    HELP_RING_CONCURRENT_CALLS,
    LABEL_EXTERNAL_DEVICE,
    LABEL_RING_CONCURRENT_CALLS,
    PBX_SYNC_FIELDS,
    PROVISIONED_NO_ANSWER_TIMEOUT,
    VOIP_CONFIG_FIELDS,
)
from odoo.addons.voip.tools.linphone import (
    PROVISIONING_KIND_BOOTSTRAP,
    PROVISIONING_KIND_REFRESH,
    PROVISIONING_URI_SCHEME,
    PROVISIONING_TOKEN_EXPIRATION_HOURS,
    PROVISIONING_TOKEN_SCOPE,
)

_logger = logging.getLogger(__name__)

ALLOWED_VOIP_BUS_MESSAGE_TYPES = frozenset({
    "voip/agent_state",
    "voip/request_agent_states",
    "voip.call.pull/initiate",
    "voip.call.pull/entry_failed",
    "voip.call.pull/suppress_invite",
    "voip.call.pull/pending_entries",
    "voip.call.pull/pending_entries_received",
    "voip.call.pull/result",
})


class ResUsers(models.Model):
    _name = "res.users"
    _inherit = [
        "res.users",
        "voip.extension.destination.mixin",
        "voip.pbx.destination.mixin",
    ]

    has_active_call = fields.Boolean()
    last_seen_phone_call = fields.Many2one("voip.call")
    voip_queue_status = fields.Selection(
        [
            ("in_call", "In Call"),
            ("waiting", "Waiting"),
            ("disconnected", "Disconnected"),
        ],
        compute="_compute_voip_queue_status",
        string="Queue Status",
    )

    uses_odoo_provider = fields.Boolean(compute="_compute_uses_odoo_provider")

    # --------------------------------------------------------------------------
    # VoIP User Configuration Fields
    # --------------------------------------------------------------------------
    # These fields mirror those defined in `res.users.settings`. The reason they
    # are not directly defined in here is that we want these fields to have
    # different access rights than the rest of the fields of `res.users`. See
    # their definition in `res.users.settings` for comprehensive documentation.
    # --------------------------------------------------------------------------
    should_call_from_another_device = fields.Boolean(
        "Use Another Device",
        help=HELP_EXTERNAL_DEVICE,
        compute="_compute_should_call_from_another_device",
        inverse="_reflect_change_in_res_users_settings",
        groups="base.group_user",
        user_writeable=True,
    )
    external_device_number = fields.Char(
        compute="_compute_external_device_number",
        help=HELP_EXTERNAL_DEVICE,
        inverse="_reflect_change_in_res_users_settings",
        groups="base.group_user",
        string=LABEL_EXTERNAL_DEVICE,
        user_writeable=True,
    )
    how_to_call_on_mobile = fields.Selection(
        [
            ("voip", "Call with Odoo Phone"),
            ("phone", "Call with phone's default app"),
            ("ask", "Always ask before calling"),
        ],
        compute="_compute_how_to_call_on_mobile",
        inverse="_reflect_change_in_res_users_settings",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_provider_id = fields.Many2one(
        "voip.provider",
        compute="_compute_voip_provider_id",
        inverse="_reflect_change_in_res_users_settings",
        groups="base.group_user",
        user_writeable=True,
    )
    pbx_extension_number = fields.Char(
        related="res_users_settings_id.pbx_extension_number",
        readonly=False,
        string="Odoo Phone Extension",
    )
    has_assigned_did_number = fields.Boolean(
        related="res_users_settings_id.has_assigned_did_number",
    )
    can_manage_pbx_extension = fields.Boolean(related="res_users_settings_id.can_manage_pbx_extension")
    voip_secret = fields.Char(
        compute="_compute_voip_secret",
        inverse="_reflect_change_in_res_users_settings",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_username = fields.Char(
        compute="_compute_voip_username",
        inverse="_reflect_change_in_res_users_settings",
        groups="base.group_user",
        user_writeable=True,
    )
    linphone_provisioning_qr_code = fields.Char(
        string="Provisioning",
        help="1) Install Linphone on your smartphone\n"
             "2) Scan the QR code\n"
             "\n"
             "Linphone holds a single account, so scanning replaces the one already configured on that smartphone.",
        compute="_compute_linphone_provisioning",
        groups="base.group_user",
    )
    linphone_provisioning_url = fields.Char(
        string="Provisioning Link",
        help="Paste this link in the remote provisioning setting of Linphone Desktop.\n"
             "\n"
             "Single use, like the QR code: it is invalidated as soon as either one is used.",
        compute="_compute_linphone_provisioning",
        groups="base.group_user",
    )

    voip_pbx_user_id = fields.Integer(
        string="PBX User ID",
        copy=False,
        groups="base.group_system",
    )
    voip_pbx_user_uuid = fields.Char(
        string="PBX User UUID",
        copy=False,
        groups="base.group_system",
    )
    voip_pbx_line_id = fields.Integer(
        string="PBX Line ID",
        copy=False,
        groups="base.group_system",
    )
    voip_pbx_agent_id = fields.Integer(
        string="PBX Agent ID",
        copy=False,
        groups="base.group_system",
    )
    voip_no_answer_timeout = fields.Integer(
        compute="_compute_voip_no_answer_timeout",
        inverse="_reflect_change_in_res_users_settings",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_no_answer_destination_type = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_TYPES,
        compute="_compute_voip_no_answer_destination_type",
        inverse="_inverse_voip_no_answer_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_no_answer_destination_kind = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_KINDS,
        compute="_compute_voip_no_answer_destination_kind",
        inverse="_inverse_voip_no_answer_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_no_answer_destination_ref = fields.Reference(
        selection=PBX_USER_FORWARD_DESTINATION_MODELS,
        compute="_compute_voip_no_answer_destination_ref",
        inverse="_inverse_voip_no_answer_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_no_answer_outcall_number = fields.Char(
        compute="_compute_voip_no_answer_outcall_number",
        inverse="_inverse_voip_no_answer_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_no_answer_immediate_destination = fields.Char(
        compute="_compute_voip_no_answer_immediate_destination",
        inverse="_inverse_voip_no_answer_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_busy_destination_type = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_TYPES,
        compute="_compute_voip_busy_destination_type",
        inverse="_inverse_voip_busy_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_busy_destination_kind = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_KINDS,
        compute="_compute_voip_busy_destination_kind",
        inverse="_inverse_voip_busy_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_busy_destination_ref = fields.Reference(
        selection=PBX_USER_FORWARD_DESTINATION_MODELS,
        compute="_compute_voip_busy_destination_ref",
        inverse="_inverse_voip_busy_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_busy_outcall_number = fields.Char(
        compute="_compute_voip_busy_outcall_number",
        inverse="_inverse_voip_busy_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_disconnected_destination_type = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_TYPES,
        compute="_compute_voip_disconnected_destination_type",
        inverse="_inverse_voip_disconnected_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_disconnected_destination_kind = fields.Selection(
        PBX_USER_FORWARD_DESTINATION_KINDS,
        compute="_compute_voip_disconnected_destination_kind",
        inverse="_inverse_voip_disconnected_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_disconnected_destination_ref = fields.Reference(
        selection=PBX_USER_FORWARD_DESTINATION_MODELS,
        compute="_compute_voip_disconnected_destination_ref",
        inverse="_inverse_voip_disconnected_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_disconnected_outcall_number = fields.Char(
        compute="_compute_voip_disconnected_outcall_number",
        inverse="_inverse_voip_disconnected_destination",
        groups="base.group_user",
        user_writeable=True,
    )
    voip_ring_concurrent_calls = fields.Boolean(
        compute="_compute_voip_ring_concurrent_calls",
        help=HELP_RING_CONCURRENT_CALLS,
        inverse="_reflect_change_in_res_users_settings",
        groups="base.group_user",
        string=LABEL_RING_CONCURRENT_CALLS,
        user_writeable=True,
    )

    @api.model
    def _get_from_pbx_user_uuid(self, user_uuid):
        if not user_uuid:
            return self.browse()
        return self.sudo().search([("voip_pbx_user_uuid", "=", user_uuid)], limit=1)

    @api.depends("voip_provider_id")
    def _compute_uses_odoo_provider(self):
        for user in self:
            user.uses_odoo_provider = user.voip_provider_id.is_odoo_provider

    def _select_odoo_voip_provider(self):
        odoo_provider = self.env["voip.pbx.service"].voip_provider
        changed_users = self.env["res.users"]
        for user in self:
            settings = self.env["res.users.settings"].sudo()._find_or_create_for_user(user)
            if settings.voip_provider_id == odoo_provider:
                continue
            settings.with_context(
                voip_skip_config_bus=True,
                voip_skip_pbx_sync=True,
            ).voip_provider_id = odoo_provider
            changed_users |= user
        if changed_users:
            if not self.env.context.get("voip_skip_pbx_sync"):
                changed_users.sudo().routing_extension_id.filtered("pbx_extension_id")._sync_pbx()
            if not self.env.context.get("voip_skip_config_bus"):
                changed_users._bus_send("voip.config/updated", {})

    @api.depends("has_active_call", "im_status")
    def _compute_voip_queue_status(self):
        for user in self:
            if user.has_active_call:
                user.voip_queue_status = "in_call"
            elif user.im_status == "offline":
                user.voip_queue_status = "disconnected"
            else:
                user.voip_queue_status = "waiting"

    @api.depends("res_users_settings_id.external_device_number")
    def _compute_external_device_number(self):
        for user in self:
            user.external_device_number = user.res_users_settings_id.external_device_number

    @api.depends("res_users_settings_id.how_to_call_on_mobile")
    def _compute_how_to_call_on_mobile(self):
        for user in self:
            user.how_to_call_on_mobile = user.res_users_settings_id.how_to_call_on_mobile

    @api.depends("res_users_settings_id.should_call_from_another_device")
    def _compute_should_call_from_another_device(self):
        for user in self:
            user.should_call_from_another_device = user.res_users_settings_id.should_call_from_another_device

    @api.depends_context("uid")
    @api.depends(
        "uses_odoo_provider",
        "voip_username",
        "res_users_settings_id.voip_linphone_provisioning_serial",
    )
    def _compute_linphone_provisioning(self):
        for user in self:
            if user == self.env.user and user.uses_odoo_provider and user.voip_username:
                url = user._get_linphone_provisioning_url()
                qr_code = self.env["ir.actions.report"].barcode(
                    "QR",
                    f"{PROVISIONING_URI_SCHEME}{url}",
                    width=512,
                    height=512,
                    barLevel="M",
                )
                user.linphone_provisioning_qr_code = image_data_uri(qr_code)
                user.linphone_provisioning_url = url
            else:
                user.linphone_provisioning_qr_code = False
                user.linphone_provisioning_url = False

    def _get_linphone_provisioning_url(self, expiration_hours=PROVISIONING_TOKEN_EXPIRATION_HOURS):
        """Single-use bootstrap URL, the one encoded in the QR code."""
        self.ensure_one()
        # The serial is signed in, and serving a bootstrap document bumps it:
        # every URL issued before becomes invalid. sudo() because the QR is
        # computed in the user's own environment.
        settings = self.sudo().res_users_settings_id
        return self._linphone_provisioning_url(hash_sign(
            self.env(su=True),
            PROVISIONING_TOKEN_SCOPE,
            [PROVISIONING_KIND_BOOTSTRAP, self.id, settings.voip_linphone_provisioning_serial],
            expiration_hours=expiration_hours,
        ))

    def _get_linphone_refresh_url(self):
        """Durable URL the phone re-fetches at every core start.

        No expiration and no secret in the payload: the request is authorised by
        the PROVISIONING_KEY_HEADER header, which the bootstrap document
        provisioned into the phone's own configuration. Every phone of a user
        shares this URL and is told apart by its key.
        """
        self.ensure_one()
        return self._linphone_provisioning_url(hash_sign(
            self.env(su=True),
            PROVISIONING_TOKEN_SCOPE,
            [PROVISIONING_KIND_REFRESH, self.id],
        ))

    def _linphone_provisioning_url(self, token):
        return f"{self.get_base_url()}/voip/linphone_provisioning/{token}"

    @api.depends("res_users_settings_id.voip_provider_id")
    def _compute_voip_provider_id(self):
        for user in self:
            user.voip_provider_id = user.res_users_settings_id.voip_provider_id

    @api.depends("res_users_settings_id.voip_secret")
    def _compute_voip_secret(self):
        for user in self:
            user.voip_secret = user._filtered_access('write').res_users_settings_id.voip_secret

    @api.depends("res_users_settings_id.voip_username")
    def _compute_voip_username(self):
        for user in self:
            user.voip_username = user.res_users_settings_id.voip_username

    @api.depends("res_users_settings_id.voip_no_answer_timeout")
    def _compute_voip_no_answer_timeout(self):
        for user in self:
            user.voip_no_answer_timeout = user.res_users_settings_id.voip_no_answer_timeout

    @api.depends("res_users_settings_id.voip_no_answer_destination_type")
    def _compute_voip_no_answer_destination_type(self):
        for user in self:
            user.voip_no_answer_destination_type = user.res_users_settings_id.voip_no_answer_destination_type

    @api.depends("res_users_settings_id.voip_no_answer_destination_kind")
    def _compute_voip_no_answer_destination_kind(self):
        for user in self:
            user.voip_no_answer_destination_kind = user.res_users_settings_id.voip_no_answer_destination_kind

    @api.depends("res_users_settings_id.voip_no_answer_destination_ref")
    def _compute_voip_no_answer_destination_ref(self):
        for user in self:
            user.voip_no_answer_destination_ref = user.res_users_settings_id.voip_no_answer_destination_ref

    @api.depends("res_users_settings_id.voip_no_answer_immediate_destination")
    def _compute_voip_no_answer_immediate_destination(self):
        for user in self:
            user.voip_no_answer_immediate_destination = user.res_users_settings_id.voip_no_answer_immediate_destination

    @api.depends("res_users_settings_id.voip_no_answer_outcall_number")
    def _compute_voip_no_answer_outcall_number(self):
        for user in self:
            user.voip_no_answer_outcall_number = user.res_users_settings_id.voip_no_answer_outcall_number

    def _inverse_voip_no_answer_destination(self):
        self._reflect_voip_destination_change("no_answer")

    @api.depends("res_users_settings_id.voip_busy_destination_type")
    def _compute_voip_busy_destination_type(self):
        for user in self:
            user.voip_busy_destination_type = user.res_users_settings_id.voip_busy_destination_type

    @api.depends("res_users_settings_id.voip_busy_destination_kind")
    def _compute_voip_busy_destination_kind(self):
        for user in self:
            user.voip_busy_destination_kind = user.res_users_settings_id.voip_busy_destination_kind

    @api.depends("res_users_settings_id.voip_busy_destination_ref")
    def _compute_voip_busy_destination_ref(self):
        for user in self:
            user.voip_busy_destination_ref = user.res_users_settings_id.voip_busy_destination_ref

    @api.depends("res_users_settings_id.voip_busy_outcall_number")
    def _compute_voip_busy_outcall_number(self):
        for user in self:
            user.voip_busy_outcall_number = user.res_users_settings_id.voip_busy_outcall_number

    @api.depends("res_users_settings_id.voip_disconnected_destination_type")
    def _compute_voip_disconnected_destination_type(self):
        for user in self:
            user.voip_disconnected_destination_type = user.res_users_settings_id.voip_disconnected_destination_type

    @api.depends("res_users_settings_id.voip_disconnected_destination_kind")
    def _compute_voip_disconnected_destination_kind(self):
        for user in self:
            user.voip_disconnected_destination_kind = user.res_users_settings_id.voip_disconnected_destination_kind

    @api.depends("res_users_settings_id.voip_disconnected_destination_ref")
    def _compute_voip_disconnected_destination_ref(self):
        for user in self:
            user.voip_disconnected_destination_ref = user.res_users_settings_id.voip_disconnected_destination_ref

    @api.depends("res_users_settings_id.voip_disconnected_outcall_number")
    def _compute_voip_disconnected_outcall_number(self):
        for user in self:
            user.voip_disconnected_outcall_number = user.res_users_settings_id.voip_disconnected_outcall_number

    @api.depends("res_users_settings_id.voip_ring_concurrent_calls")
    def _compute_voip_ring_concurrent_calls(self):
        for user in self:
            user.voip_ring_concurrent_calls = (
                user.res_users_settings_id.voip_ring_concurrent_calls
            )

    def _inverse_voip_busy_destination(self):
        self._reflect_voip_destination_change("busy")

    def _inverse_voip_disconnected_destination(self):
        self._reflect_voip_destination_change("disconnected")

    def _get_voip_user_configuration_fields(self) -> list[str]:
        """
        List of the VoIP-related fields that are configurable by the user.
        This grants access to user settings model for the inverse function.
        """
        return [
            "external_device_number",
            "how_to_call_on_mobile",
            "should_call_from_another_device",
            "voip_ring_concurrent_calls",
            "voip_secret",
            "voip_username",
            "voip_provider_id",
            "voip_no_answer_timeout",
        ]

    def _voip_wants_wakeup_token(self):
        """Whether the PBX should be able to wake this user's browser.

        Only for a user who forwards a call no device of theirs can take
        nowhere: with a destination, Wazo hands the call over at once instead
        of holding the caller while a push races a browser into registering.
        """
        self.ensure_one()
        return self.sudo().res_users_settings_id.voip_disconnected_destination_type != "forward"

    def _voip_disconnected_forward_number(self):
        """The number a disconnected user's calls are forwarded to by default."""
        self.ensure_one()
        number = self._phone_format(fname="phone")
        return number if number and E164_NUMBER_RE.fullmatch(number) else False

    def _prepare_pbx_user_settings(self):
        self.ensure_one()
        settings = self.env["res.users.settings"].sudo()._find_or_create_for_user(self)
        vals = {}
        if not settings.voip_secret:
            vals["voip_secret"] = secrets.token_urlsafe(24)
        if not settings.voip_busy_destination_type:
            vals["voip_busy_destination_type"] = "none"
        phone = self.partner_id.phone and self.partner_id._phone_format(
            number=self.partner_id.phone,
            country=self.partner_id.country_id,
        )
        has_valid_phone = phone and E164_NUMBER_RE.fullmatch(phone)
        if not settings.voip_no_answer_destination_type:
            if not settings.voip_no_answer_timeout:
                vals["voip_no_answer_timeout"] = PROVISIONED_NO_ANSWER_TIMEOUT
            if has_valid_phone:
                vals.update({
                    "voip_no_answer_destination_type": "forward",
                    "voip_no_answer_destination_kind": "external",
                    "voip_no_answer_outcall_number": phone,
                })
        if not settings.voip_disconnected_destination_type:
            if disconnected_phone := self._voip_disconnected_forward_number():
                vals.update({
                    "voip_disconnected_destination_type": "forward",
                    "voip_disconnected_destination_kind": "external",
                    "voip_disconnected_outcall_number": disconnected_phone,
                })
            else:
                vals["voip_disconnected_destination_type"] = "none"
        if vals:
            should_notify_config = bool(VOIP_CONFIG_FIELDS & vals.keys())
            settings.with_context(
                voip_skip_config_bus=True,
                voip_skip_pbx_sync=True,
            ).write(vals)
            if should_notify_config and not self.env.context.get("voip_skip_config_bus"):
                self._bus_send("voip.config/updated", {})
        return settings

    def _sync_pbx_user(self):
        """Ensure this user exists in the PBX without creating an extension."""
        self.ensure_one()
        user = self.sudo()
        settings = user._prepare_pbx_user_settings()
        if (
            user.voip_pbx_user_id
            and user.voip_pbx_user_uuid
            and user.voip_pbx_line_id
            and settings.voip_username
            and settings.voip_secret
        ):
            return
        ids = self.env["voip.pbx.service"]._sync_user(
            user_id=user.voip_pbx_user_id or None,
            user_uuid=user.voip_pbx_user_uuid or None,
            line_id=user.voip_pbx_line_id or None,
            user_name=user.name,
            user_login=user.login,
            odoo_user_id=user.id,
            sip_secret=settings.voip_secret,
            simultaneous_calls=settings._get_pbx_simultaneous_calls(),
        )
        user.with_context(voip_skip_pbx_sync=True).write({
            "voip_pbx_user_id": ids["user_id"],
            "voip_pbx_user_uuid": ids["user_uuid"],
            "voip_pbx_line_id": ids["line_id"],
        })
        settings._voip_store_sip_username(ids.get("sip_username"))

    def _get_pbx_agent_names(self):
        self.ensure_one()
        firstname, _, lastname = (self.name or self.login).partition(" ")
        return {
            "firstname": firstname,
            "lastname": lastname or firstname,
        }

    @api.constrains("share")
    def _check_portal_user_has_no_extension(self):
        if self.filtered("share").sudo().routing_extension_id:
            raise ValidationError(_("A user with a PBX extension must remain an internal user."))

    def write(self, vals):
        should_sync_pbx = PBX_SYNC_FIELDS & vals.keys() and not self.env.context.get("voip_skip_pbx_sync")
        if not should_sync_pbx:
            return super().write(vals)

        res = super(ResUsers, self.with_context(voip_skip_pbx_sync=True)).write(vals)
        self.res_users_settings_id._voip_sync_pbx()
        return res

    def _ensure_pbx_voicemail(self):
        """Create the personal voicemail once the PBX identity is available."""
        for user in self.sudo().filtered("voip_pbx_user_id"):
            # User provisioning disables its own recursive PBX sync, but the
            # independently created voicemail must still be sent to Wazo.
            user.env["voip.voicemail"].with_context(
                voip_skip_pbx_sync=False,
            )._ensure_for_user(user)

    @api.model
    def reset_last_seen_phone_call(self):
        domain = [("user_id", "=", self.env.user.id)]
        last_call = self.env["voip.call"].search(domain, order="id desc", limit=1)
        self.env.user.last_seen_phone_call = last_call.id

    def _get_voip_config(self) -> dict:
        """ Build the value for the voipConfig key, used in the web client through the mail.tools.discuss.Store
        Subclass to inject additional options.
        """
        provider = self.voip_provider_id
        uses_odoo_provider = provider.is_odoo_provider
        did = main_did = outbound_did = self.env["voip.did.number"]
        personal_dids = shared_dids = self.env["voip.did.number"]
        pbx_extension = self.env["voip.extension"]
        if uses_odoo_provider or self.voip_pbx_user_id:
            pbx_extension = self.sudo().routing_extension_id
            user_dids = self.env["voip.did.number"].sudo().search(
                [("user_id", "=", self.id), ("state", "in", ("active", "suspended", "ordering", "pending"))],
            )
            did = user_dids[:1]
            available_dids = self.env["voip.did.number"].sudo().search([
                ("destination_ref", "!=", False),
                ("state", "=", "active"),
            ])
            routing_destination_by_did_id = {
                available_did.id: available_did._get_routing_destination()
                for available_did in available_dids
            }
            personal_dids = available_dids.filtered(
                lambda available_did: (
                    routing_destination_by_did_id[available_did.id]._name == "res.users"
                    and routing_destination_by_did_id[available_did.id] == self
                ),
            )
            shared_dids = available_dids.filtered(
                lambda available_did: (
                    routing_destination_by_did_id[available_did.id]._name
                    in SHARED_DESTINATION_TYPE_BY_MODEL
                ),
            )
            main_did = self.env["voip.did.number"].sudo().search([
                ("is_default_outgoing_number", "=", True),
                ("state", "=", "active"),
            ], limit=1)
            outbound_did = personal_dids[:1] or shared_dids[:1] or main_did

        def format_did(available_did):
            return {
                "countryId": available_did.country_id.id,
                "countryName": available_did.country_id.name,
                "flagUrl": available_did.country_id.image_url,
                "formatted": available_did._phone_get_formatted(available_did.did_number)
                or available_did.did_number,
                "number": available_did.did_number,
            }
        return {
            "callActivityTypeId": self.env["mail.activity.type"].search([("category", "=", "phonecall")], limit=1).id,
            "didNumber": did.did_number or None,
            "didNumberFormatted": (did.did_number and did._phone_get_formatted(did.did_number)) or did.did_number or None,
            "didNumberState": did.state or None,
            "mainNumber": main_did.did_number or None,
            "mainNumberFormatted": (
                main_did.did_number and main_did._phone_get_formatted(main_did.did_number)
            ) or main_did.did_number or None,
            "buyCreditsUrl": get_buy_credits_action(self.env)["url"] if did.state == "suspended" else None,
            "usesOdooProvider": uses_odoo_provider,
            "mode": provider.mode or "demo",
            "missedCalls": self.env["voip.call"]._get_number_of_missed_calls(),
            "outboundCallerId": outbound_did.did_number or None,
            "outboundCallerIdFormatted": (
                outbound_did.did_number and outbound_did._phone_get_formatted(outbound_did.did_number)
            ) or outbound_did.did_number or None,
            "outboundNumbers": [format_did(personal_did) for personal_did in personal_dids],
            "sharedOutboundNumbers": [{
                **format_did(shared_did),
                "destinationType": SHARED_DESTINATION_TYPE_BY_MODEL.get(
                    routing_destination_by_did_id[shared_did.id]._name,
                ),
            } for shared_did in shared_dids],
            "isInternalCallingProvisioned": bool(
                self.voip_pbx_user_id
                and self.voip_pbx_line_id
            ),
            "pbxExtensionNumber": pbx_extension.number or None,
            "pbxAddress": provider.pbx_ip or "localhost",
            "recordingPolicy": provider.recording_policy or "disabled",
            "webSocketUrl": provider.ws_server or "ws://localhost",
            "voicemailCode": provider.voicemail_code or None,
        }

    @api.model
    def get_current_voip_config(self):
        user = self.env.user
        settings = self.env["res.users.settings"]._find_or_create_for_user(user)
        return {
            "voipConfig": user._get_voip_config(),
            "settings": settings._res_users_settings_format([
                "id",
                "voip_username",
                "voip_secret",
            ]),
        }

    def _store_init_global_fields(self, res: Store.FieldList):
        super()._store_init_global_fields(res)
        if self._is_internal():
            # sudo: internal users can access voip config
            res.attr("voipConfig", self.sudo()._get_voip_config())

    def _reflect_voip_destination_change(self, fallback):
        """Write destination fields atomically from their inverses."""
        field_names = [
            f"voip_{fallback}_destination_type",
            f"voip_{fallback}_destination_kind",
            f"voip_{fallback}_destination_ref",
            f"voip_{fallback}_outcall_number",
        ]
        if fallback == "no_answer":
            field_names.append("voip_no_answer_immediate_destination")
        for user in self:
            settings = self.env["res.users.settings"]._find_or_create_for_user(user)
            if all(settings[field_name] == user[field_name] for field_name in field_names):
                continue
            settings.with_context(
                voip_skip_config_bus=True,
                voip_skip_pbx_sync=True,
            ).write({
                field_name: user[field_name]
                for field_name in field_names
            })
            if not self.env.context.get("voip_skip_pbx_sync"):
                settings._voip_sync_pbx()

    def _reflect_change_in_res_users_settings(self):
        """
        Updates the values of the VoIP User Configuration Fields in `res_users_settings_ids` to have the same values as
        their related fields in `res.users`. If there is no `res.users.settings` record for the user, then the record is
        created.

        This method is intended to be used as an inverse for VoIP Configuration Fields.
        """
        notify_voip_config_users = self.env["res.users"]
        for user in self:
            settings = self.env["res.users.settings"]._find_or_create_for_user(user)
            configuration = {
                field: user[field] for field in self._get_voip_user_configuration_fields()
            }
            configuration["how_to_call_on_mobile"] = (
                user.how_to_call_on_mobile or settings.how_to_call_on_mobile
            )
            pbx_sync_fields = {
                field_name
                for field_name in PBX_SYNC_FIELDS
                if settings[field_name] != user[field_name]
            }
            sync_odoo_extension = (
                not self.env.context.get("voip_skip_pbx_sync")
                and user.voip_provider_id == self.env["voip.pbx.service"].voip_provider
                and settings.voip_provider_id != user.voip_provider_id
            )
            voip_config_changed = any(
                settings[field_name] != user[field_name] for field_name in VOIP_CONFIG_FIELDS
            )
            if voip_config_changed:
                notify_voip_config_users |= user
            settings.with_context(
                voip_skip_config_bus=True,
                voip_skip_pbx_sync=True,
            ).update(configuration)
            if sync_odoo_extension:
                settings._sync_odoo_extension()
            if pbx_sync_fields and not self.env.context.get("voip_skip_pbx_sync"):
                settings._voip_sync_pbx()
        if notify_voip_config_users:
            notify_voip_config_users._bus_send("voip.config/updated", {})

    def _store_voip_fields(self, res: Store.FieldList):
        res.one("partner_id", "_store_partner_fields")

    def _store_im_status_fields(self, res: Store.FieldList):
        super()._store_im_status_fields(res)
        res.from_method("_store_has_active_call_fields")

    def _store_manual_im_status_fields(self, res: Store.FieldList):
        super()._store_manual_im_status_fields(res)
        res.from_method("_store_has_active_call_fields")

    def _store_has_active_call_fields(self, res: Store.FieldList):
        res.attr(
            "should_display_in_call_im_status",
            lambda user: user.has_active_call and user.manual_im_status != "offline",
        )

    @api.model
    def action_voip_bus_send(self, message_type, payload):
        if not self.env.user._is_internal():
            raise AccessError(self.env._("Only internal users can broadcast VoIP messages"))
        if message_type not in ALLOWED_VOIP_BUS_MESSAGE_TYPES:
            raise ValidationError(self.env._("Invalid VOIP message type: %(type)s", type=message_type))
        self.env.user._bus_send(message_type, payload)
