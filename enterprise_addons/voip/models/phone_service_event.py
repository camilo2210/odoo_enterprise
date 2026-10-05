import functools
import logging
import time
from datetime import datetime, timedelta, UTC

from psycopg2.errors import UniqueViolation

from odoo import api, fields, models
from odoo.api import Environment
from odoo.exceptions import ConcurrencyError
from odoo.http import Response
from odoo.modules.registry import Registry
from odoo.sql_db import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY

from odoo.addons.voip.models.utils import is_valid_uuid4, normalize_caller_number, same_number
from odoo.addons.voip.models.voip_call import LIVE_CALL_STATES, TERMINAL_CALL_STATES

_logger = logging.getLogger(__name__)

CALL_EVENTS = (
    "call_created",
    "call_answered",
    "call_updated",
    "call_ended",
)

PUSH_EVENTS = (
    "odoo_call_push_notification",
    "odoo_call_cancel_push_notification",
)

VOICEMAIL_EVENTS = (
    "global_voicemail_message_created",
    "user_voicemail_message_created",
)

HANDLED_EVENTS = (
    *CALL_EVENTS,
    *PUSH_EVENTS,
    *VOICEMAIL_EVENTS,
    "phone_number_status",
    "advanced_order_status",
    "advanced_order_comment",
    "requirement_group_status",
    "call_cost",
)

EVENT_RETENTION = timedelta(hours=12)

HANGUP_CAUSE_USER_BUSY = 17
HANGUP_CAUSE_CALL_REJECTED = 21
HANGUP_CAUSE_ANSWERED_ELSEWHERE = 26

DISPOSITION_BY_HANGUP_CAUSE = {
    HANGUP_CAUSE_USER_BUSY: "busy",
    HANGUP_CAUSE_CALL_REJECTED: "rejected",
    HANGUP_CAUSE_ANSWERED_ELSEWHERE: "completed_elsewhere",
}

MAX_EVENT_PROCESS_RETRIES = 5
EVENT_PROCESS_RETRY_DELAY = 0.1


def _notify_event_not_processed(registry, uid, event_id):
    with registry.cursor() as cr:
        env = Environment(cr, uid, {})
        event = env["voip.phone.service.event"].browse(event_id).sudo()
        user = event._get_user_from_pbx_call_event(event.payload)
        if user:
            user.partner_id._bus_send(
                "voip.call/event_not_processed",
                {"id": event.id, "from": event._get_display_phone_number_from_pbx_call_event(event.payload)})


def _process_event_after_response(dbname, uid, event_id):
    registry = Registry(dbname)
    for attempt in range(1, MAX_EVENT_PROCESS_RETRIES + 1):
        try:
            with registry.cursor() as cr:
                env = Environment(cr, uid, {})
                event = env["voip.phone.service.event"].browse(event_id).sudo()
                try:
                    event._process_event()
                except (*PG_CONCURRENCY_EXCEPTIONS_TO_RETRY, ConcurrencyError):
                    raise
                except Exception:
                    cr.rollback()  # nosemgrep: commit-in-models
                    _logger.exception("Processing of phone service event %s failed.", event_id)
                    _notify_event_not_processed(registry, uid, event_id)
            return
        except (*PG_CONCURRENCY_EXCEPTIONS_TO_RETRY, ConcurrencyError):
            if attempt == MAX_EVENT_PROCESS_RETRIES:
                _logger.warning(
                    "Concurrent processing failed for phone service event %s after %s attempts.",
                    event_id, MAX_EVENT_PROCESS_RETRIES, exc_info=True)
                _notify_event_not_processed(registry, uid, event_id)
                return
            time.sleep(EVENT_PROCESS_RETRY_DELAY)


