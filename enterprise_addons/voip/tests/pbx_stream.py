"""Realistic Wazo event streams for the phone-service event tests.

Every sequence here is modelled on conversations captured from the dev PBX in
July 2026, so a scenario test declares only the decisions — who registers, who
picks up, who declines — and this module emits the events the PBX really sends
around them, including the ones easy to forget: a wakeup push per member whose
channel id is *not* the SIP leg id, the ``call_updated`` bracket around
``call_created``, and a cancel push per member ahead of its hangup.

The two bugs this suite failed to catch both lived in events no test emitted.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

NOTIFY_SEND = "odoo.addons.voip.models.voip_call.VoipCall._notify_devices_send"

HANGUP_NORMAL_CLEARING = 16
HANGUP_USER_BUSY = 17
HANGUP_NO_ANSWER = 19
HANGUP_CALL_REJECTED = 21
HANGUP_ANSWERED_ELSEWHERE = 26
# The cause a dial_mobile internal channel hangs up with when the softphone it
# was originated for never registers (captured 2026-07-24).
HANGUP_INTERWORKING = 127

# Per-destination configuration, not a constant of the PBX: 15 seconds on the
# captured call group, 32 on a user's own extension.
GROUP_RING_TIMEOUT = "15"
USER_RING_TIMEOUT = "32"


class PbxClock:
    """Wall clock for a scenario, advancing like a real call does.

    It starts at the real present because ``_has_ring_window_elapsed`` compares
    a push's wakeup stamp against ``Datetime.now()``: a scenario dated in the
    past would look like a webhookd redelivery arriving after its ring window
    and would silently ring no device.
    """

    def __init__(self, start=None):
        self.now = start or datetime.now(timezone.utc).replace(microsecond=0)

    def tick(self, seconds=1):
        self.now += timedelta(seconds=seconds)
        return self.stamp

    @property
    def stamp(self):
        return self.now.isoformat()


class PbxMember:
    """A user the PBX is ringing, and the channels it uses to reach them.

    A member who registers gets a SIP leg, which is what a later event can
    settle. A member who does not gets nothing of their own: the push that wakes
    them names the channel that raised ``Pushmobile`` and that channel's SIP
    Call-ID (``Uniqueid`` and ``WAZO_SIP_CALL_ID`` in wazo-calld's dial_mobile
    bus consumer), and on a direct call — captured 2026-07-23, confirmed in
    Asterisk CEL — the AGI runs on the caller's own channel before the callee's
    is dialled. So the wakeup handle a logged-out member is reached by is the
    caller's channel, not theirs.
    """

    def __init__(self, ring, login, user_uuid, index):
        self.ring = ring
        self.login = login
        self.user_uuid = user_uuid
        if ring.wakeup_per_member:
            self.wakeup_id = f"{ring.epoch}.{1400 + index}"
            self.wakeup_sip_call_id = ""
        else:
            self.wakeup_id = ring.caller_channel_id
            self.wakeup_sip_call_id = ring.caller_sip_call_id
        self.leg_id = f"{ring.epoch + 1}.{1500 + index}"
        self.sip_call_id = f"sip-{login}"
        self.registered = False
        self.push_payload = None


class PbxLeg:
    """The SIP leg of a member whose softphone is registered.

    A member registered on several devices gets one leg each, all folded into
    that user's single call, so the leg owns its own channel ids rather than
    borrowing the member's.
    """

    def __init__(self, ring, member, leg_id=None, sip_call_id=None):
        self.ring = ring
        self.member = member
        self.leg_id = leg_id or member.leg_id
        self.sip_call_id = sip_call_id or member.sip_call_id

    def _payload(self, **overrides):
        payload = {
            "call_id": self.leg_id,
            "conversation_id": self.ring.conversation_id,
            "sip_call_id": self.sip_call_id,
            "direction": self.ring.direction,
            "is_caller": False,
            "user_uuid": self.member.user_uuid,
            "dialed_extension": self.ring.dialed_extension,
            "caller_id_name": self.ring.caller_name,
            "caller_id_number": self.ring.caller_number,
            "peer_caller_id_name": self.ring.caller_name,
            "peer_caller_id_number": self.ring.caller_number,
            "status": "Ringing",
            "talking_to": {},
            "bridges": [],
        }
        payload.update(overrides)
        return payload

    def created(self, **overrides):
        """Wazo brackets ``call_created`` with ``call_updated`` on both sides."""
        self.member.registered = True
        self.updated(**overrides)
        self.ring.emit("call_created", self._payload(**overrides))
        self.updated(**overrides)
        return self

    def updated(self, **overrides):
        self.ring.emit("call_updated", self._payload(**overrides))
        return self

    def answers(self, **overrides):
        payload = self._payload(
            status="Up",
            talking_to={self.ring.trunk_id: None},
            bridges=[f"wazo-dial-mobile-{self.ring.conversation_id}"],
        )
        payload.update(overrides)
        self.ring.answered_at = self.ring.clock.stamp
        self.ring.emit("call_answered", payload)
        self.updated(status="Up")
        return self

    def ends(self, cause=HANGUP_NORMAL_CLEARING, answered=False, **overrides):
        payload = self._payload(
            status="Up" if answered else "Ringing",
            answer_time=self.ring.answered_at if answered else None,
            reason_code=cause,
        )
        payload.update(overrides)
        self.ring.emit("call_ended", payload)
        return self


class PbxTrunk:
    """The inbound external leg: no softphone user, owns no user-facing call.

    Wazo answers this leg itself, unbridged, to run reject and no-answer
    fallbacks — which is why an ``answer_time`` on it proves nothing.
    """

    def __init__(self, ring):
        self.ring = ring

    def _payload(self, **overrides):
        payload = {
            "call_id": self.ring.caller_channel_id,
            "conversation_id": self.ring.conversation_id,
            "sip_call_id": self.ring.caller_sip_call_id,
            "direction": "inbound",
            "is_caller": True,
            "user_uuid": None,
            "dialed_extension": self.ring.dialed_extension,
            "caller_id_name": self.ring.caller_name,
            "caller_id_number": self.ring.caller_number,
            "peer_caller_id_name": self.ring.caller_name,
            "peer_caller_id_number": self.ring.caller_number,
            "status": "Ringing",
            "talking_to": {},
            "bridges": [],
        }
        payload.update(overrides)
        return payload

    def created(self, **overrides):
        self.ring.emit("call_created", self._payload(**overrides))
        return self

    def answers_bridged(self, member):
        """A real pickup: the trunk is bridged to the member who answered."""
        self.ring.emit("call_answered", self._payload(
            status="Up",
            talking_to={member.leg_id: None},
            bridges=[f"bridge-{self.ring.conversation_id}"],
        ))
        return self

    def answers_unbridged(self):
        """The PBX answering for a fallback announcement, bridged to nothing."""
        self.ring.emit("call_answered", self._payload(status="Up"))
        return self

    def ends(self, answered=True, cause=HANGUP_NORMAL_CLEARING):
        self.ring.emit("call_ended", self._payload(
            answer_time=self.ring.clock.stamp if answered else None,
            reason_code=cause,
        ))
        return self


class PbxConversation:
    """One conversation on the PBX clock: what every event of it shares."""

    def __init__(self, case, conversation_id, epoch=1784800000):
        self.case = case
        self.clock = PbxClock()
        self.epoch = epoch
        self.conversation_id = conversation_id
        # Asterisk's Linkedid is the id of the channel that opened the
        # conversation — the caller's — so the conversation identifier and that
        # channel's id are the same string, and every event of the conversation
        # can name it.
        self.caller_channel_id = conversation_id
        self.answered_at = None
        self.sequence = 0
        # Two streams can describe one conversation — a dialer's own leg and the
        # ring it triggers — and an event id repeated across them would be
        # dropped as a redelivery, so each stream numbers its events apart.
        self.stream_key = ""

    def emit(self, event_type, payload):
        """Emit at the clock's current instant.

        Only ``wait`` moves the clock, so a call's duration is exactly the time
        the scenario says it lasted rather than an artefact of how many events
        it happened to send. Real streams do put many events in one second.
        """
        self.sequence += 1
        self.case.ingest_call_event(
            f"{self.conversation_id}:{self.stream_key}{self.sequence}:{event_type}",
            event_type, payload, self.clock.stamp)

    def wait(self, seconds):
        """Let call time pass without the PBX saying anything."""
        self.clock.tick(seconds)
        return self

    @property
    def answered_at_naive(self):
        """The answer instant as Odoo stores it, for comparing to start_date."""
        return datetime.fromisoformat(self.answered_at).astimezone(
            timezone.utc).replace(tzinfo=None)


class PbxDial(PbxConversation):
    """One outgoing call: the events the PBX emits for the dialer's own leg.

    This is the whole stream a call placed from a native SIP phone produces on
    the client side — no browser saw it, and the outbound trunk leg is filtered
    out by the phone service. The leg is reclassified to "internal" on hangup
    whatever it was while the call was up, which is why ``is_caller`` and not
    ``direction`` is what identifies it.
    """

    def __init__(self, case, user_uuid, caller_number, caller_name,
                 dialed_extension, conversation_id, direction="outbound",
                 sip_call_id="sip-dialer", epoch=1784800000):
        super().__init__(case, conversation_id, epoch)
        self.user_uuid = user_uuid
        self.caller_number = caller_number
        self.caller_name = caller_name
        self.dialed_extension = dialed_extension
        self.direction = direction
        self.sip_call_id = sip_call_id
        self.stream_key = "dial-"

    def _payload(self, **overrides):
        payload = {
            "call_id": self.caller_channel_id,
            "conversation_id": self.conversation_id,
            "sip_call_id": self.sip_call_id,
            "direction": self.direction,
            "is_caller": True,
            "user_uuid": self.user_uuid,
            "dialed_extension": self.dialed_extension,
            # On the dialer's own leg the caller id is their own identity, and
            # the connected line is whoever they reached.
            "caller_id_name": self.caller_name,
            "caller_id_number": self.caller_number,
            "peer_caller_id_name": "",
            "peer_caller_id_number": self.dialed_extension,
            "status": "Ringing",
            "talking_to": {},
            "bridges": [],
        }
        payload.update(overrides)
        return payload

    def created(self, **overrides):
        self.emit("call_created", self._payload(**overrides))
        return self

    def answers(self, **overrides):
        """The callee picked up: Asterisk answers the dialer's channel and bridges."""
        self.answered_at = self.clock.stamp
        payload = self._payload(
            status="Up",
            talking_to={f"{self.conversation_id}-callee": None},
            bridges=[f"bridge-{self.conversation_id}"],
        )
        payload.update(overrides)
        self.emit("call_answered", payload)
        return self

    def ends(self, cause=HANGUP_NORMAL_CLEARING, answered=False, **overrides):
        payload = self._payload(
            direction="internal",
            status="Up" if answered else "Ringing",
            answer_time=self.answered_at if answered else None,
            reason_code=cause,
        )
        payload.update(overrides)
        self.emit("call_ended", payload)
        return self


