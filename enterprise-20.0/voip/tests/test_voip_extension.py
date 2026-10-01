from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI
from odoo.addons.voip.models.res_users_settings import (
    PBX_SINGLE_CALL_LIMIT,
    PROVISIONED_NO_ANSWER_TIMEOUT,
)
from odoo.addons.voip.tests.common_voip import (
    PBX_TEST_AGENT_ID,
    PBX_TEST_USER_ID,
    VoipPhoneServiceCase,
    calls_for,
    capture_pbx_calls,
    pbx_router,
)


@tagged("post_install", "-at_install")
class TestVoipExtension(VoipPhoneServiceCase):
    def test_call_flow_node_configuration_context(self):
        call_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({"name": "Context-aware group"})

        self.assertFalse(call_group.is_call_flow_node_configuration)
        self.assertTrue(
            call_group.with_context(
                voip_call_flow_node_configuration=True,
            ).is_call_flow_node_configuration
        )

    def test_portal_user_cannot_have_extension(self):
        internal_user = new_test_user(self.env, login="extension_internal_user")
        portal_user = new_test_user(
            self.env,
            login="extension_portal_user",
            groups="base.group_portal",
        )
        extensions = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True)

        extension = extensions._find_or_create_for_user(internal_user)
        self.assertEqual(extension.destination_ref, internal_user)

        with self.assertRaisesRegex(
            ValidationError,
            "Only internal users can be assigned a PBX extension",
        ):
            extensions._find_or_create_for_user(portal_user)
        with self.assertRaisesRegex(
            ValidationError,
            "Only internal users can be assigned a PBX extension",
        ):
            extensions.create({"destination_ref": f"res.users,{portal_user.id}"})
        with self.assertRaisesRegex(
            ValidationError,
            "Only internal users can be assigned a PBX extension",
        ):
            extension.destination_ref = portal_user
        self.assertEqual(extension.destination_ref, internal_user)
        with self.assertRaisesRegex(
            ValidationError,
            "A user with a PBX extension must remain an internal user",
        ):
            internal_user.group_ids = [Command.set([self.env.ref("base.group_portal").id])]
        self.assertFalse(internal_user.share)

    def test_user_provisioning_sets_no_answer_timeout_with_destination(self):
        user = new_test_user(
            self.env,
            login="wazo_user",
            name="Wazo User",
            phone="+3281234567",
            country_id=self.env.ref("base.be").id,
        )

        calls, patcher = capture_pbx_calls()
        with patcher:
            self.env["voip.extension"].create({
                "number": "101",
                "destination_ref": f"res.users,{user.id}",
            })

        settings = user.res_users_settings_id
        self.assertEqual(settings.voip_no_answer_destination_type, "forward")
        self.assertEqual(settings.voip_no_answer_destination_kind, "external")
        self.assertEqual(settings.voip_no_answer_outcall_number, "+3281234567")
        self.assertEqual(settings.voip_no_answer_timeout, PROVISIONED_NO_ANSWER_TIMEOUT)
        self.assertEqual(settings.voip_busy_destination_type, "none")
        self.assertEqual(settings.voip_disconnected_destination_type, "forward")
        self.assertEqual(settings.voip_disconnected_destination_kind, "external")
        self.assertEqual(settings.voip_disconnected_outcall_number, "+3281234567")
        routing_calls = calls_for(calls, "update_user_routing")
        self.assertEqual(len(routing_calls), 1)
        self.assertEqual(routing_calls[0]["params"], {
            "always_destination": None,
            "busy_destination": {"cause": "busy", "timeout": 5, "type": "hangup"},
            "no_answer_destination": {
                "exten": "3281234567",
                "type": "outcall",
            },
            "fail_destination": {
                "exten": "3281234567",
                "type": "outcall",
            },
            "no_answer_timeout": PROVISIONED_NO_ANSWER_TIMEOUT,
            "simultaneous_calls": PBX_SINGLE_CALL_LIMIT,
            "user_id": 10,
        })

    def test_user_provisioning_defaults_to_personal_voicemail_without_phone(self):
        user = new_test_user(
            self.env,
            login="wazo_user_without_phone",
            name="Wazo User Without Phone",
        )

        calls, patcher = capture_pbx_calls()
        with patcher:
            self.env["voip.extension"].create({
                "number": "103",
                "destination_ref": f"res.users,{user.id}",
            })

        settings = user.res_users_settings_id
        voicemail = self.env["voip.voicemail"].search([("user_id", "=", user.id)])
        self.assertEqual(settings.voip_no_answer_destination_type, "forward")
        self.assertEqual(settings.voip_no_answer_destination_kind, "voip.voicemail")
        self.assertEqual(settings.voip_no_answer_destination_ref, voicemail)
        self.assertEqual(settings.voip_no_answer_timeout, PROVISIONED_NO_ANSWER_TIMEOUT)
        self.assertEqual(settings.voip_busy_destination_type, "none")
        routing_calls = calls_for(calls, "update_user_routing")
        self.assertEqual(len(routing_calls), 1)
        self.assertEqual(routing_calls[0]["params"], {
            "always_destination": None,
            "busy_destination": {"cause": "busy", "timeout": 5, "type": "hangup"},
            "no_answer_destination": {
                "type": "voicemail",
                "voicemail_id": voicemail.pbx_voicemail_id,
            },
            "fail_destination": None,
            "no_answer_timeout": PROVISIONED_NO_ANSWER_TIMEOUT,
            "simultaneous_calls": PBX_SINGLE_CALL_LIMIT,
            "user_id": 10,
        })

    def test_user_provisioning_uses_active_did_as_outgoing_caller_id(self):
        user = new_test_user(
            self.env,
            login="wazo_caller_id_user",
            name="Caller ID User",
            country_id=self.env.ref("base.be").id,
        )
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "102",
            "destination_ref": f"res.users,{user.id}",
        })
        did = self.env["voip.did.number"].with_context(install_mode=True).create({
            "did_number": "+3287000001",
            "destination_ref": f"res.users,{user.id}",
            "did_number_type": "local",
            "state": "active",
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)
        extension._sync_pbx()

        sync_calls = calls_for(calls, "sync_user_extension")
        self.assertEqual(len(sync_calls), 1)
        self.assertEqual(sync_calls[0]["params"]["outgoing_caller_id"], "+3287000001")

        calls.clear()
        did.write({"state": "suspended"})

        caller_id_calls = calls_for(calls, "update_user_caller_id")
        self.assertEqual(len(caller_id_calls), 1)
        self.assertEqual(caller_id_calls[0]["params"]["outgoing_caller_id"], "default")

    def test_user_provisioning_asks_for_the_wake_capability_only_when_needed(self):
        """A user who forwards a call no device can take is handed over by
        Wazo; the wake capability is for the one with nowhere to forward."""
        reachable = new_test_user(
            self.env,
            login="wazo_reachable_user",
            name="Reachable User",
            country_id=self.env.ref("base.be").id,
        )
        self.env["res.users.settings"].sudo()._find_or_create_for_user(
            reachable,
        ).with_context(voip_skip_pbx_sync=True).write({
            "voip_disconnected_destination_type": "forward",
            "voip_disconnected_destination_kind": "external",
            "voip_disconnected_outcall_number": "+32499123456",
        })
        unreachable = new_test_user(
            self.env,
            login="wazo_unreachable_user",
            name="Unreachable User",
            country_id=self.env.ref("base.be").id,
        )

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        for number, user in (("111", reachable), ("112", unreachable)):
            self.env["voip.extension"].create({
                "number": number,
                "destination_ref": f"res.users,{user.id}",
            })

        wakeup = [call["params"]["wakeup_token_enabled"]
                  for call in calls_for(calls, "sync_user_extension")]
        self.assertEqual(wakeup, [False, True])

    def test_user_provisioning_omits_old_pbx_refs(self):
        user = new_test_user(
            self.env,
            login="wazo_missing_ref_user",
            name="Missing Ref User",
        )
        user.res_users_settings_id.with_context(voip_skip_pbx_sync=True).write({
            "voip_provider_id": self.env.ref("voip.odoo_provider").id,
            "voip_secret": "sip-secret",
        })
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "122",
            "destination_ref": f"res.users,{user.id}",
        })
        sync_calls = []

        def capture(route, params, **kw):
            if route.endswith("/sync_user_extension"):
                sync_calls.append(dict(params))
            return pbx_router(route, params)

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=capture):
            extension._sync_pbx()

        self.assertEqual(len(sync_calls), 1)
        for field_name in (
            "user_id",
            "line_id",
            "extension_id",
        ):
            self.assertIsNone(sync_calls[0][field_name])
        self.assertFalse({name for name in sync_calls[0] if name.startswith("old_")})

    def test_clearing_credentials_deprovisions_user(self):
        user = new_test_user(
            self.env,
            login="wazo_revoke_user",
            name="Revoke User",
            voip_pbx_user_uuid="pbx-user-uuid",
        )
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "119",
            "destination_ref": f"res.users,{user.id}",
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        extension._clear_user_sip_credentials()

        deprovision_calls = calls_for(calls, "deprovision_user")
        self.assertEqual(len(deprovision_calls), 1)
        self.assertEqual(deprovision_calls[0]["params"]["user_uuid"], "pbx-user-uuid")

    def test_deleting_extension_defers_the_pbx_delete_and_deprovision_until_commit(self):
        user = new_test_user(
            self.env,
            login="deferred_delete_user",
            name="Deferred Delete User",
            voip_pbx_user_uuid="pbx-deferred-user-uuid",
        )
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "199",
            "destination_ref": f"res.users,{user.id}",
        })
        extension.with_context(voip_skip_pbx_sync=True).pbx_extension_id = 42

        calls, patcher = capture_pbx_calls()
        with patcher:
            extension.with_context(voip_skip_pbx_sync=False).unlink()
            self.assertFalse(calls_for(calls, "delete_extension"))
            self.assertFalse(calls_for(calls, "deprovision_user"))
            self.env.cr.postcommit.run()

        delete_ext_calls = calls_for(calls, "delete_extension")
        self.assertEqual(delete_ext_calls[0]["params"], {"extension_id": 42})
        deprovision_calls = calls_for(calls, "deprovision_user")
        self.assertEqual(deprovision_calls[0]["params"]["user_uuid"], "pbx-deferred-user-uuid")

    def test_deleting_call_group_drops_extension_and_did_route(self):
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
        })
        call_group.with_context(voip_skip_pbx_sync=True).write({
            "pbx_group_id": 70,
            "pbx_group_uuid": "group-uuid",
        })
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "103",
            "destination_ref": f"voip.call.group,{call_group.id}",
        })
        extension.with_context(voip_skip_pbx_sync=True).pbx_extension_id = 41
        did = self.env["voip.did.number"].with_context(install_mode=True).create({
            "did_number": "+3287000002",
            "destination_ref": f"voip.call.group,{call_group.id}",
            "did_number_type": "local",
            "state": "active",
            "pbx_incall_id": 50,
            "pbx_incall_extension_id": 60,
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        call_group.with_context(voip_skip_pbx_sync=False).unlink()
        self.env.cr.postcommit.run()

        self.assertFalse(extension.exists())
        self.assertFalse(did.destination_ref)
        self.assertFalse(did.pbx_incall_id)
        self.assertFalse(did.pbx_incall_extension_id)
        delete_incall_calls = calls_for(calls, "delete_incall")
        self.assertEqual(len(delete_incall_calls), 1)
        delete_group_calls = calls_for(calls, "delete_group")
        self.assertEqual(len(delete_group_calls), 1)

    def test_deleting_call_group_defers_the_pbx_delete_until_commit(self):
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Deferred delete group",
        })
        call_group.with_context(voip_skip_pbx_sync=True).write({
            "pbx_group_id": 71,
            "pbx_group_uuid": "deferred-group-uuid",
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            call_group.with_context(voip_skip_pbx_sync=False).unlink()
            self.assertFalse(calls_for(calls, "delete_group"))
            self.env.cr.postcommit.run()

        delete_group_calls = calls_for(calls, "delete_group")
        self.assertEqual(len(delete_group_calls), 1)
        self.assertEqual(delete_group_calls[0]["params"]["group_uuid"], "deferred-group-uuid")

    def test_call_group_only_syncs_incomplete_users(self):
        complete_user = new_test_user(
            self.env,
            login="complete_call_group_user",
            name="Complete Call Group User",
            voip_pbx_user_id=10,
            voip_pbx_user_uuid="complete-user-uuid",
            voip_pbx_line_id=20,
            voip_username="complete_call_group_user",
            voip_secret="secret",
        )
        incomplete_user = new_test_user(
            self.env,
            login="incomplete_call_group_user",
            name="Incomplete Call Group User",
        )
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "user_ids": [
                Command.link(complete_user.id),
                Command.link(incomplete_user.id),
            ],
        })
        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        call_group._sync_pbx()

        sync_user_calls = calls_for(calls, "sync_user")
        self.assertEqual(len(sync_user_calls), 1)
        self.assertEqual(sync_user_calls[0]["params"]["user_login"], incomplete_user.login)
        sync_group_calls = calls_for(calls, "sync_group")
        self.assertEqual(sync_group_calls[0]["params"]["user_ids"], [10, 10])

    def test_queue_agents_include_call_group_users_without_duplicates(self):
        first_user = new_test_user(
            self.env,
            login="first_queue_user",
            name="First Queue User",
        )
        second_user = new_test_user(
            self.env,
            login="second_queue_user",
            name="Second Queue User",
        )
        self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "107",
            "destination_ref": f"res.users,{first_user.id}",
        })
        self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "108",
            "destination_ref": f"res.users,{second_user.id}",
        })
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "user_ids": [
                Command.link(first_user.id),
                Command.link(second_user.id),
            ],
        })
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "allowed_user_ids": [Command.link(first_user.id)],
            "allowed_call_group_ids": [Command.link(call_group.id)],
        })

        self.assertEqual(queue.resolved_agent_user_ids, first_user | second_user)
        self.assertEqual(first_user.voip_queue_status, "disconnected")

        first_user.has_active_call = True

        self.assertEqual(first_user.voip_queue_status, "in_call")

    def test_call_group_agent_change_updates_stored_queue_agents(self):
        first_user = new_test_user(
            self.env,
            login="first_stored_queue_user",
            name="First Stored Queue User",
            voip_pbx_user_uuid="first-user-uuid",
        )
        second_user = new_test_user(
            self.env,
            login="second_stored_queue_user",
            name="Second Stored Queue User",
            voip_pbx_user_uuid="second-user-uuid",
        )
        self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "116",
            "destination_ref": f"res.users,{first_user.id}",
        })
        self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "117",
            "destination_ref": f"res.users,{second_user.id}",
        })
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "user_ids": [Command.link(first_user.id)],
        })
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "pbx_queue_id": 50,
            "allowed_call_group_ids": [Command.link(call_group.id)],
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)
        call_group.with_context(voip_skip_pbx_sync=False).write({
            "user_ids": [Command.set([second_user.id])],
        })

        self.assertEqual(queue.resolved_agent_user_ids, second_user)
        sync_group_calls = calls_for(calls, "sync_group")
        self.assertEqual(len(sync_group_calls), 1)
        self.assertEqual(sync_group_calls[0]["params"]["group_name"], "Support")
        sync_queue_calls = calls_for(calls, "sync_queue")
        self.assertTrue(len(sync_queue_calls) >= 1)
        self.assertEqual(sync_queue_calls[-1]["params"]["agent_ids"], [PBX_TEST_AGENT_ID])

    def test_deleting_required_agent_extension_recreates_it(self):
        user = new_test_user(
            self.env,
            login="extension_lifecycle_user",
            voip_pbx_user_id=11,
            voip_pbx_user_uuid="extension-lifecycle-user",
            voip_pbx_line_id=21,
        )
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "123",
            "destination_ref": f"res.users,{user.id}",
            "pbx_extension_id": 40,
        })
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "user_ids": [Command.link(user.id)],
            "pbx_group_id": 51,
            "pbx_group_uuid": "group-uuid",
        })
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "pbx_queue_id": 70,
            "allowed_call_group_ids": [Command.link(call_group.id)],
        })
        self.env["voip.queue.agent"].create({
            "queue_id": queue.id,
            "user_id": user.id,
            "pbx_agent_id": PBX_TEST_AGENT_ID,
            "agent_number": extension.number,
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        extension.with_context(voip_skip_pbx_sync=False).unlink()

        self.assertFalse(calls_for(calls, "sync_group"))
        self.assertEqual(queue.agent_ids.user_id, user)
        self.assertTrue(user.routing_extension_id)
        self.assertNotEqual(user.routing_extension_id.number, "123")
        self.assertEqual(calls_for(calls, "sync_queue")[-1]["params"]["agent_ids"], [PBX_TEST_AGENT_ID])

    def test_deleting_call_group_resyncs_direct_queue(self):
        user = new_test_user(self.env, login="deleted_group_queue_user")
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "125",
            "destination_ref": f"res.users,{user.id}",
        })
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support Group",
            "user_ids": [Command.link(user.id)],
            "pbx_group_id": 50,
            "pbx_group_uuid": "deleted-group-uuid",
        })
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support Queue",
            "pbx_queue_id": 70,
            "allowed_call_group_ids": [Command.link(call_group.id)],
        })
        self.env["voip.queue.agent"].create({
            "queue_id": queue.id,
            "user_id": user.id,
            "pbx_agent_id": PBX_TEST_AGENT_ID,
            "agent_number": extension.number,
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        call_group.with_context(voip_skip_pbx_sync=False).unlink()

        self.assertFalse(queue.allowed_call_group_ids)
        self.assertFalse(queue.agent_ids)
        self.assertFalse(calls_for(calls, "sync_queue")[-1]["params"]["agent_ids"])

    def test_queue_sync_uses_existing_extensions_and_removes_pbx_queue_on_delete(self):
        user = new_test_user(
            self.env,
            login="queue_sync_user",
            name="Queue Sync User",
        )
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "100",
            "destination_ref": f"res.users,{user.id}",
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        queue = self.env["voip.queue"].create({
            "name": "Support",
            "allowed_user_ids": [Command.link(user.id)],
            "strategy": "leastrecent",
            "agent_timeout": 25,
            "queue_timeout": 90,
            "retry_on_timeout": 8,
            "max_waiting_calls": 12,
        })

        self.assertEqual(queue.pbx_queue_id, 70)
        self.assertEqual(queue.agent_ids.user_id, user)
        self.assertEqual(queue.agent_ids.pbx_agent_id, PBX_TEST_AGENT_ID)
        self.assertEqual(queue.agent_ids.agent_number, "100")

        sync_agent_calls = calls_for(calls, "sync_agent")
        self.assertEqual(len(sync_agent_calls), 1)
        self.assertEqual(sync_agent_calls[0]["params"]["firstname"], "Queue")
        self.assertEqual(sync_agent_calls[0]["params"]["lastname"], "Sync User")

        sync_queue_calls = calls_for(calls, "sync_queue")
        self.assertEqual(len(sync_queue_calls), 1)
        self.assertEqual(sync_queue_calls[0]["params"]["odoo_queue_id"], queue.id)
        self.assertEqual(sync_queue_calls[0]["params"]["queue_label"], "Support")
        self.assertEqual(sync_queue_calls[0]["params"]["strategy"], "leastrecent")
        self.assertEqual(sync_queue_calls[0]["params"]["agent_timeout"], 25)
        self.assertEqual(sync_queue_calls[0]["params"]["queue_timeout"], 90)
        self.assertEqual(sync_queue_calls[0]["params"]["retry_delay"], 8)
        self.assertEqual(sync_queue_calls[0]["params"]["max_waiting_calls"], 12)
        self.assertEqual(sync_queue_calls[0]["params"]["agent_ids"], [PBX_TEST_AGENT_ID])

        calls.clear()
        extension.with_context(voip_skip_pbx_sync=False).write({"number": "101"})
        self.assertEqual(queue.agent_ids.agent_number, "101")
        sync_agent_calls = calls_for(calls, "sync_agent")
        self.assertEqual(len(sync_agent_calls), 1)
        self.assertEqual(sync_agent_calls[0]["params"]["agent_number"], "101")

        calls.clear()
        queue.write({"queue_timeout": 120})
        sync_queue_calls = calls_for(calls, "sync_queue")
        self.assertEqual(len(sync_queue_calls), 1)
        self.assertEqual(sync_queue_calls[0]["params"]["queue_id"], 70)
        self.assertEqual(sync_queue_calls[0]["params"]["queue_timeout"], 120)

        calls.clear()
        queue.unlink()
        self.env.cr.postcommit.run()
        delete_queue_calls = calls_for(calls, "delete_queue")
        self.assertEqual(len(delete_queue_calls), 1)

    def test_extension_renumber_resyncs_direct_routes(self):
        extension_target = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Extension target",
            "pbx_group_id": 51,
            "pbx_group_uuid": "extension-target-uuid",
        })
        extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "number": "9511",
            "destination_ref": f"voip.call.group,{extension_target.id}",
            "pbx_extension_id": 40,
        })
        route_owner = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "Route owner",
            "no_answer_destination_ref": f"voip.extension,{extension.id}",
            "pbx_group_id": 52,
            "pbx_group_uuid": "route-owner-uuid",
        })
        self.env["voip.did.number"].with_context(voip_skip_pbx_sync=True).create({
            "did_number": "+3287000951",
            "destination_ref": f"voip.extension,{extension.id}",
            "did_number_type": "local",
            "state": "active",
        })

        calls, patcher = capture_pbx_calls()
        with patcher:
            extension.with_context(voip_skip_pbx_sync=False).number = "9512"

        incall = calls_for(calls, "sync_incall")[-1]["params"]
        self.assertEqual(incall["destination"], {
            "type": "extension",
            "exten": "9512",
        })
        route = next(
            call["params"]
            for call in calls_for(calls, "update_group_routing")
            if call["params"]["group_uuid"] == route_owner.pbx_group_uuid
        )
        self.assertEqual(route["no_answer_destination"], {
            "type": "extension",
            "exten": "9512",
        })

    def test_queue_agent_status_refresh_uses_wazo_agent_state(self):
        user = new_test_user(
            self.env,
            login="queue_status_user",
            name="Queue Status User",
        )
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "pbx_queue_id": 70,
        })
        agent = self.env["voip.queue.agent"].create({
            "queue_id": queue.id,
            "user_id": user.id,
            "pbx_agent_id": 80,
            "agent_number": "100",
        })

        with patch.object(
            self.env["voip.pbx.service"].__class__,
            "_get_agents",
            return_value=[{
                "id": 80,
                "logged": False,
                "paused": False,
                "queues": [{
                    "id": 70,
                    "logged": True,
                    "paused": True,
                    "paused_reason": "Break",
                }],
            }],
        ):
            queue._refresh_agent_statuses()

        self.assertTrue(agent.is_logged)
        self.assertTrue(agent.is_paused)
        self.assertEqual(agent.pause_reason, "Break")
        self.assertEqual(agent.status, "paused")
        self.assertTrue(agent.status_last_sync)

    def test_queue_agent_status_sort_order_does_not_change_agent_sequence(self):
        user = new_test_user(self.env, login="queue_status_order_user")
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
        })
        agent = self.env["voip.queue.agent"].create({
            "queue_id": queue.id,
            "user_id": user.id,
            "sequence": 7,
        })

        for status, expected_order in {
            "in_call": 0,
            "available": 1,
            "paused": 2,
            "unavailable": 3,
            "logged_out": 4,
            "unknown": 5,
        }.items():
            agent.status = status
            self.assertEqual(agent.status_sort_order, expected_order)
            self.assertEqual(agent.sequence, 7)

    def test_regular_user_can_only_manage_own_queue_membership(self):
        user = new_test_user(self.env, login="regular_queue_member", groups="base.group_user")
        other_user = new_test_user(self.env, login="other_queue_member", groups="base.group_user")
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
        })
        agent = self.env["voip.queue.agent"].create({
            "queue_id": queue.id,
            "user_id": user.id,
        })
        other_agent = self.env["voip.queue.agent"].create({
            "queue_id": queue.id,
            "user_id": other_user.id,
        })
        agent_model = self.env["voip.queue.agent"].with_user(user)

        self.assertEqual(
            agent_model.get_current_user_queue_memberships(),
            [{
                "id": agent.id,
                "is_logged": False,
                "queue_id": queue.id,
                "queue_name": "Support",
            }],
        )
        with patch.object(agent.__class__, "action_login_to_queue", autospec=True) as login:
            agent_model.set_current_user_queue_membership(agent.id, True)
        login.assert_called_once()
        with self.assertRaises(AccessError):
            agent_model.set_current_user_queue_membership(other_agent.id, True)

    def test_queue_extension_is_provisioned_and_deleted_with_queue(self):
        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        queue = self.env["voip.queue"].create({"name": "Support"})
        extension = self.env["voip.extension"].create({
            "number": "112",
            "destination_ref": f"voip.queue,{queue.id}",
        })

        self.assertEqual(extension.pbx_extension_id, 40)
        self.assertEqual(
            extension._get_pbx_incall_destination(),
            {"type": "queue", "queue_id": 70},
        )
        sync_queue_ext_calls = calls_for(calls, "sync_queue_extension")
        self.assertEqual(len(sync_queue_ext_calls), 1)
        self.assertEqual(sync_queue_ext_calls[0]["params"]["extension_number"], "112")
        self.assertEqual(sync_queue_ext_calls[0]["params"]["queue_id"], 70)

        calls.clear()
        queue.unlink()
        self.env.cr.postcommit.run()

        self.assertFalse(extension.exists())
        delete_queue_ext_calls = calls_for(calls, "delete_queue")
        self.assertTrue(len(delete_queue_ext_calls) >= 1)
        delete_ext_calls = calls_for(calls, "delete_extension")
        self.assertEqual(delete_ext_calls[0]["params"], {"extension_id": 40})

    def test_queue_can_only_be_linked_to_one_extension(self):
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
        })
        self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "113",
            "destination_ref": f"voip.queue,{queue.id}",
        })

        with self.assertRaises(ValidationError):
            self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
                "number": "114",
                "destination_ref": f"voip.queue,{queue.id}",
            })

    def test_queue_extension_can_be_moved_to_another_queue(self):
        first_queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "First",
            "pbx_queue_id": 50,
        })
        second_queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Second",
            "pbx_queue_id": 60,
        })
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "115",
            "destination_ref": f"voip.queue,{first_queue.id}",
            "pbx_extension_id": 40,
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        extension.with_context(voip_skip_pbx_sync=False).write({
            "destination_ref": f"voip.queue,{second_queue.id}",
        })

        sync_queue_ext_calls = calls_for(calls, "sync_queue_extension")
        self.assertEqual(len(sync_queue_ext_calls), 1)
        self.assertEqual(sync_queue_ext_calls[0]["params"]["extension_id"], 40)
        self.assertEqual(sync_queue_ext_calls[0]["params"]["extension_number"], "115")
        self.assertEqual(sync_queue_ext_calls[0]["params"]["queue_id"], 60)
        self.assertFalse({name for name in sync_queue_ext_calls[0]["params"] if name.startswith("old_")})

    def test_queue_extension_can_be_moved_to_user(self):
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "pbx_queue_id": 50,
        })
        user = new_test_user(self.env, login="queue_to_user", name="Queue to User")
        external_provider = self.env["voip.provider"].create({
            "name": "External Provider",
            "mode": "prod",
        })
        user.res_users_settings_id.with_context(voip_skip_pbx_sync=True).write({
            "voip_provider_id": external_provider.id,
        })
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "116",
            "destination_ref": f"voip.queue,{queue.id}",
            "pbx_extension_id": 40,
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        extension.with_context(voip_skip_pbx_sync=False).write({
            "destination_ref": f"res.users,{user.id}",
        })

        sync_user_ext_calls = calls_for(calls, "sync_user_extension")
        self.assertEqual(len(sync_user_ext_calls), 1)
        self.assertFalse({name for name in sync_user_ext_calls[0]["params"] if name.startswith("old_")})

    def test_queue_extension_can_be_moved_to_call_group(self):
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "pbx_queue_id": 50,
        })
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Sales",
            "pbx_group_uuid": "group-uuid",
        })
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "number": "117",
            "destination_ref": f"voip.queue,{queue.id}",
            "pbx_extension_id": 40,
        })

        calls, patcher = capture_pbx_calls()
        patcher.start()
        self.addCleanup(patcher.stop)

        extension.with_context(voip_skip_pbx_sync=False).write({
            "destination_ref": f"voip.call.group,{call_group.id}",
        })

        sync_group_ext_calls = calls_for(calls, "sync_group_extension")
        self.assertEqual(len(sync_group_ext_calls), 1)
        self.assertFalse({name for name in sync_group_ext_calls[0]["params"] if name.startswith("old_")})


