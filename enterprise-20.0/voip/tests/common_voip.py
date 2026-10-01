from unittest.mock import patch

from odoo.tests.common import HttpCase, new_test_user
from odoo.tools import BinaryBytes

from odoo.addons.voip.models.phone_service_api import PBX_SYNC_ECHO_IDS, PhoneServiceAPI
from odoo.addons.voip.tools.wav import encode_wav, pack_int16_samples

# Canonical ids the mock returns — assertions in ported tests match these.
PBX_TEST_USER_ID = 10
PBX_TEST_USER_UUID = "pbx-user-uuid"
PBX_TEST_LINE_ID = 20
PBX_TEST_EXTENSION_ID = 40
PBX_TEST_INCALL_ID = 50
PBX_TEST_INCALL_EXTENSION_ID = 60
PBX_TEST_GROUP_ID = 60
PBX_TEST_GROUP_UUID = "pbx-group-uuid"
PBX_TEST_QUEUE_ID = 70
PBX_TEST_AGENT_ID = 80
PBX_TEST_VOICEMAIL_ID = 100
PBX_TEST_SCHEDULE_ID = 110
PBX_TEST_MOH_UUID = "pbx-moh-uuid"
PBX_TEST_AUTH_USERNAME = "pbx-auth-username"
PBX_TEST_SIP_USERNAME = "pbx-sip-username"
TTS_TEST_VOICE = "Telnyx.NaturalHD.astra"


def tts_sound_values(text):
    """Return a consistent generated TTS sound payload for unrelated tests."""
    return {
        "data": BinaryBytes(encode_wav(
            pack_int16_samples([0] * 8), channels=1, sample_width=2, frame_rate=8000,
        )),
        "generated_tts_text": text.strip(),
        "generated_tts_voice": TTS_TEST_VOICE,
        "tts_text": text,
        "tts_voice": TTS_TEST_VOICE,
    }


_PBX_RESPONSES = {
    "sync_user": {
        "user_id": PBX_TEST_USER_ID, "user_uuid": PBX_TEST_USER_UUID,
        "line_id": PBX_TEST_LINE_ID, "sip_username": PBX_TEST_SIP_USERNAME,
    },
    "sync_user_extension": {
        "user_id": PBX_TEST_USER_ID, "user_uuid": PBX_TEST_USER_UUID,
        "line_id": PBX_TEST_LINE_ID, "extension_id": PBX_TEST_EXTENSION_ID,
        "sip_username": PBX_TEST_SIP_USERNAME, "auth_username": PBX_TEST_AUTH_USERNAME,
    },
    "update_user_routing": {},
    "update_user_caller_id": {},
    "sync_group": {"group_id": PBX_TEST_GROUP_ID, "group_uuid": PBX_TEST_GROUP_UUID},
    "sync_group_extension": {"extension_id": PBX_TEST_EXTENSION_ID},
    "sync_queue": {"queue_id": PBX_TEST_QUEUE_ID},
    "sync_queue_extension": {"extension_id": PBX_TEST_EXTENSION_ID},
    "sync_agent": {"agent_id": PBX_TEST_AGENT_ID},
    "sync_voicemail": {"voicemail_id": PBX_TEST_VOICEMAIL_ID},
    "sync_schedule": {"schedule_id": PBX_TEST_SCHEDULE_ID},
    "sync_incall": {
        "incall_id": PBX_TEST_INCALL_ID,
        "extension_id": PBX_TEST_INCALL_EXTENSION_ID,
    },
    "get_queue_status": {"members": []},
    "delete_incall": {},
    "delete_extension": {},
    "delete_group": {},
    "delete_queue": {},
    "delete_voicemail": {},
    "upload_voicemail_greeting": {},
    "delete_voicemail_greeting": {},
    "get_voicemail_message_recording": {
        "file_content_base64": "UklGRg==",
        "mimetype": "audio/wav",
    },
    "sync_moh": {"moh_uuid": PBX_TEST_MOH_UUID, "moh_name": "canonical-moh-name"},
    "delete_moh": {},
    "upload_sound": {},
    "deprovision_user": {},
    "hangup_call": {},
}


