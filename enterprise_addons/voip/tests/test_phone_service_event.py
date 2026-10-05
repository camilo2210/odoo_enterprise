"""What a phone-service event stream does to a call, scenario by scenario.

A scenario is one call as the people in it live it: who was rung, how many Odoo
tabs the callee had open, and how the call ended. The tables below enumerate
them and name the test that encodes each one.

The tab count is what decides who can act. With none, the softphone is
unregistered: Wazo dials no SIP leg, the push notification is the only channel
to the user, and its action buttons the only way to answer or decline. With
one, the browser holds the INVITE and acts on it locally. With two, both are
registered, the call folds their legs together, and the tab that loses must
still be settled.

    -    no test encodes this scenario
    n/a  cannot happen (no registered softphone to act in)
    name the test below that encodes it, verified against a captured call

A cell carries a name only once the scenario has been replayed on the dev PBX
and the test asserts what that capture actually shows — the stream fixtures
this suite is built on are only as true as the calls they were read from.

Call to one user, on their extension or their DID

    how it ended                       0 tabs    1 tab     2 tabs
    answered in the tab                n/a       -         -
    answered from the notification     -         -         -
    declined in the tab                n/a       -         -
    declined from the notification     logged_out_user_    -         -
                                       declines_a_direct_call
    nobody answers, the ring times out -         -         -
    the caller gives up first          -         -         -

Call to a call group: every member rings, exactly one outcome each

    how it ended for this member       0 tabs    1 tab     2 tabs
    answered in the tab                n/a       -         -
    answered from the notification     -         -         -
    declined in the tab                n/a       -         -
    declined from the notification     -         -         -
    a colleague answered first         one_member_answers_ -         -
                                       the_loser_is_logged_out
    nobody answers, the ring times out -         -         -
    the caller gives up first          -         -         -

Call to a call queue: same outcomes, but the queue answers the caller itself
before distributing, so the trunk carries an answer that proves nothing

    how it ended for this agent        0 tabs    1 tab     2 tabs
    answered in the tab                n/a       -         -
    answered from the notification     -         -         -
    declined in the tab                n/a       -         -
    declined from the notification     -         -         -
    a colleague answered first         -         -         -
    nobody answers, the ring times out -         -         -
    the caller gives up first          -         -         -

The rest of the suite is not scenarios but the invariants underneath them:
caller-number resolution, the ordering and idempotency of the event stream,
browser-to-webhook correlation, and the notification payload itself.
"""

import functools
import json
import threading
import time

from datetime import datetime
from itertools import permutations
from unittest.mock import patch

from psycopg2.errors import UniqueViolation

from odoo.exceptions import ConcurrencyError
from odoo.tests import tagged
from odoo.tests.common import release_test_lock
from odoo.tools import hash_sign, mute_logger

from odoo.addons.voip.controllers.phone_service_api_controller import WEBHOOK_TOKEN_SCOPE

from .common_voip import VoipPhoneServiceCase
from .pbx_stream import (
    HANGUP_ANSWERED_ELSEWHERE,
    HANGUP_CALL_REJECTED,
    HANGUP_INTERWORKING,
    HANGUP_NO_ANSWER,
    HANGUP_NORMAL_CLEARING,
    HANGUP_USER_BUSY,
    USER_RING_TIMEOUT,
    PbxDial,
    PbxRing,
    PbxScenarioMixin,
)

from odoo.addons.voip.models.phone_service_api import CLIENT_SECRET_PARAM
from odoo.addons.voip.models.phone_service_event import _process_event_after_response

NOTIFY = "odoo.addons.voip.models.voip_call.VoipCall._notify_devices"
NOTIFY_SEND = "odoo.addons.voip.models.voip_call.VoipCall._notify_devices_send"
HANGUP_CALL = "odoo.addons.voip.models.phone_service_api.PhoneServiceAPI.hangup_call"
DECLINE_CALL = "odoo.addons.voip.models.phone_service_api.PhoneServiceAPI.decline_call"
PROCESS_EVENT = "odoo.addons.voip.models.phone_service_event.VoipPhoneServiceEvent._process_event"
EVENT_LOGGER = "odoo.addons.voip.models.phone_service_event"
CALL_LOGGER = "odoo.addons.voip.models.voip_call"

UUID_BERNARD = "pbx-uuid-bernard"
UUID_BOB = "pbx-uuid-bob"
CONVERSATION = "conv-1"
GROUP_EXTENSION = "1010"
# Acting on a notification goes through an authenticated HTTP route, the way
# the service worker calls it.
MEMBER_PASSWORD = "scenario-password"


class PhoneServiceEventCase(PbxScenarioMixin, VoipPhoneServiceCase):
    """Scenario base: one registered user, push recording armed.

    Tests describe a situation as the PBX presents it and assert two outputs:
    the ordered web pushes the browser received, and the final call of every
    user involved.
    """

    def setUp(self):
        super().setUp()
        self.voip_users = {}
        self.user = self.add_member(
            login="bernard", name="Bernard Bernoulli",
            phone="+3281234567", user_uuid=UUID_BERNARD)
        self.phone = self.get_user_phone(self.user)
        self.PhoneServiceEvent = self.env["voip.phone.service.event"]
        self.setUpPushRecording()

    def ingest_call_event(self, event_id, event_type, payload, occurred_at):
        event = self.PhoneServiceEvent._register_event(
            event_id,
            event_type,
            payload,
            self.PhoneServiceEvent._parse_naive_utc(occurred_at),
        )
        if event:
            event._process_event()

    def add_member(self, login="bob", name="Bob Bristow",
                   phone="+3281234599", user_uuid=UUID_BOB):
        # HTTP worker commits can preserve a member created by a previous
        # scenario outside the main HttpCase rollback.
        self.env["res.users"].sudo().search([("login", "=", login)]).unlink()
        member = self.new_voip_user(phone=phone, user_login=login, user_name=name)
        member.voip_pbx_user_uuid = user_uuid
        member.password = MEMBER_PASSWORD
        self.voip_users[login] = member
        return member

    def reset_calls(self):
        """Drop this test's own calls, never the dev database's."""
        self.env["voip.call"].sudo().search([
            ("user_id", "in", [user.id for user in self.voip_users.values()]),
        ]).unlink()
        self.env["voip.conversation"].sudo().search(
            [("conversation_identifier", "like", "conv-")]).unlink()
        self.clearPushes()

    def inbound_ring(self, members=None, **overrides):
        """An outside caller reaching a user on their DID."""
        values = {
            "members": members or {"bernard": UUID_BERNARD},
            "caller_number": self.partner_phone,
            "caller_name": "Fred Edison",
            "dialed_extension": self.phone,
            "direction": "inbound",
            "conversation_id": CONVERSATION,
            "ring_timeout": USER_RING_TIMEOUT,
        }
        values.update(overrides)
        return PbxRing(self, **values)

    def direct_ring(self, **overrides):
        """A colleague dialling this user's own extension."""
        values = {
            "members": {"bernard": UUID_BERNARD},
            "caller_number": "1004",
            "caller_name": "alice",
            "dialed_extension": self.user.voip_username,
            "direction": "internal",
            "conversation_id": CONVERSATION,
            "ring_timeout": USER_RING_TIMEOUT,
        }
        values.update(overrides)
        return PbxRing(self, **values)

    def group_ring(self, members=None, **overrides):
        """An internal caller reaching a call group's members."""
        values = {
            "members": members or {"bernard": UUID_BERNARD, "bob": UUID_BOB},
            "caller_number": "1004",
            "caller_name": "Alice",
            "dialed_extension": GROUP_EXTENSION,
            "direction": "internal",
            "conversation_id": CONVERSATION,
            "wakeup_per_member": True,
        }
        values.update(overrides)
        return PbxRing(self, **values)

    def dial_out(self, **overrides):
        """This user dialling an outside number from a device of their own."""
        values = {
            "user_uuid": UUID_BERNARD,
            "caller_number": self.user.voip_username,
            "caller_name": "Bernard Bernoulli",
            "dialed_extension": self.partner_phone,
            "direction": "outbound",
            "conversation_id": CONVERSATION,
        }
        values.update(overrides)
        return PbxDial(self, **values)

    def dial_colleague(self, **overrides):
        """This user dialling a colleague's extension."""
        values = {
            "dialed_extension": "1004",
            "direction": "internal",
        }
        values.update(overrides)
        return self.dial_out(**values)

    def call_of(self, login):
        return self.env["voip.call"].sudo().search([
            ("direction", "=", "incoming"),
            ("user_id.login", "=", login),
        ])

    def outgoing_call_of(self, login):
        return self.env["voip.call"].sudo().search([
            ("direction", "=", "outgoing"),
            ("user_id.login", "=", login),
        ])

    def conversation_calls(self):
        return self.env["voip.call"].sudo().search(
            [("conversation_id.conversation_identifier", "=", CONVERSATION)])

    def browser_invite(self, conversation_identifier=CONVERSATION, sip_call_id="sip-browser", user=None):
        with mute_logger(CALL_LOGGER):
            return self.env["voip.call"].with_user(user or self.user).get_or_create({
                "direction": "incoming",
                "phone_number": self.partner_phone,
                "conversation_identifier": conversation_identifier,
                "sip_call_id": sip_call_id,
            })


