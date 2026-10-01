from unittest.mock import patch

from odoo import Command, fields
from odoo.tests.common import new_test_user

from odoo.addons.voip.models.voip_queue_agent import VoipQueueAgent
from odoo.addons.voip.tests.common_voip import (
    PBX_TEST_AGENT_ID,
    PBX_TEST_QUEUE_ID,
    VoipPhoneServiceCase,
)


class TestVoipQueueAgentStatusHelpers(VoipPhoneServiceCase):
    """Pure status-derivation helpers: no records needed."""

    def test_get_status_from_queue_member_paused_takes_priority(self):
        status = VoipQueueAgent._get_status_from_queue_member({"Paused": "1", "InCall": "1"})
        self.assertEqual(status, "paused")

    def test_get_status_from_queue_member_in_call_from_incall_flag(self):
        status = VoipQueueAgent._get_status_from_queue_member({"Paused": "0", "InCall": "1"})
        self.assertEqual(status, "in_call")

    def test_get_status_from_queue_member_in_call_from_status_code(self):
        status = VoipQueueAgent._get_status_from_queue_member({"Paused": "0", "Status": "2"})
        self.assertEqual(status, "in_call")

    def test_get_status_from_queue_member_available(self):
        status = VoipQueueAgent._get_status_from_queue_member({"Paused": "0", "Status": "1"})
        self.assertEqual(status, "available")

    def test_get_status_from_queue_member_unavailable(self):
        status = VoipQueueAgent._get_status_from_queue_member({"Paused": "0", "Status": "5"})
        self.assertEqual(status, "unavailable")

    def test_get_status_from_queue_member_unknown_status_code(self):
        status = VoipQueueAgent._get_status_from_queue_member({"Paused": "0", "Status": "99"})
        self.assertEqual(status, "unknown")

    def test_get_user_id_from_queue_member_interface_parses_the_user_id(self):
        user_id = VoipQueueAgent._get_user_id_from_queue_member_interface("PJSIP/odoo-42_abcdef")
        self.assertEqual(user_id, 42)

    def test_get_user_id_from_queue_member_interface_rejects_wrong_prefix(self):
        self.assertFalse(
            VoipQueueAgent._get_user_id_from_queue_member_interface("SIP/other-42_abcdef"),
        )

    def test_get_user_id_from_queue_member_interface_rejects_missing_underscore(self):
        self.assertFalse(
            VoipQueueAgent._get_user_id_from_queue_member_interface("PJSIP/odoo-42"),
        )

    def test_get_user_id_from_queue_member_interface_rejects_non_decimal_id(self):
        self.assertFalse(
            VoipQueueAgent._get_user_id_from_queue_member_interface("PJSIP/odoo-abc_xyz"),
        )

    def test_get_status_from_wazo_agent_logged_out_takes_priority(self):
        status = VoipQueueAgent._get_status_from_wazo_agent(
            {"status": "in_call"}, is_logged=False, is_paused=True,
        )
        self.assertEqual(status, "logged_out")

    def test_get_status_from_wazo_agent_paused(self):
        status = VoipQueueAgent._get_status_from_wazo_agent({}, is_logged=True, is_paused=True)
        self.assertEqual(status, "paused")

    def test_get_status_from_wazo_agent_in_call(self):
        status = VoipQueueAgent._get_status_from_wazo_agent(
            {"status": "busy"}, is_logged=True, is_paused=False,
        )
        self.assertEqual(status, "in_call")

    def test_get_status_from_wazo_agent_defaults_to_available(self):
        status = VoipQueueAgent._get_status_from_wazo_agent({}, is_logged=True, is_paused=False)
        self.assertEqual(status, "available")


