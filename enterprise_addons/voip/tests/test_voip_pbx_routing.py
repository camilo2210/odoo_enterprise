import psycopg2

from odoo.tests import tagged
from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from odoo.addons.voip.tests.common_voip import (
    VoipPhoneServiceCase,
    calls_for,
    capture_pbx_calls,
    tts_sound_values,
)


@tagged("post_install", "-at_install")
class TestVoipPbxRouting(VoipPhoneServiceCase):
    def test_standalone_ivr_option_digits_are_valid_and_unique(self):
        menu_sound = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({"name": "IVR menu", **tts_sound_values("Choose an option.")})
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Standalone IVR",
            "menu_sound_id": menu_sound.id,
        })
        options = self.env["voip.ivr.option"].with_context(voip_skip_pbx_sync=True)
        options.create({"digit": "1", "ivr_id": ivr.id})

        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            options.create({"digit": "invalid", "ivr_id": ivr.id})
        with (
            self.assertRaises(psycopg2.IntegrityError),
            mute_logger("odoo.sql_db"),
            self.env.cr.savepoint(),
        ):
            options.create({"digit": "1", "ivr_id": ivr.id})

    def test_standalone_call_group_no_answer_routing(self):
        call_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Standalone group",
            "no_answer_destination_ref": f"res.partner,{self.partner_be.id}",
            "pbx_group_uuid": "standalone-group-uuid",
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            call_group._sync_pbx_routing()

        self.assertEqual(calls_for(calls, "update_group_routing"), [{
            "route": "/api/phone_service/1/pbx/update_group_routing",
            "params": {
                "group_uuid": "standalone-group-uuid",
                "no_answer_destination": {
                    "type": "outcall",
                    "exten": "3287654321",
                },
            },
        }])

    def test_standalone_queue_fallback_routing(self):
        busy_message = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Queue busy",
            **tts_sound_values("Please call again later."),
        })
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Standalone queue",
            "busy_destination_ref": f"voip.sound,{busy_message.id}",
            "no_answer_destination_ref": f"res.partner,{self.partner_be.id}",
            "pbx_queue_id": 201,
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            queue._sync_pbx_routing()

        self.assertEqual(calls_for(calls, "update_queue_routing"), [{
            "route": "/api/phone_service/1/pbx/update_queue_routing",
            "params": {
                "queue_id": 201,
                "no_answer_destination": {
                    "type": "outcall",
                    "exten": "3287654321",
                },
                "busy_destination": {
                    "type": "sound",
                    "filename": busy_message._get_pbx_sound_filename(),
                },
            },
        }])

    def test_standalone_ivr_routing_and_sounds(self):
        menu_sound, greeting_sound, invalid_sound, abort_sound = self.env[
            "voip.sound"
        ].with_context(voip_skip_pbx_sync=True).create([
            {"name": "IVR menu", **tts_sound_values("Choose an option.")},
            {"name": "IVR greeting", **tts_sound_values("Welcome.")},
            {"name": "IVR invalid", **tts_sound_values("Invalid choice.")},
            {"name": "IVR abort", **tts_sound_values("Goodbye.")},
        ])
        invalid_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({"name": "Invalid input group", "pbx_group_id": 202})
        timeout_queue = self.env["voip.queue"].with_context(
            voip_skip_pbx_sync=True,
        ).create({"name": "Timeout queue", "pbx_queue_id": 203})
        abort_voicemail = self.env["voip.voicemail"].with_context(
            voip_skip_pbx_sync=True,
        ).create({"name": "Abort voicemail", "pbx_voicemail_id": 204})
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Standalone IVR",
            "abort_destination_ref": f"voip.voicemail,{abort_voicemail.id}",
            "abort_sound_id": abort_sound.id,
            "greeting_sound_id": greeting_sound.id,
            "invalid_destination_ref": f"voip.call.group,{invalid_group.id}",
            "invalid_sound_id": invalid_sound.id,
            "menu_sound_id": menu_sound.id,
            "pbx_ivr_id": 205,
            "timeout": 8,
            "timeout_destination_ref": f"voip.queue,{timeout_queue.id}",
        })
        option = self.env["voip.ivr.option"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "digit": "1",
            "destination_ref": f"res.partner,{self.partner_be.id}",
            "ivr_id": ivr.id,
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            ivr.with_context(voip_skip_pbx_sync=False)._sync_pbx()

        sync_call, = calls_for(calls, "sync_ivr")
        self.assertEqual(sync_call["params"], {
            "ivr_id": 205,
            "ivr_name": "Standalone IVR",
            "description": None,
            "menu_sound": menu_sound._get_pbx_sound_filename(),
            "greeting_sound": greeting_sound._get_pbx_sound_filename(),
            "max_tries": 3,
            "invalid_destination": {"type": "group", "group_id": 202},
            "invalid_sound": invalid_sound._get_pbx_sound_filename(),
            "timeout": 8,
            "timeout_destination": {"type": "queue", "queue_id": 203},
            "abort_destination": {"type": "voicemail", "voicemail_id": 204},
            "abort_sound": abort_sound._get_pbx_sound_filename(),
            "choices": [{
                "digit": option.digit,
                "destination": {
                    "type": "outcall",
                    "exten": "3287654321",
                },
            }],
        })

    def test_deleting_ivr_defers_the_pbx_delete_until_commit(self):
        menu_sound = self.env["voip.sound"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Deferred IVR menu",
            **tts_sound_values("Choose an option."),
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Deferred delete IVR",
            "menu_sound_id": menu_sound.id,
            "pbx_ivr_id": 206,
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            ivr.with_context(voip_skip_pbx_sync=False).unlink()
            self.assertFalse(calls_for(calls, "delete_ivr"))
            self.env.cr.postcommit.run()

        delete_ivr_calls = calls_for(calls, "delete_ivr")
        self.assertEqual(len(delete_ivr_calls), 1)
        self.assertEqual(delete_ivr_calls[0]["params"]["ivr_id"], 206)

    def test_deleting_voicemail_defers_the_pbx_delete_until_commit(self):
        voicemail = self.env["voip.voicemail"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Deferred delete voicemail",
            "pbx_voicemail_id": 207,
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            voicemail.with_context(voip_skip_pbx_sync=False).unlink()
            self.assertFalse(calls_for(calls, "delete_voicemail"))
            self.env.cr.postcommit.run()

        delete_voicemail_calls = calls_for(calls, "delete_voicemail")
        self.assertEqual(len(delete_voicemail_calls), 1)
        self.assertEqual(delete_voicemail_calls[0]["params"]["voicemail_id"], 207)