@tagged("-at_install", "post_install")
class TestIncomingDirect(PhoneServiceEventCase):
    """One caller, one callee: the whole lifecycle, end to end."""

    def test_answered_call_runs_its_full_lifecycle(self):
        ring = self.inbound_ring()
        ring.push("bernard")
        ring.leg("bernard").created()
        ring.leg("bernard").answers()
        ring.wait(25)
        ring.cancel_push("bernard")
        ring.leg("bernard").ends(answered=True)

        self.assertPushes([
            ("bernard", "calling"),
            ("bernard", "calling"),
            ("bernard", "ongoing"),
            ("bernard", "terminated"),
        ])
        self.assertOutcome({"bernard": {
            "state": "terminated",
            "direction": "incoming",
            "phone_number": self.partner_phone,
            "user_id": self.user.id,
            "duration": 25,
        }})
        call = self.call_of("bernard")
        self.assertEqual(call.conversation_id.conversation_identifier, CONVERSATION)
        self.assertEqual(call.start_date, ring.answered_at_naive)
        leg = call.leg_ids.filtered(lambda leg: leg.pbx_call_id)
        self.assertRecordValues(leg, [{
            "conversation_id": call.conversation_id.id,
            "voip_call_id": call.id,
            "sip_call_id": "sip-bernard",
            "role": "participant",
        }])
        self.assertTrue(leg.answered_at)
        self.assertTrue(leg.ended_at)

    def test_nobody_answers(self):
        ring = self.inbound_ring()
        ring.push("bernard")
        ring.leg("bernard").created()
        ring.wait(15)
        ring.cancel_push("bernard")
        ring.leg("bernard").ends()

        self.assertPushes([
            ("bernard", "calling"),
            ("bernard", "calling"),
            ("bernard", "missed"),
        ])
        self.assertOutcome({"bernard": {"state": "missed", "start_date": False}})

    def test_callee_declines(self):
        ring = self.inbound_ring()
        ring.push("bernard")
        ring.leg("bernard").created()
        ring.leg("bernard").ends(cause=HANGUP_CALL_REJECTED)

        self.assertPushes([
            ("bernard", "calling"),
            ("bernard", "calling"),
            ("bernard", "rejected"),
        ])
        self.assertOutcome({"bernard": {"state": "rejected"}})

    def test_callee_is_busy(self):
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").ends(cause=HANGUP_USER_BUSY)
        self.assertOutcome({"bernard": {"state": "rejected"}})

    def test_a_second_hangup_changes_nothing(self):
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").ends()
        with self.assertNoPushes():
            ring.leg("bernard").ends()
        self.assertOutcome({"bernard": {"state": "missed"}})

    def test_two_devices_of_one_user_share_a_call(self):
        # A user registered on several devices gets one leg each; the losing
        # device is cleared with plain normal clearing an instant after the
        # other picks up, and that must not end the call.
        ring = self.inbound_ring()
        second = ring.second_device("bernard")
        ring.leg("bernard").created()
        second.created()
        ring.leg("bernard").answers()
        ring.wait(4)
        with self.assertNoPushes():
            second.ends()

        self.assertOutcome({"bernard": {"state": "ongoing"}})
        self.assertEqual(
            set(self.call_of("bernard").leg_ids.mapped("sip_call_id")),
            {"sip-bernard", "sip-bernard-second"})

    def test_interlocutor_refreshed_after_an_attended_transfer(self):
        # A REFER-driven transfer emits no transfer event: the connected-line
        # change on the user's own leg is the only signal.
        transferee = self.env["res.partner"].create(
            {"name": "Tina Transferee", "phone": "+3287659999"})
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").answers()
        call = self.call_of("bernard")
        call.partner_id = self.partner_be
        ring.leg("bernard").updated(status="Up", peer_caller_id_number="003287659999")

        self.assertRecordValues(call, [{
            "state": "ongoing",
            "phone_number": "+3287659999",
            "partner_id": transferee.id,
        }])

    def test_trunk_connected_line_never_moves_the_interlocutor(self):
        # The trunk's connected line transits through Asterisk placeholders
        # while a transfer completes; only the user leg is trusted.
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").answers()
        ring.trunk().created(status="Up", peer_caller_id_number="s")

        self.assertOutcome({"bernard": {
            "state": "ongoing", "phone_number": self.partner_phone}})

    def test_connected_line_while_ringing_keeps_the_ring_time_number(self):
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").updated(peer_caller_id_number="003287659999")
        self.assertOutcome({"bernard": {
            "state": "calling", "phone_number": self.partner_phone}})

    def test_caller_number_is_normalized(self):
        for raw in ("32485794187", "0032485794187", "+32485794187"):
            with self.subTest(raw=raw):
                self.reset_calls()
                ring = self.inbound_ring(conversation_id=f"conv-{raw}")
                ring.leg("bernard").created(
                    caller_id_number=raw, peer_caller_id_number=raw)
                self.assertEqual(self.call_of("bernard").phone_number, "+32485794187")

    def test_callee_leg_ignores_its_own_caller_id(self):
        # On the callee leg Wazo fills caller_id_* with the callee's own
        # identity and puts the remote party in peer_caller_id_*.
        ring = self.inbound_ring()
        ring.leg("bernard").created(
            dialed_extension="18254139450",
            caller_id_number="1000",
            peer_caller_id_number="0032485794187")
        self.assertEqual(self.call_of("bernard").phone_number, "+32485794187")

    def test_internal_callee_leg_resolves_the_caller_extension(self):
        caller = self.add_member(
            login="carol", name="Carol Caller", phone="+3281234568", user_uuid="pbx-uuid-carol")
        caller_extension = self.env["voip.extension"].search(
            [("destination_ref", "=", f"res.users,{caller.id}")]).number
        ring = self.group_ring(members={"bernard": UUID_BERNARD})
        ring.leg("bernard").created(
            caller_id_number=self.user.voip_username,
            peer_caller_id_number=caller.voip_username)

        self.assertEqual(self.call_of("bernard").phone_number, caller_extension)
        self.assertEqual(self.call_of("bernard").user_id, self.user)

    def test_settled_number_survives_the_hangup_reclassification(self):
        # Wazo reclassifies the callee leg as direction=internal on hangup,
        # with the raw caller number; the settled number must not be rewritten.
        raw = "00" + self.partner_phone.lstrip("+")
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").answers()
        ring.wait(5)
        ring.leg("bernard").ends(
            answered=True, direction="internal",
            caller_id_number=raw, peer_caller_id_number=raw)

        self.assertOutcome({"bernard": {
            "state": "terminated", "phone_number": self.partner_phone, "duration": 5}})

    def test_a_reclassified_leg_never_settles_the_callee_extension(self):
        # Wazo swaps caller and peer when it reclassifies a leg as internal on
        # hangup, so the reversal that reads a ringing leg correctly reads a
        # reclassified one backwards and yields the callee's own extension.
        # Ringing alone does not protect the number: when two devices ring, the
        # losing leg is reclassified and ends before the other answers.
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        call = self.call_of("bernard")
        self.assertEqual(call.phone_number, self.partner_phone)
        self.assertEqual(call.state, "calling")

        extension = self.env["voip.extension"].search(
            [("destination_ref", "=", f"res.users,{self.user.id}")]).number
        reclassified = dict(
            ring.leg("bernard")._payload(),
            direction="internal",
            caller_id_number=self.partner_phone,
            peer_caller_id_number=extension,
        )
        Event = self.env["voip.phone.service.event"].sudo()
        self.assertEqual(
            Event._get_display_phone_number_from_pbx_call_event(reclassified), extension,
            "the reclassified payload resolves to the callee's own extension")

        Event._ensure_user_call(reclassified, call.conversation_id)
        self.assertEqual(call.phone_number, self.partner_phone)

    def test_a_second_live_call_cannot_duplicate_a_user_conversation(self):
        # A call is the user's point of view on one conversation; a second
        # ringing device joins it instead of opening another. Two legs racing to
        # create it cannot both win, whatever their transactions saw.
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        call = self.call_of("bernard")

        with self.assertRaises(UniqueViolation), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.env["voip.call"].sudo().create({
                "direction": call.direction,
                "phone_number": self.partner_phone,
                "user_id": call.user_id.id,
                "conversation_id": call.conversation_id.id,
            })

    def test_the_hangup_reclassification_never_settles_a_raw_number(self):
        raw = "00" + self.partner_phone.lstrip("+")
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").ends(
            cause=HANGUP_CALL_REJECTED, direction="internal",
            caller_id_number=raw, peer_caller_id_number=raw)

        self.assertOutcome({"bernard": {
            "state": "rejected", "phone_number": self.partner_phone}})


