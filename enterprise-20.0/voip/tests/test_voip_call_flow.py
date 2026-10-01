from unittest.mock import patch

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI
from odoo.addons.voip.tests.common_voip import (
    VoipPhoneServiceCase,
    pbx_router,
    tts_sound_values,
)


def _capture_pbx_calls():
    calls = []

    def side_effect(route, params, **kwargs):
        calls.append((route, params))
        return pbx_router(route, params)

    return calls, patch.object(
        PhoneServiceAPI,
        "_call_phone_service",
        side_effect=side_effect,
    )


def _start_node():
    return {
        "id": "start",
        "type": "start",
        "outputs": [{
            "id": "next",
            "direction": "output",
            "provides": "flow",
            "maxConnections": 1,
        }],
    }


def _call_group_node(node_id, call_group):
    return {
        "id": node_id,
        "type": "call_group",
        "input": {
            "id": "input",
            "direction": "input",
            "accepts": ["flow"],
        },
        "outputs": [{
            "id": "no_answer",
            "direction": "output",
            "provides": "flow",
            "maxConnections": 1,
        }],
        "record": {
            "resModel": "voip.call.group",
            "resId": call_group.id,
        },
    }


def _record_node(node_id, node_type, record):
    return {
        "id": node_id,
        "type": node_type,
        "input": {
            "id": "input",
            "direction": "input",
            "accepts": ["flow"],
        },
        "outputs": [],
        "record": {
            "resModel": record._name,
            "resId": record.id,
        },
    }


def _queue_node(node_id, queue):
    node = _record_node(node_id, "queue", queue)
    node["outputs"] = [
        {
            "id": output_id,
            "direction": "output",
            "provides": "flow",
            "maxConnections": 1,
        }
        for output_id in ("no_answer", "busy")
    ]
    return node


def _ivr_node(node_id, ivr):
    node = _record_node(node_id, "ivr", ivr)
    node["outputs"] = [
        {
            "id": output_id,
            "direction": "output",
            "provides": "flow",
            "maxConnections": 1,
        }
        for output_id in (
            *(f"option-{option.id}" for option in ivr.option_ids),
            "invalid",
            "timeout",
            "abort",
        )
    ]
    return node


def _hangup_node(node_id, accepts=("flow",)):
    return {
        "id": node_id,
        "type": "hangup",
        "input": {
            "id": "input",
            "direction": "input",
            "accepts": list(accepts),
        },
        "outputs": [],
    }


def _connection(source_node_id, source_port_id, target_node_id):
    return {
        "sourceNodeId": source_node_id,
        "sourcePortId": source_port_id,
        "targetNodeId": target_node_id,
        "targetPortId": "input",
    }


def _time_condition_node(node_id, time_condition):
    node = _record_node(node_id, "time_condition", time_condition)
    node["outputs"] = [
        {"id": "open", "direction": "output", "provides": "flow", "maxConnections": 1},
        {"id": "closed", "direction": "output", "provides": "flow", "maxConnections": 1},
    ]
    return node


