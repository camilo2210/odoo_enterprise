import ast
import logging
import re
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from psycopg2.errors import UniqueViolation

from odoo import api, fields, models
from odoo.exceptions import ConcurrencyError
from odoo.fields import Domain
from odoo.sql_db import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY
from odoo.tools.misc import clean_context
from odoo.tools.sql import SQL

from odoo.addons.mail.tools.discuss import Store
from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI
from odoo.addons.voip.models.utils import normalize_caller_number, same_number

_logger = logging.getLogger(__name__)

# Accepted state transitions for VoIP calls
CALL_STATE_TRANSITIONS = {
    "incoming": {
        # Valid transitions
        ("calling", "ongoing"), ("ongoing", "terminated"),
        ("calling", "rejected"),
        ("calling", "missed"),
        ("calling", "completed_elsewhere"),

        # Allow recovery from unexpected endings
        ("ended_unexpectedly", "ongoing"),
        ("ended_unexpectedly", "terminated"),
        ("ended_unexpectedly", "rejected"),
        ("ended_unexpectedly", "missed"),
        ("ended_unexpectedly", "completed_elsewhere"),

        # Allow recovery from tab concurrency issues
        ("rejected", "ongoing"),
        ("missed", "ongoing"),
        ("missed", "rejected"),
        ("completed_elsewhere", "ongoing"),

        # A peer's answer revises a "missed" its own cancel raced into.
        ("missed", "completed_elsewhere"),

        # Allows end_call() to precede start_call().
        # The caller is responsible for ensuring end_call() is only reached for established calls.
        ("calling", "terminated"),
    },
    "outgoing": {
        # Valid transitions
        ("calling", "ongoing"), ("ongoing", "terminated"),
        ("calling", "rejected"),
        ("calling", "aborted"),

        # Allow recovery from unexpected endings
        ("ended_unexpectedly", "ongoing"),
        ("ended_unexpectedly", "terminated"),
        ("ended_unexpectedly", "rejected"),
        ("ended_unexpectedly", "aborted"),

        # Allows end_call() to precede start_call().
        # The caller is responsible for ensuring end_call() is only reached for established calls.
        ("calling", "terminated"),
    },
}

CALLING_CALL_TIMEOUT = relativedelta(minutes=5)
ONGOING_CALL_TIMEOUT = relativedelta(hours=4)

TERMINAL_CALL_STATES = ("aborted", "completed_elsewhere", "missed", "rejected", "terminated")
LIVE_CALL_STATES = ("calling", "ongoing")