@tagged("-at_install", "post_install")
class TestGroupRing(PhoneServiceEventCase):
    """A call group rings several members; exactly one outcome each."""

    def setUp(self):
        super().setUp()
        self.member_b = self.add_member()

    def test_one_member_answers_both_registered(self):
        ring = self.group_ring()
        ring.push_all()
        ring.leg("bernard").created()
        ring.leg("bob").created()
        ring.leg("bernard").answers()
        ring.cancel_push("bob")
        ring.leg("bob").ends()
        ring.wait(5)
        ring.cancel_push("bernard")
        ring.leg("bernard").ends(answered=True)

        self.assertPushes([
            ("bernard", "calling"),
            ("bob", "calling"),
            ("bernard", "calling"),
            ("bob", "calling"),
            ("bernard", "ongoing"),
            ("bob", "completed_elsewhere"),
            ("bernard", "terminated"),
        ])
        self.assertOutcome({
            "bernard": {"state": "terminated", "duration": 5},
            "bob": {"state": "completed_elsewhere"},
        })

    def test_one_member_answers_the_loser_is_logged_out(self):
        # The loser never registers, so Wazo dials it no SIP leg and its cancel
        # push is the only event it will ever get. Nothing later can correct a
        # wrong verdict, so the answer has to settle it.
        ring = self.group_ring()
        ring.push_all()
        ring.leg("bernard").created()
        ring.leg("bernard").answers()
        ring.cancel_push("bob")
        ring.cancel_push("bernard")
        ring.wait(5)
        ring.leg("bernard").ends(answered=True)

        self.assertPushes([
            ("bernard", "calling"),
            ("bob", "calling"),
            ("bernard", "calling"),
            ("bernard", "ongoing"),
            ("bob", "completed_elsewhere"),
            ("bernard", "terminated"),
        ])
        self.assertOutcome({
            "bernard": {"state": "terminated", "duration": 5},
            "bob": {"state": "completed_elsewhere"},
        })
        self.assertFalse(self.call_of("bob").leg_ids.filtered("pbx_call_id"))

    def test_a_cancel_racing_ahead_of_the_answer_is_revised(self):
        # Each event is processed in its own transaction, so a logged-out
        # member's cancel can be settled before the answer commits. It lands on
        # "missed" and shows a missed-call notification, which the answer then
        # retracts: the flash is visible, and asserted here so it stays known.
        ring = self.group_ring()
        ring.push_all()
        ring.leg("bernard").created()
        ring.cancel_push("bob")
        ring.leg("bernard").answers()
        ring.cancel_push("bernard")
        ring.wait(5)
        ring.leg("bernard").ends(answered=True)

        self.assertPushes([
            ("bernard", "calling"),
            ("bob", "calling"),
            ("bernard", "calling"),
            ("bob", "missed"),
            ("bernard", "ongoing"),
            ("bob", "completed_elsewhere"),
            ("bernard", "terminated"),
        ])
        self.assertOutcome({
            "bernard": {"state": "terminated", "duration": 5},
            "bob": {"state": "completed_elsewhere"},
        })

    def test_nobody_answers_both_registered(self):
        ring = self.group_ring()
        ring.push_all()
        ring.leg("bernard").created()
        ring.leg("bob").created()
        ring.wait(15)
        ring.cancel_push("bernard")
        ring.leg("bernard").ends()
        ring.cancel_push("bob")
        ring.leg("bob").ends()

        self.assertPushes([
            ("bernard", "calling"),
            ("bob", "calling"),
            ("bernard", "calling"),
            ("bob", "calling"),
            ("bernard", "missed"),
            ("bob", "missed"),
        ])
        self.assertOutcome({
            "bernard": {"state": "missed"},
            "bob": {"state": "missed"},
        })

    def test_nobody_answers_both_logged_out(self):
        # No legs at all: each cancel is the only settling signal there is, and
        # both members must still get their missed-call notification.
        ring = self.group_ring()
        ring.push_all()
        ring.wait(15)
        ring.cancel_all()

        self.assertPushes([
            ("bernard", "calling"),
            ("bob", "calling"),
            ("bernard", "missed"),
            ("bob", "missed"),
        ])
        self.assertOutcome({
            "bernard": {"state": "missed"},
            "bob": {"state": "missed"},
        })

    def test_dial_mobile_legs_without_a_sip_call_id_do_not_collide(self):
        # Each member is reached on a dial_mobile internal channel whose
        # call_ended carries no SIP Call-ID. Both legs must persist: stored as
        # NULL they fall outside the SIP-Call-ID unique index, where an empty
        # string would collide and the second event would be dropped.
        ring = self.group_ring()
        ring.push_all()
        ring.mobile_leg("bernard").ends(cause=HANGUP_INTERWORKING)
        ring.mobile_leg("bob").ends(cause=HANGUP_INTERWORKING)

        self.assertPushes([
            ("bernard", "calling"),
            ("bob", "calling"),
            ("bernard", "missed"),
            ("bob", "missed"),
        ])
        self.assertOutcome({
            "bernard": {"state": "missed"},
            "bob": {"state": "missed"},
        })
        legs = self.env["voip.call.leg"].sudo().search([
            ("conversation_id.conversation_identifier", "=", CONVERSATION),
            ("pbx_call_id", "like", "%-mobile"),
        ])
        self.assertEqual(len(legs), 2)
        self.assertEqual(legs.mapped("sip_call_id"), [False, False])
        self.assertEqual(legs.mapped("role"), ["participant", "participant"])

    def test_a_member_declining_is_not_overwritten_by_a_peer_answer(self):
        # Declining is the member's own act; a colleague picking up afterwards
        # must not rewrite it as "completed elsewhere".
        ring = self.group_ring()
        ring.push_all()
        ring.leg("bernard").created()
        ring.leg("bob").created()
        ring.leg("bob").ends(cause=HANGUP_CALL_REJECTED)
        ring.leg("bernard").answers()
        ring.wait(5)
        ring.leg("bernard").ends(answered=True)

        self.assertOutcome({
            "bernard": {"state": "terminated", "duration": 5},
            "bob": {"state": "rejected"},
        })

    def test_a_member_declining_before_the_answer_stays_rejected(self):
        ring = self.group_ring()
        ring.push_all()
        ring.leg("bernard").created()
        ring.leg("bob").created()
        ring.leg("bernard").answers()
        ring.leg("bob").ends(cause=HANGUP_CALL_REJECTED)
        ring.wait(5)
        ring.leg("bernard").ends(answered=True)

        self.assertOutcome({
            "bernard": {"state": "terminated", "duration": 5},
            "bob": {"state": "rejected"},
        })

    def test_answered_elsewhere_cause_is_honoured(self):
        ring = self.group_ring()
        ring.push_all()
        ring.leg("bernard").created()
        ring.leg("bob").created()
        ring.leg("bernard").answers()
        ring.leg("bob").ends(cause=HANGUP_ANSWERED_ELSEWHERE)
        ring.wait(5)
        ring.leg("bernard").ends(answered=True)

        self.assertOutcome({
            "bernard": {"state": "terminated", "duration": 5},
            "bob": {"state": "completed_elsewhere"},
        })

    def test_a_ring_in_another_conversation_is_untouched(self):
        other = self.group_ring(
            members={"bob": UUID_BOB}, conversation_id="conv-2")
        other.push("bob")
        ring = self.group_ring(members={"bernard": UUID_BERNARD})
        ring.push("bernard")
        ring.leg("bernard").created()
        ring.leg("bernard").answers()

        self.assertOutcome({
            "bernard": {"state": "ongoing"},
            "bob": {"state": "calling"},
        })