@tagged("post_install", "-at_install")
class TestVoipCallFlowValidation(VoipPhoneServiceCase):
    def _create_call_group(self, name):
        return self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": name,
        })

    def test_create_call_flow_with_default_graph(self):
        call_flow = self.env["voip.call.flow"].create({})

        self.assertEqual(call_flow.node_count, 1)
        self.assertEqual(call_flow.graph_data["nodes"][0]["type"], "start")
        self.assertFalse(call_flow.graph_data["connections"])

    def test_terminal_did_cannot_be_assigned_to_call_flow(self):
        call_flow = self.env["voip.call.flow"].create({"name": "Terminal DID flow"})
        for index, state in enumerate(("failure", "released"), start=1):
            with self.subTest(state=state):
                did = self.env["voip.did.number"].create({
                    "did_number": f"+328700020{index}",
                    "did_number_type": "local",
                    "state": state,
                })
                with self.assertRaisesRegex(
                    ValidationError,
                    "Failed or released phone numbers cannot have a destination",
                ):
                    did.destination_ref = call_flow

    def test_non_terminal_did_can_be_assigned_to_call_flow(self):
        call_flow = self.env["voip.call.flow"].create({"name": "Assignable DID flow"})
        for index, state in enumerate(("pending", "suspended"), start=1):
            with self.subTest(state=state):
                did = self.env["voip.did.number"].create({
                    "did_number": f"+328700021{index}",
                    "did_number_type": "local",
                    "state": state,
                })
                did.destination_ref = call_flow
                self.assertEqual(did.destination_ref, call_flow)

    def test_terminal_state_clears_call_flow_destination(self):
        call_flow = self.env["voip.call.flow"].create({"name": "Cleared DID flow"})
        for index, state in enumerate(("failure", "released"), start=1):
            with self.subTest(state=state):
                did = self.env["voip.did.number"].create({
                    "did_number": f"+328700022{index}",
                    "destination_ref": f"voip.call.flow,{call_flow.id}",
                    "did_number_type": "local",
                    "state": "pending",
                })
                did.state = state
                self.assertFalse(did.destination_ref)

    def test_releasing_a_routed_did_number_defers_the_incall_delete_until_commit(self):
        call_flow = self.env["voip.call.flow"].create({"name": "Deferred incall flow"})
        did_number = self.env["voip.did.number"].with_context(voip_skip_pbx_sync=True).create({
            "did_number": "+3287000133",
            "destination_ref": f"voip.call.flow,{call_flow.id}",
            "did_number_type": "local",
            "state": "active",
            "pbx_incall_id": 50,
            "pbx_incall_extension_id": 60,
        })

        calls, patcher = _capture_pbx_calls()
        with patcher:
            did_number.with_context(voip_skip_pbx_sync=False).state = "released"
            self.assertFalse([
                params for route, params in calls if route.endswith("/delete_incall")
            ])
            self.env.cr.postcommit.run()

        delete_incall_calls = [
            params for route, params in calls if route.endswith("/delete_incall")
        ]
        self.assertEqual(len(delete_incall_calls), 1)
        self.assertEqual(delete_incall_calls[0], {"incall_id": 50, "extension_id": 60})
        self.assertFalse(did_number.pbx_incall_id)
        self.assertFalse(did_number.pbx_incall_extension_id)

    def test_rerouting_a_did_number_before_commit_still_deletes_its_old_incall(self):
        """If this DID is released (capturing its old incall/extension pair
        for a deferred delete) and then re-routed with a brand new pair
        within the same transaction, the old pair must still be deleted:
        only checking whether *some* route currently exists would wrongly
        treat that new, unrelated route as proof the old one survived,
        leaking the old incall/extension in Wazo forever."""
        call_flow = self.env["voip.call.flow"].create({"name": "Rerouted flow"})
        did_number = self.env["voip.did.number"].with_context(voip_skip_pbx_sync=True).create({
            "did_number": "+3287000135",
            "destination_ref": f"voip.call.flow,{call_flow.id}",
            "did_number_type": "local",
            "state": "active",
            "pbx_incall_id": 50,
            "pbx_incall_extension_id": 60,
        })

        calls, patcher = _capture_pbx_calls()
        with patcher:
            did_number.with_context(voip_skip_pbx_sync=False).state = "released"
            # Simulate this same DID being re-routed with a brand new pair
            # later in the same transaction, before postcommit ever runs.
            did_number.with_context(voip_skip_pbx_sync=True).write({
                "state": "active",
                "destination_ref": f"voip.call.flow,{call_flow.id}",
                "pbx_incall_id": 91,
                "pbx_incall_extension_id": 92,
            })
            self.env.cr.postcommit.run()

        delete_incall_calls = [
            params for route, params in calls if route.endswith("/delete_incall")
        ]
        self.assertEqual(len(delete_incall_calls), 1)
        self.assertEqual(delete_incall_calls[0], {"incall_id": 50, "extension_id": 60})
        self.assertEqual(did_number.pbx_incall_id, 91)
        self.assertEqual(did_number.pbx_incall_extension_id, 92)

    def test_multiple_start_nodes_are_rejected_before_pbx_sync(self):
        second_start = _start_node()
        second_start["id"] = "second-start"
        graph_data = {
            "nodes": [_start_node(), second_start],
            "connections": [],
        }
        calls, patcher = _capture_pbx_calls()
        with patcher, self.assertRaisesRegex(ValidationError, "exactly one Start node"):
            self.env["voip.call.flow"].create({"graph_data": graph_data})
        self.assertFalse(calls)

    def test_graph_requires_one_start_node(self):
        graph_data = {
            "nodes": [_hangup_node("hangup")],
            "connections": [],
        }

        with self.assertRaisesRegex(ValidationError, "exactly one Start node"):
            self.env["voip.call.flow"].create({"graph_data": graph_data})

    def test_unconnected_start_node_resolves_to_hangup(self):
        call_flow = self.env["voip.call.flow"].create({})

        self.assertEqual(
            call_flow._get_pbx_destination(),
            {"type": "hangup", "cause": "normal"},
        )

    def test_start_node_with_multiple_connections_is_rejected(self):
        graph_data = {
            "nodes": [_start_node(), _hangup_node("first"), _hangup_node("second")],
            "connections": [
                _connection("start", "next", "first"),
                _connection("start", "next", "second"),
            ],
        }
        call_flow = self.env["voip.call.flow"].create({})
        with self.assertRaisesRegex(ValidationError, "saturated port"):
            call_flow.graph_data = graph_data

    def test_start_node_resolves_connected_hangup(self):
        graph_data = {
            "nodes": [_start_node(), _hangup_node("hangup")],
            "connections": [_connection("start", "next", "hangup")],
        }
        call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

        self.assertEqual(
            call_flow._get_pbx_destination(),
            {"type": "hangup", "cause": "normal"},
        )

    def test_terminal_node_pbx_destinations(self):
        audio_message = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Routing message",
            **tts_sound_values("Please hold."),
        })
        call_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({"name": "Routing group", "pbx_group_id": 101})
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Routing queue",
            "pbx_queue_id": 102,
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Routing IVR",
            "menu_sound_id": audio_message.id,
            "pbx_ivr_id": 103,
        })
        # A "Play Audio" node is itself a Menu with no dial choices; its
        # wrapper Menu needs its own sound (a sound can only ever belong to
        # one Menu, see voip.ivr's _menu_sound_unique).
        audio_message_sound = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Routing audio message",
            **tts_sound_values("Please hold."),
        })
        audio_message_ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Routing audio message",
            "menu_sound_id": audio_message_sound.id,
            "is_audio_message": True,
            "pbx_ivr_id": 106,
        })
        voicemail = self.env["voip.voicemail"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Routing voicemail",
            "pbx_voicemail_id": 104,
        })
        user = self.new_voip_user(user_login="call_flow_destination_user")
        user.with_context(voip_skip_pbx_sync=True).voip_pbx_user_id = 105
        extension = self.env["voip.extension"].search([
            ("destination_ref", "=", f"res.users,{user.id}"),
        ])
        destinations = (
            ("call_group", call_group, {"type": "group", "group_id": 101}),
            ("queue", queue, {"type": "queue", "queue_id": 102}),
            ("ivr", ivr, {"type": "ivr", "ivr_id": 103}),
            (
                "audio_message",
                audio_message_ivr,
                {"type": "ivr", "ivr_id": 106},
            ),
            ("voicemail", voicemail, {"type": "voicemail", "voicemail_id": 104}),
            ("user", user, {"type": "user", "user_id": 105}),
            ("contact", self.partner_be, {"type": "outcall", "exten": "3287654321"}),
            ("extension", extension, {"type": "extension", "exten": extension.number}),
        )
        for node_type, record, expected_destination in destinations:
            with self.subTest(node_type=node_type):
                graph_data = {
                    "nodes": [_start_node(), _record_node(node_type, node_type, record)],
                    "connections": [_connection("start", "next", node_type)],
                }
                call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

                self.assertEqual(call_flow._get_pbx_destination(), expected_destination)

    def test_unsupported_pbx_destination_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "not a supported PBX destination"):
            self.env["voip.pbx.service"]._get_pbx_destination(self.env.company)

    def test_outcall_node_pbx_destination(self):
        call_flow = self.env["voip.call.flow"].create({})

        self.assertEqual(
            call_flow._get_node_pbx_destination({
                "type": "outcall",
                "data": {"extension": "+3287654321"},
            }, {call_flow.id}),
            {"type": "outcall", "exten": "3287654321"},
        )

    def test_invalid_connections_are_rejected_before_pbx_sync(self):
        start = _start_node()
        first_hangup = _hangup_node("first")
        second_hangup = _hangup_node("second")
        scenarios = {
            "missing port": {
                "nodes": [start, first_hangup],
                "connections": [_connection("start", "missing", "first")],
            },
            "incompatible ports": {
                "nodes": [start, _hangup_node("first", accepts=("did_entry",))],
                "connections": [_connection("start", "next", "first")],
            },
            "saturated port": {
                "nodes": [start, first_hangup, second_hangup],
                "connections": [
                    _connection("start", "next", "first"),
                    _connection("start", "next", "second"),
                ],
            },
            "duplicate connection": {
                "nodes": [start, first_hangup],
                "connections": [
                    _connection("start", "next", "first"),
                    _connection("start", "next", "first"),
                ],
            },
        }
        calls, patcher = _capture_pbx_calls()
        with patcher:
            for scenario, graph_data in scenarios.items():
                with self.subTest(scenario=scenario), self.assertRaises(ValidationError):
                    self.env["voip.call.flow"].create({"graph_data": graph_data})
        self.assertFalse(calls)

    def test_duplicate_node_ids_are_rejected_before_pbx_sync(self):
        call_group = self._create_call_group("Duplicate node")
        graph_data = {
            "nodes": [_start_node(), _call_group_node("start", call_group)],
            "connections": [],
        }
        calls, patcher = _capture_pbx_calls()
        with patcher, self.assertRaisesRegex(ValidationError, "node IDs must be unique"):
            self.env["voip.call.flow"].create({"graph_data": graph_data})
        self.assertFalse(calls)

    def test_invalid_record_reference_is_rejected_before_pbx_sync(self):
        graph_data = {
            "nodes": [
                _start_node(),
                {
                    "id": "user",
                    "type": "user",
                    "input": {
                        "id": "input",
                        "direction": "input",
                        "accepts": ["flow"],
                    },
                    "outputs": [],
                    "record": {"resModel": "res.users", "resId": 0},
                },
            ],
            "connections": [_connection("start", "next", "user")],
        }
        calls, patcher = _capture_pbx_calls()
        with patcher, self.assertRaisesRegex(ValidationError, "destination.*no longer exists"):
            self.env["voip.call.flow"].create({"graph_data": graph_data})
        self.assertFalse(calls)

    def test_connection_cycle_is_accepted_and_synchronized(self):
        """Cycles between distinct nodes are an intentional pattern (e.g.
        bouncing a caller between two call groups) that a voip_admin is
        trusted to configure correctly; self-connections are allowed too."""
        first_group = self._create_call_group("First group")
        second_group = self._create_call_group("Second group")
        graph_data = {
            "nodes": [
                _start_node(),
                _call_group_node("first", first_group),
                _call_group_node("second", second_group),
            ],
            "connections": [
                _connection("start", "next", "first"),
                _connection("first", "no_answer", "second"),
                _connection("second", "no_answer", "first"),
            ],
        }
        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

        self.assertTrue(calls)
        self.assertEqual(first_group.callflow_id, call_flow)
        self.assertEqual(second_group.callflow_id, call_flow)
        self.assertEqual(first_group.no_answer_destination_ref, second_group)
        self.assertEqual(second_group.no_answer_destination_ref, first_group)

    def test_existing_membership_is_rejected_before_pbx_sync(self):
        call_group = self._create_call_group("Shared group")
        graph_data = {
            "nodes": [_start_node(), _call_group_node("group", call_group)],
            "connections": [],
        }
        self.env["voip.call.flow"].create({"graph_data": graph_data})

        calls, patcher = _capture_pbx_calls()
        with patcher, self.assertRaisesRegex(ValidationError, "already used in the Call Flow"):
            self.env["voip.call.flow"].create({"graph_data": graph_data})
        self.assertFalse(calls)

    def test_call_group_membership_and_no_answer_destination_are_synchronized(self):
        call_group = self._create_call_group("Synchronized group")
        graph_data = {
            "nodes": [
                _start_node(),
                _call_group_node("group", call_group),
                _record_node("contact", "contact", self.partner_be),
            ],
            "connections": [
                _connection("start", "next", "group"),
                _connection("group", "no_answer", "contact"),
            ],
        }
        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

        self.assertEqual(call_group.callflow_id, call_flow)
        self.assertEqual(call_group.no_answer_destination_ref, self.partner_be)
        routing_calls = [
            params
            for route, params in calls
            if route.endswith("/update_group_routing")
        ]
        self.assertEqual(routing_calls[-1]["no_answer_destination"], {
            "type": "outcall",
            "exten": "3287654321",
        })

    def test_queue_membership_and_output_destinations_are_synchronized(self):
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Synchronized queue",
        })
        busy_contact = self.env["res.partner"].create({
            "name": "Busy destination",
            "phone": "+32470000000",
            "country_id": self.env.ref("base.be").id,
        })
        graph_data = {
            "nodes": [
                _start_node(),
                _queue_node("queue", queue),
                _record_node("no-answer", "contact", self.partner_be),
                _record_node("busy", "contact", busy_contact),
            ],
            "connections": [
                _connection("start", "next", "queue"),
                _connection("queue", "no_answer", "no-answer"),
                _connection("queue", "busy", "busy"),
            ],
        }
        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

        self.assertEqual(queue.callflow_id, call_flow)
        self.assertEqual(queue.no_answer_destination_ref, self.partner_be)
        self.assertEqual(queue.busy_destination_ref, busy_contact)
        routing_calls = [
            params
            for route, params in calls
            if route.endswith("/update_queue_routing")
        ]
        self.assertEqual(routing_calls[-1], {
            "queue_id": queue.pbx_queue_id,
            "no_answer_destination": {
                "type": "outcall",
                "exten": "3287654321",
            },
            "busy_destination": {
                "type": "outcall",
                "exten": "32470000000",
            },
        })

    def test_ivr_membership_and_output_destinations_are_synchronized(self):
        audio_message = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "IVR menu",
            **tts_sound_values("Press one."),
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Synchronized IVR",
            "menu_sound_id": audio_message.id,
            "pbx_ivr_id": 106,
        })
        option = self.env["voip.ivr.option"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "ivr_id": ivr.id,
            "digit": "1",
        })
        timeout_contact, invalid_contact, abort_contact = self.env["res.partner"].create([
            {
                "name": "IVR timeout destination",
                "phone": "+32471111111",
                "country_id": self.env.ref("base.be").id,
            },
            {
                "name": "IVR invalid destination",
                "phone": "+32472222222",
                "country_id": self.env.ref("base.be").id,
            },
            {
                "name": "IVR abort destination",
                "phone": "+32473333333",
                "country_id": self.env.ref("base.be").id,
            },
        ])
        graph_data = {
            "nodes": [
                _start_node(),
                _ivr_node("ivr", ivr),
                _record_node("option", "contact", self.partner_be),
                _record_node("timeout", "contact", timeout_contact),
                _record_node("invalid", "contact", invalid_contact),
                _record_node("abort", "contact", abort_contact),
            ],
            "connections": [
                _connection("start", "next", "ivr"),
                _connection("ivr", f"option-{option.id}", "option"),
                _connection("ivr", "timeout", "timeout"),
                _connection("ivr", "invalid", "invalid"),
                _connection("ivr", "abort", "abort"),
            ],
        }
        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

        self.assertEqual(ivr.callflow_id, call_flow)
        self.assertEqual(option.destination_ref, self.partner_be)
        self.assertEqual(ivr.timeout_destination_ref, timeout_contact)
        self.assertEqual(ivr.invalid_destination_ref, invalid_contact)
        self.assertEqual(ivr.abort_destination_ref, abort_contact)
        sync_calls = [
            params
            for route, params in calls
            if route.endswith("/sync_ivr")
        ]
        self.assertEqual(sync_calls[-1]["choices"], [{
            "digit": "1",
            "destination": {
                "type": "outcall",
                "exten": "3287654321",
            },
        }])
        self.assertEqual(
            sync_calls[-1]["timeout_destination"], {"type": "outcall", "exten": "32471111111"}
        )
        self.assertEqual(
            sync_calls[-1]["invalid_destination"], {"type": "outcall", "exten": "32472222222"}
        )
        self.assertEqual(
            sync_calls[-1]["abort_destination"], {"type": "outcall", "exten": "32473333333"}
        )

    def test_unrelated_graph_edit_does_not_resync_an_unchanged_call_group(self):
        call_group = self._create_call_group("Stable group")
        graph_data = {
            "nodes": [
                _start_node(),
                _call_group_node("group", call_group),
                _hangup_node("no-answer"),
            ],
            "connections": [
                _connection("start", "next", "group"),
                _connection("group", "no_answer", "no-answer"),
            ],
        }
        call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow.graph_data = {
                **graph_data,
                "nodes": [*graph_data["nodes"], _hangup_node("unrelated")],
            }

        self.assertFalse(calls)

    def test_unrelated_graph_edit_does_not_resync_an_unchanged_queue(self):
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Stable queue",
        })
        graph_data = {
            "nodes": [
                _start_node(),
                _queue_node("queue", queue),
                _hangup_node("no-answer"),
                _hangup_node("busy"),
            ],
            "connections": [
                _connection("start", "next", "queue"),
                _connection("queue", "no_answer", "no-answer"),
                _connection("queue", "busy", "busy"),
            ],
        }
        call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow.graph_data = {
                **graph_data,
                "nodes": [*graph_data["nodes"], _hangup_node("unrelated")],
            }

        self.assertFalse(calls)

    def test_unrelated_graph_edit_does_not_resync_an_unchanged_ivr(self):
        audio_message = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Stable IVR menu",
            **tts_sound_values("Press one."),
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Stable IVR",
            "menu_sound_id": audio_message.id,
            "pbx_ivr_id": 106,
        })
        option = self.env["voip.ivr.option"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "ivr_id": ivr.id,
            "digit": "1",
        })
        graph_data = {
            "nodes": [
                _start_node(),
                _ivr_node("ivr", ivr),
                _hangup_node("option"),
                _hangup_node("timeout"),
                _hangup_node("invalid"),
                _hangup_node("abort"),
            ],
            "connections": [
                _connection("start", "next", "ivr"),
                _connection("ivr", f"option-{option.id}", "option"),
                _connection("ivr", "timeout", "timeout"),
                _connection("ivr", "invalid", "invalid"),
                _connection("ivr", "abort", "abort"),
            ],
        }
        call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow.graph_data = {
                **graph_data,
                "nodes": [*graph_data["nodes"], _hangup_node("unrelated")],
            }

        self.assertFalse(calls)

    def test_call_flow_owned_records_reject_direct_modifications(self):
        audio_message = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Protected IVR menu",
            **tts_sound_values("Press one."),
        })
        call_group = self._create_call_group("Protected group")
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Protected queue",
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Protected IVR",
            "menu_sound_id": audio_message.id,
            "pbx_ivr_id": 107,
        })
        option = self.env["voip.ivr.option"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "ivr_id": ivr.id,
            "digit": "1",
        })
        graph_data = {
            "nodes": [
                _start_node(),
                _call_group_node("group", call_group),
                _queue_node("queue", queue),
                _ivr_node("ivr", ivr),
            ],
            "connections": [],
        }
        call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})

        membership_scenarios = (
            ("call group", call_group),
            ("queue", queue),
            ("IVR", ivr),
        )
        for scenario, record in membership_scenarios:
            with self.subTest(operation="membership", model=scenario):
                with self.assertRaisesRegex(ValidationError, "membership"):
                    record.callflow_id = False

        destination_scenarios = (
            (
                "call group",
                call_group,
                {"no_answer_destination_ref": f"res.partner,{self.partner_be.id}"},
            ),
            (
                "queue",
                queue,
                {"busy_destination_ref": f"res.partner,{self.partner_be.id}"},
            ),
            (
                "IVR",
                ivr,
                {"timeout_destination_ref": f"res.partner,{self.partner_be.id}"},
            ),
        )
        for scenario, record, values in destination_scenarios:
            with self.subTest(operation="destination", model=scenario):
                with self.assertRaisesRegex(ValidationError, "PBX destinations"):
                    record.write(values)

        with self.assertRaisesRegex(ValidationError, "options of an IVR"):
            ivr.option_ids = [Command.create({"digit": "2"})]
        with self.assertRaisesRegex(ValidationError, "options of an IVR"):
            option.digit = "2"
        with self.assertRaisesRegex(ValidationError, "options of an IVR"):
            self.env["voip.ivr.option"].create({
                "ivr_id": ivr.id,
                "digit": "2",
            })

        create_scenarios = (
            ("voip.call.group", {"name": "Invalid group"}),
            ("voip.queue", {"name": "Invalid queue"}),
            (
                "voip.ivr",
                {"name": "Invalid IVR", "menu_sound_id": audio_message.id},
            ),
        )
        for model_name, values in create_scenarios:
            with self.subTest(operation="create membership", model=model_name):
                with self.assertRaisesRegex(ValidationError, "membership"):
                    self.env[model_name].create({
                        **values,
                        "callflow_id": call_flow.id,
                    })

        calls, patcher = _capture_pbx_calls()
        with patcher:
            for scenario, record in membership_scenarios:
                with self.subTest(operation="delete", model=scenario):
                    with self.assertRaisesRegex(ValidationError, "Remove.*Call Flow"):
                        record.unlink()
                    self.assertTrue(record.exists())
        self.assertFalse(calls)

    def test_removing_nodes_releases_memberships_and_destinations(self):
        audio_message = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Released IVR menu",
            **tts_sound_values("Press one."),
        })
        call_group = self._create_call_group("Released group")
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Released queue",
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Released IVR",
            "menu_sound_id": audio_message.id,
            "pbx_ivr_id": 108,
        })
        option = self.env["voip.ivr.option"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "ivr_id": ivr.id,
            "digit": "1",
        })
        graph_data = {
            "nodes": [
                _start_node(),
                _call_group_node("group", call_group),
                _queue_node("queue", queue),
                _ivr_node("ivr", ivr),
                _record_node("destination", "contact", self.partner_be),
            ],
            "connections": [
                _connection("start", "next", "group"),
                _connection("group", "no_answer", "destination"),
                _connection("queue", "no_answer", "destination"),
                _connection("queue", "busy", "destination"),
                _connection("ivr", f"option-{option.id}", "destination"),
                _connection("ivr", "timeout", "destination"),
            ],
        }
        call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})
        self.assertEqual(call_group.no_answer_destination_ref, self.partner_be)
        self.assertEqual(queue.no_answer_destination_ref, self.partner_be)
        self.assertEqual(queue.busy_destination_ref, self.partner_be)
        self.assertEqual(option.destination_ref, self.partner_be)
        self.assertEqual(ivr.timeout_destination_ref, self.partner_be)

        call_flow.graph_data = {
            "nodes": [_start_node()],
            "connections": [],
        }

        self.assertFalse(call_group.callflow_id)
        self.assertFalse(call_group.no_answer_destination_ref)
        self.assertFalse(queue.callflow_id)
        self.assertFalse(queue.no_answer_destination_ref)
        self.assertFalse(queue.busy_destination_ref)
        self.assertFalse(ivr.callflow_id)
        self.assertFalse(ivr.timeout_destination_ref)
        self.assertFalse(ivr.invalid_destination_ref)
        self.assertFalse(ivr.abort_destination_ref)
        self.assertFalse(option.destination_ref)

        for record in (call_group, queue, ivr):
            record.with_context(voip_skip_pbx_sync=True).unlink()
            self.assertFalse(record.exists())

    def test_archived_call_flow_no_longer_routes_did_calls(self):
        call_flow = self.env["voip.call.flow"].create({
            "graph_data": {
                "nodes": [
                    _start_node(),
                    _record_node("contact", "contact", self.partner_be),
                ],
                "connections": [_connection("start", "next", "contact")],
            },
        })
        self.env["voip.did.number"].with_context(voip_skip_pbx_sync=True).create({
            "did_number": "+3287000123",
            "destination_ref": f"voip.call.flow,{call_flow.id}",
            "did_number_type": "local",
            "state": "active",
        })
        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow.active = False
            self.assertIsNone(call_flow._get_pbx_destination())
            archived_sync = next(
                params
                for route, params in reversed(calls)
                if route.endswith("/sync_incall")
            )
            calls.clear()
            call_flow.active = True
            restored_sync = next(
                params
                for route, params in reversed(calls)
                if route.endswith("/sync_incall")
            )

        self.assertIsNone(archived_sync["destination"])
        self.assertIsNone(archived_sync["schedule_id"])
        self.assertEqual(restored_sync["destination"], {
            "type": "outcall",
            "exten": "3287654321",
        })
        self.assertIsNone(restored_sync["schedule_id"])

    def test_extension_renumber_resyncs_call_flow_routes(self):
        call_group = self._create_call_group("Extension target")
        extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "number": "9511",
            "destination_ref": f"voip.call.group,{call_group.id}",
            "pbx_extension_id": 40,
        })
        call_flow = self.env["voip.call.flow"].create({
            "name": "Extension route",
            "graph_data": {
                "nodes": [
                    _start_node(),
                    _record_node("extension", "extension", extension),
                ],
                "connections": [_connection("start", "next", "extension")],
            },
        })
        self.env["voip.did.number"].with_context(voip_skip_pbx_sync=True).create({
            "did_number": "+3287000952",
            "destination_ref": f"voip.call.flow,{call_flow.id}",
            "did_number_type": "local",
            "state": "active",
        })

        calls, patcher = _capture_pbx_calls()
        with patcher:
            extension.with_context(voip_skip_pbx_sync=False).number = "9512"

        sync_values = next(
            params
            for route, params in reversed(calls)
            if route.endswith("/sync_incall")
        )
        self.assertEqual(sync_values["destination"], {
            "type": "extension",
            "exten": "9512",
        })

    def test_deleting_call_flow_clears_phone_number_destination(self):
        call_flow = self.env["voip.call.flow"].create({"name": "Referenced flow"})
        reference = f"voip.call.flow,{call_flow.id}"
        did_number = self.env["voip.did.number"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "did_number": "+3287000126",
            "destination_ref": reference,
            "did_number_type": "local",
            "state": "active",
        })

        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow.unlink()
        self.assertFalse(calls)
        self.assertFalse(call_flow.exists())
        self.assertFalse(did_number.destination_ref)

    def test_deleting_call_flow_releases_members_and_time_conditions(self):
        audio_message = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Deleted flow IVR menu",
            **tts_sound_values("Press one."),
        })
        call_group = self._create_call_group("Deleted flow group")
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Deleted flow queue",
            "pbx_queue_id": 112,
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Deleted flow IVR",
            "menu_sound_id": audio_message.id,
            "pbx_ivr_id": 113,
        })
        option = self.env["voip.ivr.option"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "ivr_id": ivr.id,
            "digit": "1",
        })
        time_condition = self.env["voip.time.condition"].create({
            "name": "Deleted flow time condition",
        })
        graph_data = {
            "nodes": [
                _start_node(),
                _call_group_node("group", call_group),
                _time_condition_node("tc", time_condition),
                _queue_node("queue", queue),
                _ivr_node("ivr", ivr),
                _record_node("destination", "contact", self.partner_be),
            ],
            "connections": [
                _connection("start", "next", "tc"),
                _connection("tc", "open", "group"),
                _connection("tc", "closed", "destination"),
                _connection("group", "no_answer", "destination"),
                _connection("queue", "no_answer", "destination"),
                _connection("queue", "busy", "destination"),
                _connection("ivr", f"option-{option.id}", "destination"),
                _connection("ivr", "timeout", "destination"),
            ],
        }
        call_flow = self.env["voip.call.flow"].create({"graph_data": graph_data})
        pbx_schedule_id = time_condition.pbx_schedule_id
        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow.unlink()
            self.env.cr.postcommit.run()

        self.assertTrue(call_group.exists())
        self.assertFalse(call_group.callflow_id)
        self.assertFalse(call_group.no_answer_destination_ref)
        self.assertTrue(queue.exists())
        self.assertFalse(queue.callflow_id)
        self.assertFalse(queue.no_answer_destination_ref)
        self.assertFalse(queue.busy_destination_ref)
        self.assertTrue(ivr.exists())
        self.assertFalse(ivr.callflow_id)
        self.assertFalse(ivr.timeout_destination_ref)
        self.assertFalse(ivr.invalid_destination_ref)
        self.assertFalse(ivr.abort_destination_ref)
        self.assertFalse(option.destination_ref)
        self.assertTrue(time_condition.exists())
        self.assertFalse(time_condition.callflow_id)
        self.assertFalse(time_condition.open_destination_ref)
        self.assertFalse(time_condition.closed_destination_ref)
        self.assertFalse(time_condition.pbx_schedule_id)
        self.assertIn(
            {"schedule_id": pbx_schedule_id},
            [
                params
                for route, params in calls
                if route.endswith("/delete_schedule")
            ],
        )