class TestVoipQueueAgentRefresh(VoipPhoneServiceCase):
    def setUp(self):
        super().setUp()
        self.user = new_test_user(self.env, login="queue_member_status_user")
        self.queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "pbx_queue_id": 70,
        })
        self.agent = self.env["voip.queue.agent"].create({
            "queue_id": self.queue.id,
            "user_id": self.user.id,
            "pbx_agent_id": 80,
            "agent_number": "100",
        })

    def test_write_status_from_queue_member_updates_all_fields(self):
        now = fields.Datetime.now()

        self.agent._write_status_from_queue_member({
            "Paused": "1", "PausedReason": "Break", "InCall": "0", "Status": "1",
        }, now)

        self.assertTrue(self.agent.is_logged)
        self.assertTrue(self.agent.is_paused)
        self.assertEqual(self.agent.pause_reason, "Break")
        self.assertEqual(self.agent.status, "paused")
        self.assertEqual(self.agent.status_last_sync, now)

    def test_get_queue_member_matches_by_agent_name(self):
        member = {"Name": "Agent/100", "StateInterface": "PJSIP/odoo-999_x"}
        queue_members_by_queue_id = {self.queue.id: [member]}

        self.assertEqual(self.agent._get_queue_member(queue_members_by_queue_id), member)

    def test_get_queue_member_matches_by_state_interface_user_id(self):
        member = {"Name": "Agent/other", "StateInterface": f"PJSIP/odoo-{self.user.id}_x"}
        queue_members_by_queue_id = {self.queue.id: [member]}

        self.assertEqual(self.agent._get_queue_member(queue_members_by_queue_id), member)

    def test_get_queue_member_returns_false_when_absent(self):
        queue_members_by_queue_id = {self.queue.id: [
            {"Name": "Agent/other", "StateInterface": "PJSIP/odoo-999_x"},
        ]}

        self.assertFalse(self.agent._get_queue_member(queue_members_by_queue_id))

    def test_refresh_prefers_queue_member_over_wazo_agent(self):
        queue_members_by_queue_id = {self.queue.id: [{"Name": "Agent/100", "Paused": "0", "InCall": "1"}]}
        wazo_agents_by_id = {80: {"id": 80, "status": "available", "queues": []}}

        self.agent._refresh_statuses_from_wazo(wazo_agents_by_id, queue_members_by_queue_id)

        self.assertEqual(self.agent.status, "in_call")

    def test_refresh_falls_back_to_wazo_queue_data_without_a_queue_member(self):
        wazo_agents_by_id = {80: {
            "id": 80, "status": "available",
            "queues": [{"id": 70, "logged": True, "paused": False}],
        }}

        self.agent._refresh_statuses_from_wazo(wazo_agents_by_id, {})

        self.assertTrue(self.agent.is_logged)
        self.assertEqual(self.agent.status, "available")

    def test_refresh_resets_to_unknown_without_wazo_agent_or_queue_member(self):
        self.agent.write({"is_logged": True, "status": "available"})

        self.agent._refresh_statuses_from_wazo({}, {})

        self.assertFalse(self.agent.is_logged)
        self.assertFalse(self.agent.is_paused)
        self.assertEqual(self.agent.status, "unknown")