@tagged("-at_install", "post_install")
class TestPushWakeup(PhoneServiceEventCase):
    """The wakeup push: the only channel to a softphone that is not registered."""

    def test_push_alone_bootstraps_and_rings_the_call(self):
        ring = self.inbound_ring()
        ring.push("bernard")

        self.assertPushes([("bernard", "calling")])
        self.assertOutcome({"bernard": {
            "state": "calling",
            "direction": "incoming",
            "phone_number": self.partner_phone,
            "user_id": self.user.id,
        }})
        self.assertEqual(
            self.call_of("bernard").wakeup_pbx_call_id,
            ring.member("bernard").wakeup_id,
            "the wakeup channel is the only handle to decline on while unregistered")

    def test_push_display_number_is_normalized(self):
        # Push payloads carry no direction, so the number resolves through the
        # fallback branch and must still be normalized.
        ring = self.inbound_ring()
        ring.push("bernard", peer_caller_id_number="00" + self.partner_phone.lstrip("+"))
        self.assertEqual(self.call_of("bernard").phone_number, self.partner_phone)

    def test_push_renotifies_a_call_already_ringing(self):
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.push("bernard")
        self.assertPushes([("bernard", "calling"), ("bernard", "calling")])
        self.assertOutcome({"bernard": {"state": "calling"}})

    def test_a_push_arriving_after_its_ring_window_does_not_ring(self):
        # webhookd redelivers with backoff, so a push can arrive minutes late.
        # The call is still recorded for the equally late cancel to settle, but
        # the devices must not offer a call that can no longer be answered.
        ring = self.inbound_ring()
        with self.assertNoPushes():
            ring.push("bernard", mobile_wakeup_timestamp="2020-01-01T10:00:00+00:00")
        self.assertOutcome({"bernard": {"state": "calling"}})

        ring.cancel_push("bernard")
        self.assertPushes([("bernard", "missed")])
        self.assertOutcome({"bernard": {"state": "missed"}})

    def test_push_and_cancel_on_an_answered_call_change_nothing(self):
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").answers()
        with self.assertNoPushes():
            ring.push("bernard")
            ring.cancel_push("bernard")
        self.assertOutcome({"bernard": {"state": "ongoing"}})

    def test_a_push_matching_no_call_is_reported(self):
        with (
            self.assertNoPushes(),
            self.assertLogs(EVENT_LOGGER, "WARNING") as log_cm,
        ):
            self.ingest_call_event(
                "orphan-push", "odoo_call_push_notification",
                {"call_id": "leg-9", "sip_call_id": "sip-unknown"},
                "2026-01-01T10:00:00+00:00")
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn("Ignoring PBX call push event orphan-push without matching call", log_cm.output[0])
        self.assertNotIn("sip-unknown", log_cm.output[0])
        self.assertFalse(self.conversation_calls())


