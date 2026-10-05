import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import SUPERUSER_ID, Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.mail import append_content_to_html

from .pbx_service import PBX_INCALL_DESTINATION_MODELS, SHARED_DESTINATION_TYPE_BY_MODEL
from odoo.addons.voip.models.phone_service_api import (
    MAX_PHONE_NUMBERS_PER_REQUEST,
    PhoneServiceAPI,
    PhoneServiceError,
    get_buy_credits_action,
)
from odoo.addons.voip.models.utils import digits, normalize_caller_number

_logger = logging.getLogger(__name__)

DID_NUMBER_TYPES = [
    ("mobile", "Mobile"),
    ("local", "Local"),
    ("national", "National"),
    ("toll_free", "Toll-free"),
]


class VoipDidNumber(models.Model):
    """Provider-backed DID number assigned to users and synchronized with phone_service."""

    _name = "voip.did.number"
    _description = "VoIP DID Number"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "did_number"
    _order = "id desc"

    did_number = fields.Char(
        string="Phone Number", required=True, tracking=True, readonly=True,
    )
    is_default_outgoing_number = fields.Boolean(
        string="Default Outgoing Number",
        copy=False,
        tracking=True,
        help="Use this phone number as the caller ID for outgoing calls.",
    )
    main_number_status = fields.Selection(
        [("main", "Default Outgoing Number")],
        compute="_compute_main_number_status",
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        compute="_compute_user_id",
        store=True,
        ondelete="set null",
    )
    destination_ref = fields.Reference(
        selection=PBX_INCALL_DESTINATION_MODELS,
        string="Destination",
        copy=False,
    )
    pbx_incall_id = fields.Integer(
        string="PBX Incall ID",
        copy=False,
        groups="base.group_system",
    )
    pbx_incall_extension_id = fields.Integer(
        string="PBX Incall Extension ID",
        copy=False,
        groups="base.group_system",
    )
    requirement_group_id = fields.Many2one(
        "voip.requirement.group",
        string="Requirement Group",
        readonly=True,
        index="btree_not_null",
    )
    number_request_id = fields.Many2one(
        "voip.did.number.request",
        string="Number Request",
        readonly=True,
        index="btree_not_null",
        ondelete="set null",
    )
    telnyx_synced_comment_ids = fields.Json(
        readonly=True,
        default=list,
        help="List of Telnyx comment IDs already posted to chatter (for deduplication)",
    )
    requirement_statuses = fields.Json(
        readonly=True,
        default=dict,
        help="Latest regulatory review statuses for this phone number, keyed by requirement ID.",
    )
    requirement_review_state = fields.Selection(
        [
            ("under_review", "Under Review"),
            ("action_required", "Action Required"),
            ("approved", "Approved"),
        ],
        compute="_compute_requirement_review",
    )
    state = fields.Selection(
        [
            ("ordering", "Ordering"),
            ("pending", "Under Review"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("failure", "Failure"),
            ("released", "Released"),
        ],
        default="ordering",
        tracking=True,
        required=True,
    )

    country_id = fields.Many2one("res.country", index="btree_not_null")
    country_flag_url = fields.Char(related="country_id.image_url", string="Country Flag")
    did_number_type = fields.Selection(
        DID_NUMBER_TYPES,
        required=True,
        readonly=True,
    )

    location = fields.Char()
    purchase_date = fields.Datetime(readonly=True)
    has_pending_action_requirement = fields.Boolean(
        compute="_compute_has_pending_action_requirement",
        help="True if an action requirement (identity verification) is awaiting completion.",
    )

    _did_number_unique = models.Constraint(
        "UNIQUE(did_number)", "This DID number already exists!",
    )
    _default_outgoing_number_unique = models.UniqueIndex(
        "(is_default_outgoing_number) WHERE is_default_outgoing_number",
        "Only one phone number can be the default outgoing number.",
    )

    # --- ORM + compute ---

    def _creation_message(self):
        return self.env._("Phone Number created")

    @api.depends("is_default_outgoing_number")
    def _compute_main_number_status(self):
        for did in self:
            did.main_number_status = "main" if did.is_default_outgoing_number else False

    @api.depends(
        "requirement_statuses",
        "requirement_group_id.requirement_ids",
        "requirement_group_id.requirement_ids.did_number_id",
        "requirement_group_id.requirement_ids.field_type",
        "requirement_group_id.requirement_ids.telnyx_requirement_id",
    )
    def _compute_requirement_review(self):
        for did in self:
            statuses = did.requirement_statuses or {}
            requirement_ids = {
                requirement.telnyx_requirement_id
                for requirement in did.requirement_group_id.requirement_ids
                if requirement.telnyx_requirement_id
                and (requirement.field_type != "action" or requirement.did_number_id == did)
            }
            if "rejected" in statuses.values():
                did.requirement_review_state = "action_required"
            elif (
                statuses
                and requirement_ids.issubset(statuses)
                and all(status == "approved" for status in statuses.values())
            ):
                did.requirement_review_state = "approved"
            else:
                did.requirement_review_state = "under_review"

    @api.depends(
        "requirement_group_id",
        "requirement_group_id.requirement_ids",
        "requirement_group_id.requirement_ids.field_type",
        "requirement_group_id.requirement_ids.did_number_id",
        "requirement_group_id.requirement_ids.action_verification_url",
    )
    def _compute_has_pending_action_requirement(self):
        for did in self:
            if not did.requirement_group_id:
                did.has_pending_action_requirement = False
                continue
            pending = did.requirement_group_id.requirement_ids.filtered(
                lambda r, did=did: (
                    r.field_type == "action" and r.did_number_id == did and not r.action_verification_url
                ),
            )
            did.has_pending_action_requirement = bool(pending)

    @api.depends("destination_ref")
    def _compute_user_id(self):
        for did in self:
            did.user_id = (
                did.destination_ref
                if did.destination_ref and did.destination_ref._name == "res.users"
                else False
            )

    def _get_routing_destination(self):
        """Return the record this number actually rings, resolving a
        ``voip.extension`` destination to what it routes to (an extension
        cannot itself be assigned to another extension)."""
        self.ensure_one()
        destination = self.destination_ref
        if destination and destination._name == "voip.extension":
            return destination.destination_ref
        return destination

    def _is_shared_destination(self):
        """Whether this number's destination is shown to every user as a
        selectable outgoing caller ID (see ``SHARED_DESTINATION_TYPE_BY_MODEL``)."""
        self.ensure_one()
        destination = self._get_routing_destination()
        return bool(destination) and destination._name in SHARED_DESTINATION_TYPE_BY_MODEL

    @api.constrains("state", "destination_ref")
    def _check_terminal_state_has_no_destination(self):
        if any(did.state in ("failure", "released") and did.destination_ref for did in self):
            raise ValidationError(
                self.env._("Failed or released phone numbers cannot have a destination."),
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_default_outgoing_number") and vals.get("state", "ordering") != "active":
                raise UserError(self.env._("Only an active phone number can be the default outgoing number."))
            if vals.get("state") in ("released", "failure"):
                vals["destination_ref"] = False
        records = super().create(vals_list)
        if not self.env.context.get("install_mode"):
            records._subscribe_status_followers()
            users = records.user_id
            if not self.env.context.get("voip_skip_pbx_sync"):
                users.with_context(voip_skip_config_bus=True)._select_odoo_voip_provider()
                sync_records = records.with_context(voip_skip_config_bus=True)
                sync_records._sync_user_provisioning(users)
                sync_records._sync_pbx_incall()
                sync_records._sync_user_outgoing_caller_ids(users)
            records._notify_softphone_config_updated(
                users,
                # Shared numbers (group/queue/menu/call flow destinations) are shown to
                # every user, so a number created with such a destination must be
                # broadcast to everyone, not only to its (possibly unrelated) owner.
                all_users=any(
                    record.is_default_outgoing_number or record._is_shared_destination()
                    for record in records
                ),
            )
        return records

    @api.model
    def _create_or_reuse_for_order(self, vals_list):
        reusable = {
            did.did_number: did
            for did in self.search([
                ("did_number", "in", [vals["did_number"] for vals in vals_list]),
                ("state", "in", ("released", "failure")),
            ])
        }
        reused = self.browse()
        to_create = []
        for vals in vals_list:
            existing = reusable.get(vals["did_number"])
            if existing:
                existing.write({**vals, "requirement_statuses": {}})
                reused |= existing
            else:
                to_create.append(vals)
        if reused:
            reused._clear_previous_action_requirements()
        records = reused | self.create(to_create)
        action_requirements = []
        for did in records.filtered("requirement_group_id"):
            template = did.requirement_group_id.requirement_ids.filtered(
                lambda requirement: requirement.field_type == "action" and not requirement.did_number_id,
            )[:1]
            if template:
                action_requirements.append({
                    "telnyx_requirement_id": template.telnyx_requirement_id,
                    "name": template.name,
                    "description": template.description,
                    "field_type": "action",
                    "example": template.example,
                    "requirement_group_ids": [Command.link(did.requirement_group_id.id)],
                    "did_number_id": did.id,
                })
        self.env["voip.requirement"].with_context(skip_validation=True).create(action_requirements)
        return records

    def _clear_previous_action_requirements(self):
        self.env["voip.requirement"].search([
            ("did_number_id", "in", self.ids),
            ("field_type", "=", "action"),
        ]).unlink()

    def write(self, vals):
        default_outgoing_field = "is_default_outgoing_number"
        skip_default_outgoing_check = self.env.context.get("voip_skip_default_outgoing_check")
        config_changed = bool({
            "did_number",
            "destination_ref",
            "state",
            default_outgoing_field,
        } & vals.keys())
        notify_all_users = (
            default_outgoing_field in vals
            or bool({"did_number", "state"} & vals.keys() and self.filtered(default_outgoing_field))
        )
        loses_default_outgoing_number = (
            vals.get("state") not in (None, "active")
            and self.filtered(default_outgoing_field)
        )
        if vals.get(default_outgoing_field):
            self.ensure_one()
            if vals.get("state", self.state) != "active":
                raise UserError(self.env._(
                    "Only an active phone number can be the default outgoing number.",
                ))
            previous_default = self.sudo().search([
                (default_outgoing_field, "=", True),
                ("id", "!=", self.id),
            ])
            if previous_default:
                previous_default.with_context(
                    voip_skip_config_bus=True,
                    voip_skip_default_outgoing_check=True,
                ).write({
                    default_outgoing_field: False,
                })
                previous_default.flush_recordset([default_outgoing_field])
        elif (
            default_outgoing_field in vals
            and not vals[default_outgoing_field]
            and not skip_default_outgoing_check
            and self.filtered(default_outgoing_field)
        ):
            raise UserError(self.env._(
                "Select another default outgoing number before clearing the current one.",
            ))
        if vals.get("state") in ("released", "failure"):
            vals["destination_ref"] = False
        destination_before_by_id = {}
        if "destination_ref" in vals:
            destination_before_by_id = {did.id: did._get_routing_destination() for did in self}
        do_sync = bool({"destination_ref", "state"} & vals.keys())
        users_before = self.env["res.users"]
        if do_sync:
            users_before = self.user_id
        res = super().write(vals)
        if "destination_ref" in vals:
            self._subscribe_status_followers()
            # Shared numbers (group/queue/menu/call flow destinations) are shown to
            # every user, not just the DID's own user_id, so a change that touches a
            # currently- or formerly-shared destination must be broadcast to everyone
            # rather than only to the DID's (possibly unrelated) owner.
            notify_all_users = notify_all_users or any(
                (destination_before_by_id[did.id] and destination_before_by_id[did.id]._name in SHARED_DESTINATION_TYPE_BY_MODEL)
                or did._is_shared_destination()
                for did in self
            )
        if do_sync:
            users_after = self.user_id
            if not self.env.context.get("voip_skip_pbx_sync"):
                if "destination_ref" in vals:
                    (users_after - users_before).with_context(
                        voip_skip_config_bus=True,
                    )._select_odoo_voip_provider()
                users = users_before | users_after
                records = self.with_context(voip_skip_config_bus=True)
                records._sync_user_provisioning(users)
                records._sync_pbx_incall()
                records._sync_user_outgoing_caller_ids(users)
        if vals.get(default_outgoing_field) and not self.env.context.get("voip_skip_pbx_sync"):
            self.env["voip.pbx.service"]._update_default_outgoing_number(
                phone_number=self.did_number,
            )
        if loses_default_outgoing_number and not self.env.context.get("voip_skip_pbx_sync"):
            self.with_context(voip_skip_config_bus=True)._ensure_default_outgoing_number()
        if config_changed:
            self._notify_softphone_config_updated(
                users_before | self.user_id,
                all_users=notify_all_users,
            )
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_check_released(self):
        if any(did.state not in ("released", "failure") for did in self):
            raise UserError(
                self.env._("You must release phone numbers before deleting them."),
            )
        if not self.env.context.get("voip_skip_pbx_sync"):
            self._sync_pbx_incall()
            self._sync_user_provisioning(self.user_id)

    # --- Chatter ---

    def post_notification(self, body):
        for did in self:
            did.message_post(body=body, message_type="notification", subtype_xmlid="mail.mt_note")

    def _subscribe_status_followers(self):
        for did in self:
            partners = did.create_uid.partner_id | did.user_id.partner_id
            if partners:
                did.sudo().message_subscribe(partner_ids=partners.ids)

    def _track_log_get_default_subtype(self, track_init_values):
        if "state" in track_init_values:
            return self.env.ref("voip.mt_did_number_state")
        return super()._track_log_get_default_subtype(track_init_values)

    def _message_compute_body_with_trackings(self, body, tracking_values):
        state_change = next(
            (val for val in tracking_values if val.get("field_name") == "state"),
            None,
        )
        if not state_change:
            return super()._message_compute_body_with_trackings(body, tracking_values)
        new_state = state_change.get("new_value")
        if self.state == "active":
            custom_html = Markup("<p>%s</p>") % self.env._(
                "Your phone number is now active and can be assigned.",
            )
        elif self.state == "failure":
            custom_html = Markup("<p>%s</p>") % self.env._(
                "Your phone number activation has failed.",
            )
        else:
            custom_html = Markup("<p>%s</p>") % self.env._(
                'Your phone number is in "%(state)s" state.', state=new_state,
            )
        other_trackings = [val for val in tracking_values if val is not state_change]
        if other_trackings:
            custom_html += super()._message_compute_body_with_trackings(
                "", other_trackings,
            )
        return append_content_to_html(
            body, custom_html, plaintext=False, add_line_breaks=False,
        )

    def _notify_get_recipients_groups_fillup(self, groups, message, model_description):
        groups = super()._notify_get_recipients_groups_fillup(
            groups, message, model_description,
        )
        for _group_name, _group_func, group_data in groups:
            button_access = group_data.get("button_access")
            if button_access:
                button_access["title"] = self.env._("View Phone Number")
        return groups

    # --- User provisioning ---

    def _notify_softphone_config_updated(self, users, *, all_users=False):
        if self.env.context.get("voip_skip_config_bus"):
            return
        if all_users:
            users = self.env["res.users"].sudo().search([
                ("active", "=", True),
                ("share", "=", False),
            ])
        if users:
            users._bus_send("voip.config/updated", {})

    def _sync_user_provisioning(self, users):
        if not users:
            return
        live_dids = self.env["voip.did.number"].sudo().search([
            ("user_id", "in", users.ids),
            ("state", "in", ("ordering", "pending", "active", "suspended")),
        ])

        service = self.env["voip.pbx.service"]
        odoo_provider = service.voip_provider
        extension_model = self.env["voip.extension"]
        settings_model = self.env["res.users.settings"].sudo()
        live_dids = live_dids.filtered(
            lambda did: did.user_id.res_users_settings_id.voip_provider_id == odoo_provider,
        )
        for did in live_dids:
            user = did.user_id
            settings = settings_model._find_or_create_for_user(user)
            if (
                not settings.voip_username
                or not settings.voip_secret
                or not user.voip_pbx_user_id
                or not user.voip_pbx_line_id
            ):
                user._sync_pbx_user()
            extension_model._find_or_create_for_user(user)
        # A non-active personal number must not override the tenant's Default Outgoing Number.
        active_dids = live_dids.filtered(lambda did: did.state == "active")
        users_without_active_did = users - active_dids.user_id
        pbx_users_to_reset = users_without_active_did.sudo().filtered("voip_pbx_user_id")
        if pbx_users_to_reset:
            service = self.env["voip.pbx.service"]
            for user in pbx_users_to_reset:
                try:
                    service._update_user_caller_id(
                        user_id=user.voip_pbx_user_id,
                        outgoing_caller_id="default",
                    )
                except PhoneServiceError as error:
                    if error.error_key != "not_found":
                        raise
                    user.write({
                        "voip_pbx_user_id": False,
                        "voip_pbx_user_uuid": False,
                        "voip_pbx_line_id": False,
                    })

    def _sync_user_outgoing_caller_ids(self, users):
        """Set personal caller IDs after their incalls make them available in Wazo."""
        active_dids = self.env["voip.did.number"].sudo().search([
            ("user_id", "in", users.ids),
            ("state", "=", "active"),
        ])
        service = self.env["voip.pbx.service"]
        for did in active_dids:
            if did.user_id.voip_pbx_user_id:
                service._update_user_caller_id(
                    user_id=did.user_id.voip_pbx_user_id,
                    outgoing_caller_id=did.did_number,
                )

    def _sync_pbx_incall(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        service = self.env["voip.pbx.service"]
        for did in self.sudo():
            has_route = did.pbx_incall_id or did.pbx_incall_extension_id
            if did.state == "active" and did.destination_ref:
                destination = did.destination_ref
                ids = service._sync_incall(
                    incall_id=did.pbx_incall_id,
                    incall_extension_id=did.pbx_incall_extension_id,
                    did_number=did.did_number,
                    destination=service._get_pbx_destination(destination),
                    schedule_id=(
                        destination._get_pbx_incall_schedule_id()
                        if destination._name == "voip.call.flow"
                        else None
                    ),
                )
                did.with_context(voip_skip_pbx_sync=True).write({
                    "pbx_incall_id": ids["incall_id"],
                    "pbx_incall_extension_id": ids["extension_id"],
                })
            elif has_route:
                incall_id = did.pbx_incall_id
                extension_id = did.pbx_incall_extension_id
                did_id = did.id

                # This can be reached while this write is itself a side
                # effect of another record's ondelete hook (e.g.
                # _unlink_did_routes clearing destination_ref before that
                # record's own row is deleted), so it's deferred: the
                # delete never reaches Wazo if that other deletion is
                # rejected. But a savepoint rollback (unlike a full
                # Cursor.rollback()) wouldn't discard this callback even if
                # it undid the write below, so re-check that the route
                # really is cleared once this actually commits.
                def _run(env, did_id=did_id, incall_id=incall_id, extension_id=extension_id):
                    did_number = env["voip.did.number"].browse(did_id).exists()
                    # Only skip when the *same* pair we captured is still in
                    # place (the savepoint-rollback case): if this DID was
                    # instead disabled and then re-enabled with a new
                    # incall/extension pair in the same transaction, the
                    # current pair differs, and this captured old route
                    # still needs deleting - it would otherwise leak in
                    # Wazo forever.
                    if (
                        did_number
                        and did_number.pbx_incall_id == incall_id
                        and did_number.pbx_incall_extension_id == extension_id
                    ):
                        return
                    env["voip.pbx.service"]._delete_incall(
                        incall_id=incall_id, extension_id=extension_id,
                    )

                service._call_after_commit(_run)
                did.with_context(voip_skip_pbx_sync=True).write({
                    "pbx_incall_id": False,
                    "pbx_incall_extension_id": False,
                })

    # --- Requirements & ordering ---

    def action_open_submit_requirements(self):
        self.ensure_one()
        return {
            "name": self.env._("Update Requirements"),
            "type": "ir.actions.act_window",
            "res_model": "voip.requirement.group",
            "res_id": self.requirement_group_id.id,
            "view_mode": "form",
            "view_id": self.env.ref("voip.view_requirement_group_submit_form").id,
            "target": "new",
            "context": {"did_number_id": self.id},
        }

    def update_requirement_group(self):
        self.ensure_one()
        if not self.requirement_group_id:
            return
        PhoneServiceAPI(self.env).assign_requirement_group(
            self.did_number,
            self.requirement_group_id.telnyx_requirement_group_id,
        )

    def action_set_as_main_number(self):
        self.ensure_one()
        self.is_default_outgoing_number = True

    @api.model
    def _ensure_default_outgoing_number(self):
        """Keep an active Default Outgoing Number selected, or clear the PBX caller ID."""
        default_did = self.sudo().search([
            ("is_default_outgoing_number", "=", True),
        ], limit=1)
        if default_did and default_did.state == "active":
            return default_did
        if default_did:
            default_did.with_context(
                voip_skip_default_outgoing_check=True,
                voip_skip_pbx_sync=True,
            ).is_default_outgoing_number = False
        first_purchased_did = self.sudo().search([
            ("purchase_date", "!=", False),
            ("state", "=", "active"),
        ], order="purchase_date, id", limit=1)
        if first_purchased_did:
            first_purchased_did.is_default_outgoing_number = True
            if default_did:
                first_purchased_did._notify_main_number_promoted()
        elif default_did and not self.env.context.get("voip_skip_pbx_sync"):
            self.env["voip.pbx.service"]._update_default_outgoing_number(phone_number=None)
        return first_purchased_did

    def _notify_main_number_promoted(self):
        self.ensure_one()
        admin_partners = self.env.ref("voip.group_voip_admin").all_user_ids.partner_id
        if admin_partners:
            self.message_notify(
                subject=self.env._("Odoo Phone Default Outgoing Number changed"),
                body=self.env._(
                    "%(number)s was automatically selected as the Default Outgoing Number because the "
                    "previous Default Outgoing Number is no longer active.",
                    number=self._phone_get_formatted(self.did_number) or self.did_number,
                ),
                partner_ids=admin_partners.ids,
            )

    def order_from_phone_service(self):
        if not self:
            return
        already_provisioned = self.filtered(lambda r: r.state in ("pending", "active", "suspended"))
        if already_provisioned:
            raise UserError(self.env._("These phone numbers cannot be ordered again."))
        if len(self) > MAX_PHONE_NUMBERS_PER_REQUEST:
            raise UserError(self.env._(
                "Cannot order more than %(max)s numbers at once.", max=MAX_PHONE_NUMBERS_PER_REQUEST,
            ))
        phone_service_api = PhoneServiceAPI(self.env)
        now = fields.Datetime.now()
        phone_numbers = [
            {
                "phone_number": did.did_number,
                "requirement_group_id": did.requirement_group_id.telnyx_requirement_group_id or None,
            }
            for did in self
        ]
        results = phone_service_api.order_phone_numbers(phone_numbers)
        valid_states = dict(self._fields["state"].selection)
        unconfirmed = []
        for did in self:
            result = results.get(did.did_number)
            status = result.get("status") if result else None
            if not status or status not in valid_states:
                unconfirmed.append(did.did_number)
                continue
            did.write({
                "state": status,
                "purchase_date": now,
            })
            _logger.info("Queued DID %s for ordering", did.did_number)
        try:
            with self.env.cr.savepoint():
                self._ensure_default_outgoing_number()
        except UserError as error:
            _logger.warning(
                "Could not synchronize the PBX Default Outgoing Number after ordering phone numbers: %s",
                error,
            )
        if unconfirmed:
            _logger.warning(
                "order_phone_numbers response omitted %s/%s requested numbers: %s",
                len(unconfirmed), len(self), ", ".join(unconfirmed),
            )
            raise UserError(self.env._(
                "The phone service did not confirm the order for: %(numbers)s.",
                numbers=", ".join(unconfirmed),
            ))

    @api.model
    def _get_from_number(self, number):
        """Return the active DID matching `number` in any of its common forms
        ("+32…", "0032…", bare digits)."""
        normalized_number = digits(number)
        candidate_numbers = {
            number,
            normalized_number,
            f"+{normalized_number}" if normalized_number else None,
            normalize_caller_number(number),
        }
        return self.sudo().search([
            ("did_number", "in", [number for number in candidate_numbers if number]),
            ("state", "=", "active"),
        ], limit=1)

    # --- Status sync ---

    @api.model
    def _handle_status_event(self, payload):
        phone_number = payload.get("phone_number")
        state = payload.get("state")
        if not phone_number or not state:
            _logger.warning(
                "_handle_status_event: missing phone_number/state (got phone_number=%s, state=%s)",
                bool(phone_number), bool(state),
            )
            return
        if state not in dict(self._fields["state"].selection):
            _logger.warning("_handle_status_event: unknown state %r for %s", state, phone_number)
            return
        did = self.sudo().search([("did_number", "=", phone_number)], limit=1)
        advanced_order = payload.get("advanced_order")
        number_request = self.env["voip.did.number.request"]
        if isinstance(advanced_order, dict):
            number_request = number_request.sudo().search([
                ("request_uuid", "=", advanced_order.get("request_uuid")),
            ], limit=1)
            if not number_request:
                _logger.warning("_handle_status_event: unknown advanced number request")
                return
            if (
                did
                and did.state not in ("failure", "released")
                and did.number_request_id != number_request
            ):
                _logger.warning("_handle_status_event: phone number belongs to another request")
                return
        if not did or (isinstance(advanced_order, dict) and did.state in ("failure", "released")):
            if not isinstance(advanced_order, dict):
                return
            country = number_request.country_id
            number_type = number_request.did_number_type
            requester = number_request.requested_by_id
            requirement_group = number_request.requirement_group_id
            existing_number = self.sudo().search([
                ("user_id", "=", requester.id),
                ("state", "!=", "released"),
            ], limit=1)
            assign_to_requester = requester.active and not existing_number
            did = self.with_user(requester).sudo()._create_or_reuse_for_order([{
                "did_number": phone_number,
                "state": state,
                "country_id": country.id,
                "did_number_type": number_type,
                "requirement_group_id": requirement_group.id or False,
                "number_request_id": number_request.id,
                "purchase_date": fields.Datetime.now(),
            }])
            if assign_to_requester and state not in ("failure", "released"):
                did.with_context(voip_skip_pbx_sync=True).destination_ref = requester
                requester.with_context(voip_skip_pbx_sync=True)._select_odoo_voip_provider()
                did._sync_pbx_after_status_update(requester)
        did = did.with_user(SUPERUSER_ID)
        if number_request and not did.number_request_id:
            did.number_request_id = number_request
        event = payload.get("event")
        error = payload.get("error")
        old_state = did.state
        users_before = did.user_id
        did.with_context(voip_skip_pbx_sync=True).write({"state": state})
        if "requirement_statuses" in payload:
            did._sync_requirement_statuses(payload["requirement_statuses"])
        if old_state != state:
            did._notify_status_updated()
            did._sync_pbx_after_status_update(users_before | did.user_id)
        if event == "deletion_confirmed":
            did.post_notification(self.env._("Number deletion confirmed by the provider."))
            return
        if event == "deletion_failed":
            if error:
                did.post_notification(self.env._("Number deletion failed: %(error)s", error=error))
            return
        if event in ("order_created", "order_in_progress"):
            label = self.env._("created") if event == "order_created" else self.env._("in progress")
            did.post_notification(
                self.env._("Number order update: %(status)s.", status=label),
            )
        elif event == "order_failed" and error:
            error = {
                "insufficient_credits": self.env._(
                    "You do not have enough credits to complete this operation.",
                ),
                "number_unavailable": self.env._(
                    "The search result expired or the number became unavailable. "
                    "Search again and complete the purchase promptly. No credits were charged.",
                ),
            }.get(error, error)
            did.post_notification(
                self.env._("Number order failed: %(error)s", error=error),
            )
        did._fetch_and_post_sub_order_comments()

    def _sync_requirement_statuses(self, statuses):
        self.ensure_one()
        if not isinstance(statuses, dict) or statuses == (self.requirement_statuses or {}):
            return
        previous_rejected = {
            requirement_id
            for requirement_id, status in (self.requirement_statuses or {}).items()
            if status == "rejected"
        }
        newly_rejected = {
            requirement_id
            for requirement_id, status in statuses.items()
            if status == "rejected" and requirement_id not in previous_rejected
        }
        self.requirement_statuses = statuses
        requirements = self.requirement_group_id.requirement_ids.filtered(
            lambda requirement: (
                requirement.telnyx_requirement_id in newly_rejected
                and (requirement.field_type != "action" or requirement.did_number_id == self)
            ),
        )
        if not requirements:
            return
        names = ", ".join(requirements.mapped("name"))
        if len(requirements) == 1:
            body = self.env._(
                "Action required: a regulatory requirement was rejected: %(requirements)s. "
                "Review the guidelines in the chatter, then click Update Requirements.",
                requirements=names,
            )
        else:
            body = self.env._(
                "Action required: %(count)s regulatory requirements were rejected: %(requirements)s. "
                "Review the guidelines in the chatter, then click Update Requirements.",
                count=len(requirements),
                requirements=names,
            )
        self.message_post(
            body=body,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=self.user_id.partner_id.ids,
            notify_skip_followers=True,
        )

    def _sync_pbx_after_status_update(self, users, schedule_retry=True):
        """Best-effort PBX sync after the provider status has been persisted."""
        self.ensure_one()
        try:
            # Separate savepoints: a routing failure must not discard the IDs
            # of PBX objects the user provisioning just created, or the retry
            # would recreate them and conflict.
            with self.env.cr.savepoint():
                self._ensure_default_outgoing_number()
            with self.env.cr.savepoint():
                self._sync_user_provisioning(users)
            with self.env.cr.savepoint():
                self._sync_pbx_incall()
            with self.env.cr.savepoint():
                self._sync_user_outgoing_caller_ids(users)
        except UserError as error:
            _logger.warning(
                "Could not synchronize PBX after DID %s status changed to %s: %s",
                self.did_number,
                self.state,
                error,
            )
            if schedule_retry:
                self._schedule_provisioning_retry()

    def _notify_status_updated(self):
        self.ensure_one()
        self.create_uid._bus_send(
            "voip.did_number/status_updated",
            {
                "id": self.id,
                "phone_number": self.did_number,
                "state": self.state,
            },
        )

    def _sync_number_statuses(self):
        if not self:
            return
        status_by_number = PhoneServiceAPI(self.env).get_phone_number_statuses(
            self.mapped("did_number"),
        )
        valid_states = dict(self._fields["state"].selection)
        for number in self:
            info = status_by_number.get(number.did_number)
            if not info:
                continue
            if "requirement_statuses" in info:
                number._sync_requirement_statuses(info["requirement_statuses"])
            if info["state"] in valid_states:
                users_before = number.user_id
                old_state = number.state
                number.with_context(voip_skip_pbx_sync=True).state = info["state"]
                if old_state != number.state:
                    number._notify_status_updated()
                    number._sync_pbx_after_status_update(users_before | number.user_id)
        try:
            with self.env.cr.savepoint():
                self._ensure_default_outgoing_number()
        except UserError as error:
            _logger.warning(
                "Could not synchronize the PBX Default Outgoing Number after polling number statuses: %s",
                error,
            )

    def action_refresh_number_statuses(self):
        dids = self.search([])
        dids._sync_number_statuses()
        for did in dids.filtered(lambda d: d.state == "pending"):
            did._fetch_and_post_sub_order_comments()
        if dids.filtered(lambda d: d.state in ("ordering", "pending")):
            message = self.env._(
                "Numbers still being ordered will update on their own, without"
                " another refresh.",
            )
        else:
            message = self.env._("The phone number statuses are up to date.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Refreshed"),
                "message": message,
                "type": "info",
            },
        }

    @api.model
    def _cron_sync_number_statuses(self):
        self.action_refresh_number_statuses()

    # --- Provisioning safety net ---

    def _filter_under_provisioned(self):
        """Return live user-assigned DIDs whose PBX provisioning is incomplete.

        `_sync_user_provisioning` is idempotent and level-triggered, but every
        caller only drives it on a state *transition*. A DID that reaches
        `active` while the PBX tenant isn't ready yet (or on any transient
        Wazo/IAP error) lands active with no line and is never retried, because
        no further transition happens. This predicate lets the safety-net cron
        re-drive provisioning for exactly those numbers.
        """
        odoo_provider = self.env["voip.pbx.service"].voip_provider
        incomplete = self.browse()
        for did in self.sudo():
            if (
                did.state not in ("ordering", "pending", "active", "suspended")
                or not did.user_id
            ):
                continue
            settings = did.user_id.res_users_settings_id
            if settings.voip_provider_id != odoo_provider:
                continue
            if (
                not settings.voip_username
                or not settings.voip_secret
                or not did.user_id.voip_pbx_user_id
                or not did.user_id.voip_pbx_line_id
                or not did.user_id.routing_extension_id
                or (
                    did.state == "active"
                    and (not did.pbx_incall_id or not did.pbx_incall_extension_id)
                )
            ):
                incomplete |= did
        return incomplete

    def _schedule_provisioning_retry(self):
        """Ask the heal cron to re-attempt provisioning shortly, so a transient
        failure recovers in ~a minute instead of waiting for the next tick."""
        cron = self.env.ref("voip.ir_cron_voip_heal_provisioning", raise_if_not_found=False)
        if cron:
            cron._trigger(fields.Datetime.now() + timedelta(seconds=60))

    @api.model
    def _cron_heal_provisioning(self):
        live_dids = self.search([
            ("state", "in", ("ordering", "pending", "active", "suspended")),
            ("user_id", "!=", False),
        ])
        for did in live_dids._filter_under_provisioned():
            did._sync_pbx_after_status_update(did.user_id, schedule_retry=False)

    def _fetch_and_post_sub_order_comments(self):
        self.ensure_one()
        if self.state == "ordering":
            return
        try:
            comments = PhoneServiceAPI(self.env).get_phone_number_comments(self.did_number)
        except UserError as error:
            _logger.warning("Could not fetch comments for DID %s: %s", self.did_number, error)
            return
        if not comments:
            return
        synced_ids = self.telnyx_synced_comment_ids or []
        new_synced_ids = list(synced_ids)
        for comment in comments:
            comment_id = comment.get("id")
            body = comment.get("body", "")
            if not body or comment_id in synced_ids:
                continue
            date_label = self.env._("Date:")
            message_body = Markup(
                "<p>%s</p><p class='text-muted small'>%s %s</p>",
            ) % (body, date_label, comment.get("created_at", ""))
            self.message_post(
                body=message_body,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            new_synced_ids.append(comment_id)
        if new_synced_ids != synced_ids:
            self.telnyx_synced_comment_ids = new_synced_ids

    # --- Release ---

    def action_release_number(self):
        self.ensure_one()
        number = self.did_number
        try:
            PhoneServiceAPI(self.env).release_phone_number(number)
            self.write({"state": "released"})
        except UserError as e:
            _logger.warning("Failed to release DID %s: %s", number, e)
            params = {
                "title": self.env._("Not Released"),
                "message": self.env._("The phone number could not be released."),
                "type": "warning",
            }
        else:
            params = {
                "title": self.env._("Released"),
                "message": self.env._("The phone number was released."),
                "type": "info",
                "next": {"type": "ir.actions.act_window_close"},
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": params,
        }

    def action_buy_credits(self):
        return get_buy_credits_action(self.env)