class PbxRing(PbxConversation):
    """One conversation: the events the PBX emits while ringing its members."""

    def __init__(self, case, members, caller_number, caller_name,
                 dialed_extension, direction, conversation_id,
                 caller_sip_call_id="sip-caller", wakeup_per_member=False,
                 ring_timeout=GROUP_RING_TIMEOUT, epoch=1784800000):
        super().__init__(case, conversation_id, epoch)
        self.caller_sip_call_id = caller_sip_call_id
        # Whether each member's push names a channel of its own. Both shapes
        # were captured on 2026-07-23: a group ring forks one Local channel per
        # member and raises Pushmobile on each, so each push names its own
        # channel and carries no SIP Call-ID (that channel has none); a direct
        # call raises it on the caller's channel, before the callee's exists,
        # so every push of that ring names the caller and the caller's INVITE.
        self.wakeup_per_member = wakeup_per_member
        self.ring_timeout = ring_timeout
        self.caller_number = caller_number
        self.caller_name = caller_name
        self.dialed_extension = dialed_extension
        self.direction = direction
        self.trunk_id = self.caller_channel_id
        self.members = {
            login: PbxMember(self, login, user_uuid, index)
            for index, (login, user_uuid) in enumerate(members.items())
        }
        self._legs = {}

    def member(self, login):
        return self.members[login]

    def leg(self, login):
        if login not in self._legs:
            self._legs[login] = PbxLeg(self, self.members[login])
        return self._legs[login]

    def second_device(self, login):
        """Another registered device of the same user, on its own channel."""
        member = self.members[login]
        return PbxLeg(
            self, member,
            leg_id=f"{member.leg_id}-second",
            sip_call_id=f"{member.sip_call_id}-second")

    def mobile_leg(self, login):
        """The dial_mobile internal channel a push-woken member is reached on.

        Wazo originates it with a bare ARI originate, so it never sends a SIP
        INVITE and carries no SIP Call-ID; its own ``call_ended`` is the event
        that settles a member whose softphone never registered.
        """
        member = self.members[login]
        leg = PbxLeg(self, member, leg_id=f"{member.leg_id}-mobile")
        leg.sip_call_id = ""
        return leg

    def trunk(self):
        return PbxTrunk(self)

    def _push_payload(self, member, **overrides):
        payload = {
            "call_id": member.wakeup_id,
            "conversation_id": self.conversation_id,
            "sip_call_id": member.wakeup_sip_call_id,
            "user_uuid": member.user_uuid,
            "peer_caller_id_name": self.caller_name,
            "peer_caller_id_number": self.caller_number,
            "video": False,
            "ring_timeout": self.ring_timeout,
            "mobile_wakeup_timestamp": self.clock.stamp,
        }
        payload.update(overrides)
        return payload

    def push(self, login, **overrides):
        member = self.members[login]
        member.push_payload = self._push_payload(member, **overrides)
        self.emit("odoo_call_push_notification", member.push_payload)
        return self

    def push_all(self, **overrides):
        for login in self.members:
            self.push(login, **overrides)
        return self

    def cancel_push(self, login):
        """Wazo stops ringing a member: it never says why."""
        member = self.members[login]
        self.emit(
            "odoo_call_cancel_push_notification",
            member.push_payload or self._push_payload(member))
        return self

    def cancel_all(self):
        for login in self.members:
            self.cancel_push(login)
        return self