@tagged("-at_install", "post_install")
class TestNotificationActions(PhoneServiceEventCase):
    """Acting on a call through the notification's own buttons.

    With no tab open the softphone is unregistered: the PBX dials the user no
    SIP leg, the notification is the whole of their interface, and its buttons
    act through the server instead of on a local INVITE. Whatever the user
    settles there, the PBX events still in flight must not undo.
    """

    def decline_from_the_notification(self, login):
        """Press Decline on the last notification this user received.

        Goes through the route the service worker posts to, with the call id
        taken from the captured push rather than from the database, so the
        payload keeps carrying what the worker needs to act at all. Returns
        both PBX calls it could have made: which one it chose is the whole
        question of whose channel a decline may hang up.
        """
        push = next(
            push for push in reversed(self.captured_pushes) if push.login == login)
        self.assertIn("VOIP:DECLINE_INCOMING_CALL", push.actions)
        self.authenticate(login, MEMBER_PASSWORD)
        with patch(HANGUP_CALL) as hangup_call, patch(DECLINE_CALL) as decline_call:
            self.make_jsonrpc_request(
                "/voip/decline_incoming_call", {"call_id": push.data["res_id"]})
        return hangup_call, decline_call

    def test_logged_out_user_declines_a_direct_call(self):
        # Captured 2026-07-23: alice on 1004 calls a user whose softphone is not
        # registered. The push rings the desktop, the user presses Decline, and
        # the cancel push the PBX sends three quarters of a second later must
        # leave the call rejected instead of settling it as missed.
        ring = self.direct_ring()
        ring.push("bernard")
        hangup_call, decline_call = self.decline_from_the_notification("bernard")
        with self.assertNoPushes():
            ring.cancel_push("bernard")

        # The second push is what clears the notification still ringing on the
        # user's other devices; the cancel that follows stays silent so it
        # cannot downgrade the rejection to a miss.
        self.assertPushes([("bernard", "calling"), ("bernard", "rejected")])
        self.assertPushActions([
            ("bernard", ["VOIP:ANSWER_INCOMING_CALL", "VOIP:DECLINE_INCOMING_CALL"]),
            ("bernard", []),
        ])
        self.assertOutcome({"bernard": {
            "state": "rejected",
            "phone_number": "1004",
            "start_date": False,
        }})
        # The only PBX handle a push carries is the channel that raised
        # Pushmobile, and on a direct call that channel is the caller's own:
        # hanging it up would drop the caller mid-ring. The PBX is asked to
        # stop ringing this member of this conversation instead, and resolves
        # the ring leg — which does not exist yet when the push is sent — itself.
        decline_call.assert_called_once_with(CONVERSATION, UUID_BERNARD)
        hangup_call.assert_not_called()

    def test_the_declined_call_keeps_no_leg_of_the_caller(self):
        # The push names the caller's channel and the caller's SIP Call-ID.
        # Recording that Call-ID here would make the caller's own INVITE resolve
        # to the callee's call, and would offer the cancel a second way in.
        ring = self.direct_ring()
        ring.push("bernard")
        self.decline_from_the_notification("bernard")

        call = self.call_of("bernard")
        self.assertEqual(call.wakeup_pbx_call_id, ring.caller_channel_id)
        self.assertFalse(call.leg_ids)
        self.assertFalse(self.env["voip.call.leg"].search(
            [("sip_call_id", "=", ring.caller_sip_call_id)]))


@tagged("-at_install", "post_install")
class TestBrowserCorrelation(PhoneServiceEventCase):
    """Matching the browser's own INVITE to the call the webhooks describe."""

    def test_invite_joins_the_call_by_conversation_id(self):
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        result = self.browser_invite(sip_call_id="browser-leg-not-yet-seen")

        call = self.call_of("bernard")
        self.assertEqual(result["ids"], call.ids)
        self.assertIn("browser-leg-not-yet-seen", call.leg_ids.mapped("sip_call_id"))

    def test_invite_joins_the_call_by_sip_call_id(self):
        # A re-INVITE whose control handle does not match still resolves
        # through the leg already tracking this Call-ID.
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        result = self.browser_invite(
            conversation_identifier="unrelated-handle", sip_call_id="sip-bernard")
        self.assertEqual(result["ids"], self.call_of("bernard").ids)

    def test_a_webhook_reconciles_onto_the_browser_leg(self):
        # The INVITE arrives first and creates a leg keyed only by Call-ID; the
        # webhook must stamp it rather than split it in two.
        self.browser_invite(sip_call_id="sip-bernard")
        ring = self.inbound_ring()
        ring.leg("bernard").created()

        call = self.call_of("bernard")
        leg = self.env["voip.call.leg"].search([("sip_call_id", "=", "sip-bernard")])
        self.assertRecordValues(leg, [{
            "pbx_call_id": ring.member("bernard").leg_id,
            "conversation_id": call.conversation_id.id,
            "voip_call_id": call.id,
        }])

    def test_an_invite_without_the_conversation_header_is_reported(self):
        # The Odoo provider always stamps X-Odoo-Conversation-Id. An INVITE
        # without it shares no key with the conversation: a PBX-side defect to
        # report, not to repair with a fuzzy recency match.
        with self.assertLogs(CALL_LOGGER, "WARNING") as log_cm:
            invited = self.env["voip.call"].with_user(self.user).get_or_create({
                "direction": "incoming",
                "phone_number": self.partner_phone,
                "sip_call_id": "browser-call-id",
            })
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn("without X-Odoo-Conversation-Id", log_cm.output[0])
        self.assertIn("browser-call-id", log_cm.output[0])

        ring = self.inbound_ring()
        ring.push("bernard")
        pushed = self.conversation_calls()
        self.assertNotEqual(pushed.ids, invited["ids"])
        self.assertEqual(pushed.state, "calling")

    def test_a_provider_without_webhooks_correlates_by_leg_alone(self):
        self.user.res_users_settings_id.voip_provider_id = self.env["voip.provider"].create(
            {"name": "Generic PBX"})
        VoipCall = self.env["voip.call"].with_user(self.user)
        result = VoipCall.get_or_create({
            "direction": "incoming",
            "phone_number": self.partner_phone,
            "sip_call_id": "call-id-only",
        })
        call = VoipCall.browse(result["ids"][0])
        self.assertRecordValues(call.leg_ids, [{
            "sip_call_id": "call-id-only",
            "conversation_id": False,
        }])
        self.assertEqual(VoipCall._find_by_sip_call_id("call-id-only"), call)

    def test_the_pending_match_tolerates_number_formats(self):
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        VoipCall = self.env["voip.call"].with_user(self.user)
        self.assertEqual(
            VoipCall._find_recent_pending_incoming_call(
                "00" + self.partner_phone.lstrip("+")),
            self.call_of("bernard"))
        self.assertFalse(
            VoipCall._find_recent_pending_incoming_call("+3299999999"))


