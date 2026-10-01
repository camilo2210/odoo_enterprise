from datetime import timedelta
from unittest.mock import patch

from .common_voip import VoipPhoneServiceCase
from freezegun import freeze_time

from odoo import fields
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools import mute_logger


HANGUP_CALL = "odoo.addons.voip.models.phone_service_api.PhoneServiceAPI.hangup_call"


class TestVoipCall(TransactionCase):
    def test_rejected_call_is_not_reverted_to_missed(self):
        call = self.env["voip.call"].create({
            "phone_number": "+15550001111",
            "direction": "incoming",
            "user_id": self.env.uid,
        })
        call.reject_call()
        call.miss_call()
        self.assertEqual(call.state, "rejected")

    def test_decline_via_pbx_noop_without_conversation(self):
        call = self.env["voip.call"].create({
            "phone_number": "+15550001111",
            "direction": "incoming",
            "user_id": self.env.uid,
        })
        with patch(HANGUP_CALL) as hangup_call:
            call._decline_via_pbx()
        hangup_call.assert_not_called()

    def test_get_recent_phone_calls_by_partner_id(self):
        partner_a = self.env["res.partner"].create({"name": "Partner A"})
        partner_b = self.env["res.partner"].create({"name": "Partner B"})
        calls = self.env["voip.call"].create([
            {
                "phone_number": "+32498111111",
                "partner_id": partner_a.id,
                "user_id": self.env.uid,
            },
            {
                "phone_number": "+32498222222",
                "partner_id": partner_b.id,
                "user_id": self.env.uid,
            },
            {
                "phone_number": "+32498111111",
                "partner_id": partner_a.id,
                "user_id": self.env.uid,
            },
        ])

        result = self.env["voip.call"].get_recent_phone_calls(partner_id=partner_a.id)

        self.assertEqual(set(result["ids"]), set((calls[0] | calls[2]).ids))

    def test_get_prefill_data_returns_partner_identity(self):
        partner = self.env["res.partner"].create({
            "name": "Prefill Partner",
            "phone": "+32499123456",
        })

        result = self.env["voip.call"].get_prefill_data("res.partner", partner.id)

        self.assertEqual(result["partner_id"], partner.id)
        self.assertTrue(result["phone"])

    def test_has_active_call_is_synchronized_on_create(self):
        incoming_user = new_test_user(self.env, login="voip_incoming_user")
        outgoing_user = new_test_user(self.env, login="voip_outgoing_user")
        ongoing_user = new_test_user(self.env, login="voip_ongoing_user")

        self.env["voip.call"].create({
            "phone_number": "1234567890",
            "direction": "incoming",
            "state": "calling",
            "user_id": incoming_user.id,
        })
        self.env["voip.call"].create({
            "phone_number": "0987654321",
            "direction": "outgoing",
            "state": "calling",
            "user_id": outgoing_user.id,
        })
        self.env["voip.call"].create({
            "phone_number": "1122334455",
            "direction": "incoming",
            "state": "ongoing",
            "start_date": fields.Datetime.now(),
            "user_id": ongoing_user.id,
        })

        self.assertFalse(incoming_user.has_active_call)
        self.assertTrue(outgoing_user.has_active_call)
        self.assertTrue(ongoing_user.has_active_call)

    def test_has_active_call_is_synchronized_on_write(self):
        user = new_test_user(self.env, login="voip_write_active_call_user")
        call = self.env["voip.call"].create({
            "phone_number": "0987654321",
            "direction": "incoming",
            "state": "calling",
            "user_id": user.id,
        })
        self.assertFalse(user.has_active_call)

        call.start_call()
        self.assertEqual(call.state, "ongoing")
        self.assertTrue(user.has_active_call)

        call.end_call()
        self.assertEqual(call.state, "terminated")
        self.assertFalse(user.has_active_call)

    def test_stale_calls_are_not_active_for_presence(self):
        calling_user = new_test_user(self.env, login="voip_stale_calling_user")
        ongoing_user = new_test_user(self.env, login="voip_stale_ongoing_user")

        with freeze_time("2024-01-01 12:00:00"):
            calling_call = self.env["voip.call"].create({
                "phone_number": "1234567890",
                "direction": "outgoing",
                "state": "calling",
                "user_id": calling_user.id,
            })
            ongoing_call = self.env["voip.call"].create({
                "phone_number": "0987654321",
                "direction": "incoming",
                "state": "ongoing",
                "start_date": fields.Datetime.now(),
                "user_id": ongoing_user.id,
            })
            self.env.cr.execute(
                "UPDATE voip_call SET create_date = %s WHERE id IN %s",
                (fields.Datetime.now(), (calling_call.id, ongoing_call.id)),
            )
            calling_call.invalidate_recordset(["create_date"])

        self.assertTrue(calling_user.has_active_call)
        self.assertTrue(ongoing_user.has_active_call)

        with freeze_time("2024-01-01 12:06:00"):
            calling_call._sync_has_active_call()
        with freeze_time("2024-01-01 16:01:00"):
            ongoing_call._sync_has_active_call()

        self.assertFalse(calling_user.has_active_call)
        self.assertFalse(ongoing_user.has_active_call)

    def test_cleanup_stuck_calls(self):
        call_stuck_calling = self.env[
            "voip.call"
        ].create(  # Create a call that is stuck in 'calling' state (older than 5 minutes)
            {
                "phone_number": "1234567890",
                "direction": "outgoing",
                "state": "calling",
            },
        )
        self.env.cr.execute(
            "UPDATE voip_call SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(minutes=6), call_stuck_calling.id),
        )
        call_stuck_calling.invalidate_recordset(["create_date"])
        call_ok_calling = self.env[
            "voip.call"
        ].create(  # Create a call that is NOT stuck in 'calling' state (created now)
            {
                "phone_number": "0987654321",
                "direction": "outgoing",
                "state": "calling",
            },
        )
        call_stuck_ongoing = self.env[
            "voip.call"
        ].create(  # Create a call that is stuck in 'ongoing' state (older than 4 hours)
            {
                "phone_number": "1122334455",
                "direction": "outgoing",
                "state": "ongoing",
                "start_date": fields.Datetime.now() - timedelta(hours=5),
            },
        )
        call_ok_ongoing = self.env[
            "voip.call"
        ].create(  # Create a call that is NOT stuck in 'ongoing' state (3 hours ago)
            {
                "phone_number": "5544332211",
                "direction": "outgoing",
                "state": "ongoing",
                "start_date": fields.Datetime.now() - timedelta(hours=3),
            },
        )

        self.env["voip.call"]._cleanup_stuck_calls()
        self.assertEqual(call_stuck_calling.state, "ended_unexpectedly")
        self.assertEqual(call_ok_calling.state, "calling")
        self.assertEqual(call_stuck_ongoing.state, "ended_unexpectedly")
        self.assertEqual(call_ok_ongoing.state, "ongoing")

    def test_is_within_same_company_true_with_contacts_of_same_company(self):
        caller = new_test_user(self.env, login="test_user")
        company = self.env["res.partner"].create(
            {
                "name": "Test Company",
            },
        )
        caller_partner = self.env["res.partner"].create(
            {
                "name": "Contact 1",
                "parent_id": company.id,
            },
        )
        callee_partner = self.env["res.partner"].create(
            {
                "name": "Contact 2",
                "parent_id": company.id,
            },
        )
        self.assertEqual(caller_partner.commercial_partner_id, company)
        self.assertEqual(callee_partner.commercial_partner_id, company)
        caller.partner_id = caller_partner
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "partner_id": callee_partner.id,
                "user_id": caller.id,
            },
        )
        self.assertTrue(call.is_within_same_company)

    def test_is_within_same_company_false_with_contacts_of_different_companies(self):
        caller = new_test_user(self.env, login="test_user")
        company_1 = self.env["res.partner"].create(
            {
                "name": "Test Company 1",
            },
        )
        company_2 = self.env["res.partner"].create(
            {
                "name": "Test Company 2",
            },
        )
        caller_partner = self.env["res.partner"].create(
            {
                "name": "Contact 1",
                "parent_id": company_1.id,
            },
        )
        callee_partner = self.env["res.partner"].create(
            {
                "name": "Contact 2",
                "parent_id": company_2.id,
            },
        )
        self.assertEqual(caller_partner.commercial_partner_id, company_1)
        self.assertEqual(callee_partner.commercial_partner_id, company_2)
        caller.partner_id = caller_partner
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "partner_id": callee_partner.id,
                "user_id": caller.id,
            },
        )
        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_false_no_partner(self):
        caller = new_test_user(self.env, login="test_user")
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "user_id": caller.id,
            },
        )
        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_false_user_no_partner(self):
        company = self.env["res.partner"].create(
            {
                "name": "Test Company",
            },
        )
        caller = new_test_user(self.env, login="test_user")
        callee_partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "partner@example.com",
            },
        )
        callee_partner.commercial_partner_id = company
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "partner_id": callee_partner.id,
                "user_id": caller.id,
            },
        )
        self.assertFalse(call.is_within_same_company)

    def test_get_contact_info_with_voip_extension(self):
        """
        Tests that `get_contact_info` resolves extensions based on the user's provider.

        - Internal users are found when the dialed phone number matches their extension.
        - The search for extensions is scoped to the user's VoIP provider to prevent cross-provider conflicts.
        """
        provider_a = self.env["voip.provider"].create({"name": "Provider A"})
        provider_b = self.env["voip.provider"].create({"name": "Provider B"})
        user_of_a = new_test_user(self.env, login="User A", voip_username="8888", voip_provider_id=provider_a.id)
        user_of_b = new_test_user(self.env, login="User B", voip_username="8888", voip_provider_id=provider_b.id)
        voip_user = new_test_user(
            self.env, login="voip_user",
            voip_provider_id=provider_a.id,  # user's provider is Provider A
        )
        call = self.env["voip.call"].create(
            {
                "phone_number": "8888",
                "user_id": voip_user.id,
            },
        )
        store_data = call.with_user(voip_user).get_contact_info().as_dict()

        # Found user should be the one linked to Provider A.
        self.assertEqual(store_data["res.partner"][0]["id"], user_of_a.partner_id.id)

        voip_user.voip_provider_id = provider_b.id  # Change user's provider for Provider B.
        call = self.env["voip.call"].create(
            {
                "phone_number": "8888",
                "user_id": voip_user.id,
            },
        )
        store_data = call.with_user(voip_user).get_contact_info().as_dict()

        # Found user should now be the one linked to Provider B.
        self.assertEqual(store_data["res.partner"][0]["id"], user_of_b.partner_id.id)

    def test_duration_stored_and_end_date_computed(self):
        caller = new_test_user(self.env, login="test_user")
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "user_id": caller.id,
            },
        )

        call.start_call()
        five_minutes_ago = fields.Datetime.now() - timedelta(minutes=5)
        call.write({"start_date": five_minutes_ago, "duration": False})
        call.end_call()
        call.invalidate_recordset()

        self.assertGreater(call.duration, 0)
        expected_end_date = call.start_date + timedelta(seconds=call.duration)
        self.assertEqual(call.end_date, expected_end_date)

    def test_start_end_call_uses_provided_timestamps(self):
        """start_call and end_call record the provided timestamps as start_date and duration."""
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "direction": "incoming",
        })
        call.start_call(at="2024-01-01 12:00:00")
        call.end_call(at="2024-01-01 12:05:00")
        self.assertEqual(call.state, "terminated")
        self.assertEqual(call.start_date, fields.Datetime.to_datetime("2024-01-01 12:00:00"))
        self.assertEqual(call.duration, 300)  # 5 minutes in seconds

    def test_end_call_then_start_call_out_of_order(self):
        """When end_call runs before start_call (out-of-order webhook delivery),
        start_call corrects start_date and computes duration from the placeholder."""
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "direction": "incoming",
        })
        call.end_call(at="2024-01-01 12:05:00")
        self.assertEqual(call.state, "terminated")
        self.assertEqual(call.start_date, fields.Datetime.to_datetime("2024-01-01 12:05:00"))  # placeholder
        self.assertEqual(call.duration, 0)

        call.start_call(at="2024-01-01 12:00:00")
        self.assertEqual(call.state, "terminated")  # state unchanged
        self.assertEqual(call.start_date, fields.Datetime.to_datetime("2024-01-01 12:00:00"))  # corrected
        self.assertEqual(call.duration, 300)  # 5 minutes in seconds

    def test_start_call_without_at(self):
        """start_call(at=None) uses the current time as start_date."""
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "direction": "incoming",
        })
        with freeze_time("2024-01-01 12:00:00"):
            call.start_call()
        self.assertEqual(call.state, "ongoing")
        self.assertEqual(call.start_date, fields.Datetime.to_datetime("2024-01-01 12:00:00"))

    def test_end_call_without_at(self):
        """end_call(at=None) uses the current time to compute duration."""
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "direction": "incoming",
        })
        call.start_call(at="2024-01-01 12:00:00")
        with freeze_time("2024-01-01 12:05:00"):
            call.end_call()
        self.assertEqual(call.state, "terminated")
        start = fields.Datetime.to_datetime("2024-01-01 12:00:00")
        end = fields.Datetime.to_datetime("2024-01-01 12:05:00")
        duration = (end - start).total_seconds()
        self.assertEqual(call.duration, duration)  # 5 minutes in seconds

    def test_end_call_without_at_no_start_date(self):
        """end_call(at=None) with no prior start_call stores current time as placeholder and duration=0."""
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "direction": "incoming",
        })
        with freeze_time("2024-01-01 12:00:00"):
            call.end_call()
        self.assertEqual(call.state, "terminated")
        self.assertEqual(call.start_date, fields.Datetime.to_datetime("2024-01-01 12:00:00"))
        self.assertEqual(call.duration, 0)

    def test_start_call_without_at_after_end_call(self):
        """start_call(at=None) after end_call corrects start_date to now; duration is clamped to 0."""
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "direction": "incoming",
        })
        call.end_call(at="2024-01-01 12:05:00")
        with freeze_time("2024-01-01 12:10:00"):
            call.start_call()
        self.assertEqual(call.state, "terminated")
        self.assertEqual(call.start_date, fields.Datetime.to_datetime("2024-01-01 12:10:00"))
        self.assertEqual(call.duration, 0)  # max(0, past_placeholder - now) clamps to 0

    def test_end_date_searches(self):
        """
        Test searching voip.call records by end_date computed field using
        various operators and Odoo syntax (required to ensure that the calendar
        view works, with records that start out of range but end within range).
        """
        self.env["voip.call"].search([]).unlink()
        caller = new_test_user(self.env, login="test_user")
        base_date = fields.Datetime.now()

        # Create test records with different start_date and duration values
        calls = self.env["voip.call"].create([
            {
                "phone_number": "+1111111111",
                "user_id": caller.id,
                "start_date": base_date,
                "duration": 1 * 3600,  # end_date = base_date + 1 hour
            },
            {
                "phone_number": "+2222222222",
                "user_id": caller.id,
                "start_date": base_date + timedelta(hours=1),
                "duration": 2 * 3600,  # end_date = base_date + 3 hours
            },
            {
                "phone_number": "+3333333333",
                "user_id": caller.id,
                "start_date": base_date + timedelta(hours=2),
                "duration": 3 * 3600,  # end_date = base_date + 5 hours
            },
            {
                "phone_number": "+4444444444",
                "user_id": caller.id,
                "start_date": base_date + timedelta(hours=1),  # ! same as end_date of first call
                "duration": False,  # end_date is False (no duration yet)
            },
            {
                "phone_number": "+5555555555",
                "user_id": caller.id,
                # no start_date/duration (end_date is False)
            },
        ])

        test_date = base_date + timedelta(hours=2)

        # Test equality operator (=)
        results = self.env["voip.call"].search([("end_date", "=", base_date + timedelta(hours=1))])
        self.assertEqual(results.ids, [calls[0].id])

        # Test less than (<)
        results = self.env["voip.call"].search([("end_date", "<", test_date)])
        self.assertEqual(results.ids, [calls[0].id])

        # Test less than or equal (<=)
        results = self.env["voip.call"].search([("end_date", "<=", test_date)])
        self.assertEqual(results.ids, [calls[0].id])

        # Test greater than (>)
        results = self.env["voip.call"].search([("end_date", ">", test_date)])
        self.assertEqual(results.ids, [calls[1].id, calls[2].id])

        # Test greater than or equal (>=)
        results = self.env["voip.call"].search([("end_date", ">=", test_date)])
        self.assertEqual(results.ids, [calls[1].id, calls[2].id])

        # Test not equal (!=)
        results = self.env["voip.call"].search([("end_date", "!=", calls[1].end_date)])
        self.assertEqual(results.ids, [calls[0].id, calls[2].id, calls[3].id, calls[4].id])

        # Test with Odoo special syntax: +1w (1 week from now)
        results = self.env["voip.call"].search([("end_date", "<", "+1w")])
        self.assertEqual(results.ids, [calls[0].id, calls[1].id, calls[2].id])

    def test_effective_start_date_searches(self):
        """
        Test searching voip.call records by effective_start_date computed field
        using various operators and Odoo syntax (required to ensure that the
        calendar view works, even for calls that did not start).
        """
        self.env["voip.call"].search([]).unlink()
        caller = new_test_user(self.env, login="test_user")
        base_date = fields.Datetime.now()

        # Create test records with different scenarios
        calls = self.env["voip.call"].create([
            {
                "phone_number": "+1111111111",
                "user_id": caller.id,
                "start_date": base_date + timedelta(hours=1),
            },
            {
                "phone_number": "+2222222222",
                "user_id": caller.id,
                "start_date": base_date + timedelta(hours=3),
            },
            {
                "phone_number": "+3333333333",
                "user_id": caller.id,
                "start_date": base_date + timedelta(days=8),
            },
            {
                "phone_number": "+4444444444",
                "user_id": caller.id,
                # no start_date, will use create_date
            },
        ])

        test_date = base_date + timedelta(hours=2)

        # Test equality operator (=)
        results = self.env["voip.call"].search([("effective_start_date", "=", base_date + timedelta(hours=1))])
        self.assertEqual(results.ids, [calls[0].id])
        results = self.env["voip.call"].search([("effective_start_date", "=", calls[3].create_date)])
        self.assertEqual(results.ids, [calls[3].id])

        # Test less than (<)
        results = self.env["voip.call"].search([("effective_start_date", "<", test_date)])
        self.assertEqual(results.ids, [calls[0].id, calls[3].id])

        # Test less than or equal (<=)
        results = self.env["voip.call"].search([("effective_start_date", "<=", test_date)])
        self.assertEqual(results.ids, [calls[0].id, calls[3].id])

        # Test greater than (>)
        results = self.env["voip.call"].search([("effective_start_date", ">", test_date)])
        self.assertEqual(results.ids, [calls[1].id, calls[2].id])

        # Test greater than or equal (>=)
        results = self.env["voip.call"].search([("effective_start_date", ">=", test_date)])
        self.assertEqual(results.ids, [calls[1].id, calls[2].id])

        # Test not equal (!=)
        results = self.env["voip.call"].search([("effective_start_date", "!=", calls[0].effective_start_date)])
        self.assertEqual(results.ids, [calls[1].id, calls[2].id, calls[3].id])

        # Test with Odoo special syntax: +1w (1 week from now)
        results = self.env["voip.call"].search([("effective_start_date", "<", "+1w")])
        self.assertEqual(results.ids, [calls[0].id, calls[1].id, calls[3].id])

    def _create_call_with_automated_activity(self):
        """Helper: create an outgoing call with automated activity via create_and_format."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        result = self.env["voip.call"].create_and_format(
            phone_number="+1234567890",
            direction="outgoing",
            res_id=partner.id,
            res_model="res.partner",
        )
        return self.env["voip.call"].browse(result["ids"][0])

    def test_create_activity_is_automated(self):
        """create_and_format should create an activity with automated=True."""
        call = self._create_call_with_automated_activity()
        self.assertTrue(call.activity_id)
        self.assertTrue(call.activity_id.automated)

    def test_abort_call_cleans_automated_activity(self):
        """abort_call should delete the automated activity."""
        call = self._create_call_with_automated_activity()
        activity = call.activity_id
        call.abort_call()
        self.assertEqual(call.state, "aborted")
        self.assertFalse(activity.exists())

    def test_reject_call_cleans_automated_activity(self):
        """reject_call should delete the automated activity."""
        call = self._create_call_with_automated_activity()
        activity = call.activity_id
        call.reject_call()
        self.assertEqual(call.state, "rejected")
        self.assertFalse(activity.exists())

    def test_end_call_preserves_automated_activity(self):
        """end_call should NOT delete the automated activity."""
        call = self._create_call_with_automated_activity()
        activity = call.activity_id
        call.end_call()
        self.assertEqual(call.state, "terminated")
        self.assertTrue(activity.exists())

    def test_cleanup_stuck_calls_cleans_automated_activity(self):
        """_cleanup_stuck_calls should delete the automated activity on stuck calls."""
        call = self._create_call_with_automated_activity()
        activity = call.activity_id
        self.env.cr.execute(
            "UPDATE voip_call SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(minutes=30), call.id),
        )
        call.invalidate_recordset(["create_date"])
        call.state = "calling"

        self.env["voip.call"]._cleanup_stuck_calls()
        self.assertEqual(call.state, "ended_unexpectedly")
        self.assertFalse(activity.exists())

    def test_cleanup_does_not_touch_non_automated_activity(self):
        """Calls with non-automated activities should not have their activity cleaned up."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "direction": "outgoing",
            "state": "calling",
        })
        activity = partner.activity_schedule(
            "mail.mail_activity_data_call",
            summary="Manual activity",
            user_id=self.env.uid,
            automated=False,
        )
        call.activity_id = activity.id

        call.reject_call()
        self.assertEqual(call.state, "rejected")
        self.assertTrue(activity.exists(), "Non-automated activity should not be deleted")

    def test_action_log_call_without_form_context(self):
        """action_log_call() without active_model/active_id should configure the wizard
        to log against the call's contact."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": partner.id,
        })
        with Form.from_action(self.env, call.action_log_call()) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, partner)
            self.assertEqual(form.res_ids, f"[{partner.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "res.partner")

    def test_action_log_call_with_matching_model(self):
        """When active_model matches a registered option (res.partner),
        the wizard should pre-select that record type and record."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": partner.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="res.partner", active_id=partner.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, partner)
            self.assertEqual(form.res_ids, f"[{partner.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "res.partner")

    def test_action_log_call_with_non_matching_model(self):
        """When active_model does NOT match any registered option, the wizard
        should fall back to the default contact behavior."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": partner.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="nonexistent.model", active_id=999),
        ) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, partner)
            self.assertEqual(form.res_ids, f"[{partner.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "res.partner")

    def test_action_log_call_with_mismatched_record(self):
        """When action_log_call receives a mismatched record (a record doesn't
        link to the call's partner), it should fall back to the call's own
        partner."""
        call_partner = self.env["res.partner"].create({"name": "Call Partner"})
        other_partner = self.env["res.partner"].create({"name": "Other Partner"})
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": call_partner.id,
        })
        with Form.from_action(
            self.env,
            call.action_log_call(
                active_model="res.partner", active_id=other_partner.id,
            ),
        ) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, call_partner)
            self.assertEqual(form.res_ids, f"[{call_partner.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "res.partner")

    def _make_cost_line(self, **payload):
        return self.env["voip.call.cost.line"].create({
            "event_id": payload.pop("event_id", "evt"),
            "occurred_at": payload.pop("occurred_at", fields.Datetime.now()),
            "credits": payload.pop("credits", 0.3369),
            "payload": payload,
        })

    def _store_cost(self, event_id, total_cost):
        self.env["voip.call.cost.line"]._handle_call_cost_event(
            event_id,
            {"total_cost": total_cost, "from": "+32485794187"},
            fields.Datetime.now(),
        )
        return self.env["voip.call.cost.line"].search([("event_id", "=", event_id)])

    def test_zero_cost_creates_no_cost_line(self):
        self.assertFalse(self._store_cost("evt_zero", "0.0000"))

    def test_nonzero_cost_creates_cost_line(self):
        self.assertTrue(self._store_cost("evt_nonzero", "0.3369"))

    @mute_logger("odoo.sql_db")
    def test_duplicate_cost_event_is_ignored(self):
        self._store_cost("evt_duplicate", "0.3369")
        lines = self._store_cost("evt_duplicate", "0.3369")
        self.assertEqual(len(lines), 1)

    def test_cost_display_blank_when_zero(self):
        call = self.env["voip.call"].create({
            "phone_number": "+32485794187", "direction": "incoming", "user_id": self.env.uid,
        })
        self.assertEqual(call.cost_display, "")

    def test_cost_display_shown_when_nonzero(self):
        call = self.env["voip.call"].create({
            "phone_number": "+32485794187", "direction": "outgoing", "user_id": self.env.uid,
        })
        self._make_cost_line(
            event_id="evt_disp", direction="outgoing", billed_duration_secs=60,
            **{"from": "+14375291026", "to": "+32485794187"})
        self.assertIn("Credits", call.cost_display)

    def test_cost_line_matches_outgoing_call_by_number_and_time(self):
        call = self.env["voip.call"].create({
            "phone_number": "+32485794187",
            "direction": "outgoing",
            "user_id": self.env.uid,
        })
        line = self._make_cost_line(
            event_id="evt_out",
            direction="outgoing",
            billed_duration_secs=60,
            **{"from": "+14375291026", "to": "+32485794187"},
        )
        self.assertEqual(line.call_id, call)
        self.assertAlmostEqual(call.cost, 0.3369)

    def test_cost_line_matches_incoming_call_by_caller_number(self):
        call = self.env["voip.call"].create({
            "phone_number": "+32485794187",
            "direction": "incoming",
            "user_id": self.env.uid,
        })
        line = self._make_cost_line(
            event_id="evt_in",
            direction="incoming",
            billed_duration_secs=60,
            **{"from": "+32485794187", "to": "+14375291026"},
        )
        self.assertEqual(line.call_id, call)

    def test_cost_line_matches_despite_national_format(self):
        call = self.env["voip.call"].create({
            "phone_number": "0485794187",
            "direction": "outgoing",
            "user_id": self.env.uid,
        })
        line = self._make_cost_line(
            event_id="evt_natl", direction="outgoing", to="+32485794187",
        )
        self.assertEqual(line.call_id, call)

    def test_cost_line_unmatched_when_number_differs(self):
        self.env["voip.call"].create({
            "phone_number": "+32499999999",
            "direction": "outgoing",
            "user_id": self.env.uid,
        })
        line = self._make_cost_line(
            event_id="evt_nomatch", direction="outgoing", to="+32485794187",
        )
        self.assertFalse(line.call_id)

    def test_cost_line_unmatched_when_call_outside_window(self):
        self.env["voip.call"].create({
            "phone_number": "+32485794187",
            "direction": "outgoing",
            "user_id": self.env.uid,
        })
        # The call exists now, but this cost lands two hours later: it falls
        # before the lookback window, so it must not attach.
        line = self._make_cost_line(
            event_id="evt_old", direction="outgoing", to="+32485794187",
            billed_duration_secs=60,
            occurred_at=fields.Datetime.now() + timedelta(hours=2),
        )
        self.assertFalse(line.call_id)

    def test_orphan_cost_line_rematched_when_call_appears_later(self):
        """A cost recorded before its call exists stays unlinked, then is
        attached by the re-match cron once the call shows up."""
        line = self._make_cost_line(
            event_id="evt_orphan", direction="outgoing", billed_duration_secs=60,
            to="+32485794187",
        )
        self.assertFalse(line.call_id, "no matching call exists yet")

        call = self.env["voip.call"].create({
            "phone_number": "+32485794187",
            "direction": "outgoing",
            "user_id": self.env.uid,
        })
        self.env["voip.call.cost.line"]._cron_link_orphan_cost_lines()

        self.assertEqual(line.call_id, call)
        self.assertAlmostEqual(call.cost, 0.3369)

    def test_cost_line_disambiguates_between_calls_to_same_number(self):
        """Two calls to the same number sit in the window: the cost attaches to
        the one whose end is closest to when the cost was emitted -- even a few-
        second call whose billed duration is rounded up to a minute -- and the
        ambiguity is logged rather than resolved by creation order."""
        now = fields.Datetime.now()
        earlier = self.env["voip.call"].create({
            "phone_number": "+32485794187", "direction": "outgoing",
            "user_id": self.env.uid,
            "start_date": now - timedelta(seconds=300), "duration": 120,
        })
        just_ended = self.env["voip.call"].create({
            "phone_number": "+32485794187", "direction": "outgoing",
            "user_id": self.env.uid,
            "start_date": now - timedelta(seconds=3), "duration": 3,
        })
        with self.assertLogs(
            "odoo.addons.voip.models.voip_call_cost_line", level="WARNING",
        ) as log_cm:
            line = self._make_cost_line(
                event_id="evt_ambiguous", direction="outgoing",
                billed_duration_secs=60, to="+32485794187", occurred_at=now,
            )
        self.assertEqual(line.call_id, just_ended)
        self.assertFalse(earlier.cost)
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn("evt_ambiguous", log_cm.output[0])


@tagged("-at_install", "post_install")
class TestVoipCallCallerResolution(VoipPhoneServiceCase):
    """An incoming call's caller-id is resolved at creation (the reliable browser
    INVITE path), so it is readable even when the PBX webhook can't reach the
    server (e.g. a localhost dev server)."""

    def setUp(self):
        super().setUp()
        self.user = self.new_voip_user()
        self.extension = self.env["voip.extension"].search(
            [("destination_ref", "=", f"res.users,{self.user.id}")], limit=1)

    def _create_incoming(self, phone_number, direction="incoming"):
        result = self.env["voip.call"].with_user(self.user).create_and_format(
            phone_number=phone_number, direction=direction)
        return self.env["voip.call"].browse(result["ids"][0])

    def test_incoming_internal_username_stored_as_extension(self):
        call = self._create_incoming(self.user.voip_username)
        self.assertEqual(call.phone_number, self.extension.number)

    def test_resolve_incoming_internal_username_returns_extension(self):
        self.assertTrue(self.extension.number)
        self.assertEqual(
            self.env["voip.call"]._resolve_incoming_caller_number(self.user.voip_username),
            self.extension.number)

    def test_resolve_incoming_external_number_normalized_to_e164(self):
        self.assertEqual(
            self.env["voip.call"]._resolve_incoming_caller_number("0032485794187"), "+32485794187")

    def test_resolve_incoming_unknown_identity_left_unchanged(self):
        self.assertEqual(
            self.env["voip.call"]._resolve_incoming_caller_number("sip-junk_abc"), "sip-junk_abc")

    def test_incoming_external_number_stored_as_e164(self):
        call = self._create_incoming("0032485794187")
        self.assertEqual(call.phone_number, "+32485794187")

    def test_outgoing_number_left_untouched(self):
        call = self._create_incoming(self.user.voip_username, direction="outgoing")
        self.assertEqual(call.phone_number, self.user.voip_username)

    def test_get_contact_info_resolves_partner_from_extension(self):
        call = self.env["voip.call"].create({
            "phone_number": self.extension.number,
            "direction": "incoming",
            "user_id": self.user.id,
        })
        store_data = call.with_user(self.user).get_contact_info().as_dict()
        self.assertEqual(store_data["res.partner"][0]["id"], self.user.partner_id.id)


@tagged("-at_install", "post_install")
class TestVoipCallOutgoingDialResolution(VoipPhoneServiceCase):
    """Dialing a colleague's own DID is rewritten to their extension so the call
    stays internal (PBX-only) instead of looping out the trunk, which would
    destroy the caller's identity."""

    def setUp(self):
        super().setUp()
        self.user = self.new_voip_user()
        self.user_phone = self.get_user_phone(self.user)
        self.extension = self.env["voip.extension"].search(
            [("destination_ref", "=", f"res.users,{self.user.id}")], limit=1)

    def _resolve(self, number):
        return self.env["voip.call"].with_user(self.user).resolve_outgoing_dial_number(number)

    def test_own_did_resolves_to_extension(self):
        self.assertEqual(self._resolve(self.user_phone), {
            "number": self.extension.number,
            "is_internal": True,
        })

    def test_did_in_non_e164_form_resolves_to_extension(self):
        self.assertEqual(self._resolve(self.user_phone.replace("+", "00")), {
            "number": self.extension.number,
            "is_internal": True,
        })

    def test_known_extension_is_internal(self):
        self.assertEqual(self._resolve(self.extension.number), {
            "number": self.extension.number,
            "is_internal": True,
        })

    def test_feature_code_is_internal(self):
        self.assertEqual(self._resolve("*551"), {
            "number": "*551",
            "is_internal": True,
        })

    def test_non_did_number_is_external(self):
        self.assertEqual(self._resolve("+3287654321"), {
            "number": "+3287654321",
            "is_internal": False,
        })

    def test_short_unknown_number_is_external(self):
        self.assertEqual(self._resolve("123"), {
            "number": "123",
            "is_internal": False,
        })

    def test_released_did_left_external(self):
        did = self.env["voip.did.number"].search([("user_id", "=", self.user.id)])
        did.with_context(voip_skip_pbx_sync=True).state = "released"
        self.assertEqual(self._resolve(self.user_phone), {
            "number": self.user_phone,
            "is_internal": False,
        })
