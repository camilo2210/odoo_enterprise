import base64
import json

from odoo import Command
from odoo.tests import new_test_user, tagged
from odoo.tools import BinaryBytes

from odoo.addons.voip.models.pbx_service import PBX_TENANT_RECOVERY_SCHEMA_VERSION
from odoo.addons.voip.models.phone_service_api import CLIENT_UUID_PARAM
from odoo.addons.voip.tests.common_voip import VoipPhoneServiceCase, capture_pbx_calls
from odoo.addons.voip.tools.wav import encode_wav, pack_int16_samples

from .test_voip_call_flow import (
    _call_group_node,
    _connection,
    _hangup_node,
    _record_node,
    _start_node,
    _time_condition_node,
)


FORBIDDEN_WAZO_ID_KEYS = {
    "extension_id",
    "group_id",
    "group_uuid",
    "incall_extension_id",
    "incall_id",
    "ivr_id",
    "line_id",
    "moh_uuid",
    "queue_id",
    "schedule_id",
    "user_id",
    "user_uuid",
    "voicemail_id",
}


def _wav_data(value=0):
    return BinaryBytes(encode_wav(
        pack_int16_samples([value] * 8),
        channels=1,
        sample_width=2,
        frame_rate=8000,
    ))


def _outcall_node(node_id, number):
    return {
        "id": node_id,
        "type": "outcall",
        "data": {"extension": number},
        "input": {
            "id": "input",
            "direction": "input",
            "accepts": ["flow"],
        },
        "outputs": [],
    }