@tagged("-at_install", "post_install")
class TestOutgoingFromDevice(PhoneServiceEventCase):
    """Calls the user placed, which the PBX may be the only witness of.

    A call dialled from a native SIP phone has no browser to record it, so the
    caller leg's own events are the whole story. The same events also reach a
    call the browser did place, and must join it rather than double it.
    """

    def test_answered_outgoing_call_runs_its_full_lifecycle(self):
        dial = self.dial_out()
        dial.created()
        dial.answers()
        dial.wait(42)
        dial.ends(answered=True)

        self.assertOutcome({"bernard": {
            "state": "terminated",
            "direction": "outgoing",
            "phone_number": self.partner_phone,
            "user_id": self.user.id,
            "duration": 42,
        }}, direction="outgoing")
        call = self.outgoing_call_of("bernard")
        self.assertEqual(call.conversation_id.conversation_identifier, CONVERSATION)
        self.assertEqual(call.start_date, dial.answered_at_naive)
        self.assertRecordValues(call.leg_ids, [{
            "conversation_id": call.conversation_id.id,
            "voip_call_id": call.id,
            "sip_call_id": "sip-dialer",
            "pbx_call_id": CONVERSATION,
            "role": "source",
        }])

    def test_a_call_the_user_placed_pushes_no_notification(self):
        with self.assertNoPushes():
            dial = self.dial_out()
            dial.created()
            dial.answers()
            dial.ends(answered=True)

    def test_a_callee_who_never_answers_aborts_the_call(self):
        dial = self.dial_out()
        dial.created()
        dial.wait(30)
        dial.ends(cause=HANGUP_NO_ANSWER)

        self.assertOutcome(
            {"bernard": {"state": "aborted", "duration": 0}}, direction="outgoing")

    def test_a_busy_callee_rejects_the_call(self):
        dial = self.dial_out()
        dial.created()
        dial.ends(cause=HANGUP_USER_BUSY)

        self.assertOutcome({"bernard": {"state": "rejected"}}, direction="outgoing")

    def test_a_declining_callee_rejects_the_call(self):
        dial = self.dial_out()
        dial.created()
        dial.ends(cause=HANGUP_CALL_REJECTED)

        self.assertOutcome({"bernard": {"state": "rejected"}}, direction="outgoing")

    def test_dialling_a_colleague_leaves_their_own_verdict_alone(self):
        # The caller's leg shares the conversation with the callee's, so its
        # role decides the callee's fate: read as a participant, its answer
        # would pass for a colleague picking up and revise the callee's missed
        # call to "completed elsewhere". It is a source, like an inbound trunk.
        bob = self.add_member()
        extension = bob.routing_extension_id.number
        dial = self.dial_colleague(dialed_extension=extension)
        ring = PbxRing(
            self, members={"bob": UUID_BOB}, caller_number=self.user.voip_username,
            caller_name="Bernard Bernoulli", dialed_extension=extension,
            direction="internal", conversation_id=CONVERSATION)
        dial.created()
        ring.leg("bob").created()
        ring.wait(20)
        ring.leg("bob").ends()
        dial.ends(cause=HANGUP_NO_ANSWER)

        self.assertPushes([("bob", "calling"), ("bob", "missed")])
        self.assertOutcome({"bob": {"state": "missed", "direction": "incoming"}})
        self.assertOutcome({"bernard": {
            "state": "aborted",
            "direction": "outgoing",
            "phone_number": extension,
        }}, direction="outgoing")

    def test_calling_a_group_they_belong_to_keeps_both_calls(self):
        # One conversation holding both directions for one user: the live-call
        # unique index is keyed on direction, so both control handles can be
        # the conversation id.
        dial = self.dial_colleague(dialed_extension=GROUP_EXTENSION)
        ring = self.group_ring(members={"bernard": UUID_BERNARD})
        dial.created()
        ring.leg("bernard").created()

        for call in (self.outgoing_call_of("bernard"), self.call_of("bernard")):
            self.assertEqual(call.state, "calling")
            self.assertEqual(call.conversation_id.conversation_identifier, CONVERSATION)

    def test_a_browser_placed_call_is_not_duplicated_by_its_webhooks(self):
        # The browser sends its INVITE's Call-ID, which the PBX reports back as
        # the caller leg's sip_call_id: the two converge on one record, and the
        # number the browser resolved survives the raw dialled digits.
        placed = self.env["voip.call"].with_user(self.user).get_or_create({
            "direction": "outgoing",
            "phone_number": self.partner_phone,
            "sip_call_id": "sip-dialer",
        })
        dial = self.dial_out(dialed_extension="081234567")
        dial.created()
        dial.answers()
        dial.ends(answered=True)

        call = self.outgoing_call_of("bernard")
        self.assertEqual(call.ids, placed["ids"])
        self.assertRecordValues(call, [{
            "state": "terminated",
            "phone_number": self.partner_phone,
        }])
        self.assertEqual(call.conversation_id.conversation_identifier, CONVERSATION)
        self.assertEqual(len(call.leg_ids), 1)

    def test_a_call_the_webhooks_created_first_takes_the_browser_in(self):
        dial = self.dial_out()
        dial.created()
        placed = self.env["voip.call"].with_user(self.user).get_or_create({
            "direction": "outgoing",
            "phone_number": self.partner_phone,
            "sip_call_id": "sip-dialer",
        })
        dial.answers()
        dial.ends(answered=True)

        call = self.outgoing_call_of("bernard")
        self.assertEqual(call.ids, placed["ids"])
        self.assertEqual(call.state, "terminated")
        self.assertEqual(len(call.leg_ids), 1)


@tagged("-at_install", "post_install")
class TestNotificationPayload(PhoneServiceEventCase):
    """What the service worker actually receives, beyond the call state."""

    def test_each_notification_offers_the_actions_of_its_state(self):
        # The actions are the only part the user can act on, and nothing else
        # asserts them: a ringing call must offer Answer and Decline, a missed
        # one Call Back, and a settled one nothing at all.
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").ends()

        self.assertPushActions([
            ("bernard", ["VOIP:ANSWER_INCOMING_CALL", "VOIP:DECLINE_INCOMING_CALL"]),
            ("bernard", ["VOIP:CALL_BACK_MISSED_CALL"]),
        ])

    def test_a_settled_call_offers_no_action(self):
        member_b = self.add_member()
        ring = self.group_ring()
        ring.push_all()
        ring.leg("bernard").created()
        ring.leg("bernard").answers()
        ring.cancel_push("bob")

        self.assertPushActions([
            ("bernard", ["VOIP:ANSWER_INCOMING_CALL", "VOIP:DECLINE_INCOMING_CALL"]),
            ("bob", ["VOIP:ANSWER_INCOMING_CALL", "VOIP:DECLINE_INCOMING_CALL"]),
            ("bernard", ["VOIP:ANSWER_INCOMING_CALL", "VOIP:DECLINE_INCOMING_CALL"]),
            ("bernard", []),
            ("bob", []),
        ])
        self.assertEqual(self.call_of(member_b.login).state, "completed_elsewhere")

    def test_every_notification_uses_the_incoming_call_scenario(self):
        # The scenario is what lets the OS render call-style notification
        # buttons instead of the generic ones.
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        ring.leg("bernard").ends()

        self.assertTrue(self.captured_pushes)
        for push in self.captured_pushes:
            self.assertEqual(push.scenario, "incoming-call")
            self.assertIn("/web/", push.icon)
            self.assertEqual(push.data["type"], "VOIP:CALL_NOTIFICATION")
            self.assertEqual(push.data["model"], "voip.call")

    def test_the_notification_payload_carries_the_control_handle(self):
        # The browser matches a notification action to its local INVITE by
        # control handle, the conversation key every leg shares.
        ring = self.inbound_ring()
        ring.leg("bernard").created()
        call = self.call_of("bernard")
        with patch(NOTIFY_SEND) as send:
            call._notify_devices()
        data = send.call_args.args[0]
        self.assertEqual(data["control_handle"], CONVERSATION)
        self.assertEqual(data["control_handle"], call.control_handle)
        self.assertEqual(data["call_state"], "calling")


