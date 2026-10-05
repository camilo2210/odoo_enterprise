from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.voip.tests.common_voip import VoipPhoneServiceCase

from .test_voip_call_flow import (
    _call_group_node,
    _capture_pbx_calls,
    _connection,
    _hangup_node,
    _queue_node,
    _record_node,
    _start_node,
    _time_condition_node,
)


@tagged("voip", "post_install", "-at_install")
class TestVoipCallFlowTimeCondition(VoipPhoneServiceCase):
    def _create_time_condition(self, **vals):
        return self.env["voip.time.condition"].create({"timezone": "UTC", **vals})

    def _create_graph(self, time_condition):
        return {
            "nodes": [
                _start_node(),
                _time_condition_node("condition", time_condition),
                _record_node("open", "contact", self.partner_be),
                _hangup_node("closed"),
            ],
            "connections": [
                _connection("start", "next", "condition"),
                _connection("condition", "open", "open"),
                _connection("condition", "closed", "closed"),
            ],
        }

    def test_syncs_open_and_closed_periods_and_incall_schedule(self):
        time_condition = self._create_time_condition(
            name="Office hours",
            period_ids=[
                Command.create({
                    "mode": "open",
                    "all_day": False,
                    "hours_start": 9.0,
                    "hours_end": 17.0,
                    "week_days": "1-5",
                }),
                Command.create({
                    "mode": "closed",
                    "month_days": "25",
                    "months": "12",
                }),
            ],
        )
        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow = self.env["voip.call.flow"].create({
                "graph_data": self._create_graph(time_condition),
            })
            did = self.env["voip.did.number"].with_context(
                voip_skip_pbx_sync=True
            ).create({
                "did_number": "+3287000312",
                "destination_ref": f"voip.call.flow,{call_flow.id}",
                "did_number_type": "local",
                "state": "active",
            })
            did.with_context(voip_skip_pbx_sync=False)._sync_pbx_incall()

        schedule_values = next(
            params for route, params in calls if route.endswith("/sync_schedule")
        )
        self.assertEqual(
            schedule_values["schedule_name"],
            f"Odoo Time Condition {time_condition.id}: Office hours",
        )
        self.assertNotIn("enabled", schedule_values)
        self.assertEqual(schedule_values["closed_destination"], {
            "type": "hangup",
            "cause": "normal",
        })
        self.assertEqual(schedule_values["open_periods"], [{
            "hours_start": "09:00",
            "hours_end": "17:00",
            "week_days": [1, 2, 3, 4, 5],
            "month_days": list(range(1, 32)),
            "months": list(range(1, 13)),
        }])
        self.assertEqual(schedule_values["exceptional_periods"], [{
            "hours_start": "00:00",
            "hours_end": "23:59",
            "week_days": list(range(1, 8)),
            "month_days": [25],
            "months": [12],
            "destination": {"type": "hangup", "cause": "normal"},
        }])
        incall_values = next(
            params for route, params in calls if route.endswith("/sync_incall")
        )
        self.assertEqual(incall_values["destination"], {
            "type": "outcall",
            "exten": "3287654321",
        })
        self.assertEqual(incall_values["schedule_id"], time_condition.pbx_schedule_id)
        self.assertEqual(time_condition.callflow_id, call_flow)
        self.assertEqual(time_condition.open_destination_ref, self.partner_be)
        self.assertFalse(time_condition.closed_destination_ref)

    def test_period_modification_resyncs_existing_schedule(self):
        time_condition = self._create_time_condition(period_ids=[Command.create({
            "mode": "open",
        })])
        calls, patcher = _capture_pbx_calls()
        with patcher:
            self.env["voip.call.flow"].create({
                "graph_data": self._create_graph(time_condition),
            })
            calls.clear()
            time_condition.period_ids.write({
                "all_day": False,
                "hours_start": 10.0,
                "hours_end": 16.0,
            })

        schedule_values = next(
            params for route, params in calls if route.endswith("/sync_schedule")
        )
        self.assertEqual(schedule_values["schedule_id"], time_condition.pbx_schedule_id)
        self.assertEqual(schedule_values["open_periods"][0]["hours_start"], "10:00")
        self.assertEqual(schedule_values["open_periods"][0]["hours_end"], "16:00")

    def test_unconnected_outputs_fall_back_to_hangup(self):
        time_condition = self._create_time_condition(period_ids=[Command.create({
            "mode": "closed",
        })])
        graph = self._create_graph(time_condition)
        graph["connections"] = graph["connections"][:1]
        calls, patcher = _capture_pbx_calls()
        with patcher:
            self.env["voip.call.flow"].create({"graph_data": graph})

        schedule_values = next(
            params for route, params in calls if route.endswith("/sync_schedule")
        )
        hangup = {"type": "hangup", "cause": "normal"}
        self.assertEqual(schedule_values["closed_destination"], hangup)
        self.assertEqual(schedule_values["exceptional_periods"][0]["destination"], hangup)

    def test_orphan_condition_does_not_require_a_group_or_queue_owner(self):
        time_condition = self._create_time_condition()
        graph = self._create_graph(time_condition)
        graph["connections"][0] = _connection("start", "next", "open")
        _, patcher = _capture_pbx_calls()
        with patcher:
            call_flow = self.env["voip.call.flow"].create({"graph_data": graph})

        self.assertEqual(time_condition.callflow_id, call_flow)
        self.assertFalse(time_condition.call_group_id)
        self.assertFalse(time_condition.queue_id)

    def test_second_condition_can_be_attached_to_a_call_group(self):
        root_condition = self._create_time_condition(name="Main line hours")
        group_condition = self._create_time_condition(name="Support hours")
        call_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True
        ).create({
            "name": "Support",
            "pbx_group_id": 111,
            "pbx_group_uuid": "11111111-1111-1111-1111-111111111111",
        })
        graph = self._create_graph(root_condition)
        graph["nodes"].extend([
            _time_condition_node("group-condition", group_condition),
            _call_group_node("group", call_group),
        ])
        graph["connections"][1] = _connection(
            "condition", "open", "group-condition"
        )
        graph["connections"].extend([
            _connection("group-condition", "open", "group"),
            _connection("group-condition", "closed", "closed"),
        ])
        calls, patcher = _capture_pbx_calls()
        with patcher:
            self.env["voip.call.flow"].create({"graph_data": graph})

        self.assertEqual(group_condition.call_group_id, call_group)
        self.assertFalse(group_condition.queue_id)
        attachment = next(
            params for route, params in calls if route.endswith("/sync_group_schedule")
        )
        self.assertEqual(attachment, {
            "group_uuid": call_group.pbx_group_uuid,
            "schedule_id": group_condition.pbx_schedule_id,
        })

    def test_non_root_condition_can_be_attached_to_a_queue(self):
        time_condition = self._create_time_condition(name="Queue hours")
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support queue",
            "pbx_queue_id": 222,
        })
        graph = {
            "nodes": [
                _start_node(),
                _hangup_node("hangup"),
                _time_condition_node("condition", time_condition),
                _queue_node("queue", queue),
            ],
            "connections": [
                _connection("start", "next", "hangup"),
                _connection("condition", "open", "queue"),
                _connection("condition", "closed", "hangup"),
            ],
        }
        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow = self.env["voip.call.flow"].create({"graph_data": graph})

        self.assertEqual(time_condition.queue_id, queue)
        attachment = next(
            params for route, params in calls if route.endswith("/sync_queue_schedule")
        )
        self.assertEqual(attachment, {
            "queue_id": queue.pbx_queue_id,
            "schedule_id": time_condition.pbx_schedule_id,
        })

        calls.clear()
        with patcher:
            call_flow.graph_data = {
                "nodes": [_start_node(), _hangup_node("hangup"), _queue_node("queue", queue)],
                "connections": [_connection("start", "next", "hangup")],
            }
        detachment = next(
            params for route, params in calls if route.endswith("/sync_queue_schedule")
        )
        self.assertEqual(detachment, {
            "queue_id": queue.pbx_queue_id,
            "schedule_id": None,
        })

    def test_used_condition_cannot_be_deleted_from_its_form(self):
        time_condition = self._create_time_condition()
        _, patcher = _capture_pbx_calls()
        with patcher:
            self.env["voip.call.flow"].create({
                "graph_data": self._create_graph(time_condition),
            })
            with self.assertRaisesRegex(ValidationError, "Remove this record"):
                time_condition.unlink()

    def test_removing_node_keeps_condition_and_deletes_schedule(self):
        time_condition = self._create_time_condition()
        calls, patcher = _capture_pbx_calls()
        with patcher:
            call_flow = self.env["voip.call.flow"].create({
                "graph_data": self._create_graph(time_condition),
            })
            schedule_id = time_condition.pbx_schedule_id
            calls.clear()
            call_flow.graph_data = {
                "nodes": [_start_node(), _hangup_node("hangup")],
                "connections": [_connection("start", "next", "hangup")],
            }
            self.env.cr.postcommit.run()

        self.assertTrue(time_condition.exists())
        self.assertFalse(time_condition.callflow_id)
        self.assertFalse(time_condition.open_destination_ref)
        self.assertFalse(time_condition.closed_destination_ref)
        self.assertFalse(time_condition.pbx_schedule_id)
        deletion = next(
            params for route, params in calls if route.endswith("/delete_schedule")
        )
        self.assertEqual(deletion["schedule_id"], schedule_id)