@tagged("voip", "post_install", "-at_install")
class TestPbxTenantRecoveryPayload(VoipPhoneServiceCase):
    def _create_user(self, login, name=None):
        user = new_test_user(
            self.env,
            login=login,
            name=name or login.title(),
            voip_username=f"{login}-sip",
            voip_secret=f"{login}-sip-secret",
        )
        user.res_users_settings_id.with_context(
            voip_skip_config_bus=True,
            voip_skip_pbx_sync=True,
        ).voip_provider_id = self.env.ref("voip.odoo_provider")
        return user

    def _create_sound(self, name, value=0):
        return self.env["voip.sound"].with_context(voip_skip_pbx_sync=True).create({
            "name": name,
            "source_type": "upload",
            "data": _wav_data(value),
            "data_filename": f"{name.lower().replace(' ', '_')}.wav",
        })

    def _payload_by_id(self, payload, key):
        return {item["odoo_id"]: item for item in payload[key]}

    def _assert_no_wazo_ids(self, value):
        if isinstance(value, dict):
            self.assertFalse(FORBIDDEN_WAZO_ID_KEYS & value.keys())
            for item in value.values():
                self._assert_no_wazo_ids(item)
        elif isinstance(value, list):
            for item in value:
                self._assert_no_wazo_ids(item)

    def test_payload_has_versioned_json_contract_and_is_deterministic(self):
        service = self.env["voip.pbx.service"]

        first_payload = service._get_tenant_recovery_payload()
        second_payload = service._get_tenant_recovery_payload()

        self.assertEqual(first_payload, second_payload)
        self.assertEqual(
            list(first_payload),
            [
                "schema_version",
                "client_uuid",
                "default_outgoing_number",
                "sounds",
                "music_on_holds",
                "users",
                "extensions",
                "voicemails",
                "groups",
                "queues",
                "ivrs",
                "schedules",
                "incalls",
            ],
        )
        self.assertEqual(
            first_payload["schema_version"],
            PBX_TENANT_RECOVERY_SCHEMA_VERSION,
        )
        self.assertEqual(
            first_payload["client_uuid"],
            self.env["ir.config_parameter"].get_str(CLIENT_UUID_PARAM),
        )
        json.dumps(first_payload)

    def test_recovery_destinations_use_stable_odoo_references(self):
        service = self.env["voip.pbx.service"]
        user = self._create_user("destination-user")
        extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "number": "4101",
            "destination_ref": f"res.users,{user.id}",
            "pbx_extension_id": 901,
        })
        sound = self._create_sound("Destination sound")
        call_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Destination group",
            "pbx_group_id": 902,
            "pbx_group_uuid": "old-group-uuid",
        })
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Destination queue",
            "pbx_queue_id": 903,
        })
        voicemail = self.env["voip.voicemail"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Destination voicemail",
            "pbx_voicemail_id": 904,
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Destination menu",
            "menu_sound_id": sound.id,
            "pbx_ivr_id": 905,
        })
        destinations = (
            (user, {"type": "user", "odoo_id": user.id}),
            (extension, {"type": "extension", "exten": "4101"}),
            (sound, {"type": "sound", "filename": sound._get_pbx_sound_filename()}),
            (call_group, {"type": "group", "odoo_id": call_group.id}),
            (queue, {"type": "queue", "odoo_id": queue.id}),
            (ivr, {"type": "ivr", "odoo_id": ivr.id}),
            (voicemail, {"type": "voicemail", "odoo_id": voicemail.id}),
            (self.partner_be, {"type": "outcall", "exten": "3287654321"}),
        )

        for destination, expected in destinations:
            with self.subTest(model=destination._name):
                self.assertEqual(
                    service._get_pbx_recovery_destination(destination),
                    expected,
                )
        self.assertIsNone(service._get_pbx_recovery_destination(False))

    def test_payload_contains_complete_standalone_configuration(self):
        service = self.env["voip.pbx.service"]
        sound = self._create_sound("Welcome", value=1)
        music_on_hold = self.env["voip.music.on.hold"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Support waiting music",
            "sort": "random_start",
            "pbx_moh_uuid": "old-moh-uuid",
            "pbx_moh_name": "old-moh-name",
            "track_ids": [Command.create({
                "sequence": 20,
                "audio_message_id": sound.id,
            })],
        })
        user = self._create_user("support-agent", "Support Agent")
        user.with_context(voip_skip_pbx_sync=True).write({
            "voip_pbx_agent_id": 906,
            "voip_pbx_line_id": 907,
            "voip_pbx_user_id": 908,
            "voip_pbx_user_uuid": "old-user-uuid",
        })
        user_extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "number": "4201",
            "destination_ref": f"res.users,{user.id}",
            "pbx_extension_id": 909,
        })
        voicemail = self.env["voip.voicemail"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Support mailbox",
            "audio_message_id": sound.id,
            "pbx_voicemail_id": 910,
            "pbx_voicemail_number": "9010",
        })
        call_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Support group",
            "user_ids": [Command.link(user.id)],
            "music_on_hold_id": music_on_hold.id,
            "no_answer_destination_ref": f"voip.voicemail,{voicemail.id}",
            "pbx_group_id": 911,
            "pbx_group_uuid": "old-support-group-uuid",
            "timeout": 25,
            "user_timeout": 12,
        })
        group_extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "number": "4202",
            "destination_ref": f"voip.call.group,{call_group.id}",
            "pbx_extension_id": 912,
        })
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support queue",
            "allowed_user_ids": [Command.link(user.id)],
            "busy_destination_ref": f"voip.call.group,{call_group.id}",
            "no_answer_destination_ref": f"voip.sound,{sound.id}",
            "music_on_hold_id": music_on_hold.id,
            "pbx_queue_id": 913,
            "strategy": "leastrecent",
            "agent_timeout": 18,
            "queue_timeout": 75,
            "retry_on_timeout": 7,
            "max_waiting_calls": 4,
        })
        queue_extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "number": "4203",
            "destination_ref": f"voip.queue,{queue.id}",
            "pbx_extension_id": 914,
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support menu",
            "menu_sound_id": sound.id,
            "invalid_destination_ref": f"voip.call.group,{call_group.id}",
            "timeout_destination_ref": f"voip.queue,{queue.id}",
            "abort_destination_ref": f"voip.voicemail,{voicemail.id}",
            "option_ids": [Command.create({
                "digit": "1",
                "destination_ref": f"res.partner,{self.partner_be.id}",
            })],
            "pbx_ivr_id": 915,
            "max_tries": 4,
            "timeout": 9,
        })
        user.res_users_settings_id.with_context(voip_skip_pbx_sync=True).write({
            "voip_no_answer_destination_type": "forward",
            "voip_no_answer_destination_kind": "voip.voicemail",
            "voip_no_answer_destination_ref": f"voip.voicemail,{voicemail.id}",
            "voip_no_answer_timeout": 14,
            "voip_busy_destination_type": "forward",
            "voip_busy_destination_kind": "external",
            "voip_busy_outcall_number": "+32470000000",
            "voip_disconnected_destination_type": "forward",
            "voip_disconnected_destination_kind": "external",
            "voip_disconnected_outcall_number": "+32470000001",
        })
        did = self.env["voip.did.number"].with_context(voip_skip_pbx_sync=True).create({
            "did_number": "+3287000401",
            "destination_ref": f"res.users,{user.id}",
            "did_number_type": "local",
            "is_default_outgoing_number": True,
            "pbx_incall_id": 916,
            "pbx_incall_extension_id": 917,
            "state": "active",
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            payload = service._get_tenant_recovery_payload()

        self.assertFalse(calls)
        self.assertEqual(payload["default_outgoing_number"], did.did_number)
        self._assert_no_wazo_ids(payload)

        sounds = self._payload_by_id(payload, "sounds")
        self.assertEqual(
            base64.b64decode(sounds[sound.id]["content_base64"]),
            sound._get_pbx_sound_content(),
        )
        self.assertEqual(sounds[sound.id]["format"], "wav")

        mohs = self._payload_by_id(payload, "music_on_holds")
        self.assertEqual(mohs[music_on_hold.id], {
            "odoo_id": music_on_hold.id,
            "name": "Support waiting music",
            "sort": "random_start",
            "files": [{
                "filename": f"001_odoo_audio_{sound.id}.wav",
                "sound_odoo_id": sound.id,
            }],
        })

        users = self._payload_by_id(payload, "users")
        self.assertEqual(users[user.id]["sip_secret"], "support-agent-sip-secret")
        self.assertEqual(users[user.id]["extension_odoo_id"], user_extension.id)
        self.assertEqual(users[user.id]["outgoing_caller_id"], did.did_number)
        self.assertEqual(users[user.id]["routing"], {
            "no_answer_destination": {"type": "voicemail", "odoo_id": voicemail.id},
            "busy_destination": {"type": "outcall", "exten": "32470000000"},
            "fail_destination": {"type": "outcall", "exten": "32470000001"},
            "always_destination": None,
            "no_answer_timeout": 14,
        })

        extensions = self._payload_by_id(payload, "extensions")
        self.assertEqual(extensions[user_extension.id]["destination"], {
            "model": "res.users",
            "odoo_id": user.id,
        })
        self.assertEqual(extensions[group_extension.id]["destination"], {
            "model": "voip.call.group",
            "odoo_id": call_group.id,
        })
        self.assertEqual(extensions[queue_extension.id]["destination"], {
            "model": "voip.queue",
            "odoo_id": queue.id,
        })

        groups = self._payload_by_id(payload, "groups")
        self.assertEqual(groups[call_group.id]["user_odoo_ids"], [user.id])
        self.assertEqual(
            groups[call_group.id]["no_answer_destination"],
            {"type": "voicemail", "odoo_id": voicemail.id},
        )

        queues = self._payload_by_id(payload, "queues")
        self.assertEqual(queues[queue.id]["agents"], [{
            "user_odoo_id": user.id,
            "extension_number": user_extension.number,
            "firstname": "Support",
            "lastname": "Agent",
            "sequence": 1,
        }])
        self.assertEqual(
            queues[queue.id]["busy_destination"],
            {"type": "group", "odoo_id": call_group.id},
        )

        ivrs = self._payload_by_id(payload, "ivrs")
        self.assertEqual(
            ivrs[ivr.id]["invalid_destination"],
            {"type": "group", "odoo_id": call_group.id},
        )
        self.assertEqual(
            ivrs[ivr.id]["timeout_destination"],
            {"type": "queue", "odoo_id": queue.id},
        )
        self.assertEqual(
            ivrs[ivr.id]["abort_destination"],
            {"type": "voicemail", "odoo_id": voicemail.id},
        )
        self.assertEqual(ivrs[ivr.id]["choices"], [{
            "digit": "1",
            "destination": {"type": "outcall", "exten": "3287654321"},
        }])

        voicemails = self._payload_by_id(payload, "voicemails")
        self.assertEqual(voicemails[voicemail.id]["number"], "9010")
        self.assertEqual(voicemails[voicemail.id]["greeting"], "unavailable")
        self.assertEqual(
            voicemails[voicemail.id]["greeting_sound_odoo_id"], sound.id,
        )
        incalls = self._payload_by_id(payload, "incalls")
        self.assertEqual(incalls[did.id]["destination"], {
            "type": "user",
            "odoo_id": user.id,
        })
        self.assertIsNone(incalls[did.id]["schedule_odoo_id"])

    def test_call_flow_routes_and_schedules_are_normalized(self):
        call_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({"name": "Open hours group", "pbx_group_id": 920})
        condition = self.env["voip.time.condition"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Office hours",
            "timezone": "Europe/Brussels",
            "pbx_schedule_id": 921,
            "period_ids": [
                Command.create({
                    "mode": "open",
                    "all_day": False,
                    "hours_start": 9.0,
                    "hours_end": 17.5,
                    "week_days": "1-5",
                }),
                Command.create({
                    "mode": "closed",
                    "month_days": "25",
                    "months": "12",
                }),
            ],
        })
        graph_data = {
            "nodes": [
                _start_node(),
                _time_condition_node("condition", condition),
                _call_group_node("open", call_group),
                _outcall_node("closed", "+32471111111"),
                _hangup_node("after-group"),
            ],
            "connections": [
                _connection("start", "next", "condition"),
                _connection("condition", "open", "open"),
                _connection("condition", "closed", "closed"),
                _connection("open", "no_answer", "after-group"),
            ],
        }
        call_flow = self.env["voip.call.flow"].create({
            "name": "Office routing",
            "graph_data": graph_data,
        })
        did = self.env["voip.did.number"].with_context(voip_skip_pbx_sync=True).create({
            "did_number": "+3287000402",
            "destination_ref": f"voip.call.flow,{call_flow.id}",
            "did_number_type": "local",
            "state": "active",
        })

        payload = self.env["voip.pbx.service"]._get_tenant_recovery_payload()

        schedule = self._payload_by_id(payload, "schedules")[condition.id]
        self.assertEqual(
            schedule["closed_destination"],
            {"type": "outcall", "exten": "32471111111"},
        )
        self.assertEqual(schedule["open_periods"][0]["hours_start"], "09:00")
        self.assertEqual(schedule["open_periods"][0]["hours_end"], "17:30")
        self.assertEqual(schedule["exceptional_periods"][0]["month_days"], [25])
        self.assertEqual(
            schedule["exceptional_periods"][0]["destination"],
            schedule["closed_destination"],
        )
        self.assertIsNone(schedule["owner"])
        incall = self._payload_by_id(payload, "incalls")[did.id]
        self.assertEqual(incall["destination"], {
            "type": "group",
            "odoo_id": call_group.id,
        })
        self.assertEqual(incall["schedule_odoo_id"], condition.id)
        groups = self._payload_by_id(payload, "groups")
        self.assertEqual(
            groups[call_group.id]["no_answer_destination"],
            {"type": "hangup", "cause": "normal"},
        )

    def test_immediate_user_forward_is_kept_separate_from_no_answer(self):
        user = self._create_user("immediate-forward")
        settings = user.res_users_settings_id
        settings.with_context(voip_skip_pbx_sync=True).write({
            "voip_no_answer_destination_type": "forward",
            "voip_no_answer_destination_kind": "external",
            "voip_no_answer_immediate_destination": "+32472222222",
            "voip_no_answer_outcall_number": "+32473333333",
            "voip_no_answer_timeout": 0,
        })

        payload = self.env["voip.pbx.service"]._get_tenant_recovery_payload()
        routing = self._payload_by_id(payload, "users")[user.id]["routing"]

        self.assertIsNone(routing["no_answer_destination"])
        self.assertEqual(routing["always_destination"], "+32472222222")
        self.assertEqual(routing["no_answer_timeout"], 0)

    def test_non_serving_resources_are_excluded(self):
        user = self._create_user("former-phone-user")
        user.res_users_settings_id.with_context(
            voip_skip_pbx_sync=True,
        ).voip_provider_id = False
        user.with_context(voip_skip_pbx_sync=True).write({
            "voip_pbx_user_id": 930,
            "voip_pbx_user_uuid": "stale-user-uuid",
            "voip_pbx_line_id": 931,
        })
        orphan_condition = self.env["voip.time.condition"].with_context(
            voip_skip_pbx_sync=True,
        ).create({"name": "Unused condition", "pbx_schedule_id": 932})
        non_active_dids = self.env["voip.did.number"].with_context(
            voip_skip_pbx_sync=True,
        ).create([
            {
                "did_number": "+3287000403",
                "did_number_type": "local",
                "state": "pending",
                "destination_ref": f"res.partner,{self.partner_be.id}",
            },
            {
                "did_number": "+3287000404",
                "did_number_type": "local",
                "state": "suspended",
                "destination_ref": f"res.partner,{self.partner_be.id}",
            },
        ])

        payload = self.env["voip.pbx.service"]._get_tenant_recovery_payload()

        self.assertNotIn(user.id, self._payload_by_id(payload, "users"))
        self.assertNotIn(orphan_condition.id, self._payload_by_id(payload, "schedules"))
        incalls = self._payload_by_id(payload, "incalls")
        for did in non_active_dids:
            with self.subTest(state=did.state):
                self.assertNotIn(did.id, incalls)

    def test_active_call_flow_user_is_included_without_provider_setting(self):
        user = new_test_user(
            self.env,
            login="call-flow-only-user",
            name="Call Flow Only User",
            voip_secret="call-flow-secret",
        )
        graph_data = {
            "nodes": [_start_node(), _record_node("user", "user", user)],
            "connections": [_connection("start", "next", "user")],
        }
        self.env["voip.call.flow"].create({
            "name": "Direct user",
            "graph_data": graph_data,
        })

        payload = self.env["voip.pbx.service"]._get_tenant_recovery_payload()

        self.assertIn(user.id, self._payload_by_id(payload, "users"))

    def test_payload_lists_are_ordered_by_odoo_id(self):
        first_created = self._create_sound("Second by name", value=2)
        second_created = self._create_sound("First by name", value=1)

        payload = self.env["voip.pbx.service"]._get_tenant_recovery_payload()
        sound_ids = [sound["odoo_id"] for sound in payload["sounds"]]

        self.assertLess(first_created.id, second_created.id)
        self.assertEqual(sound_ids, sorted(sound_ids))