@tagged("-at_install", "post_install")
class TestTrunkFallback(PhoneServiceEventCase):
    """The trunk leg, which Wazo answers itself to run its fallbacks.

    Captured 2026-07-14: on reject or no answer the PBX answers the caller
    unbridged to play an announcement or take voicemail, so an ``answer_time``
    on the trunk proves nothing. Only a bridge proves a device picked up.
    """

    def test_source_leg_creates_no_user_call(self):
        ring = self.inbound_ring()
        ring.trunk().created()

        conversation = self.env["voip.conversation"].sudo().search(
            [("conversation_identifier", "=", CONVERSATION)])
        self.assertEqual(len(conversation), 1)
        self.assertFalse(self.conversation_calls())
        leg = self.env["voip.call.leg"].search([("sip_call_id", "=", ring.caller_sip_call_id)])
        self.assertEqual(leg.role, "source")
        self.assertFalse(leg.voip_call_id)

    def test_an_unbridged_trunk_answer_never_resurrects_a_reject(self):
        ring = self.inbound_ring()
        ring.trunk().created()
        ring.leg("bernard").created()
        ring.leg("bernard").ends(cause=HANGUP_CALL_REJECTED)
        ring.trunk().answers_unbridged()
        ring.trunk().ends()

        self.assertOutcome({"bernard": {"state": "rejected", "start_date": False}})

    def test_an_unbridged_trunk_answer_never_resurrects_a_miss(self):
        ring = self.inbound_ring()
        ring.trunk().created()
        ring.leg("bernard").created()
        ring.trunk().answers_unbridged()
        ring.leg("bernard").ends()

        self.assertOutcome({"bernard": {"state": "missed", "start_date": False}})

    def test_a_pushed_call_is_missed_by_the_fallback_answered_trunk(self):
        # Logged out: the push bootstraps the call and no callee leg ever
        # exists, so the trunk's own answered hangup is all that arrives.
        ring = self.inbound_ring()
        ring.trunk().created()
        ring.push("bernard")
        ring.trunk().ends()

        self.assertOutcome({"bernard": {"state": "missed", "start_date": False}})

    def test_a_bridged_trunk_answer_is_a_real_pickup(self):
        # The incident from before the plugin stamped X-Odoo-Conversation-Id:
        # the browser INVITE carries only the callee Call-ID, the bridged trunk
        # is the ONLY answered leg and the device leg ends reason-21. It must
        # converge on one terminated call, never a duplicate or a reject.
        ring = self.inbound_ring()
        self.browser_invite(conversation_identifier=None, sip_call_id="sip-bernard")
        ring.trunk().created()
        ring.leg("bernard").created()
        ring.trunk().answers_bridged(ring.member("bernard"))
        ring.leg("bernard").ends(cause=HANGUP_CALL_REJECTED)
        ring.trunk().ends()

        self.assertOutcome({"bernard": {"state": "terminated"}})
        self.assertTrue(self.call_of("bernard").start_date)

    def test_the_graph_converges_whatever_the_delivery_order(self):
        # webhookd gives no ordering guarantee, so every permutation of one
        # call's events must land on the same single call, leg set and state.
        steps = ("trunk_created", "leg_created", "answered", "ended")
        for index, order in enumerate(permutations(steps)):
            with self.subTest(order=order):
                # Each order needs its own conversation: event ids are derived
                # from it, and reusing them would let the deduplication drop a
                # whole permutation as already seen and pass vacuously.
                self.reset_calls()
                ring = self.inbound_ring(conversation_id=f"conv-perm-{index}")
                trunk = ring.trunk()
                leg = ring.leg("bernard")
                ring.answered_at = ring.clock.stamp
                actions = {
                    "trunk_created": trunk.created,
                    "leg_created": leg.created,
                    "answered": leg.answers,
                    "ended": functools.partial(leg.ends, answered=True),
                }
                for step in order:
                    actions[step]()

                conversation = self.env["voip.conversation"].sudo().search(
                    [("conversation_identifier", "=", ring.conversation_id)])
                self.assertEqual(len(conversation), 1, "exactly one conversation")
                calls = self.env["voip.call"].sudo().search(
                    [("conversation_id", "=", conversation.id)])
                self.assertEqual(len(calls), 1, "one call, no duplicate or orphan")
                self.assertEqual(calls.state, "terminated")
                self.assertEqual(
                    set(conversation.leg_ids.mapped("role")), {"source", "participant"})

    def test_a_replayed_stream_is_idempotent(self):
        for _ in range(2):
            ring = self.inbound_ring()
            ring.trunk().created()
            ring.leg("bernard").created()
            ring.leg("bernard").answers()
            ring.wait(5)
            ring.leg("bernard").ends(answered=True)

        self.assertEqual(len(self.conversation_calls()), 1)
        self.assertOutcome({"bernard": {"state": "terminated", "duration": 5}})


@tagged("-at_install", "post_install")
class TestEventPlumbing(PhoneServiceEventCase):
    """Dispatch, deduplication and the pure disposition mapping."""

    def test_hangup_disposition_mapping(self):
        cases = [
            ({"answer_time": "2026-01-01T10:00:05+00:00", "reason_code": HANGUP_NORMAL_CLEARING},
             "answered", "an answer outranks any cause"),
            ({"answer_time": None, "reason_code": HANGUP_USER_BUSY}, "busy", ""),
            ({"answer_time": None, "reason_code": HANGUP_CALL_REJECTED}, "rejected", ""),
            ({"answer_time": None, "reason_code": HANGUP_ANSWERED_ELSEWHERE},
             "completed_elsewhere", ""),
        ]
        for payload, expected, message in cases:
            with self.subTest(payload=payload):
                self.assertEqual(
                    self.PhoneServiceEvent._hangup_disposition(payload), expected, message)

        for reason_code in (16, 18, 19, 20, 487):
            with self.subTest(reason_code=reason_code):
                self.assertEqual(
                    self.PhoneServiceEvent._hangup_disposition(
                        {"answer_time": None, "reason_code": reason_code}),
                    "missed", "no answer and no known cause reads as missed")

    def test_an_event_is_processed_once(self):
        ring = self.inbound_ring()
        payload = ring.leg("bernard")._payload()
        for _ in range(2):
            self.ingest_call_event(
                "same-id", "call_created", payload, "2026-01-01T10:00:00+00:00")

        self.assertPushes([("bernard", "calling")])
        self.assertEqual(len(self.conversation_calls()), 1)

    def test_a_hangup_for_an_unknown_call_is_a_noop(self):
        with self.assertNoPushes():
            self.ingest_call_event(
                "orphan-hangup", "call_ended",
                {"conversation_id": "unknown", "sip_call_id": "x",
                 "answer_time": "2026-01-01T10:00:05+00:00", "reason_code": 16},
                "2026-01-01T10:00:00+00:00")
        self.assertFalse(self.conversation_calls())

    def test_a_leg_naming_no_known_recipient_is_reported(self):
        ring = self.inbound_ring()
        with (
            self.assertNoPushes(),
            self.assertLogs(EVENT_LOGGER, "WARNING") as log_cm,
        ):
            ring.leg("bernard").created(user_uuid="nobody", dialed_extension="999")
        self.assertEqual(
            len(log_cm.output), 1,
            "only call_created names a recipient; the call_updated bracket "
            "resolves through its leg and stays silent")
        self.assertIn("without Odoo softphone recipient", log_cm.output[0])
        self.assertNotIn("nobody", log_cm.output[0])
        self.assertNotIn("999", log_cm.output[0])
        self.assertFalse(self.conversation_calls())