class CapturedPush:
    """One web push, as the service worker would receive it."""

    def __init__(self, call, data, actions, icon, scenario):
        self.login = call.user_id.login
        self.state = data["call_state"]
        self.data = data
        self.actions = [action["action"] for action in actions or ()]
        self.icon = icon
        self.scenario = scenario


class PbxScenarioMixin:
    """Push recording and outcome assertions for scenario tests."""

    def setUpPushRecording(self):
        self.pushes = []
        self.captured_pushes = []

        def capture(call, data, actions, icon, scenario):
            self.captured_pushes.append(CapturedPush(call, data, actions, icon, scenario))
            self.pushes.append((call.user_id.login, data["call_state"]))

        patcher = patch(NOTIFY_SEND, capture)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assertPushActions(self, expected):
        """Assert the buttons each push offered, in order.

        The actions are the only part of a notification the user can act on,
        and they are state-dependent: a ringing call offers Answer/Decline, a
        missed one offers Call Back, and a call already settled offers nothing.
        """
        self.assertEqual(
            [(push.login, push.actions) for push in self.captured_pushes], expected)

    def assertPushes(self, expected):
        """Assert the exact ordered web pushes the scenario produced.

        Recorded at ``_notify_devices_send`` rather than ``_notify_devices`` so
        the eligibility filter and the payload the service worker reads stay
        under test: ``call_state`` here is the field the worker matches its
        transition table against.
        """
        self.assertEqual(self.pushes, expected)

    def assertPushesSince(self, mark, expected):
        self.assertEqual(self.pushes[mark:], expected)

    @contextmanager
    def assertNoPushes(self):
        mark = len(self.pushes)
        yield
        self.assertEqual(self.pushes[mark:], [])

    def clearPushes(self):
        self.pushes.clear()
        self.captured_pushes.clear()

    def assertOutcome(self, expected, direction="incoming"):
        """Assert each user's final call in ``direction``, keyed by login.

        Scoped to the users this test created: the suite runs against a
        persistent dev database whose real calls would otherwise leak in.
        """
        calls = self.env["voip.call"].sudo().search([
            ("direction", "=", direction),
            ("user_id", "in", [user.id for user in self.voip_users.values()]),
        ])
        actual = {}
        for call in calls:
            self.assertNotIn(
                call.user_id.login, actual,
                f"{call.user_id.login} has more than one {direction} call")
            actual[call.user_id.login] = call
        self.assertEqual(sorted(actual), sorted(expected))
        for login, values in expected.items():
            self.assertRecordValues(actual[login], [values])