@tagged("post_install", "-at_install")
class TestVoipDisconnectedDestination(VoipPhoneServiceCase):
    """Where a call goes when no device of the user's can take it."""

    def _new_routed_user(self, login):
        user = new_test_user(
            self.env,
            login=login,
            name=login.replace("_", " ").title(),
            country_id=self.env.ref("base.be").id,
            voip_pbx_user_uuid=f"uuid-{login}",
        )
        user.with_context(voip_skip_pbx_sync=True).voip_pbx_user_id = PBX_TEST_USER_ID
        self.env["res.users.settings"].sudo()._find_or_create_for_user(user)
        return user

    def test_an_external_destination_is_sent_as_the_fail_destination(self):
        user = self._new_routed_user("disconnected_outcall")

        calls, patcher = capture_pbx_calls()
        with patcher:
            user.write({
                "voip_disconnected_destination_type": "forward",
                "voip_disconnected_destination_kind": "external",
                "voip_disconnected_outcall_number": "+32499123456",
            })

        routing_calls = calls_for(calls, "update_user_routing")
        self.assertEqual(len(routing_calls), 1)
        self.assertEqual(routing_calls[0]["params"]["fail_destination"], {
            "type": "outcall",
            "exten": "32499123456",
        })

    def test_the_pbx_flips_the_wake_up_token_from_the_routing_call_alone(self):
        """The destination and the wake capability are two halves of one
        decision, so the destination alone tells the service which way to settle
        the token -- no credential travels, and no second round-trip."""
        user = self._new_routed_user("disconnected_token")

        calls, patcher = capture_pbx_calls()
        with patcher:
            user.write({
                "voip_disconnected_destination_type": "forward",
                "voip_disconnected_destination_kind": "external",
                "voip_disconnected_outcall_number": "+32499123457",
            })
            self.assertFalse(user._voip_wants_wakeup_token())
            user.write({
                "voip_disconnected_destination_type": "none",
                "voip_disconnected_outcall_number": False,
            })

        routing_calls = calls_for(calls, "update_user_routing")
        self.assertEqual(len(routing_calls), 2)
        self.assertIsNotNone(routing_calls[0]["params"]["fail_destination"])
        self.assertIsNone(routing_calls[1]["params"]["fail_destination"])
        for call in routing_calls:
            self.assertNotIn("auth", call["params"])
        self.assertTrue(user._voip_wants_wakeup_token())

    def test_an_internal_destination_is_resolved_like_the_other_slots(self):
        user = self._new_routed_user("disconnected_pbx")
        voicemail = self.env["voip.voicemail"].sudo()._ensure_for_user(user)

        calls, patcher = capture_pbx_calls()
        with patcher:
            user.write({
                "voip_disconnected_destination_type": "forward",
                "voip_disconnected_destination_kind": "voip.voicemail",
                "voip_disconnected_destination_ref": f"voip.voicemail,{voicemail.id}",
            })

        routing_calls = calls_for(calls, "update_user_routing")
        self.assertEqual(len(routing_calls), 1)
        self.assertEqual(routing_calls[0]["params"]["fail_destination"], {
            "type": "voicemail",
            "voicemail_id": voicemail.pbx_voicemail_id,
        })

    def test_an_external_destination_must_be_a_valid_e164_number(self):
        user = self._new_routed_user("disconnected_bad_number")

        with self.assertRaisesRegex(ValidationError, "E.164"):
            user.write({
                "voip_disconnected_destination_type": "forward",
                "voip_disconnected_destination_kind": "external",
                "voip_disconnected_outcall_number": "call reception",
            })