def _sync_process_event_after_response(dbname, uid, event_id, response_sent, processed):
    try:
        response_sent.wait(timeout=2)
        _process_event_after_response(dbname, uid, event_id)
    finally:
        processed.set()


@tagged("-at_install", "post_install")
class TestVoipPhoneServiceEventWebhookRoundtrip(VoipPhoneServiceCase):
    """Drive ``/voip/api/phone_service/event`` over HTTP so the ack-then-process machinery
    runs for real: signed request, 200 ack, then ``_process_event_after_response`` on a fresh
    registry cursor and Environment via ``call_on_close``. This is the layer
    the direct ``ingest_call_event`` tests skip, and where upstream registry
    API drift breaks first."""

    CLIENT_SECRET = "test_voip_client_secret"

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_str(CLIENT_SECRET_PARAM, self.CLIENT_SECRET)
        self.user = self.new_voip_user()
        self.user.voip_pbx_user_uuid = "pbx-uuid-webhook"
        self.phone = self.get_user_phone(self.user)
        self._event_seq = 0

    def _payload(self, **overrides):
        payload = {
            "call_id": "leg-w1",
            "conversation_id": "conv-webhook",
            "sip_call_id": "sip-w1",
            "direction": "inbound",
            "is_caller": False,
            "dialed_extension": self.phone,
            "user_uuid": "pbx-uuid-webhook",
            "caller_id_number": self.partner_phone,
            "peer_caller_id_number": self.phone,
        }
        payload.update(overrides)
        return payload

    def _receive(self, event_type, payload):
        self._event_seq += 1
        token = hash_sign(
            self.env(su=True),
            WEBHOOK_TOKEN_SCOPE,
            {
                "data": {
                    "id": f"webhook-evt-{self._event_seq}",
                    "event_type": event_type,
                    "payload": payload,
                    "occurred_at": "2026-01-01T10:00:00+00:00",
                },
                "meta": {},
            },
            expiration=datetime.fromtimestamp(time.time() + 300),
            secret=self.env["iap.account"]._hash_iap_token(self.CLIENT_SECRET),
        )
        body = json.dumps({"token": token}).encode()
        response_sent = threading.Event()
        processed = threading.Event()
        with patch(
            "odoo.addons.voip.models.phone_service_event._process_event_after_response",
            functools.partial(
                _sync_process_event_after_response,
                response_sent=response_sent,
                processed=processed,
            ),
        ):
            try:
                res = self.url_open("/voip/api/phone_service/event", data=body, headers={
                    "Content-Type": "application/json",
                })
                res.raise_for_status()
            finally:
                response_sent.set()
            with release_test_lock():
                self.assertTrue(
                    processed.wait(timeout=5),
                    "post-response processing did not finish")

    def _webhook_call(self):
        return self.env["voip.call"].sudo().search(
            [("conversation_id.conversation_identifier", "=", "conv-webhook")])

    def test_signed_webhook_is_processed_after_ack(self):
        with patch(NOTIFY) as notify:
            self._receive("call_created", self._payload())
        call = self._webhook_call()
        self.assertRecordValues(call, [{
            "state": "calling",
            "direction": "incoming",
            "phone_number": self.partner_phone,
            "user_id": self.user.id,
        }])
        self.assertIn("sip-w1", call.leg_ids.mapped("sip_call_id"))
        self.assertTrue(notify.called)
        with patch(NOTIFY):
            self._receive("call_answered", {
                "conversation_id": "conv-webhook", "sip_call_id": "sip-w1"})
        call.invalidate_recordset()
        self.assertEqual(call.state, "ongoing")

    def test_after_response_retries_concurrency_error(self):
        with (
            patch(PROCESS_EVENT, side_effect=[ConcurrencyError(), None]) as process_event,
            patch("odoo.addons.voip.models.phone_service_event.time.sleep"),
            patch("odoo.addons.voip.models.phone_service_event._notify_event_not_processed") as notify_failure,
        ):
            self._receive("call_created", self._payload())
        self.assertEqual(process_event.call_count, 2)
        self.assertFalse(notify_failure.called)

    def test_failed_processing_notifies_user(self):
        with (
            patch(PROCESS_EVENT, side_effect=ValueError("boom")),
            self.assertLogs(EVENT_LOGGER, level="ERROR") as log_cm,
        ):
            self._receive("call_created", self._payload())
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn("Processing of phone service event", log_cm.output[0])
        bus_messages = self.env["bus.bus"].sudo().search(
            [("message", "like", "event_not_processed")])
        self.assertEqual(len(bus_messages), 1)

    def test_failed_processing_notifies_the_other_party_number(self):
        """The user is told about the call with their correspondent, whichever
        side placed it: on the leg of a call the user placed, the caller id is
        their own."""
        for label, payload, number in (
            ("incoming", self._payload(), self.partner_phone),
            ("outgoing", self._payload(
                direction="outbound",
                is_caller=True,
                dialed_extension=self.partner_phone,
                caller_id_number=self.user.voip_username,
                peer_caller_id_number=self.partner_phone,
            ), self.partner_phone),
        ):
            with (
                self.subTest(label),
                patch(PROCESS_EVENT, side_effect=ValueError("boom")),
                mute_logger(EVENT_LOGGER),
            ):
                self._receive("call_created", payload)
                bus_message = self.env["bus.bus"].sudo().search(
                    [("message", "like", "event_not_processed")], order="id desc", limit=1)
                self.assertEqual(json.loads(bus_message.message)["payload"]["from"], number)

    def test_failed_processing_rolls_back_partial_writes(self):
        # _ensure_leg fails after the conversation and the call were created:
        # nothing may survive, as the deduplication on event_id means a
        # half-applied event would never be reprocessed.
        with (
            patch(
                "odoo.addons.voip.models.phone_service_event"
                ".VoipPhoneServiceEvent._ensure_leg",
                side_effect=ValueError("boom")),
            self.assertLogs(EVENT_LOGGER, level="ERROR") as log_cm,
        ):
            self._receive("call_created", self._payload())
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn("Processing of phone service event", log_cm.output[0])
        self.assertFalse(self._webhook_call())
        self.assertFalse(self.env["voip.conversation"].sudo().search(
            [("conversation_identifier", "=", "conv-webhook")]))
        bus_messages = self.env["bus.bus"].sudo().search(
            [("message", "like", "event_not_processed")])
        self.assertEqual(len(bus_messages), 1)