class VoipCall(models.Model):
    """User-facing phone call record synchronized with provider and softphone events."""

    _name = "voip.call"
    _inherit = ["mail.thread.main.attachment", "voip.phone.country.mixin"]
    _description = "Phone call"
    _explanation = "Represents a single Voice over IP (VoIP) phone call."

    conversation_id = fields.Many2one(comodel_name="voip.conversation", readonly=True, index="btree_not_null")
    cost_line_ids = fields.One2many("voip.call.cost.line", "call_id", groups="voip.group_voip_admin")
    cost = fields.Float(string="Cost (Credits)", readonly=True, help="Cost of the call in Credits", groups="voip.group_voip_admin", compute="_compute_cost", store=True)
    cost_display = fields.Char(compute="_compute_cost_display", string="Cost", export_string_translation=False, groups="voip.group_voip_admin")
    phone_number = fields.Char(required=True, readonly=True)
    phone_number_formatted = fields.Char(
        compute="_compute_phone_number_formatted",
        export_string_translation=False,
    )
    direction = fields.Selection(
        [
            ("incoming", "Incoming"),
            ("outgoing", "Outgoing"),
        ],
        default="outgoing",
        readonly=True,
    )
    state = fields.Selection(
        [
            ("aborted", "Aborted"),
            ("completed_elsewhere", "Completed Elsewhere"),
            ("ended_unexpectedly", "Ended Unexpectedly"),
            ("calling", "Ringing"),
            ("missed", "Missed"),
            ("ongoing", "Ongoing"),
            ("rejected", "Rejected"),
            ("terminated", "Completed"),
        ],
        default="calling",
        index=True,
        readonly=True,
    )
    artifact_ids = fields.One2many("mail.call.artifact", "voip_call_id", string="Artifacts")
    start_date = fields.Datetime(readonly=True)
    duration = fields.Integer("Duration (s)", readonly=True, help="Duration of the call in seconds")
    effective_start_date = fields.Datetime(compute="_compute_effective_start_date", compute_sql="_compute_sql_effective_start_date", compute_sudo=True)
    end_date = fields.Datetime(compute="_compute_end_date", compute_sql="_compute_sql_end_date", compute_sudo=True)
    has_recording = fields.Boolean(compute="_compute_has_recording", compute_sql="_compute_sql_has_recording", compute_sudo=True)

    is_production = fields.Boolean(default=True, readonly=True, export_string_translation=False,
        help="Whether the call happened in a production environment. True for all calls created before this tracking was implemented.")
    is_within_same_company = fields.Boolean(compute="_compute_is_within_same_company", store=True)
    activity_id = fields.Many2one("mail.activity", index="btree_not_null")
    activity_mail_message_id = fields.Many2one("mail.message", index="btree_not_null", export_string_translation=False)
    partner_id = fields.Many2one("res.partner", "Contact", index=True)
    # Kept as the name the softphone gives a call, no longer as a correlation
    # key: get_or_create matches on the conversation and on the legs.
    control_handle = fields.Char("Control Handle", readonly=True, export_string_translation=False)
    wakeup_pbx_call_id = fields.Char(
        readonly=True, export_string_translation=False,
        help="PBX call id of the dial_mobile wakeup channel that rang this member while "
             "their softphone was unregistered. The decline handle when no SIP leg exists.")
    leg_ids = fields.One2many(comodel_name="voip.call.leg", inverse_name="voip_call_id", readonly=True)
    user_id = fields.Many2one("res.users", "User", default=lambda self: self.env.uid, index=True)
    country_id = fields.Many2one("res.country", compute="_compute_country_id", store=True, index="btree_not_null")
    country_flag_url = fields.Char(related="country_id.image_url", string="Country Flag")
    call_count = fields.Integer(compute="_compute_call_count", help="The total number of calls made to the same phone number.")
    image_1920 = fields.Binary(related="partner_id.image_1920")
    avatar_128 = fields.Binary(related="partner_id.avatar_128")
    duration_human_readable = fields.Char(compute="_compute_duration_human_readable", export_string_translation=False)
    activity_done_label = fields.Char(compute="_compute_activity_done_label", export_string_translation=False)
    # activity related document
    activity_res_model = fields.Char(related="activity_id.res_model")
    activity_res_model_id = fields.Many2one(related="activity_id.res_model_id", string="Logged On")
    activity_res_id = fields.Many2oneReference(
        related="activity_id.res_id",
        string="Logged On (ID)",
        model_field="activity_res_model",
    )

    @api.depends("cost_line_ids.credits")
    def _compute_cost(self):
        for call in self:
            call.cost = sum(call.cost_line_ids.mapped("credits"))

    @api.depends("cost")
    def _compute_cost_display(self):
        for call in self:
            call.cost_display = self.env._(
                "%(cost_in_credits)s Credits",
                cost_in_credits=f"{call.cost:.4f}",
            ) if call.cost else ""

    @api.depends("duration_human_readable")
    def _compute_activity_done_label(self):
        for call in self:
            call.activity_done_label = self.env._("Call done (%(duration)s)", duration=call.duration_human_readable)

    # A call is one user's point of view on one conversation, so a second device
    # ringing must join it rather than open another. The find-or-create in
    # phone_service_event cannot hold that on its own: the events of a
    # conversation are processed in parallel transactions, and under REPEATABLE
    # READ none of them sees an insert the others have not committed, so two
    # ringing devices both search, both find nothing and both create. This index
    # is what makes the loser fail and retry. Live states only - a terminal call
    # is history, and a later call may legitimately reuse the conversation.
    # Named after the index init() used to create by hand, so an existing
    # database adopts it instead of ending up with two identical ones. Direction
    # is part of the key because one conversation can hold both directions for
    # the same user: calling a group they are a member of rings them back,
    # giving them a live outgoing and a live incoming call in that conversation.
    _unique_live_per_user_conversation = models.UniqueIndex(
        f"(conversation_id, user_id, direction) WHERE state IN {LIVE_CALL_STATES}",
        message="A user can only have one live call per conversation and direction.",
    )
    # The same invariant for the calls the index above cannot see: a provider
    # that stamps no conversation leaves conversation_id NULL, and Postgres
    # keeps NULLs distinct, so those rows never collide there. Their key is the
    # Call-ID the browser sent as control_handle. The two predicates are
    # disjoint, so no call is covered twice.
    _check_unique_control_handle_per_user = models.UniqueIndex(
        f"(control_handle, user_id, direction) "
        f"WHERE conversation_id IS NULL AND state IN {LIVE_CALL_STATES}",
        message="A user can only have one live call per control handle and direction.",
    )
    # Supports _get_prioritized_contacts: for the current user's calls, scan
    # partner-linked calls in descending recency order.
    _prioritized_contacts_idx = models.Index(
        "(user_id, create_date DESC, partner_id) WHERE partner_id IS NOT NULL",
    )

    @api.model_create_multi
    def create(self, vals_list):
        calls = super().create(vals_list)
        calls._sync_has_active_call()
        return calls

    def write(self, vals):
        fields_affecting_active_call = {"create_date", "direction", "start_date", "state", "user_id"}
        should_sync_active_call = bool(fields_affecting_active_call & vals.keys())
        users_to_sync = self.user_id if should_sync_active_call else self.env["res.users"]
        calls_to_cleanup = self.env["voip.call"]
        if vals.get("state") in {"aborted", "rejected", "ended_unexpectedly"}:
            calls_to_cleanup = self.filtered(lambda call: call.direction == "outgoing")
        result = super().write(vals)
        if should_sync_active_call:
            users_to_sync |= self.user_id
            self._sync_has_active_call(users=users_to_sync)
        calls_to_cleanup._cleanup_automated_activity()
        return result

    @api.depends("partner_id", "phone_number")
    def _compute_call_count(self):
        if not self.ids:
            self.call_count = 0
            return
        query = SQL(
            """
            SELECT
                call_1.id,
                COUNT(DISTINCT call_2.id) AS count
            FROM
                voip_call AS call_1
                JOIN voip_call AS call_2 ON (
                    (
                        call_1.phone_number = call_2.phone_number
                        OR call_1.partner_id = call_2.partner_id
                    )
                )
            WHERE
                call_1.id IN %(ids)s
            GROUP BY
                call_1.id
            ORDER BY
                call_1.id;
        """,
            ids=tuple(self.ids),
        )
        self.env.cr.execute(query)
        count_by_call_id = {res["id"]: res["count"] for res in self.env.cr.dictfetchall()}
        for call in self:
            call.call_count = count_by_call_id.get(call.id)

    @api.depends("state", "partner_id.name")
    def _compute_display_name(self):
        def get_name(call):
            if call.state == "aborted":
                return self.env._("Aborted call to %(phone_number)s", phone_number=call.phone_number)
            if call.state == "missed":
                return self.env._("Missed call from %(phone_number)s", phone_number=call.phone_number)
            if call.state == "rejected":
                if call.direction == "incoming":
                    return self.env._("Rejected call from %(phone_number)s", phone_number=call.phone_number)
                return self.env._("Rejected call to %(phone_number)s", phone_number=call.phone_number)
            if call.partner_id:
                if call.direction == "incoming":
                    return self.env._("Call from %(correspondent)s", correspondent=call.partner_id.name)
                return self.env._("Call to %(correspondent)s", correspondent=call.partner_id.name)
            if call.direction == "incoming":
                return self.env._("Call from %(phone_number)s", phone_number=call.phone_number)
            return self.env._("Call to %(phone_number)s", phone_number=call.phone_number)

        for call in self:
            call.display_name = get_name(call)

    @api.depends("duration")
    def _compute_duration_human_readable(self):
        for call in self:
            if not call.duration:
                call.duration_human_readable = self.env._("0s")
                continue
            if call.duration < 60:
                call.duration_human_readable = self.env._("%(seconds)ss", seconds=call.duration)
                continue
            minutes, seconds = divmod(call.duration, 60)
            if minutes < 60:
                call.duration_human_readable = self.env._("%(minutes)sm %(seconds)ss", minutes=minutes, seconds=seconds)
                continue
            hours, minutes = divmod(minutes, 60)
            call.duration_human_readable = self.env._(
                "%(hours)sh %(minutes)sm %(seconds)ss", hours=hours, minutes=minutes, seconds=seconds,
            )

    @api.depends("create_date", "start_date")
    def _compute_effective_start_date(self):
        for call in self:
            call.effective_start_date = call.start_date or call.create_date

    def _compute_sql_effective_start_date(self, table):
        return SQL("COALESCE(%s, %s)", table.start_date, table.create_date)

    @api.depends("start_date", "duration")
    def _compute_end_date(self):
        for call in self:
            if call.start_date and call.duration:
                call.end_date = call.start_date + timedelta(seconds=call.duration)
            else:
                call.end_date = False

    def _compute_sql_end_date(self, table):
        return SQL(
            """
            CASE
                WHEN %(start)s IS NOT NULL
                 AND %(duration)s IS NOT NULL
                 AND %(duration)s > 0
                THEN %(start)s + (%(duration)s * interval '1 second')
                ELSE NULL
            END
            """,
            start=table.start_date,
            duration=table.duration,
        )

    @api.depends("artifact_ids")
    def _compute_has_recording(self):
        for call in self:
            call.has_recording = bool(call.artifact_ids)

    def _compute_sql_has_recording(self, table):
        return SQL(
            "EXISTS (SELECT 1 FROM mail_call_artifact WHERE voip_call_id = %s)",
            table.id,
        )

    @api.depends("partner_id.commercial_partner_id", "user_id.partner_id.commercial_partner_id")
    def _compute_is_within_same_company(self):
        for call in self:
            user_company = call.user_id.partner_id.commercial_partner_id
            partner_company = call.partner_id.commercial_partner_id
            call.is_within_same_company = user_company and user_company == partner_company

    @api.depends("phone_country_id")
    def _compute_country_id(self):
        for call in self:
            call.country_id = call.phone_country_id

    @api.depends("phone_number", "phone_country_id")
    def _compute_phone_number_formatted(self):
        # phone_country_id feeds _phone_format via _phone_get_country_field() when phone_number is non-E.164
        for call in self:
            call.phone_number_formatted = call._phone_get_formatted(call.phone_number)

    @api.ondelete(at_uninstall=False)
    def _unlink_send_notification(self):
        for user, calls in self.grouped(lambda c: c.user_id).items():
            user._bus_send("voip.call/delete", {"ids": calls.ids})
        self._sync_has_active_call(excluded_call_ids=self.ids)

    @api.ondelete(at_uninstall=False)
    def _unlink_cleanup_artifacts_attachments(self):
        self.artifact_ids.unlink()

    def _add_sip_call_id(self, sip_call_id):
        """Attach a SIP Call-ID to this call by materializing its leg.

        Wazo emits one leg per SIP Call-ID; all legs of a queue conversation
        share a conversation but carry distinct Call-IDs. Each Call-ID
        lives on its own ``voip.call.leg`` so the browser can match the
        notification action with whichever INVITE reached that tab or device.
        The leg is found-or-created: a webhook may already have materialized it
        (keyed by PBX call id), in which case we only bind it to this call.
        """
        if not sip_call_id:
            return
        Leg = self.env["voip.call.leg"].sudo()
        for call in self:
            leg = Leg.search([("sip_call_id", "=", sip_call_id)], limit=1)
            if leg:
                if not leg.voip_call_id:
                    leg.voip_call_id = call
            else:
                try:
                    Leg.create({
                        "voip_call_id": call.id,
                        "conversation_id": call.conversation_id.id,
                        "sip_call_id": sip_call_id,
                    })
                except UniqueViolation as e:
                    raise ConcurrencyError() from e

    def _find_by_sip_call_id(self, sip_call_id, direction="incoming"):
        """Return the call whose leg tracks ``sip_call_id``, in ``direction``.

        Scoped to the current environment user so an INVITE from one user cannot
        attach itself to another user's call record. Outgoing calls are looked
        up the same way: the browser sends its INVITE's Call-ID, which is what
        the PBX reports as ``sip_call_id`` on that same leg, so a browser call
        and its webhooks converge on one record whichever arrives first.
        """
        if not sip_call_id:
            return self.browse()
        leg = self.env["voip.call.leg"].sudo().search([
            ("sip_call_id", "=", sip_call_id),
            ("voip_call_id.direction", "=", direction),
            ("voip_call_id.user_id", "=", self.env.uid),
        ], limit=1)
        return self.browse(leg.voip_call_id.id) if leg.voip_call_id else self.browse()

    @api.model
    def _find_incoming_by_sip_call_id(self, sip_call_id):
        """Webhook-side variant of ``_find_by_sip_call_id``: PBX push events
        carry no Odoo user context, so the lookup spans all users."""
        if not sip_call_id:
            return self.sudo().browse()
        leg = self.env["voip.call.leg"].sudo().search([
            ("sip_call_id", "=", sip_call_id),
            ("voip_call_id.direction", "=", "incoming"),
        ], order="id desc", limit=1)
        return leg.voip_call_id.sudo()

    def _find_recent_pending_incoming_call(self, phone_number):
        """Return the webhook-created call while Wazo has not sent the browser leg yet.

        Wazo may first send a source-leg webhook, then deliver the browser INVITE
        with a different SIP Call-ID, and only later send the callee-leg webhook
        that carries this second SIP Call-ID. During that short race window the
        INVITE must attach to the already-notified call instead of creating a
        duplicate.
        """
        phone_numbers = [phone_number] if phone_number else []
        user = self.env["res.users.settings"]._get_user_from_voip_username(phone_number)
        if user.routing_extension_id.number:
            # Internal Wazo INVITEs expose the caller SIP username
            # (odoo-user-uuid), while the webhook stores the human extension
            # number as the call display value. Keep both candidates so the
            # browser INVITE can attach to the webhook-created call.
            phone_numbers.append(user.routing_extension_id.number)
        phone_numbers = list(dict.fromkeys(phone_numbers))
        if not phone_numbers:
            return self.browse()
        candidates = self.sudo().search([
            ("user_id", "=", self.env.uid),
            ("direction", "=", "incoming"),
            ("state", "=", "calling"),
            ("create_date", ">=", fields.Datetime.now() - timedelta(minutes=2)),
        ], order="id desc")
        for call in candidates:
            if any(same_number(call.phone_number, number) for number in phone_numbers):
                return call.sudo(False)
        return self.browse()

    def action_open_calls(self):
        self.ensure_one()
        domain = Domain("phone_number", "=", self.phone_number)
        if self.partner_id:
            domain |= Domain("partner_id", "=", self.partner_id)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Calls"),
            "res_model": "voip.call",
            "view_mode": "list,form",
            "domain": domain,
        }

    def action_log_call(self, active_model=None, active_id=None):
        """Open the Log Activity wizard for this call, pre-filled with the call's
        contact and the appropriate related model/field selection.

        If an ``active_model`` and ``active_id`` are provided (e.g. from an open
        form), attempts to find a matching ``res_model_selection`` option for
        that model; otherwise falls back to ``res.partner``.

        :param active_model: Optional model name of the record being viewed.
        :param active_id: Optional ID of the record being viewed.
        :return: An action dictionary opening the ``mail.activity.schedule`` wizard.
        """
        self.ensure_one()
        context = {
            "default_activity_category": "phonecall",
            "default_activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
            "default_call_id": self.id,
            "default_date_deadline": False,
            "default_res_model_selection": "res.partner",
            # do not use default_contact_id here
            # we have more business logic than just setting default value
            # default_* in context can be remove unexpectedly
            "voip_log_contact_id": self.partner_id.id,
        }
        if active_model and active_id:
            context.update(self._get_field_selection_for_model(active_model, active_id) or {})
        return {
            "name": self.env._("Log Activity in Chatter"),
            "type": "ir.actions.act_window",
            "res_model": "mail.activity.schedule",
            "view_mode": "form",
            "views": [(self.env.ref("voip.voip_activity_schedule_form_view").id, "form")],
            "target": "new",
            "context": context,
        }

    def _get_field_selection_for_model(self, model_name, id):
        """Find the res_model_selection option matching the given model and
        return the context dict to pre-fill the wizard.

        :return: A dict like ``{"default_lead_id": id}``, or ``None``.
        """
        if model_name == "res.partner":
            # res.partner is already handled by the default context in action_log_call
            return None
        wizard = self.env["mail.activity.schedule"].with_context(
            voip_log_contact_id=self.partner_id.id,
        ).new({"call_id": self.id})
        fields_map = wizard._get_res_model_fields()
        for value, _label in wizard._selection_res_model():
            if wizard._get_res_model_from_selection(value) != model_name:
                continue
            field_name = fields_map.get(value)
            # The field may define a ``{field}_domain`` (e.g. ``lead_id_domain``)
            # restricting which records are selectable: check that the record
            # is within that domain before pre-selecting it.
            domain_field = f"{field_name}_domain"
            if domain_field in wizard._fields:
                domain_str = wizard[domain_field] or "[]"
                domain = ast.literal_eval(domain_str)
                if not self.env[model_name].search_count(
                    Domain("id", "=", id) & Domain(domain), limit=1,
                ):
                    # The record is out of this option's domain: skip it and
                    # try the next option mapping to the same model, e.g. a
                    # plain ``sale.order`` failing the ``sale.subscription``
                    # domain still matches the ``sale.order`` option.
                    continue
            return {
                f"default_{field_name}": id,
                "default_res_model_selection": value,
            }
        return None

    @api.model
    def get_by_id(self, call_id):
        """Fetch an existing call by ID.
        """
        call = self.search([("id", "=", call_id)], limit=1)
        if not call:
            return None
        return {
            "ids": [call.id],
            "store_data": call._get_store_data(),
        }

    @api.model
    def get_prefill_data(self, res_model, res_id):
        """Get the partner phone and store data for keypad pre-filling from a
        form view, so the softphone can auto-fill the dialer and display the
        partner in the contact suggestions.

        Falls back to the record's own phone fields (via ``_phone_get_number_fields``)
        when no linked partner is found or the partner has no phone number.

        :param str res_model: model name of the record
        :param int res_id: ID of the record
        :returns: dict with ``partner_id``, ``phone`` and ``store_data``, or an empty dict
        """
        record = self.env[res_model].browse(res_id)
        # Return the same empty result for non-existent and inaccessible
        # records, so the response does not leak record existence.
        if not record.exists() or not record.has_access("read"):
            return {}

        store = Store()
        partners = record._mail_get_partners(introspect_fields=True).get(record.id)
        partner = partners[:1]
        if partner:
            store.add(partner, "_store_voip_fields")
        phone = partner.phone_formatted or partner.phone_sanitized or partner.phone or record._phone_format()
        if phone:
            return {"partner_id": partner.id, "phone": phone, "store_data": store}
        return {}

    @api.model
    def get_or_create(self, data):
        """Return the matching call record for an incoming SIP INVITE.

        Wazo webhooks and browser INVITEs can arrive in either order and can
        carry different SIP Call-IDs for the same conversation. They are
        correlated through the PBX conversation, then the SIP Call-ID header
        (webhook ``sip_call_id`` == INVITE ``Call-ID``), then the short
        pending-call fallback.

        ``conversation_identifier`` is what the ``X-Odoo-Conversation-Id``
        header carries. Only the Odoo provider is trusted to stamp it, so every
        other provider sends none and is correlated by Call-ID alone.

        The conversation match only considers live calls: a record in a
        terminal state is frozen history, so a later INVITE reusing the same
        conversation id (queue retry, transfer or park recall) starts a new
        call record instead of resurrecting the old one.
        """
        self.check_access("read")
        skip_recent_pending_match = data.pop("skip_recent_pending_match", False)
        conversation_identifier = data.get("conversation_identifier")
        sip_call_id = data.pop("sip_call_id", None)
        direction = data.get("direction")

        if (
            direction == "incoming"
            and not conversation_identifier
            and self.env.user.uses_odoo_provider
        ):
            # Without the header this call shares no key with its PBX
            # conversation: the webhook legs and the mobile push both fail to
            # find it.
            _logger.warning(
                "INVITE %s reached the softphone without X-Odoo-Conversation-Id; "
                "call of user %s cannot be correlated with its PBX conversation.",
                sip_call_id, self.env.uid,
            )

        call = self.env["voip.call"]
        if conversation_identifier:
            # sudo: ensure that the call is found if it exists
            call = self.env["voip.call"].sudo().search(
                [
                    ("conversation_id.conversation_identifier", "=", conversation_identifier),
                    ("user_id", "=", self.env.uid),
                    ("direction", "=", direction),
                    ("state", "in", LIVE_CALL_STATES),
                ],
                limit=1,
            )
        if not call:
            call = self._find_by_sip_call_id(sip_call_id, direction)
        if not call and direction == "incoming" and not skip_recent_pending_match:
            call = self._find_recent_pending_incoming_call(data.get("phone_number"))
        if call:
            call = call.sudo(False)
            call._add_sip_call_id(sip_call_id)
            call._sync_has_active_call()
            outcome = "matched"
            result = {
                "ids": [call.id],
                "store_data": call._get_store_data(),
            }
        else:
            outcome = "created"
            try:
                result = self.create_and_format(
                    **data, control_handle=conversation_identifier or sip_call_id)
            except UniqueViolation as e:
                raise ConcurrencyError() from e  # triggers Odoo's retry mechanism (UniqueViolation doesn't)
            if sip_call_id:
                # Keep the SIP identifier on a leg immediately, otherwise the next
                # webhook retry could not find this INVITE-created call by Call-ID.
                self.browse(result["ids"][0])._add_sip_call_id(sip_call_id)
        _logger.info(
            "get_or_create user=%s %s %s conversation=%s sip_call_id=%s -> %s call %s",
            self.env.uid, direction, data.get("phone_number"),
            conversation_identifier, sip_call_id, outcome, result["ids"][0])
        return result

    @api.model
    def create_and_format(
        self,
        phone_number: str,
        direction: str = "outgoing",
        partner_id: int | None = None,
        activity_id: int | None = None,
        conversation_identifier: str | None = None,
        control_handle: str | None = None,
        res_id: int | None = None,
        res_model: str | None = None,
        is_production: bool = True,
    ):
        """Creates a call from the provided values and returns it formatted for
        use in JavaScript. If a record is provided via its id and model,
        introspects it for a recipient.

        :param phone_number: Phone number of the remote party
        :param direction: Call direction
        :param partner_id: Optional partner linked to the call
        :param activity_id: Optional phone activity linked to the call
        :param conversation_identifier: Optional PBX conversation grouping the legs
        :param control_handle: Optional name the softphone gives this call
        :param res_id: Optional record ID to extract partner from
        :param res_model: Optional model name to extract partner from
        :param is_production: Whether this call is happening in a production environment.

        Returns:
            Dictionary with created call IDs and formatted data
        """
        self.check_access("read")
        if activity_id:
            self.env["mail.activity"].browse(activity_id).check_access("read")
        if direction == "incoming":
            phone_number = self._resolve_incoming_caller_number(phone_number)
        values = {
            "activity_id": activity_id,
            "conversation_id": self.env["voip.conversation"]._get_or_create(
                conversation_identifier).id,
            "control_handle": control_handle,
            "direction": direction,
            "partner_id": partner_id,
            "phone_number": phone_number,
            "user_id": self.env.uid,
            "is_production": is_production,
        }
        if res_id and res_model and (related_record := self.env[res_model].browse(res_id)).exists():
            related_record.check_access("read")
            values["partner_id"] = next(
                iter(related_record._mail_get_partners(introspect_fields=True)[related_record.id]),
                self.env["res.partner"],
            ).id
            if not activity_id:
                try:
                    with self.env.cr.savepoint():
                        values["activity_id"] = self._create_call_activity(related_record).id
                except PG_CONCURRENCY_EXCEPTIONS_TO_RETRY:
                    raise
                except Exception:
                    _logger.warning(
                        "Failed to create call activity for %s/%s",
                        res_model, res_id, exc_info=True,
                    )
        call = self.sudo().create(values).sudo(False)
        store = Store().add(call, "_store_voip_fields")
        return {"ids": [call.id], "store_data": store}

    @api.model
    def _create_call_activity(self, related_record):
        """Create a phonecall activity on the given record.
        This is used to log outgoing calls initiated from phone field clicks.

        :param related_record: the target record
        :type related_record: models.Model
        :returns: the created activity, or an empty recordset if creation failed
        :rtype: mail.activity
        """
        if not isinstance(related_record, self.pool["mail.activity.mixin"]):
            return self.env["mail.activity"]
        phonecall_activity_type_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "mail.mail_activity_data_call", raise_if_not_found=False,
        )
        if not phonecall_activity_type_id:
            phonecall_activity_type_id = self.env["mail.activity.type"].search(
                ["|", ("res_model", "=", False), ("res_model", "=", related_record._name),
                 ("category", "=", "phonecall")], limit=1,
            ).id
        if not phonecall_activity_type_id:
            return self.env["mail.activity"]
        return related_record.activity_schedule(
            activity_type_id=phonecall_activity_type_id,
            date_deadline=fields.Date.context_today(self),
            user_id=self.env.uid,
        ) or self.env["mail.activity"]

    @api.model
    def _resolve_incoming_caller_number(self, number):
        """Return the phone number an incoming call stores for `number`: a
        colleague's SIP username becomes their extension number, anything else
        is normalized."""
        if not number:
            return number
        user = self.env["res.users.settings"]._get_user_from_voip_username(number)
        if user.routing_extension_id.number:
            return user.routing_extension_id.number
        return normalize_caller_number(number)

    @api.model
    def resolve_outgoing_dial_number(self, number):
        """Resolve the PBX target and report whether it stays inside the tenant."""
        self.check_access("read")
        did = self.env["voip.did.number"]._get_from_number(number)
        if did.destination_ref:
            if did.destination_ref._name == "voip.extension":
                extension = did.destination_ref
            elif did.destination_ref._name == "res.users":
                extension = did.destination_ref.routing_extension_id
            else:
                extension = self.env["voip.extension"]
            if extension.number:
                return {"number": extension.number, "is_internal": True}
        extension = self.env["voip.extension"].sudo().search([
            ("number", "=", number),
        ], limit=1)
        return {
            "number": number,
            "is_internal": bool(extension or re.fullmatch(r"\*\d+", number or "")),
        }

    @api.model
    def get_recent_phone_calls(self, direction=None, partner_id=None, offset=0, limit=None):
        domain = Domain("user_id", "=", self.env.uid)
        if direction:
            domain &= Domain("direction", "=", direction)
        if partner_id:
            domain &= Domain("partner_id", "=", partner_id)
        calls = self.search(domain, offset=offset, limit=limit, order="create_date DESC")
        store = Store().add(calls, "_store_voip_fields")
        return {"ids": calls.ids, "store_data": store}

    def _cleanup_automated_activity(self):
        """An automated activity may be created on a record when initiating an
        outgoing call. If the call is not picked up, the activity is never
        marked as done through the regular end_call flow, so it must be
        cleaned up explicitly when the call reaches a terminal state without
        being answered.
        """
        for call in self:
            if call.activity_id and call.activity_id.automated:
                call.activity_id.sudo().unlink()

    @api.model
    def _get_prioritized_contacts(self, partner_domain, limit=3):
        domain = (
            Domain("user_id", "=", self.env.uid)
            & Domain("partner_id", "!=", False)
            & Domain("partner_id", "any", partner_domain)
        )
        # Return one row per partner, ordered by that partner's latest call,
        # without loading every matching call in Python.
        groups = self._read_group(
            domain,
            groupby=["partner_id"],
            aggregates=["create_date:max"],
            order="create_date:max desc",
            limit=limit,
        )
        return self.env["res.partner"].browse([
            partner.id for partner, _date in groups
        ])

    @api.model
    def get_empty_list_help(self, help_message):
        softphone_icon = Markup(
            '<a type="action" name="voip.open_softphone" role="button"'
            ' class="text-reset fw-bold d-inline-flex align-items-center px-1 rounded o-voip-NoContentSoftphone">'
            '<i class="oi oi-filled" data-icon="phone"></i></a>',
        )
        if self.env.user.has_group("voip.group_voip_admin"):
            content = self.env._(
                "Open the softphone %(icon)s to make your first call, or",
                icon=softphone_icon,
            )
            replacement = Markup(
                '<p>%s</p><a type="action" name="voip.action_voip_did_number_search_wizard" '
                'class="btn btn-primary mt-2">%s</a>',
            ) % (content, self.env._("Buy a Phone Number"))
        else:
            content = self.env._(
                "Open the softphone %(icon)s to make your first call.",
                icon=softphone_icon,
            )
            replacement = Markup("<p>%s</p>") % content
        help_message = help_message.replace(
            Markup('<span id="voip_buy_number_help"></span>'),
            replacement,
        )
        return super().get_empty_list_help(help_message)

    def _get_number_of_missed_calls(self) -> int:
        domain = [("user_id", "=", self.env.uid), ("state", "=", "missed")]
        last_seen_phone_call = self.env.user.last_seen_phone_call
        if last_seen_phone_call:
            domain += [("id", ">", last_seen_phone_call.id)]
        return self.search_count(domain)

    def _get_result(self, success=True):
        return {
            "ids": [self.id],
            "success": success,
            "store_data": self._get_store_data(),
        }

    def _get_store_data(self):
        return Store().add(self, "_store_voip_fields")

    def _update_state(self, new_state: str):
        self.ensure_one()
        if self.state == new_state:
            return True
        if (self.state, new_state) not in CALL_STATE_TRANSITIONS.get(self.direction):
            return False
        self.state = new_state
        return True

    def abort_call(self):
        self.check_access("read")
        return self._get_result(success=self.sudo()._update_state("aborted"))

    def start_call(self, at=None):
        self.check_access("read")
        self_sudo = self.sudo()
        at = fields.Datetime.to_datetime(at) or fields.Datetime.now()
        success = self_sudo._update_state("ongoing")
        if success:
            if not self_sudo.start_date or at < self_sudo.start_date:
                self_sudo.start_date = at
        elif self_sudo.state == "terminated":
            # Race condition: end_call ran before start_call.
            # start_date was set by end_call as a placeholder; compute the
            # duration from the real start before overwriting it.
            diff = (self_sudo.start_date - at).total_seconds()
            self_sudo.duration = max(0, round(diff))
            self_sudo.start_date = at
        return self._get_result(success=success)

    def end_call(self, at=None):
        self.check_access("read")
        self_sudo = self.sudo()
        success = self_sudo._update_state("terminated")
        if success:
            at = fields.Datetime.to_datetime(at) or fields.Datetime.now()
            if not self_sudo.start_date:
                # start_call has not run yet;
                # store at as a placeholder so start_call can compute duration.
                self_sudo.start_date = at
                self_sudo.duration = 0
            else:
                diff = (at - self_sudo.start_date).total_seconds()
                self_sudo.duration = max(0, round(diff))
        return self._get_result(success=success)

    def reject_call(self):
        self.check_access("read")
        return self._get_result(success=self.sudo()._update_state("rejected"))

    def miss_call(self):
        self.check_access("read")
        return self._get_result(success=self.sudo()._update_state("missed"))

    def complete_call_elsewhere(self):
        """Mark this ringing call as answered by another party: a colleague in
        a group/queue conversation, or the same user on another device."""
        self.check_access("read")
        return self._get_result(success=self.sudo()._update_state("completed_elsewhere"))

    def get_contact_info(self):
        self.ensure_one()
        number = self.phone_number
        # Internal extensions could theoretically be one or two digits long.
        # phone_mobile_search doesn't handle numbers that short: do a regular
        # search for the exact match:
        if len(number) < 3:
            domain = [("phone", "=", number)]
        # 00 and + both denote an international prefix. phone_mobile_search will
        # match both indifferently.
        elif number.startswith(("+", "00")):
            domain = [("phone_mobile_search", "=", number)]
        # USA: Calls between different area codes are usually prefixed with 1.
        # Conveniently, the country code for the USA also happens to be 1, so we
        # just need to add the + symbol to format it like an international call
        # and match what's supposed to be stored in the database.
        elif number.startswith("1"):
            domain = [("phone_mobile_search", "=", f"+{number}")]
        else:
            domain = [("phone_mobile_search", "=", number)]
        partner = self.env["res.partner"].search(domain, limit=1)
        if not partner:
            partner = self.env["res.users.settings"]._get_user_from_voip_username(
                number, provider=self.user_id.voip_provider_id,
            ).partner_id.sudo(False)
        if not partner:
            # The caller-id may have been resolved to an internal extension
            # number at call creation; map it back to the colleague's contact.
            partner = (
                self.env["voip.extension"]
                ._get_user_from_number(number)
                .partner_id.sudo(False)
            )
        if not partner:
            return False
        self.check_access("read")
        self.sudo().partner_id = partner
        return self._get_store_data()

    def update_activity_message(self):
        self.check_access("read")
        self.ensure_one()
        call_sudo = self.sudo()
        call_sudo.invalidate_recordset()
        if not (call_sudo.activity_mail_message_id and call_sudo.activity_id):
            return
        activity_sudo = call_sudo.activity_id
        activity_sudo.invalidate_recordset()
        if activity_sudo.user_id != call_sudo.user_id:
            return
        res_record_sudo = self.env[activity_sudo.res_model].sudo().browse(activity_sudo.res_id)
        message_sudo = call_sudo.activity_mail_message_id
        ctx = dict(clean_context(self.env.context), voip_call=call_sudo, activity=activity_sudo, feedback=activity_sudo.feedback or "")
        new_body = (
            self.env["mail.render.mixin"]
            .with_context(ctx)
            ._render_template_qweb_view(
                "voip.message_call_activity_done",
                message_sudo._name,
                message_sudo.ids,
                add_context=ctx,
            )[message_sudo.id]
        )
        res_record_sudo._message_update_content(
            message_sudo,
            body=new_body,
            strict=False,
        )

    def _cleanup_stuck_calls(self):
        """Considers calls that are "calling" or "ongoing" and suspiciously old:
        it probably means that the call end update was missed. This cleans those
        calls, marking them as "ended_unexpectedly". To be called by a cron.

        See SUSPICIOUS_OLD_IN_PROGRESS_CALLS.
        """
        now = fields.Datetime.now()
        stuck_calling = (
            Domain("state", "=", "calling")
            & Domain("create_date", "<", now - CALLING_CALL_TIMEOUT)
        )
        stuck_ongoing = (
            Domain("state", "=", "ongoing")
            & Domain("effective_start_date", "<", now - ONGOING_CALL_TIMEOUT)
        )
        stuck_calls = self.env["voip.call"].search(stuck_calling | stuck_ongoing)
        if stuck_calls:
            stuck_calls.state = "ended_unexpectedly"

    def _store_voip_fields(self, res: Store.FieldList):
        res.one("activity_id", "_store_voip_fields")
        res.one("country_id", "_store_voip_fields")
        res.extend(["create_date", "direction", "display_name", "duration", "has_recording"])
        res.one("partner_id", "_store_voip_fields")
        res.one("phone_country_id", "_store_voip_fields")
        res.extend(["phone_number", "phone_number_formatted", "start_date", "state"])

    def _notify_devices(self):
        """Send a web-push update for an incoming call state change.

        Only incoming calls tracked by a PBX conversation are eligible. The
        payload is consumed by the VoIP service worker, which can display a
        notification for actionable states or use it to update or clear an
        existing one for the others.
        """
        self.ensure_one()
        if self.direction != "incoming" or not self.conversation_id:
            return

        base_url = self.env["ir.config_parameter"].sudo().get_str("web.base.url")
        icon = (
            f"{base_url}/web/image/res.partner/{self.partner_id.id}/avatar_128?access_token={self.partner_id._get_avatar_128_access_token()}"
            if self.partner_id
            else f"{base_url}/web/static/img/odoo-icon-192x192.png"
        )

        actions = None
        if self.state == "calling":
            actions = [
                {
                    "action": "VOIP:ANSWER_INCOMING_CALL",
                    "title": self.env._("Answer"),
                },
                {
                    "action": "VOIP:DECLINE_INCOMING_CALL",
                    "title": self.env._("Decline"),
                },
            ]
        elif self.state == "missed":
            actions = [
                {
                    "action": "VOIP:CALL_BACK_MISSED_CALL",
                    "title": self.env._("Call Back"),
                },
            ]

        data = {
            "author_name": self.partner_id.display_name if self.partner_id else self.phone_number,
            "model": "voip.call",
            "res_id": self.id,
            "call_state": self.state,
            "call_phone_number": self.phone_number,
            # The browser matches the notification action to its local INVITE
            # by control handle, the key it builds from the INVITE itself — so
            # the match holds even before this browser's own SIP leg is recorded
            # server-side.
            "control_handle": self.control_handle,
            "type": "VOIP:CALL_NOTIFICATION",
        }

        scenario = "incoming-call"  # https://github.com/MicrosoftEdge/MSEdgeExplainers/blob/main/Notifications/notifications_actions_customization.md
        self._notify_devices_send(data, actions, icon, scenario)

    def _decline_via_pbx(self):
        """Decline this incoming call in the PBX, for this member alone.

        Hangs up the member's own ringing legs. A push-only member has none, and
        the push names no leg of theirs — on a direct call it names the caller's
        — so the PBX resolves the ring leg from the conversation and the user.
        """
        self.ensure_one()
        self.check_access("read")
        call_sudo = self.sudo()
        api = PhoneServiceAPI(call_sudo.env)
        handles = [
            leg.pbx_call_id
            for leg in call_sudo.leg_ids
            if leg.pbx_call_id and not leg.ended_at
        ]
        if handles:
            for call_id in handles:
                api.hangup_call(call_id)
        elif call_sudo.conversation_id and call_sudo.user_id.voip_pbx_user_uuid:
            api.decline_call(
                call_sudo.conversation_id.conversation_identifier,
                call_sudo.user_id.voip_pbx_user_uuid,
            )

    def _notify_devices_send(self, data, actions, icon, scenario):
        self.ensure_one()
        devices, private_key, public_key = self._web_push_get_partners_parameters(self.user_id.partner_id.ids)
        if not devices:
            return

        payload = {
            "title": self.display_name,
            "options": {
                "vibrate": [100, 50, 100],
                "data": data,
                "icon": icon,
            },
        }
        if actions:
            payload["options"]["actions"] = actions
        if scenario:
            payload["options"]["scenario"] = scenario

        self._web_push_send_notification(devices, private_key, public_key, payload=payload, force_direct_send=True)

    def _phone_get_number_fields(self):
        return ["phone_number"]

    def _sync_has_active_call(self, excluded_call_ids=None, users=None):
        """Synchronizes ``has_active_call`` for users linked to calls.

        This helper is normally called automatically when call events change
        whether a user has an active call.
        """
        users = users or self.user_id
        if not users:
            return

        now = fields.Datetime.now()
        fresh_outgoing_calling = (
            # Note that incoming calling is not considered an active call, until
            # the callee accepts.
            Domain("state", "=", "calling")
            & Domain("direction", "=", "outgoing")
            & Domain("create_date", ">=", now - CALLING_CALL_TIMEOUT)
        )
        fresh_ongoing = (
            Domain("state", "=", "ongoing")
            & Domain("effective_start_date", ">=", now - ONGOING_CALL_TIMEOUT)
        )
        # Note that at the moment the presence is not updated if the "freshness"
        # expires and that the call is "stuck" in calling/ongoing. It will only
        # be refreshed on the next call of the user (or via the stuck calls
        # cron once a month). Hopefully "stuck" call records will become
        # unlikely in the future.
        domain = Domain("user_id", "in", users.ids) & (fresh_outgoing_calling | fresh_ongoing)
        if excluded_call_ids:
            domain &= Domain("id", "not in", excluded_call_ids)
        active_users = self.env["voip.call"].sudo().search(domain).user_id.sudo(False)

        stores = Store.Stores()
        for user in users:
            has_active_call = user in active_users
            if user.has_active_call == has_active_call:
                continue
            user.sudo().has_active_call = has_active_call
            stores[user, "presence"].add(user, "_store_has_active_call_fields")