class VoipPhoneServiceEvent(models.Model):
    _name = "voip.phone.service.event"
    _description = "VoIP Phone Service Event"
    _rec_name = "event_id"

    event_id = fields.Char(required=True, readonly=True)
    event_type = fields.Char(required=True, readonly=True)
    payload = fields.Json(readonly=True)
    occurred_at = fields.Datetime(readonly=True)

    _unique_event_id = models.UniqueIndex(
        "(event_id)", message="A phone service event is processed only once.")

    @api.model
    def _ack_then_process(self, request_data, request_db, uid):
        event = self._register_event(
            request_data["id"], request_data["event_type"], request_data["payload"],
            self._parse_naive_utc(request_data["occurred_at"]))
        res = Response(status=200)
        if event:
            res.call_on_close(functools.partial(_process_event_after_response, request_db, uid, event.id))
        return res

    @api.model
    def _register_event(self, event_id, event_type, payload, occurred_at):
        """Persist the event once and return the new record, empty if already seen.

        The phone service forwards upstream redeliveries and our own request retries replay them, so the
        same event reaches us several times. The unique index on ``event_id`` is
        the race-safe guard: the pre-check drops the common duplicate cheaply,
        and a concurrent insert that slips past it surfaces as a UniqueViolation
        that we also read as "already seen".
        """
        if self.sudo().search_count([("event_id", "=", event_id)]):
            return self.browse()
        try:
            with self.env.cr.savepoint():
                return self.sudo().create({
                    "event_id": event_id,
                    "event_type": event_type,
                    "payload": payload,
                    "occurred_at": occurred_at,
                })
        except UniqueViolation:
            return self.browse()

    @api.model
    def _parse_naive_utc(self, timestamp):
        """Return an ISO 8601 timestamp as the naive UTC datetime Odoo stores."""
        return datetime.fromisoformat(timestamp).astimezone(UTC).replace(tzinfo=None)

    @api.autovacuum
    def _gc_processed_events(self):
        threshold = fields.Datetime.now() - EVENT_RETENTION
        self.sudo().search([("create_date", "<", threshold)]).unlink()

    def _process_event(self):
        self.ensure_one()
        match self.event_type:
            case "call_created":
                self._handle_call_created()
            case "call_answered":
                self._handle_call_answered()
            case "call_ended":
                self._handle_call_ended()
            case "call_updated":
                self._handle_call_updated()
            case "odoo_call_push_notification":
                self._handle_odoo_call_push_notification()
            case "odoo_call_cancel_push_notification":
                self._handle_odoo_call_cancel_push_notification()
            case "global_voicemail_message_created":
                self._handle_global_voicemail_message_created()
            case "user_voicemail_message_created":
                self._handle_user_voicemail_message_created()
            case "phone_number_status":
                self._handle_phone_number_status()
            case "advanced_order_status":
                self._handle_advanced_order_status()
            case "advanced_order_comment":
                self._handle_advanced_order_comment()
            case "requirement_group_status":
                self._handle_requirement_group_status()
            case "call_cost":
                self._handle_call_cost()

    def _handle_call_created(self):
        _conversation, call, _leg = self._ensure_call_records(
            self.payload, "call_created", self.occurred_at)
        if call:
            call._notify_devices()

    def _handle_call_answered(self):
        conversation, _call, leg = self._ensure_call_records(
            self.payload, "call_answered", self.occurred_at)
        if not self._is_unbridged_trunk_answer(self.payload):
            self._apply_answered(
                self._resolve_state_target(self.payload, conversation, leg), self.occurred_at)

    def _handle_call_ended(self):
        conversation, _call, leg = self._ensure_call_records(
            self.payload, "call_ended", self.occurred_at)
        self._apply_ended(
            self._resolve_state_target(self.payload, conversation, leg),
            self.payload,
            self.occurred_at,
            leg,
        )

    def _handle_call_updated(self):
        """Refresh an ongoing call's interlocutor when its connected line changes.

        A browser-driven attended transfer is a SIP REFER, which produces no
        transfer event: the only PBX signal that the user now talks to someone
        else is a ``call_updated`` on the user's own leg carrying the new
        connected line. Trunk legs are ignored — their connected line transits
        through placeholder values while the transfer completes.
        """
        payload = self.payload
        if not payload.get("user_uuid"):
            return
        call = self._find_call(payload.get("conversation_id"), payload.get("sip_call_id"))
        if not call or call.state != "ongoing":
            return
        number = payload.get("peer_caller_id_number")
        if not number or is_valid_uuid4(number):
            return
        number = self.env["voip.call"]._resolve_incoming_caller_number(number)
        if same_number(number, call.phone_number):
            # The same party in another format is not a new interlocutor;
            # rewriting it would drop the partner and activity the browser
            # resolved when it placed the call.
            return
        call.write({"phone_number": number, "partner_id": False})
        call.get_contact_info()
        self._notify_call_update(call)

    def _handle_odoo_call_push_notification(self):
        payload = self.payload
        call = self._ensure_pushed_call(payload)
        if not call:
            _logger.warning(
                "Ignoring PBX call push event %s without matching call", self.event_id)
            return
        if call.state != "calling":
            return
        # The push describes the channel that raised Pushmobile, not this
        # member: on a direct call that is the caller's own channel, and its SIP
        # Call-ID belongs to the caller's INVITE. Recording it as a leg of this
        # call would make the caller's Call-ID resolve to the callee's call, so
        # only the wakeup handle is kept — the one thing to hang up on while the
        # softphone is unregistered.
        call.wakeup_pbx_call_id = payload["call_id"]
        if not self._has_ring_window_elapsed(payload):
            call._notify_devices()

    def _handle_odoo_call_cancel_push_notification(self):
        payload = self.payload
        call = self._find_pushed_call(payload)
        if not call or call.state != "calling":
            return
        if self._has_pending_pbx_leg(call):
            return
        if self._is_answered_elsewhere(call):
            call.complete_call_elsewhere()
        else:
            call.miss_call()
        call._notify_devices()
        self._notify_call_update(call, with_missed_count=call.state == "missed")

    def _handle_global_voicemail_message_created(self):
        self.env["voip.voicemail.message"]._handle_message_created_event(
            self.event_id, self.payload, self.occurred_at)

    def _handle_user_voicemail_message_created(self):
        self.env["voip.voicemail.message"]._handle_message_created_event(
            self.event_id, self.payload, self.occurred_at)

    def _handle_phone_number_status(self):
        self.env["voip.did.number"]._handle_status_event(self.payload)

    def _handle_advanced_order_status(self):
        self.env["voip.did.number.request"]._handle_status_event(self.payload)

    def _handle_advanced_order_comment(self):
        self.env["voip.did.number.request"]._handle_comment_event(self.payload)

    def _handle_requirement_group_status(self):
        self.env["voip.requirement.group"]._handle_status_event(self.payload)

    def _handle_call_cost(self):
        self.env["voip.call.cost.line"]._handle_call_cost_event(
            self.event_id, self.payload, self.occurred_at)

    @api.model
    def _has_pending_pbx_leg(self, call):
        """Whether a PBX channel of this call still owes its own hangup event.

        The cancel only says the member stopped ringing: a group ring emits one
        whether nobody picked up or a colleague did. The member's own
        ``call_ended`` is what carries the verdict, so a member with a live PBX
        channel is settled by that event rather than by this guess — which,
        processed concurrently with the winner's answer, reads it as absent and
        lands on "missed". A member reached by push alone owns no PBX channel,
        so there the cancel stays the settling signal.
        """
        return any(leg.pbx_call_id and not leg.ended_at for leg in call.leg_ids)

    @api.model
    def _has_ring_window_elapsed(self, payload):
        """Whether the PBX has already stopped ringing for this push.

        webhookd redelivers failed webhooks with backoff, so a push can arrive
        minutes after the ring it announces; ringing the devices then would
        offer a call that can no longer be answered. The matched or
        bootstrapped call is kept so the (equally late) cancel can still
        settle it as missed.
        """
        ring_end = self._parse_naive_utc(
            payload["mobile_wakeup_timestamp"],
        ) + timedelta(seconds=int(payload["ring_timeout"]))
        return fields.Datetime.now() > ring_end

    @api.model
    def _ensure_pushed_call(self, payload):
        """Find-or-create the incoming call a push refers to.

        A live call is reused when one of its keys resolves; otherwise it is
        bootstrapped from the push.

        A logged-out user's softphone is unregistered, so Wazo dials no callee
        leg and no user-facing call exists — yet the push is the signal to ring
        the browser anyway. The enriched push carries the target user_uuid and
        conversation_id, which is all ``_ensure_user_call`` needs to build it.

        A logged-in user's browser may instead have created the call from the
        INVITE already. That INVITE carries X-Odoo-Conversation-Id (the
        wazo-calld-odoo-push plugin stamps it on the dial_mobile dial), so the
        call is keyed by the conversation id and ``_find_pushed_call`` above
        already matched it.
        """
        call = self._find_pushed_call(payload)
        if call:
            return call
        if not (payload.get("user_uuid") and payload.get("conversation_id")):
            return self.env["voip.call"].browse()
        conversation = self._ensure_conversation(payload)
        # Bootstrapped without the payload's Call-ID: it is the caller's, and a
        # leg carrying it would put the caller's INVITE on the callee's call.
        return self._ensure_user_call(dict(payload, sip_call_id=""), conversation)

    @api.model
    def _find_pushed_call(self, payload):
        """Resolve the call a PBX push event refers to.

        Only the enriched pair (user_uuid, conversation_id) identifies it. The
        payload's own SIP Call-ID belongs to the channel that raised Pushmobile,
        which on a direct call is the caller's (captured 2026-07-23) and never
        the woken member's, so resolving through it binds a member's push to
        somebody else's call.
        """
        user_uuid = payload.get("user_uuid")
        conversation_id = payload.get("conversation_id")
        if not (user_uuid and conversation_id):
            return self.env["voip.call"]
        user = self.env["res.users"]._get_from_pbx_user_uuid(user_uuid)
        if not user:
            return self.env["voip.call"]
        return self.env["voip.call"].sudo().search([
            ("conversation_id.conversation_identifier", "=", conversation_id),
            ("user_id", "=", user.id),
            ("direction", "=", "incoming"),
            ("state", "in", LIVE_CALL_STATES),
        ], limit=1)

    @api.model
    def _ensure_call_records(self, payload, event_type, occurred_at):
        """Find-or-create the {conversation, user call, leg} records this call event touches.

        An event for any leg (or the browser INVITE) may arrive in any order, so
        every lifecycle handler ensures the full trio exists before applying its
        state effect.
        """
        conversation = self._ensure_conversation(payload)
        call = self._ensure_user_call(payload, conversation)
        leg = self._ensure_leg(payload, conversation, call, event_type, occurred_at)
        return conversation, call, leg

    @api.model
    def _ensure_conversation(self, payload):
        return self.env["voip.conversation"]._get_or_create(payload["conversation_id"])

    @api.model
    def _ensure_user_call(self, payload, conversation):
        """Find-or-create the user-facing call this leg belongs to.

        Only a softphone endpoint leg owns a call; the inbound trunk/source leg
        builds the conversation and its own leg but never a user-facing call — that
        is created by the user legs and the browser INVITE, which converge
        through ``get_or_create``. A callee leg owns an incoming call, a caller
        leg the outgoing call of the user who dialed — the only record a call
        placed from a native SIP phone ever gets, since no browser saw it.

        A PBX payload always carries the conversation id and the browser
        INVITE's Call-ID, so it matches on an exact key and never falls back to
        the fuzzy number-and-recency match.
        """
        if self._is_inbound_external_leg(payload):
            return self.env["voip.call"].browse()
        user = self._get_user_from_pbx_call_event(payload)
        if not user:
            # A leg naming a recipient we cannot resolve is worth a warning; a
            # bare state-only payload (answered/hangup) is resolved via its leg.
            if payload.get("user_uuid") or payload.get("dialed_extension"):
                _logger.warning(
                    "Ignoring PBX call event for conversation %s without Odoo softphone recipient",
                    payload.get("conversation_id"),
                )
            return self.env["voip.call"].browse()
        VoipCall = self.env["voip.call"].with_user(user)
        direction = self._get_direction_from_pbx_call_event(payload)
        phone_number = self._get_display_phone_number_from_pbx_call_event(payload)
        call_sudo = self.env["voip.call"].sudo().search([
            ("conversation_id", "=", conversation.id),
            ("user_id", "=", user.id),
            ("direction", "=", direction),
            ("state", "in", LIVE_CALL_STATES),
        ], limit=1)
        if not call_sudo:
            try:
                call_data = VoipCall.get_or_create({
                    "direction": direction,
                    "phone_number": phone_number,
                    "conversation_identifier": payload["conversation_id"],
                    "sip_call_id": payload["sip_call_id"],
                    "skip_recent_pending_match": True,
                })
            except UniqueViolation as e:
                # Another leg of this conversation created the call between our
                # search and our insert; the retry sees it.
                raise ConcurrencyError() from e
            call_sudo = VoipCall.browse(call_data["ids"][0]).sudo()
        # The display number can only be refined while the call is ringing, and
        # never from a leg Wazo reclassified as internal on hangup: it swaps
        # caller and peer, so the reversal that reads a ringing leg correctly
        # reads a reclassified one backwards and settles the callee's own
        # extension. Ringing alone did not protect it - when two devices ring,
        # the losing leg is reclassified and ends before the other answers, so
        # the call is still "calling" when its number gets overwritten. An
        # outgoing call is never refined at all: the browser already stored the
        # number it resolved, which the raw dialed digits must not overwrite.
        reclassified = payload.get("direction") == "internal"
        if (
            direction == "incoming"
            and not reclassified
            and call_sudo.state == "calling"
            and call_sudo.phone_number != phone_number
        ):
            call_sudo.phone_number = phone_number
        if not call_sudo.conversation_id:
            # A call the browser created before this conversation existed.
            call_sudo.conversation_id = conversation
        call_sudo._add_sip_call_id(payload["sip_call_id"])
        return call_sudo

    @api.model
    def _ensure_leg(self, payload, conversation, call, event_type, occurred_at):
        """Upsert the leg for this SIP Call-ID and stamp its lifecycle timing.

        Reconciles onto a leg an earlier INVITE (browser stub) or webhook may
        already have created, keyed by Call-ID then by ``(conversation, pbx_call_id)``,
        so one physical leg never splits into two rows. Endpoint fields are
        (re)resolved only on creation or on the rich ``call_created`` event, so
        a timing-only answered/hangup stamp never clobbers them.
        """
        Leg = self.env["voip.call.leg"].sudo()
        sip_call_id = payload.get("sip_call_id")
        pbx_call_id = payload.get("call_id")
        leg = Leg.search([("sip_call_id", "=", sip_call_id)], limit=1) if sip_call_id else Leg.browse()
        if not leg and pbx_call_id:
            leg = Leg.search(
                [("conversation_id", "=", conversation.id), ("pbx_call_id", "=", pbx_call_id)], limit=1)
        if not leg and not pbx_call_id:
            # Not enough to key a new leg (bare state-only payload); reconcile only.
            return leg
        values = {"conversation_id": conversation.id}
        if event_type == "call_created" or not leg:
            values.update(self._resolve_leg_endpoint(payload, conversation, call))
        elif call and not leg.voip_call_id:
            values["voip_call_id"] = call.id
        if pbx_call_id:
            values["pbx_call_id"] = pbx_call_id
        if event_type == "call_answered":
            values["answered_at"] = occurred_at
        elif event_type == "call_ended":
            values["ended_at"] = occurred_at
        if leg:
            leg.write(values)
            return leg
        try:
            return Leg.create(values)
        except UniqueViolation as e:
            raise ConcurrencyError() from e

    @api.model
    def _resolve_leg_endpoint(self, payload, conversation, call=None):
        """Resolve which endpoint this leg is, and which call it folds into.

        A user's own caller leg is a "source" like the inbound trunk leg — both
        are the endpoint that opened the conversation — and that is what keeps
        ``_is_answered_elsewhere`` and ``_is_answered_on_another_device``
        correct: they read an answered *participant* leg as proof a device
        picked up, and on an internal call the caller's leg lives in the same
        conversation as the callee's. Unlike the trunk leg, it does fold into a
        call: the outgoing call of the user who dialed.
        """
        values = {"sip_call_id": payload.get("sip_call_id") or None}
        if self._is_inbound_external_leg(payload):
            values["role"] = "source"
            return values
        if not (self._is_user_caller_leg(payload) or self._is_user_callee_leg(payload)):
            values["role"] = "routing"
            return values
        values["role"] = "source" if self._is_user_caller_leg(payload) else "participant"
        target = call or self._find_user_call(payload, conversation)
        if target:
            values["voip_call_id"] = target.id
        return values

    @api.model
    def _find_user_call(self, payload, conversation):
        user = self.env["res.users"]._get_from_pbx_user_uuid(payload["user_uuid"])
        return self.env["voip.call"].sudo().search([
            ("conversation_id", "=", conversation.id),
            ("user_id", "=", user.id),
            ("direction", "=", self._get_direction_from_pbx_call_event(payload)),
        ], limit=1)

    @api.model
    def _resolve_state_target(self, payload, conversation, leg):
        """Return the call(s) a state transition (answered/hangup) applies to.

        A user leg drives its own call directly. The trunk/source leg owns no
        call, so it drives the conversation's call only when it fans out to a
        single softphone — never across a group/queue, where each member's own
        leg carries its outcome.
        """
        if leg.voip_call_id:
            return leg.voip_call_id
        if self._is_inbound_external_leg(payload) and len(conversation.call_ids) == 1:
            # The trunk leg owns no call; drive the conversation's sole softphone
            # call. Any state is eligible: a late bridged trunk answer recovers a
            # call the device leg tentatively rejected (rejected->ongoing), while
            # start_call on an already-terminated call is a safe no-op.
            return conversation.call_ids
        return self._find_call(payload.get("conversation_id"), payload.get("sip_call_id"))

    @api.model
    def _apply_answered(self, calls, occurred_at):
        for call in calls:
            if call.state == "ongoing":
                continue
            if not call.start_call(at=occurred_at)["success"]:
                continue
            call._notify_devices()
            self._notify_call_update(call)
            if call.direction == "incoming":
                # The caller's own leg answering says nothing about whether a
                # peer's ring was lost; it is the callee picking up.
                self._complete_ringing_peers(call)

    @api.model
    def _complete_ringing_peers(self, call):
        """Settle the other members of a group ring the moment one picks up.

        Left to themselves, the losers each infer the winner's answer from a
        concurrent transaction their snapshot cannot see, and a member reached
        by push alone owns no PBX channel, so no later event ever corrects it:
        that member settles "missed" and shows a missed-call notification for a
        call a colleague took. The answering transaction is the one that holds
        the fact, so it writes it to every peer instead.

        A peer already settled "missed" by its own cancel racing this answer is
        revised here — within one conversation there is one ring, so an answer
        anywhere means no one else missed anything.

        A peer still owing a hangup on its own PBX channel is left alone: that
        event carries what the member actually did, and declining is its own
        outcome that a colleague's answer must not overwrite.
        """
        if not call.conversation_id:
            return
        peers = self.env["voip.call"].sudo().search([
            ("conversation_id", "=", call.conversation_id.id),
            ("id", "!=", call.id),
            ("direction", "=", "incoming"),
            ("state", "in", ("calling", "missed")),
        ])
        for peer in peers:
            if self._has_pending_pbx_leg(peer):
                continue
            was_missed = peer.state == "missed"
            if not peer.complete_call_elsewhere()["success"]:
                continue
            peer._notify_devices()
            self._notify_call_update(peer, with_missed_count=was_missed)

    @api.model
    def _apply_ended(self, calls, payload, occurred_at, leg):
        disposition = self._hangup_disposition(payload)
        for call in calls:
            if call.state in TERMINAL_CALL_STATES:
                continue
            if disposition != "answered" and self._is_answered_on_another_device(call, leg):
                continue
            if call.direction == "outgoing":
                self._end_outgoing_call(call, disposition, occurred_at)
            else:
                self._end_incoming_call(call, payload, disposition, occurred_at)
            call._notify_devices()
            self._notify_call_update(call, with_missed_count=call.state == "missed")

    @api.model
    def _end_outgoing_call(self, call, disposition, occurred_at):
        """Settle the call of the user who dialed.

        A caller never "misses" their own call, and 'missed' is not even a legal
        outgoing state: a callee who does not pick up aborts it, and a busy or
        declined one rejects it. Asterisk propagates the far-end cause onto the
        caller channel, so this leg's own reason code carries the callee's
        verdict and the outbound trunk leg is never needed.
        """
        if call.state == "ongoing" or disposition == "answered":
            call.end_call(at=occurred_at)
        elif disposition in ("rejected", "busy"):
            call.reject_call()
        else:
            call.abort_call()

    @api.model
    def _end_incoming_call(self, call, payload, disposition, occurred_at):
        if call.state == "ongoing" or (
            disposition == "answered" and not self._is_inbound_external_leg(payload)
        ):
            # Once answered the only legal terminal is 'terminated': a later
            # reason-21 leg hangup can neither downgrade nor strand the call.
            # A trunk leg's own answer_time proves no pickup, though: the PBX
            # answers the trunk itself (unbridged) to run reject/no-answer
            # fallbacks, and call_ended strips the bridge info that tells a
            # real answer apart — a truly answered call is already 'ongoing'
            # through the bridged call_answered by the time its trunk ends.
            call.end_call(at=occurred_at)
        elif disposition in ("rejected", "busy"):
            call.reject_call()
        elif disposition == "completed_elsewhere" or self._is_answered_elsewhere(call):
            call.complete_call_elsewhere()
        else:
            call.miss_call()

    @api.model
    def _hangup_disposition(self, payload):
        if payload["answer_time"]:
            return "answered"
        return DISPOSITION_BY_HANGUP_CAUSE.get(payload["reason_code"], "missed")

    @api.model
    def _is_answered_on_another_device(self, call, leg):
        """Whether the call's user picked up on another leg of the same call.

        A user ringing on several devices gets one leg per device, all folded
        into one call. When one device answers, Wazo clears the losing devices
        with plain normal clearing (cause 16) an instant later: such a hangup
        describes the losing device only, not the call, which lives on through
        the answered leg. Role filters out the trunk source leg, which Wazo
        answers itself (unbridged) to run no-answer fallbacks.
        """
        return bool(self.env["voip.call.leg"].sudo().search_count([
            ("voip_call_id", "=", call.id),
            ("id", "!=", leg.id),
            ("role", "=", "participant"),
            ("answered_at", "!=", False),
            ("ended_at", "=", False),
        ], limit=1))

    @api.model
    def _is_answered_elsewhere(self, call):
        """Whether another member of the call's conversation picked up.

        Wazo hangs up the losing members of a group ring with plain normal
        clearing (cause 16), never answered-elsewhere (cause 26), so their
        disposition reads "missed". The winner's answer is forwarded before the
        losers' hangups: an answered participant leg on another call of the
        same conversation is the signal that tells them apart. Role filters out
        the trunk source leg, which Wazo answers itself (unbridged) to run
        no-answer fallbacks.
        """
        if not call.conversation_id:
            return False
        return bool(self.env["voip.call.leg"].sudo().search_count([
            ("conversation_id", "=", call.conversation_id.id),
            ("voip_call_id", "!=", call.id),
            ("role", "=", "participant"),
            ("answered_at", "!=", False),
        ], limit=1))

    @api.model
    def _find_call(self, conversation_id, sip_call_id):
        if not conversation_id or not sip_call_id:
            return self.env["voip.call"]
        leg = self.env["voip.call.leg"].sudo().search([
            ("conversation_id.conversation_identifier", "=", conversation_id),
            ("sip_call_id", "=", sip_call_id),
        ], limit=1)
        return leg.voip_call_id

    @api.model
    def _notify_call_update(self, call, with_missed_count=False):
        if not call.user_id:
            return
        payload = {"store_data": call._get_store_data()}
        if with_missed_count:
            payload["missedCalls"] = (
                self.env["voip.call"].with_user(call.user_id)._get_number_of_missed_calls()
            )
        call.user_id._bus_send("voip.call/update", payload)

    @api.model
    def _is_inbound_external_leg(self, payload):
        return not payload.get("user_uuid") and (
            payload.get("direction") == "inbound" or bool(payload.get("is_caller")))

    @api.model
    def _is_unbridged_trunk_answer(self, payload):
        """An answered trunk leg bridged to nothing is the PBX itself answering
        the caller to run a reject/no-answer fallback (announcement, voicemail),
        not a user picking up: only a bridge proves a device answered.
        """
        return (
            self._is_inbound_external_leg(payload)
            and not payload.get("talking_to")
            and not payload.get("bridges")
        )

    @api.model
    def _is_user_callee_leg(self, payload):
        return bool(payload.get("user_uuid")) and not payload.get("is_caller")

    @api.model
    def _is_user_caller_leg(self, payload):
        """The leg of the user who placed the call.

        Wazo reclassifies a leg's direction to "internal" on hangup, so
        ``is_caller`` is the only field that identifies it for the whole
        lifecycle.
        """
        return bool(payload.get("user_uuid")) and bool(payload.get("is_caller"))

    @api.model
    def _get_direction_from_pbx_call_event(self, payload):
        return "outgoing" if self._is_user_caller_leg(payload) else "incoming"

    @api.model
    def _get_user_from_pbx_call_event(self, payload):
        if self._is_user_caller_leg(payload):
            # On a caller leg the remote party is who was dialed, so the leg
            # owner is the user whose call this is.
            return self.env["res.users"]._get_from_pbx_user_uuid(payload["user_uuid"])
        if self._is_user_callee_leg(payload):
            user = self.env["res.users"]._get_from_pbx_user_uuid(payload["user_uuid"])
            if user:
                return user
        direction = payload.get("direction")
        if direction == "internal" and payload.get("dialed_extension"):
            return self.env["voip.extension"]._get_user_from_number(payload["dialed_extension"])
        if direction == "inbound" and payload.get("dialed_extension"):
            user = self.env["voip.did.number"]._get_from_number(payload["dialed_extension"]).user_id
            if user.sudo().voip_pbx_user_uuid:
                return user
        return self.env["res.users"]

    @api.model
    def _get_internal_caller_extension_number(self, payload, target_extension_number):
        domain = [
            ("voip_username", "in", [
                number
                for number in (payload.get("caller_id_number"), payload.get("peer_caller_id_number"))
                if number
            ]),
        ]
        if payload.get("user_uuid"):
            # On callee legs Wazo fills caller_id_* with the leg owner's own
            # identity; the owner can never be the remote party.
            leg_owner = self.env["res.users"]._get_from_pbx_user_uuid(payload["user_uuid"])
            domain.append(("user_id", "not in", leg_owner.ids))
        settings = self.env["res.users.settings"].sudo().search(domain, limit=1)
        if not settings:
            return None
        extension = settings.user_id.routing_extension_id
        return extension.number if extension.number != target_extension_number else None

    @api.model
    def _get_display_phone_number_from_pbx_call_event(self, payload):
        if self._is_user_caller_leg(payload):
            # What the user dialed, whether it stayed inside the PBX or went out
            # the trunk. Ahead of the direction branches below, which read the
            # caller id fields the wrong way round on this leg.
            return normalize_caller_number(
                payload.get("dialed_extension") or payload.get("peer_caller_id_number"))
        if payload.get("direction") == "internal":
            target_extension_number = payload.get("dialed_extension")
            candidates = [payload.get("caller_id_number"), payload.get("peer_caller_id_number")]
            if self._is_user_callee_leg(payload):
                candidates.reverse()
            return (
                self._get_internal_caller_extension_number(payload, target_extension_number)
                or normalize_caller_number(next(
                    (c for c in candidates
                     if c and c != target_extension_number and not is_valid_uuid4(c)),
                    None,
                ))
                or target_extension_number
            )
        if payload.get("direction") == "inbound":
            dialed_extension = payload.get("dialed_extension")
            candidates = [payload.get("caller_id_number"), payload.get("peer_caller_id_number")]
            if self._is_user_callee_leg(payload):
                candidates.reverse()
            number = next(
                (c for c in candidates
                 if c and c != dialed_extension and not is_valid_uuid4(c)),
                candidates[0] or candidates[1],
            )
            return normalize_caller_number(number)
        return normalize_caller_number(
            payload.get("peer_caller_id_number") or payload.get("caller_id_number"))