def pbx_router(route, params):
    """Return the canonical success response for a pbx/* route.

    Sync routes echo the ids the caller already holds (like the real ops'
    update paths); the canonical ids fill the gaps.
    """
    if route.startswith("/api/phone_service/1/pbx/"):
        key = route.rsplit("/", 1)[-1]
        data = dict(_PBX_RESPONSES.get(key, {}))
        for response_key, param_key in PBX_SYNC_ECHO_IDS.get(key, {}).items():
            if params.get(param_key):
                data[response_key] = params[param_key]
        return {"success": True, "data": data}
    # Non-pbx routes (number ordering, search, etc.) — generic success.
    return {"success": True, "data": {}}


def forbid_phone_service_http(test):
    """Fail on any phone_service HTTP call the test did not mock, so a missing
    mock is an assertion error instead of a request to the real service."""

    def _raise_unmocked(*args, **kwargs):
        raise AssertionError(
            "phone_service_api.requests.post called without an explicit mock"
        )

    patcher = patch(
        "odoo.addons.voip.models.phone_service_api.requests.post",
        side_effect=_raise_unmocked,
    )
    patcher.start()
    test.addCleanup(patcher.stop)


def mock_pbx_layer(test):
    """Stub the PBX layer: every PhoneServiceAPI call returns a canonical
    success response so no test ever reaches the network.

    Tests needing finer control (e.g. asserting on request payloads, or
    simulating failures) patch ``_call_phone_service`` locally.
    """
    patcher = patch.object(
        PhoneServiceAPI, "_call_phone_service",
        side_effect=lambda route, params, **kw: pbx_router(route, params),
    )
    patcher.start()
    test.addCleanup(patcher.stop)


def capture_pbx_calls():
    """Capture PBX calls while returning canonical successful responses."""
    calls = []

    def side_effect(route, params, **kwargs):
        calls.append({"route": route, "params": dict(params)})
        return pbx_router(route, params)

    return calls, patch.object(
        PhoneServiceAPI,
        "_call_phone_service",
        side_effect=side_effect,
    )


def calls_for(calls, route_key):
    route = f"/api/phone_service/1/pbx/{route_key}"
    return [call for call in calls if call["route"] == route]


class VoipPhoneServiceCase(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        did_numbers = cls.env["voip.did.number"].search([]).with_context(voip_skip_pbx_sync=True)
        did_numbers.write({"state": "released"})
        did_numbers.unlink()

        cls.partner_be = cls.env["res.partner"].create(
            {
                "name": "Fred Edison",
                "phone": "+3287654321",
                "country_id": cls.env.ref("base.be").id,
            }
        )

    def setUp(self):
        super().setUp()
        forbid_phone_service_http(self)
        mock_pbx_layer(self)

    @property
    def partner_phone(self):
        return self.partner_be.phone_sanitized

    def get_user_phone(self, user):
        phone_number = self.env["voip.did.number"].search(
            [
                ("user_id", "=", user.id),
            ],
            limit=1,
        )
        return phone_number.did_number

    def new_voip_user(
        self,
        phone="+3281234567",
        user_login="test_voip_user",
        user_name="Bernard Bernoulli",
        user_country_id=None,
    ):
        user = new_test_user(
            self.env,
            login=user_login,
            name=user_name,
            country_id=user_country_id or self.env.ref("base.be").id,
            voip_username=user_login,
            voip_secret=user_login,
        )
        self.env["voip.extension"].with_context(voip_skip_pbx_sync=True)._find_or_create_for_user(user)

        def handler(route, params, **kw):
            if route.startswith("/api/phone_service/1/pbx/"):
                return pbx_router(route, params)
            return {"success": True, "data": {"id": "mock_id"}}

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=handler):
            self.env["voip.did.number"].create(
                {
                    "did_number": phone,
                    "destination_ref": f"res.users,{user.id}",
                    "did_number_type": "local",
                    "state": "active",
                }
            )
        return user