class TestVoipQueueSyncRefreshesAgentStatuses(VoipPhoneServiceCase):
    def test_creating_a_queue_refreshes_its_new_agent_status(self):
        """A freshly synced agent should reflect the PBX state right away,
        instead of sitting on the "unknown" default until someone clicks
        "Refresh Agents List" or logs the agent in or out themselves.

        The refresh itself runs after commit (it's a display concern, not
        routing, so it shouldn't hold up the save) - run it synchronously
        here with postcommit.run(), like core Odoo's own after-commit sync
        tests do (e.g. microsoft_calendar), and invalidate the cache since
        it was written through a different cursor.
        """
        user = new_test_user(self.env, login="queue_sync_status_user", name="Queue Sync Status User")
        self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True
        )._find_or_create_for_user(user)

        with patch.object(
            self.env["voip.pbx.service"].__class__,
            "_get_agents",
            return_value=[{
                "id": PBX_TEST_AGENT_ID,
                "queues": [{"id": PBX_TEST_QUEUE_ID, "logged": True, "paused": False}],
            }],
        ):
            queue = self.env["voip.queue"].create({
                "name": "Support",
                "allowed_user_ids": [Command.link(user.id)],
            })
            self.env.cr.postcommit.run()

        queue.invalidate_recordset()
        self.assertEqual(queue.agent_ids.status, "available")
        self.assertTrue(queue.agent_ids.is_logged)
        self.assertTrue(queue.agent_ids.status_last_sync)

    def test_writing_queue_agent_assignment_refreshes_statuses_after_commit(self):
        """Assigning an agent should still refresh statuses like create()
        does, but deferred to after commit: it's a display concern, not
        call routing, so it shouldn't hold up the save."""
        queue = self.env["voip.queue"].create({"name": "Support"})
        user = new_test_user(self.env, login="queue_write_status_user", name="Queue Write Status User")
        self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True
        )._find_or_create_for_user(user)

        with patch.object(
            self.env["voip.pbx.service"].__class__,
            "_get_agents",
            return_value=[{
                "id": PBX_TEST_AGENT_ID,
                "queues": [{"id": PBX_TEST_QUEUE_ID, "logged": True, "paused": False}],
            }],
        ) as get_agents:
            queue.allowed_user_ids = [Command.link(user.id)]
            get_agents.assert_not_called()
            self.env.cr.postcommit.run()

        queue.invalidate_recordset()
        get_agents.assert_called_once()
        self.assertEqual(queue.agent_ids.status, "available")

    def test_creating_and_writing_a_queue_in_the_same_transaction_refreshes_once(self):
        """create() and write() can each ask for a refresh on the same
        queue within one transaction (e.g. a new queue saved with agents
        already assigned, then immediately re-assigned again) - this must
        not cost one _get_agents() round trip per call site."""
        user = new_test_user(self.env, login="queue_dedup_status_user", name="Queue Dedup Status User")
        self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True
        )._find_or_create_for_user(user)

        with patch.object(
            self.env["voip.pbx.service"].__class__,
            "_get_agents",
            return_value=[{
                "id": PBX_TEST_AGENT_ID,
                "queues": [{"id": PBX_TEST_QUEUE_ID, "logged": True, "paused": False}],
            }],
        ) as get_agents:
            queue = self.env["voip.queue"].create({
                "name": "Support",
                "allowed_user_ids": [Command.link(user.id)],
            })
            queue.allowed_user_ids = [Command.clear()]
            queue.allowed_user_ids = [Command.link(user.id)]
            self.env.cr.postcommit.run()

        get_agents.assert_called_once()

    def test_writing_unrelated_queue_fields_does_not_refresh_agent_statuses(self):
        """Renaming a queue (or any other PBX_QUEUE_SYNC_FIELDS change that
        isn't about who's assigned to it) must not trigger the global,
        unscoped agent-status refresh - only an actual membership change
        should."""
        queue = self.env["voip.queue"].create({"name": "Support"})

        with patch.object(
            self.env["voip.pbx.service"].__class__,
            "_get_agents",
        ) as get_agents:
            queue.name = "Renamed support"
            self.env.cr.postcommit.run()

        get_agents.assert_not_called()

    def test_writing_an_empty_queue_recordset_does_not_call_the_pbx(self):
        """base_partner_merge's generic reference-field sweep calls write()
        unconditionally on its search result, even when nothing matched
        (e.g. merging a contact never used as a queue's "no answer"/"busy"
        route). _refresh_agent_statuses is a global, unscoped PBX call, so
        _sync_pbx must not reach it when there is no queue to sync."""
        with patch.object(
            self.env["voip.pbx.service"].__class__,
            "_get_agents",
        ) as get_agents:
            self.env["voip.queue"].write({"name": "Support"})

        get_agents.assert_not_called()
