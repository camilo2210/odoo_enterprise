import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .pbx_service import PBX_DEFAULT_RINGING_TIME

_logger = logging.getLogger(__name__)

EXTENSION_NUMBER_RE = re.compile(r"^[1-9]\d{2,3}$")
DEFAULT_EXTENSION_NUMBER_START = 1000
MAX_EXTENSION_NUMBER = 9999


class VoipExtension(models.Model):
    _name = "voip.extension"
    _inherit = "voip.pbx.destination.mixin"
    _description = "PBX extension"
    _rec_name = "number"
    _order = "number_value, id"

    number = fields.Char(required=True, index=True, copy=False)
    number_value = fields.Integer(compute="_compute_number_value", store=True, index=True)
    pbx_extension_id = fields.Integer(
        string="PBX Extension ID",
        copy=False,
        groups="base.group_system",
    )
    destination_ref = fields.Reference(
        selection=[
            ("res.users", "User"),
            ("voip.call.group", "Group"),
            ("voip.queue", "Queue"),
        ],
        string="Destination",
        required=True,
        default=lambda self: f"res.users,{self.env.user.id}",
    )
    destination_type = fields.Selection(
        [
            ("user", "User"),
            ("call_group", "Group"),
            ("queue", "Queue"),
        ],
        compute="_compute_destination_type",
        store=True,
        index=True,
    )
    active_did_number_id = fields.Many2one(
        "voip.did.number",
        compute="_compute_active_did_number",
    )
    active_did_number = fields.Char(
        string="Phone Number",
        compute="_compute_active_did_number",
    )

    _number_unique = models.Constraint("unique(number)", "The extension number must be unique.")

    @api.depends("number")
    def _compute_number_value(self):
        for extension in self:
            extension.number_value = int(extension.number) if extension.number else 0

    def _compute_active_did_number(self):
        for extension in self:
            active_did = self.env["voip.did.number"].search([
                ("destination_ref", "=", f"voip.extension,{extension.id}"),
                ("state", "=", "active"),
            ], order="id desc", limit=1)
            extension.active_did_number_id = active_did
            extension.active_did_number = active_did.did_number

    def action_open_active_did_number(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "voip.did.number",
            "res_id": self.active_did_number_id.id,
            "view_mode": "form",
        }

    @api.depends("destination_ref")
    def _compute_destination_type(self):
        destination_types = {
            "res.users": "user",
            "voip.call.group": "call_group",
            "voip.queue": "queue",
        }
        for extension in self:
            extension.destination_type = (
                destination_types.get(extension.destination_ref._name)
                if extension.destination_ref
                else False
            )

    @api.depends("number", "destination_ref")
    def _compute_display_name(self):
        for extension in self:
            if extension.destination_ref:
                extension.display_name = f"{extension.number} ({extension.destination_ref.display_name})"
            else:
                extension.display_name = extension.number

    def _is_user_destination(self):
        self.ensure_one()
        return self.destination_ref._name == "res.users"

    def _is_call_group_destination(self):
        self.ensure_one()
        return self.destination_ref._name == "voip.call.group"

    def _is_queue_destination(self):
        self.ensure_one()
        return self.destination_ref._name == "voip.queue"

    @api.model
    def _allocate_numbers(self, count, reserved_numbers=()):
        if not count:
            return []
        existing = {
            int(extension.number)
            for extension in self.sudo().search_fetch([], ["number"])
            if extension.number.isdigit()
        }
        existing.update(int(number) for number in reserved_numbers if number.isdigit())
        allocated = []
        candidate = DEFAULT_EXTENSION_NUMBER_START
        while len(allocated) < count:
            if candidate > MAX_EXTENSION_NUMBER:
                raise ValidationError(_("No free extension number left."))
            if candidate not in existing:
                allocated.append(str(candidate))
                existing.add(candidate)
            candidate += 1
        return allocated

    @api.model
    def _find_or_create_for_user(self, user):
        user.ensure_one()
        if user.share:
            raise ValidationError(_("Only internal users can be assigned a PBX extension."))
        extension = user.with_env(self.env).routing_extension_id
        return extension or self.create({"destination_ref": f"res.users,{user.id}"})

    def _get_pbx_incall_destination(self):
        self.ensure_one()
        if self._is_user_destination():
            user = self.destination_ref.sudo()
            if not user.voip_pbx_user_id:
                self._sync_pbx()
            return {"type": "user", "user_id": user.voip_pbx_user_id}
        if self._is_call_group_destination():
            call_group = self.destination_ref
            if not call_group.pbx_group_id:
                call_group._sync_pbx()
            return {"type": "group", "group_id": call_group.pbx_group_id}
        queue = self.destination_ref
        if not queue.pbx_queue_id:
            queue._sync_pbx()
        return {"type": "queue", "queue_id": queue.pbx_queue_id}

    def _get_outgoing_caller_id(self):
        self.ensure_one()
        destination_ref = (
            f"res.users,{self.destination_ref.id}"
            if self._is_user_destination()
            else f"voip.extension,{self.id}"
        )
        did = self.env["voip.did.number"].sudo().search([
            ("destination_ref", "=", destination_ref),
            ("state", "=", "active"),
        ], order="id desc", limit=1)
        return did.did_number or None

    def _get_destination_users(self):
        return self.env["res.users"].browse([
            extension.destination_ref.id
            for extension in self
            if extension._is_user_destination()
        ])

    @api.model
    def _get_user_from_number(self, number):
        extension = self.sudo().search([("number", "=", number)], limit=1)
        if extension and extension._is_user_destination():
            return extension.destination_ref
        return self.env["res.users"]

    @api.constrains("number")
    def _check_number(self):
        for extension in self:
            if extension.number and not EXTENSION_NUMBER_RE.fullmatch(extension.number):
                raise ValidationError(_("The extension number must be between 100 and 9999."))

    @api.constrains("destination_ref")
    def _check_user_destination_is_internal(self):
        for extension in self:
            if extension._is_user_destination() and extension.destination_ref.share:
                raise ValidationError(_("Only internal users can be assigned a PBX extension."))

    @api.constrains("destination_ref")
    def _check_destination_is_unique(self):
        for extension in self:
            if extension.search_count([
                ("id", "!=", extension.id),
                ("destination_ref", "=", f"{extension.destination_ref._name},{extension.destination_ref.id}"),
            ]):
                raise ValidationError(
                    _("A PBX destination can only be linked to one extension.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        vals_without_number = [vals for vals in vals_list if not vals.get("number")]
        explicit_numbers = [vals["number"] for vals in vals_list if vals.get("number")]
        allocated_numbers = self._allocate_numbers(len(vals_without_number), reserved_numbers=explicit_numbers)
        for vals, number in zip(vals_without_number, allocated_numbers):
            vals["number"] = number
        extensions = super().create(vals_list)
        extensions._invalidate_destination_extension_cache([
            extension.destination_ref for extension in extensions
        ])
        users = extensions._get_destination_users()
        if not self.env.context.get("voip_skip_pbx_sync"):
            users.with_context(
                voip_skip_config_bus=True,
                voip_skip_pbx_sync=True,
            )._select_odoo_voip_provider()
            extensions.with_context(voip_skip_config_bus=True)._sync_pbx()
        if users and not self.env.context.get("voip_skip_config_bus"):
            users._bus_send("voip.config/updated", {})
        return extensions

    def write(self, vals):
        queues = self.env["voip.queue"]
        config_changed = bool({"destination_ref", "number"} & vals.keys())
        destination_changed = "destination_ref" in vals
        sync_queues = (
            config_changed and not self.env.context.get("voip_skip_pbx_sync")
        )
        if sync_queues:
            queues = queues._get_for_extensions(self)
        destinations_before = []
        if config_changed:
            destinations_before = [extension.destination_ref for extension in self]
        destination_users_before = self.env["res.users"]
        if config_changed:
            destination_users_before = self._get_destination_users()
        res = super().write(vals)
        if config_changed:
            self._invalidate_destination_extension_cache(
                destinations_before + [extension.destination_ref for extension in self],
            )
        if destination_changed:
            destination_users_after = self._get_destination_users()
            if not self.env.context.get("voip_skip_pbx_sync"):
                (destination_users_after - destination_users_before).with_context(
                    voip_skip_config_bus=True,
                    voip_skip_pbx_sync=True,
                )._select_odoo_voip_provider()
        if self._should_sync_pbx(vals):
            extensions = self.with_context(voip_skip_config_bus=True)
            extensions._sync_pbx()
            if "number" in vals:
                extensions._sync_pbx_references()
                self.env["voip.call.flow"].search([
                    ("active", "=", True),
                ])._sync_graph_routes()
            elif "destination_ref" in vals:
                extensions.filtered(
                    lambda extension: not extension._is_user_destination()
                )._resync_did_numbers()
        if sync_queues:
            queues |= queues._get_for_extensions(self)
            queues._recompute_agents_and_sync_pbx()
        if config_changed and not self.env.context.get("voip_skip_config_bus"):
            (destination_users_before | self._get_destination_users())._bus_send(
                "voip.config/updated", {},
            )
        return res

    def unlink(self):  # nosemgrep: unlink-override
        users = self._get_destination_users()
        destinations = [extension.destination_ref for extension in self]
        queues = self.env["voip.queue"]
        if not self.env.context.get("voip_skip_pbx_sync"):
            queues = queues._get_for_extensions(self)
        res = super(VoipExtension, self.with_context(voip_skip_config_bus=True)).unlink()
        self._invalidate_destination_extension_cache(destinations)
        if queues:
            queues._recompute_agents_and_sync_pbx()
        if users and not self.env.context.get("voip_skip_config_bus"):
            users._bus_send("voip.config/updated", {})
        return res

    def _invalidate_destination_extension_cache(self, destinations):
        for destination in destinations:
            field_names = [
                "routing_extension_id",
                "routing_extension_number",
                "has_routing_extension",
            ]
            if destination._name == "res.users":
                field_names.append("pbx_extension_number")
                destination.res_users_settings_id.invalidate_recordset([
                    "pbx_extension_number",
                ])
            destination.invalidate_recordset(field_names)

    def _should_sync_pbx(self, vals):
        return (
            bool({"number", "destination_ref"} & vals.keys())
            and not self.env.context.get("voip_skip_pbx_sync")
        )

    @api.ondelete(at_uninstall=False)
    def _unlink_pbx_resources(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        pbx_extension_id_by_id = {
            extension.id: extension.pbx_extension_id
            for extension in self.sudo().filtered("pbx_extension_id")
        }
        # Deprovisioning is itself a PBX call (unlike clearing the local
        # credentials below, which is a plain Odoo write), so its uuid must
        # be captured now and deferred along with the extension delete.
        user_uuid_by_extension_id = {}
        for extension in self.sudo().filtered(lambda ext: ext._is_user_destination()):
            user = extension.destination_ref.sudo()
            if user.voip_pbx_user_uuid:
                user_uuid_by_extension_id[extension.id] = user.voip_pbx_user_uuid
            user.res_users_settings_id._clear_sip_credentials()

        extension_ids = set(pbx_extension_id_by_id) | set(user_uuid_by_extension_id)
        if not extension_ids:
            return

        def _run(env, extension_id):
            service = env["voip.pbx.service"]
            pbx_extension_id = pbx_extension_id_by_id.get(extension_id)
            if pbx_extension_id:
                service._delete_extension(extension_id=pbx_extension_id)
            user_uuid = user_uuid_by_extension_id.get(extension_id)
            if user_uuid:
                service._deprovision_user(user_uuid)

        self.env["voip.pbx.service"]._call_after_commit_for_deleted(
            "voip.extension", list(extension_ids), _run,
        )

    def _clear_user_sip_credentials(self):
        for extension in self.sudo():
            if extension._is_user_destination():
                user = extension.destination_ref.sudo()
                if user.voip_pbx_user_uuid:
                    try:
                        extension.env["voip.pbx.service"]._deprovision_user(
                            user.voip_pbx_user_uuid)
                    except UserError as error:
                        _logger.warning(
                            "Could not deprovision the PBX user %s: %s",
                            user.id, error)
                user_settings = user.res_users_settings_id
                user_settings._clear_sip_credentials()

    def _sync_pbx(self):
        # sudo: the sync reads/writes system-only technical fields; access to the
        # business operation was already checked on the extension/number itself.
        for extension in self.sudo():
            if extension._is_call_group_destination():
                extension._sync_call_group_extension()
            elif extension._is_queue_destination():
                extension._sync_queue_extension()
            elif extension._is_user_destination():
                extension._sync_user_extension()

    def _delete_pbx_extension(self):
        self.ensure_one()
        if not self.pbx_extension_id:
            return
        self.env["voip.pbx.service"]._delete_extension(extension_id=self.pbx_extension_id)
        self.with_context(voip_skip_pbx_sync=True).pbx_extension_id = False

    def _sync_call_group_extension(self):
        self.ensure_one()
        service = self.env["voip.pbx.service"]
        call_group = self.destination_ref
        call_group._sync_pbx()
        result = service._sync_group_extension(
            extension_id=self.pbx_extension_id,
            extension_number=self.number,
            group_uuid=call_group.pbx_group_uuid,
        )
        self.with_context(voip_skip_pbx_sync=True).pbx_extension_id = result.get("extension_id", self.pbx_extension_id)

    def _sync_queue_extension(self):
        self.ensure_one()
        service = self.env["voip.pbx.service"]
        queue = self.destination_ref
        queue._sync_pbx()
        result = service._sync_queue_extension(
            extension_id=self.pbx_extension_id,
            extension_number=self.number,
            queue_id=queue.pbx_queue_id,
        )
        self.with_context(voip_skip_pbx_sync=True).pbx_extension_id = result.get("extension_id", self.pbx_extension_id)

    def _sync_user_extension(self):
        self.ensure_one()
        service = self.env["voip.pbx.service"]
        user = self.destination_ref
        user_settings = user._prepare_pbx_user_settings()
        ids = service._sync_user_extension(
            user_id=user.voip_pbx_user_id or None,
            line_id=user.voip_pbx_line_id or None,
            extension_id=self.pbx_extension_id or None,
            extension_number=self.number,
            user_name=user.name or None,
            user_login=user.login or None,
            odoo_user_id=user.id,
            sip_secret=user_settings.voip_secret,
            ring_seconds=self._get_ring_seconds(user_settings),
            simultaneous_calls=user_settings._get_pbx_simultaneous_calls(),
            outgoing_caller_id=self._get_outgoing_caller_id(),
            wakeup_token_enabled=user._voip_wants_wakeup_token(),
        )
        user_vals = {
            "voip_pbx_user_id": ids["user_id"],
            "voip_pbx_line_id": ids["line_id"],
        }
        if ids.get("user_uuid"):
            user_vals["voip_pbx_user_uuid"] = ids["user_uuid"]
        user.with_context(voip_skip_pbx_sync=True).write(user_vals)
        user.with_context(voip_skip_pbx_sync=True)._ensure_pbx_voicemail()
        self.with_context(voip_skip_pbx_sync=True).pbx_extension_id = ids["extension_id"]
        user_settings._voip_store_sip_username(ids.get("sip_username"))
        try:
            with self.env.cr.savepoint():
                self._resync_did_numbers()
                user_settings._voip_sync_pbx()
        except UserError as error:
            _logger.warning(
                "PBX user provisioned for extension %s; routing sync failed: %s",
                self.number, error)

    def _get_ring_seconds(self, user_settings):
        return (
            user_settings.voip_no_answer_timeout
            if (
                user_settings.voip_no_answer_destination_type == "forward"
                and user_settings.voip_no_answer_timeout
            )
            else PBX_DEFAULT_RINGING_TIME
        )

    def _resync_did_numbers(self):
        """The inbound route embeds the PBX user id, so it must follow it.

        DIDs listed in ``voip_skip_incall_resync_ids`` are excluded: their
        caller runs the incall sync itself right after this provisioning.
        """
        if self.env.context.get("voip_syncing_incall"):
            return
        self.env["voip.did.number"].sudo().search([
            ("destination_ref", "in", [
                f"voip.extension,{extension.id}"
                for extension in self
            ]),
            ("state", "=", "active"),
            ("id", "not in", self.env.context.get("voip_skip_incall_resync_ids") or []),
        ])._sync_pbx_incall()
