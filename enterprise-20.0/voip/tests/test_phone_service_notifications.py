from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import common, tagged
from odoo.tests.common import new_test_user

from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI, PhoneServiceError
from odoo.addons.voip.tests.common_voip import forbid_phone_service_http, mock_pbx_layer, pbx_router

REQUIREMENT_GROUP_LOGGER = "odoo.addons.voip.models.voip_requirement_group"
DID_NUMBER_LOGGER = "odoo.addons.voip.models.voip_did_number"


def _mock_phone_service(route, params, retry_registration=True):
    return pbx_router(route, params)


def _patch_phone_service():
    return patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_phone_service)


@tagged("voip")
class TestPhoneServiceNotificationsBase(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_be = cls.env.ref("base.be")
        existing = cls.env["voip.did.number"].search([]).with_context(voip_skip_pbx_sync=True)
        existing.write({"state": "released"})
        existing.unlink()
        cls.env["voip.requirement.group"].search([]).unlink()

    def setUp(self):
        super().setUp()
        forbid_phone_service_http(self)
        mock_pbx_layer(self)

    def _create_did(self, did_number="+3287000001", state="pending", **values):
        with _patch_phone_service():
            return self.env["voip.did.number"].create({
                "did_number": did_number,
                "did_number_type": "local",
                "state": state,
                "country_id": self.country_be.id,
                **values,
            })

    def _create_requirement_group(self, telnyx_id="rg_test_001", status="unapproved"):
        with _patch_phone_service():
            return self.env["voip.requirement.group"].with_context(
                skip_validation=True,
                default_country_id=self.country_be.id,
                default_did_number_type="local",
            ).create({
                "telnyx_requirement_group_id": telnyx_id,
                "status": status,
            })

    def _handle_order_event(self, payload):
        with _patch_phone_service():
            self.env["voip.did.number"]._handle_status_event(payload)

    _handle_deletion_event = _handle_order_event

    def _handle_requirement_group_event(self, payload):
        with _patch_phone_service():
            self.env["voip.requirement.group"]._handle_status_event(payload)


@tagged("voip")
class TestNumberOrderEvent(TestPhoneServiceNotificationsBase):

    def test_number_request_cron_submits_and_reconciles_open_requests(self):
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "79b0569a-c80a-44c5-8367-50a10b3bbc16",
            "state": "pending",
            "country_id": self.country_be.id,
            "did_number_type": "mobile",
            "quantity": 1,
            "requested_by_id": self.env.user.id,
        })
        comments = [{
            "id": "comment_reconciled",
            "body": "Please confirm the proposed number.",
            "created_at": "2026-09-08T10:00:00Z",
        }]

        with (
            patch.object(
                PhoneServiceAPI,
                "create_advanced_order",
                return_value={"id": "advanced_reconciled", "status": "processing"},
            ) as create_order,
            patch.object(
                PhoneServiceAPI,
                "get_number_request_statuses",
                return_value={number_request.request_uuid: {
                    "request_uuid": number_request.request_uuid,
                    "status": "hold",
                    "candidate_numbers": ["+32470000001"],
                    "comments": comments,
                }},
            ),
        ):
            number_request._cron_sync_number_requests()

        create_order.assert_called_once_with(
            request_uuid=number_request.request_uuid,
            country_code="BE",
            phone_number_type="mobile",
            quantity=1,
            area_code=None,
            requirement_group_id=None,
        )
        self.assertEqual(number_request.provider_order_id, "advanced_reconciled")
        self.assertEqual(number_request.state, "hold")
        self.assertEqual(number_request.candidate_numbers, "+32470000001")
        self.assertTrue(number_request.message_ids.filtered(
            lambda message: "Please confirm the proposed number." in (message.body or ""),
        ))

    def test_number_request_cron_surfaces_permanent_submission_failure(self):
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "c4e20d7a-2ca1-4e2d-a28f-89d700000002",
            "state": "pending",
            "country_id": self.country_be.id,
            "did_number_type": "mobile",
            "quantity": 1,
            "requested_by_id": self.env.user.id,
        })
        error = PhoneServiceError(
            "The request sent to the Odoo Phone Service is invalid.",
            error_key="bad_request",
        )

        with patch.object(PhoneServiceAPI, "create_advanced_order", side_effect=error) as submit:
            self.env["voip.did.number.request"]._cron_sync_number_requests()
            self.assertEqual(number_request.state, "failed")
            self.assertTrue(number_request.message_ids.filtered(
                lambda message: "request sent to the Odoo Phone Service is invalid" in (message.body or ""),
            ))
            submit.reset_mock()
            self.env["voip.did.number.request"]._cron_sync_number_requests()
            submit.assert_not_called()

    def test_number_request_cron_collects_delayed_terminal_comment(self):
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "db199ebe-1888-4990-803b-2a4049dd75db",
            "provider_order_id": "advanced_failed",
            "state": "failed",
            "country_id": self.country_be.id,
            "did_number_type": "mobile",
            "quantity": 1,
            "requested_by_id": self.env.user.id,
        })

        with patch.object(
            PhoneServiceAPI,
            "get_number_request_statuses",
            return_value={number_request.request_uuid: {
                "request_uuid": number_request.request_uuid,
                "status": "failed",
                "comments": [{
                    "id": "delayed_failure_comment",
                    "body": "The request could not be fulfilled.",
                    "created_at": "2026-09-08T10:00:00Z",
                }],
            }},
        ):
            number_request._cron_sync_number_requests()

        self.assertTrue(number_request.message_ids.filtered(
            lambda message: "The request could not be fulfilled." in (message.body or ""),
        ))

    def test_number_request_cron_ignores_aged_terminal_request_with_candidates(self):
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "b367e27e-f4b7-45dc-8221-834e2336573c",
            "provider_order_id": "advanced_ordered",
            "state": "ordered",
            "country_id": self.country_be.id,
            "did_number_type": "mobile",
            "quantity": 1,
            "requested_by_id": self.env.user.id,
            "candidate_numbers": "+32470000001",
        })
        self.env.cr.execute(
            "UPDATE voip_did_number_request SET write_date = %s WHERE id = %s",
            [fields.Datetime.now() - timedelta(days=2), number_request.id],
        )
        self._create_did(
            did_number="+32470000001",
            state="pending",
            number_request_id=number_request.id,
        )
        number_request.invalidate_recordset(["write_date"])
        number_request._sync_candidate_numbers({"candidate_numbers": ["+32470000001"]})

        with patch.object(PhoneServiceAPI, "get_number_request_statuses") as get_statuses:
            number_request._cron_sync_number_requests()

        get_statuses.assert_not_called()

    def test_number_request_cron_recovers_missed_adopted_number(self):
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "3dc6d0a0-5163-4b11-bf01-89d700000001",
            "provider_order_id": "advanced_ordered_recovery",
            "state": "ordered",
            "country_id": self.country_be.id,
            "did_number_type": "mobile",
            "quantity": 2,
            "requested_by_id": self.env.user.id,
            # This is a held proposal, not proof of a purchased number.
            "candidate_numbers": "+32470000001\n+32470000002",
        })
        self.env.cr.execute(
            "UPDATE voip_did_number_request SET write_date = %s WHERE id = %s",
            [fields.Datetime.now() - timedelta(days=2), number_request.id],
        )
        self._create_did(
            did_number="+32470000001",
            state="pending",
            number_request_id=number_request.id,
        )

        with patch.object(
            PhoneServiceAPI,
            "get_number_request_statuses",
            return_value={number_request.request_uuid: {
                "request_uuid": number_request.request_uuid,
                "status": "ordered",
                "candidate_numbers": ["+32470000001", "+32470000002"],
                "number_statuses": [{
                    "phone_number": "+32470000001",
                    "state": "pending",
                    "error": None,
                    "requirement_statuses": {},
                    "advanced_order": {
                        "request_uuid": number_request.request_uuid,
                    },
                }, {
                    "phone_number": "+32470000003",
                    "state": "pending",
                    "error": None,
                    "requirement_statuses": {},
                    "advanced_order": {
                        "request_uuid": number_request.request_uuid,
                    },
                }],
                "comments": [],
            }},
        ) as get_statuses:
            self.env["voip.did.number.request"]._cron_sync_number_requests()
            self.env["voip.did.number.request"]._cron_sync_number_requests()

        self.assertEqual(get_statuses.call_count, 2)
        recovered = self.env["voip.did.number"].search([
            ("did_number", "=", "+32470000003"),
        ])
        self.assertEqual(len(recovered), 1)
        self.assertFalse(self.env["voip.did.number"].search([
            ("did_number", "=", "+32470000002"),
        ]))
        self.assertEqual(recovered.number_request_id, number_request)

    def test_advanced_order_hold_shows_candidates_and_notifies_requester(self):
        buyer = new_test_user(
            self.env,
            login="voip_did_number_request_hold",
            groups="voip.group_voip_admin",
            notification_type="inbox",
        )
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "2661f040-6e3a-407c-acf1-a91bd563fd53",
            "provider_order_id": "advanced_hold",
            "state": "processing",
            "country_id": self.country_be.id,
            "did_number_type": "local",
            "quantity": 2,
            "requested_by_id": buyer.id,
        })

        event = self.env["voip.phone.service.event"].create({
            "event_id": "advanced-hold-1",
            "event_type": "advanced_order_status",
            "payload": {
                "request_uuid": number_request.request_uuid,
                "status": "hold",
                "candidate_numbers": [
                    "+85221234567", None, "+85221234567", " +85221234568 ",
                ],
            },
        })
        event.with_user(self.env.ref("base.public_user")).sudo()._process_event()

        self.assertEqual(number_request.state, "hold")
        self.assertEqual(number_request.candidate_numbers, "+85221234567\n+85221234568")
        notification = number_request.message_ids.filtered(
            lambda message: "five business days" in (message.body or ""),
        )
        self.assertEqual(len(notification), 1)
        self.assertEqual(notification.author_id, self.env.ref("base.partner_root"))
        self.assertNotIn("Telnyx", notification.body)
        self.assertIn(buyer.partner_id, notification.partner_ids)

    def test_advanced_order_status_and_comment_events_update_request(self):
        buyer = new_test_user(
            self.env,
            login="voip_did_number_request_updates",
            groups="voip.group_voip_admin",
            notification_type="inbox",
        )
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "8ffb3622-7c6b-4ccc-b65f-7a3dc0099576",
            "provider_order_id": "advanced_updates",
            "state": "pending",
            "country_id": self.country_be.id,
            "did_number_type": "local",
            "quantity": 1,
            "requested_by_id": buyer.id,
        })
        self.env.cr.precommit.run()
        status_event = self.env["voip.phone.service.event"].create({
            "event_id": "advanced-status-1",
            "event_type": "advanced_order_status",
            "payload": {
                "request_uuid": number_request.request_uuid,
                "status": "exception",
            },
        })
        status_event.with_user(self.env.ref("base.public_user")).sudo()._process_event()
        self.env.cr.precommit.run()

        tracking_message = number_request.message_ids.filtered(
            lambda message: message.message_type == "tracking",
        )
        self.assertEqual(tracking_message.author_id, self.env.ref("base.partner_root"))

        comment_payload = {
            "request_uuid": number_request.request_uuid,
            "candidate_numbers": ["+85221234569"],
            "comments": [None, {
                "id": "comment_1",
                "body": "Please clarify <which company> is the end user.",
                "commenter": "numbering@telnyx.com",
                "created_at": "2026-09-02T12:00:00Z",
            }],
        }
        for event_id in ("advanced-comment-1", "advanced-comment-redelivery"):
            event = self.env["voip.phone.service.event"].create({
                "event_id": event_id,
                "event_type": "advanced_order_comment",
                "payload": comment_payload,
            })
            event.with_user(self.env.ref("base.public_user")).sudo()._process_event()

        self.assertEqual(number_request.state, "exception")
        comments = number_request.message_ids.filtered(
            lambda message: "Please clarify" in (message.body or ""),
        )
        self.assertEqual(len(comments), 1)
        self.assertIn("&lt;which company&gt;", comments.body)
        self.assertEqual(comments.author_id, self.env.ref("base.partner_root"))
        self.assertNotIn("telnyx.com", comments.body)
        self.assertIn(buyer.partner_id, comments.partner_ids)
        self.assertEqual(number_request.candidate_numbers, "+85221234569")
        self.assertEqual(number_request.provider_synced_comment_ids, ["comment_1"])

    def test_advanced_order_comment_can_be_sent(self):
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "c8367914-c741-4fe6-9fb8-0f153be444d6",
            "provider_order_id": "advanced_reply",
            "state": "exception",
            "country_id": self.country_be.id,
            "did_number_type": "local",
            "quantity": 1,
            "requested_by_id": self.env.user.id,
            "new_comment": "  The end user is Odoo HK.  ",
        })
        with patch.object(
            PhoneServiceAPI,
            "create_advanced_order_comment",
            return_value={"id": "comment_reply"},
        ) as create_comment:
            number_request.action_send_comment()

        create_comment.assert_called_once_with(
            number_request.request_uuid, "The end user is Odoo HK.",
        )
        self.assertFalse(number_request.new_comment)
        self.assertEqual(number_request.provider_synced_comment_ids, ["comment_reply"])
        self.assertTrue(number_request.message_ids.filtered(
            lambda message: "The end user is Odoo HK." in (message.body or ""),
        ))

    def test_requirement_status_event_posts_and_notifies_one_rejection_summary(self):
        group = self._create_requirement_group()
        did = self._create_did()
        assigned_user = new_test_user(
            self.env,
            login="voip_requirement_assignee",
            context={"no_reset_password": True},
            notification_type="inbox",
        )
        did.with_context(voip_skip_pbx_sync=True).destination_ref = assigned_user
        did.requirement_group_id = group
        for requirement_id, name in (
            ("req_vat", "Belgian VAT Number"),
            ("req_registration", "Business Registration Certificate"),
            ("req_address", "Proof of Address"),
        ):
            self.env["voip.requirement"].with_context(skip_validation=True).create({
                "requirement_group_ids": [(4, group.id)],
                "telnyx_requirement_id": requirement_id,
                "name": name,
                "field_type": "textual",
                "text_value": "provided",
            })
        other_did = self._create_did(did_number="+3287000002")
        self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, group.id)],
            "telnyx_requirement_id": "req_vat",
            "name": "Other Number Identity Check",
            "field_type": "action",
            "did_number_id": other_did.id,
        })
        payload = {
            "phone_number": did.did_number,
            "state": "pending",
            "event": "requirements_updated",
            "requirement_statuses": {
                "req_vat": "rejected",
                "req_registration": "rejected",
                "req_address": "approved",
            },
        }

        self._handle_order_event(payload)
        self._handle_order_event(payload)

        self.assertEqual(did.requirement_review_state, "action_required")
        messages = did.message_ids.filtered(
            lambda message: "Belgian VAT Number" in (message.body or ""),
        )
        self.assertEqual(len(messages), 1)
        self.assertIn("Business Registration Certificate", messages.body)
        self.assertNotIn("Other Number Identity Check", messages.body)
        self.assertEqual(messages.message_type, "comment")
        self.assertEqual(messages.subtype_id, self.env.ref("mail.mt_comment"))
        self.assertEqual(messages.partner_ids, assigned_user.partner_id)
        notifications = self.env["mail.notification"].search([
            ("mail_message_id", "=", messages.id),
        ])
        self.assertEqual(notifications.res_partner_id, assigned_user.partner_id)
        self.assertEqual(notifications.notification_type, "inbox")

    def test_oldest_active_number_becomes_main_and_failover_is_sticky(self):
        first = self._create_did(did_number="+3287000040", state="active")
        second = self._create_did(did_number="+3287000041", state="active")
        now = fields.Datetime.now()
        first.purchase_date = now - timedelta(days=1)
        second.purchase_date = now

        main = self.env["voip.did.number"]._ensure_default_outgoing_number()

        self.assertEqual(main, first)
        self.assertTrue(first.is_default_outgoing_number)

        with patch.object(
            self.env.registry["voip.did.number"],
            "_notify_main_number_promoted",
            autospec=True,
        ) as notify:
            first.write({"state": "suspended"})

        self.assertFalse(first.is_default_outgoing_number)
        self.assertTrue(second.is_default_outgoing_number)
        notify.assert_called_once()

        first.write({"state": "active"})
        self.env["voip.did.number"]._ensure_default_outgoing_number()

        self.assertFalse(first.is_default_outgoing_number)
        self.assertTrue(second.is_default_outgoing_number)

    def test_phone_number_creation_message(self):
        did = self._create_did(did_number="+3287000044")

        self.assertEqual(did.message_ids[0].body, "<p>Phone Number created</p>")

    def test_only_active_number_can_be_set_as_main(self):
        pending = self._create_did(did_number="+3287000042", state="pending")

        with self.assertRaisesRegex(UserError, "Only an active phone number"):
            pending.action_set_as_main_number()

    def test_no_active_number_does_not_clear_an_unset_pbx_main_number(self):
        self._create_did(did_number="+3287000043", state="pending")

        with patch.object(
            self.env.registry["voip.pbx.service"],
            "_update_default_outgoing_number",
            autospec=True,
        ) as update_default:
            main = self.env["voip.did.number"]._ensure_default_outgoing_number()

        self.assertFalse(main)
        update_default.assert_not_called()

    def test_active_state_sets_did_active(self):
        did = self._create_did()
        self._handle_order_event({
            "phone_number": did.did_number,
            "state": "active",
            "event": None,
        })
        did.invalidate_recordset()
        self.assertEqual(did.state, "active")

    def test_active_state_updates_the_personal_outgoing_caller_id(self):
        user = new_test_user(self.env, login="active_personal_did_user")
        settings = user.res_users_settings_id
        settings.with_context(voip_skip_pbx_sync=True).write({
            "voip_provider_id": self.env.ref("voip.odoo_provider").id,
            "voip_username": "active-personal-did-user",
            "voip_secret": "sip-secret",
        })
        extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        )._find_or_create_for_user(user)
        user.with_context(voip_skip_pbx_sync=True).write({
            "voip_pbx_user_id": 999,
            "voip_pbx_user_uuid": "active-personal-did-user-uuid",
            "voip_pbx_line_id": 998,
        })
        extension.with_context(voip_skip_pbx_sync=True).pbx_extension_id = 997
        did = self.env["voip.did.number"].with_context(voip_skip_pbx_sync=True).create({
            "did_number": "+3287000044",
            "did_number_type": "local",
            "state": "pending",
            "country_id": self.country_be.id,
            "destination_ref": f"res.users,{user.id}",
        })

        with patch.object(
            self.env.registry["voip.pbx.service"],
            "_update_user_caller_id",
            autospec=True,
        ) as update_caller_id:
            self._handle_order_event({
                "phone_number": did.did_number,
                "state": "active",
                "event": None,
            })

        update_caller_id.assert_called_once()
        self.assertEqual(update_caller_id.call_args.kwargs, {
            "user_id": 999,
            "outgoing_caller_id": did.did_number,
        })

    def test_pull_sync_keeps_status_when_main_number_sync_fails(self):
        did = self._create_did()
        with (
            patch.object(
                PhoneServiceAPI,
                "get_phone_number_statuses",
                return_value={did.did_number: {"state": "active", "error": None}},
            ),
            patch.object(
                self.env.registry["voip.did.number"],
                "_ensure_default_outgoing_number",
                autospec=True,
                side_effect=UserError("PBX unavailable"),
            ),
            self.assertLogs(DID_NUMBER_LOGGER, level="WARNING"),
        ):
            did._sync_number_statuses()

        self.assertEqual(did.state, "active")

    def test_state_change_sends_status_bus_event(self):
        did = self._create_did()
        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            self._handle_order_event({
                "phone_number": did.did_number,
                "state": "active",
                "event": None,
            })

        status_calls = [
            call for call in bus_send.call_args_list
            if call.args[1] == "voip.did_number/status_updated"
        ]
        self.assertEqual(len(status_calls), 1)
        self.assertEqual(
            status_calls[0].args[2],
            {
                "id": did.id,
                "phone_number": did.did_number,
                "state": "active",
            },
        )

    def test_unchanged_state_does_not_send_status_bus_event(self):
        did = self._create_did(state="active")
        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            self._handle_order_event({
                "phone_number": did.did_number,
                "state": "active",
                "event": None,
            })

        bus_send.assert_not_called()

    def test_pull_sync_notifies_on_out_of_band_state_change(self):
        """The drift cron releases a number server-side without a webhook push,
        so the pull sync must refresh the softphone UI on the state change."""
        did = self._create_did(state="active")
        with (
            patch.object(
                PhoneServiceAPI, "get_phone_number_statuses",
                return_value={did.did_number: {"state": "released", "error": None}},
            ),
            patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send,
            _patch_phone_service(),
        ):
            did._sync_number_statuses()

        self.assertEqual(did.state, "released")
        self.assertEqual(
            sum(call.args[1] == "voip.did_number/status_updated" for call in bus_send.call_args_list),
            1,
        )

    def test_pull_sync_unchanged_state_does_not_notify(self):
        """An unchanged server status must not spuriously refresh the UI."""
        did = self._create_did(state="active")
        with (
            patch.object(
                PhoneServiceAPI, "get_phone_number_statuses",
                return_value={did.did_number: {"state": "active", "error": None}},
            ),
            patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send,
            _patch_phone_service(),
        ):
            did._sync_number_statuses()

        bus_send.assert_not_called()

    def test_pull_sync_updates_requirement_statuses(self):
        did = self._create_did()
        with (
            patch.object(
                PhoneServiceAPI,
                "get_phone_number_statuses",
                return_value={did.did_number: {
                    "state": "pending",
                    "error": None,
                    "requirement_statuses": {"req_identity": "approved"},
                }},
            ),
            _patch_phone_service(),
        ):
            did._sync_number_statuses()

        self.assertEqual(did.requirement_statuses, {"req_identity": "approved"})
        self.assertEqual(did.requirement_review_state, "approved")

    def test_order_failed_event_sets_failure_and_posts_chatter(self):
        did = self._create_did()
        self._handle_order_event({
            "phone_number": did.did_number,
            "state": "failure",
            "event": "order_failed",
            "error": "Regulatory documents rejected",
        })
        did.invalidate_recordset()
        self.assertEqual(did.state, "failure")
        messages = did.message_ids.filtered(lambda m: "Regulatory documents rejected" in (m.body or ""))
        self.assertTrue(messages)

    def test_order_failed_insufficient_credits_posts_friendly_message(self):
        did = self._create_did()
        self._handle_order_event({
            "phone_number": did.did_number,
            "state": "failure",
            "event": "order_failed",
            "error": "insufficient_credits",
        })
        did.invalidate_recordset()
        self.assertEqual(did.state, "failure")
        friendly = did.message_ids.filtered(lambda m: "enough credits" in (m.body or ""))
        self.assertTrue(friendly)
        raw = did.message_ids.filtered(lambda m: "insufficient_credits" in (m.body or ""))
        self.assertFalse(raw)

    def test_order_failed_unavailable_number_confirms_no_charge(self):
        did = self._create_did()
        self._handle_order_event({
            "phone_number": did.did_number,
            "state": "failure",
            "event": "order_failed",
            "error": "number_unavailable",
        })

        message = did.message_ids.filtered(
            lambda item: "No credits were charged" in (item.body or ""),
        )
        self.assertTrue(message)
        self.assertIn("Search again", message.body)

    def test_released_state_sets_released(self):
        did = self._create_did(state="active")
        self._handle_order_event({
            "phone_number": did.did_number,
            "state": "released",
            "event": "deletion_confirmed",
        })
        did.invalidate_recordset()
        self.assertEqual(did.state, "released")

    def test_unknown_phone_number_is_ignored(self):
        # No exception should be raised when no DID matches the phone number.
        self._handle_order_event({
            "phone_number": "+19999999999",
            "state": "active",
            "event": None,
        })

    def test_advanced_order_status_creates_and_assigns_number(self):
        buyer = new_test_user(
            self.env,
            login="voip_did_number_request_buyer",
            groups="voip.group_voip_admin",
        )
        group = self._create_requirement_group("rg_advanced")
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "996675a6-e7cf-4ddf-a5a2-b3f423e83d88",
            "provider_order_id": "advanced_linked",
            "state": "ordered",
            "country_id": self.country_be.id,
            "did_number_type": "local",
            "quantity": 1,
            "requirement_group_id": group.id,
            "requested_by_id": buyer.id,
        })
        self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, group.id)],
            "telnyx_requirement_id": "req_advanced_action",
            "name": "Identity Verification",
            "field_type": "action",
        })

        self._handle_order_event({
            "phone_number": "+3287000040",
            "state": "pending",
            "event": None,
            "advanced_order": {
                "request_uuid": number_request.request_uuid,
            },
        })

        did = self.env["voip.did.number"].search([
            ("did_number", "=", "+3287000040"),
        ])
        self.assertEqual(len(did), 1)
        self.assertEqual(did.state, "pending")
        self.assertEqual(did.country_id, self.country_be)
        self.assertEqual(did.did_number_type, "local")
        self.assertEqual(did.requirement_group_id, group)
        self.assertEqual(did.number_request_id, number_request)
        self.assertEqual(did.user_id, buyer)
        self.assertEqual(did.create_uid, buyer)
        self.assertTrue(did.purchase_date)
        action_requirement = group.requirement_ids.filtered(
            lambda requirement: requirement.did_number_id == did,
        )
        self.assertEqual(action_requirement.telnyx_requirement_id, "req_advanced_action")

    def test_advanced_order_status_reuses_released_number(self):
        buyer = new_test_user(
            self.env,
            login="voip_did_number_request_rebuyer",
            groups="voip.group_voip_admin",
        )
        released = self._create_did(did_number="+3287000042", state="released")
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "115e1131-f2c0-43c1-a0e1-9702ab4dc80c",
            "provider_order_id": "advanced_reused",
            "state": "ordered",
            "country_id": self.country_be.id,
            "did_number_type": "local",
            "quantity": 1,
            "requested_by_id": buyer.id,
        })

        self._handle_order_event({
            "phone_number": released.did_number,
            "state": "pending",
            "advanced_order": {
                "request_uuid": number_request.request_uuid,
            },
        })

        self.assertEqual(released.state, "pending")
        self.assertEqual(released.user_id, buyer)
        self.assertEqual(released.number_request_id, number_request)
        self.assertTrue(released.purchase_date)

    def test_advanced_order_status_for_unknown_request_is_ignored(self):
        with self.assertLogs(DID_NUMBER_LOGGER, level="WARNING") as log_cm:
            self._handle_order_event({
                "phone_number": "+3287000043",
                "state": "pending",
                "advanced_order": {
                    "request_uuid": "c1523f60-0f92-45e1-a308-6fd8e1740c14",
                },
            })

        self.assertFalse(self.env["voip.did.number"].search([
            ("did_number", "=", "+3287000043"),
        ]))
        self.assertTrue(any("unknown advanced number request" in line for line in log_cm.output))

    def test_advanced_order_status_does_not_claim_unrelated_number(self):
        existing = self._create_did(did_number="+3287000044", state="active")
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "be42a49f-45a5-4f45-93e1-5875b968bb54",
            "provider_order_id": "advanced_collision",
            "state": "ordered",
            "country_id": self.country_be.id,
            "did_number_type": "local",
            "quantity": 1,
            "requested_by_id": self.env.user.id,
        })

        with self.assertLogs(DID_NUMBER_LOGGER, level="WARNING") as log_cm:
            self._handle_order_event({
                "phone_number": existing.did_number,
                "state": "pending",
                "advanced_order": {"request_uuid": number_request.request_uuid},
            })

        self.assertEqual(existing.state, "active")
        self.assertFalse(existing.number_request_id)
        self.assertTrue(any("belongs to another request" in line for line in log_cm.output))

    def test_missing_required_keys_are_logged_and_ignored(self):
        with self.assertLogs(DID_NUMBER_LOGGER, level="WARNING") as log_cm:
            self._handle_order_event({"event": "order_created"})
        self.assertTrue(any("missing" in line for line in log_cm.output))

    def test_missing_state_does_not_leak_phone_number_in_logs(self):
        with self.assertLogs(DID_NUMBER_LOGGER, level="WARNING") as log_cm:
            self._handle_order_event({"phone_number": "+19999999999"})
        self.assertTrue(any("missing" in line for line in log_cm.output))
        self.assertNotIn("+19999999999", "\n".join(log_cm.output))

    def test_order_created_event_posts_chatter_without_state_change(self):
        did = self._create_did(state="pending")
        self._handle_order_event({
            "phone_number": did.did_number,
            "state": "pending",
            "event": "order_created",
        })
        did.invalidate_recordset()
        self.assertEqual(did.state, "pending")
        msgs = did.message_ids.filtered(lambda m: "created" in (m.body or ""))
        self.assertTrue(msgs)

    def test_order_in_progress_event_posts_chatter_without_state_change(self):
        did = self._create_did(state="pending")
        self._handle_order_event({
            "phone_number": did.did_number,
            "state": "pending",
            "event": "order_in_progress",
        })
        did.invalidate_recordset()
        self.assertEqual(did.state, "pending")
        msgs = did.message_ids.filtered(lambda m: "in progress" in (m.body or ""))
        self.assertTrue(msgs)

    def test_unknown_state_logs_warning(self):
        did = self._create_did(state="pending")
        with self.assertLogs(DID_NUMBER_LOGGER, level="WARNING") as log_cm:
            self._handle_order_event({
                "phone_number": did.did_number,
                "state": "weird_unknown",
            })
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn("weird_unknown", log_cm.output[0])
        did.invalidate_recordset()
        self.assertEqual(did.state, "pending")

    def test_event_only_touches_matching_number(self):
        """A state event updates only the DID with the matching phone number (each DID = one order)."""
        did_a = self._create_did(did_number="+3287000020", state="pending")
        did_c = self._create_did(did_number="+3287000022", state="pending")  # unrelated

        self._handle_order_event({
            "phone_number": "+3287000020",
            "state": "active",
            "event": None,
        })

        for did in (did_a, did_c):
            did.invalidate_recordset()
        self.assertEqual(did_a.state, "active")
        self.assertEqual(did_c.state, "pending")  # untouched

    def test_buyer_and_assigned_user_follow_number_status_updates(self):
        buyer = new_test_user(
            self.env,
            login="voip_status_buyer",
            groups="voip.group_voip_admin",
        )
        assigned_user = new_test_user(
            self.env,
            login="voip_status_assigned",
            groups="base.group_user",
        )
        with _patch_phone_service():
            did = self.env["voip.did.number"].with_user(buyer).create({
                "did_number": "+3287000030",
                "did_number_type": "local",
                "state": "ordering",
                "country_id": self.country_be.id,
            })

        self.assertIn(buyer.partner_id, did.message_partner_ids)

        did.destination_ref = assigned_user
        self.assertIn(assigned_user.partner_id, did.message_partner_ids)

    def test_buyer_assigned_to_own_number_is_followed_once(self):
        buyer = new_test_user(
            self.env,
            login="voip_status_self_buyer",
            groups="voip.group_voip_admin",
        )
        with _patch_phone_service():
            did = self.env["voip.did.number"].with_user(buyer).create({
                "did_number": "+3287000031",
                "did_number_type": "local",
                "state": "ordering",
                "country_id": self.country_be.id,
                "destination_ref": f"res.users,{buyer.id}",
            })

        own_follower = did.message_partner_ids.filtered(lambda p: p == buyer.partner_id)
        self.assertEqual(len(own_follower), 1)


@tagged("voip")
class TestRequirementGroupStatusEvent(TestPhoneServiceNotificationsBase):

    def test_approved_status_updates_field(self):
        group = self._create_requirement_group(status="pending_approval")
        self._handle_requirement_group_event({
            "requirement_group_id": group.telnyx_requirement_group_id,
            "status": "approved",
        })
        group.invalidate_recordset()
        self.assertEqual(group.status, "approved")

    def test_declined_status_posts_chatter_on_linked_dids(self):
        group = self._create_requirement_group(status="pending_approval")
        did = self._create_did()
        did.requirement_group_id = group
        self._handle_requirement_group_event({
            "requirement_group_id": group.telnyx_requirement_group_id,
            "status": "declined",
            "error": "Missing proof of address",
        })
        group.invalidate_recordset()
        self.assertEqual(group.status, "declined")
        decline_messages = did.message_ids.filtered(
            lambda m: "Missing proof of address" in (m.body or ""),
        )
        self.assertTrue(decline_messages)

    def test_status_change_fetches_linked_did_comments(self):
        """A requirement-group status change also pulls the tied numbers' comments,
        since Number Ops leaves them there with no number_order webhook of their own."""
        group = self._create_requirement_group(status="pending_approval")
        did = self._create_did(did_number="+33100000009", state="pending")
        did.requirement_group_id = group

        def fake_get_comments(phone_number):
            if phone_number == "+33100000009":
                return [{"id": "cm_rg_1", "body": "Follow-up: notarized copy needed", "created_at": "2026-05-22T10:00:00Z"}]
            return []
        with patch.object(PhoneServiceAPI, "get_phone_number_comments", side_effect=fake_get_comments), \
             _patch_phone_service():
            self.env["voip.requirement.group"]._handle_status_event({
                "requirement_group_id": group.telnyx_requirement_group_id,
                "status": "declined",
                "error": "Missing proof of address",
            })
        messages = did.message_ids.mapped("body")
        self.assertTrue(any("notarized copy needed" in m for m in messages))

    def test_dashed_status_is_normalized(self):
        group = self._create_requirement_group(status="approved")
        self._handle_requirement_group_event({
            "requirement_group_id": group.telnyx_requirement_group_id,
            "status": "no-longer-eligible",
        })
        group.invalidate_recordset()
        self.assertEqual(group.status, "no_longer_eligible")

    def test_unknown_status_is_ignored(self):
        group = self._create_requirement_group(status="approved")
        with self.assertLogs(REQUIREMENT_GROUP_LOGGER, level="WARNING") as log_cm:
            self._handle_requirement_group_event({
                "requirement_group_id": group.telnyx_requirement_group_id,
                "status": "weird_unknown_state",
            })
        group.invalidate_recordset()
        self.assertEqual(group.status, "approved")
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn("weird_unknown_state", log_cm.output[0])

    def test_missing_group_is_ignored(self):
        # No exception when telnyx_requirement_group_id doesn't match any local group.
        self._handle_requirement_group_event({
            "requirement_group_id": "nonexistent_id",
            "status": "approved",
        })


@tagged("voip")
class TestRequirementReviewContext(TestPhoneServiceNotificationsBase):

    def test_advanced_order_resubmission_reapplies_requirement_group(self):
        group = self._create_requirement_group()
        requirement = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, group.id)],
            "telnyx_requirement_id": "req_contact",
            "name": "Contact Information",
            "field_type": "textual",
            "text_value": "Updated value",
        })
        number_request = self.env["voip.did.number.request"].create({
            "request_uuid": "27dc510b-78cf-4e95-a5d8-57b9ee795c23",
            "provider_order_id": "advanced_resubmission",
            "state": "exception",
            "country_id": self.country_be.id,
            "did_number_type": "local",
            "quantity": 1,
            "requirement_group_id": group.id,
            "requested_by_id": self.env.user.id,
        })

        action = number_request.action_open_requirements()
        with patch.object(PhoneServiceAPI, "fulfill_requirement_group") as fulfill:
            group.with_context(**action["context"]).action_fulfill_requirements()

        fulfill.assert_called_once_with(
            requirement_group_id=group.telnyx_requirement_group_id,
            requirements=[{
                "requirement_id": requirement.telnyx_requirement_id,
                "field_value": "Updated value",
            }],
            request_uuid=number_request.request_uuid,
        )

    def test_did_update_keeps_provider_status_and_uses_update_wording(self):
        group = self._create_requirement_group()
        did = self._create_did()
        did.requirement_group_id = group
        pending_requirement = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, group.id)],
            "telnyx_requirement_id": "req_contact",
            "name": "Contact Information",
            "field_type": "textual",
            "text_value": "Provided value",
        })
        approved_requirement = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, group.id)],
            "telnyx_requirement_id": "req_address",
            "name": "Proof of Address",
            "field_type": "textual",
            "text_value": "Approved value",
        })
        did.requirement_statuses = {approved_requirement.telnyx_requirement_id: "approved"}
        self.assertEqual(did.requirement_review_state, "under_review")

        with patch.object(
            PhoneServiceAPI,
            "_call_phone_service",
            side_effect=_mock_phone_service,
        ) as phone_service_call:
            action = group.with_context(did_number_id=did.id).action_fulfill_requirements()

        fulfill_call = next(
            call for call in phone_service_call.call_args_list
            if call.args[0].endswith("/fulfill_requirement_group")
        )
        submitted = fulfill_call.args[1]["payload"]["regulatory_requirements"]
        self.assertEqual([item["requirement_id"] for item in submitted], [pending_requirement.telnyx_requirement_id])
        self.assertEqual(group.status, "unapproved")
        self.assertEqual(action["params"]["message"], "Requirements updated successfully.")
        self.assertEqual(did.action_open_submit_requirements()["name"], "Update Requirements")

    def test_approved_requirement_is_locked_only_for_reviewed_did(self):
        group = self._create_requirement_group()
        did = self._create_did()
        did.requirement_group_id = group
        requirement = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, group.id)],
            "telnyx_requirement_id": "req_contact",
            "name": "Contact Information",
            "field_type": "textual",
            "text_value": "Original value",
        })
        did.requirement_statuses = {"req_contact": "approved"}

        reviewed_requirement = requirement.with_context(skip_validation=False, did_number_id=did.id)
        self.assertEqual(reviewed_requirement.review_status, "approved")
        with self.assertRaisesRegex(UserError, "approved"):
            reviewed_requirement.write({"text_value": "Changed from DID"})

        reusable_requirement = requirement.with_context(skip_validation=False, did_number_id=False)
        self.assertEqual(reusable_requirement.review_status, "provided")
        reusable_requirement.write({"text_value": "Changed for a future purchase"})
        self.assertEqual(requirement.text_value, "Changed for a future purchase")


@tagged("voip")
class TestNumberDeletionEvent(TestPhoneServiceNotificationsBase):

    def test_deletion_confirmed_releases_did(self):
        did = self._create_did(did_number="+3287000010", state="active")
        self._handle_deletion_event({
            "phone_number": "+3287000010",
            "state": "released",
            "event": "deletion_confirmed",
        })
        did.invalidate_recordset()
        self.assertEqual(did.state, "released")

    def test_deletion_confirmed_is_idempotent_on_already_released(self):
        did = self._create_did(did_number="+3287000011", state="released")
        # Should not raise or post a misleading message.
        self._handle_deletion_event({
            "phone_number": "+3287000011",
            "state": "released",
            "event": "deletion_confirmed",
        })
        did.invalidate_recordset()
        self.assertEqual(did.state, "released")

    def test_deletion_failed_reverts_optimistic_release(self):
        did = self._create_did(did_number="+3287000012", state="released")
        self._handle_deletion_event({
            "phone_number": "+3287000012",
            "state": "active",
            "event": "deletion_failed",
            "error": "Provider error 42",
        })
        did.invalidate_recordset()
        self.assertEqual(did.state, "active")
        failure_messages = did.message_ids.filtered(lambda m: "Provider error 42" in (m.body or ""))
        self.assertTrue(failure_messages)

    def test_unknown_state_is_ignored(self):
        did = self._create_did(did_number="+3287000013", state="active")
        with self.assertLogs(DID_NUMBER_LOGGER, level="WARNING") as log_cm:
            self._handle_deletion_event({
                "phone_number": "+3287000013",
                "state": "weird_state",
            })
        did.invalidate_recordset()
        self.assertEqual(did.state, "active")
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn("weird_state", log_cm.output[0])

    def test_unknown_phone_number_is_ignored(self):
        # No DID matches; should silently no-op.
        self._handle_deletion_event({
            "phone_number": "+9999999999",
            "state": "released",
            "event": "deletion_confirmed",
        })


@tagged("voip")
class TestSubOrderCrossPollination(TestPhoneServiceNotificationsBase):

    def test_state_event_posts_number_comments(self):
        """A state event posts the number's comments (fetched by phone number) to the DID chatter."""
        did = self._create_did(did_number="+33100000001", state="pending")

        def fake_get_comments(phone_number):
            if phone_number == "+33100000001":
                return [{"id": "cm_fr_1", "body": "French regulatory note", "created_at": "2026-05-22T10:00:00Z"}]
            return []
        with patch.object(PhoneServiceAPI, "get_phone_number_comments", side_effect=fake_get_comments), \
             _patch_phone_service():
            self.env["voip.did.number"]._handle_status_event({
                "phone_number": "+33100000001", "state": "active", "event": None, "error": None,
            })
        messages = did.message_ids.mapped("body")
        self.assertTrue(any("French regulatory note" in m for m in messages))

    def test_order_in_progress_event_posts_number_comments(self):
        """order_in_progress is the review window where Telnyx adds comments, so
        the event must surface them (it used to return before fetching)."""
        did = self._create_did(did_number="+33100000002", state="pending")

        def fake_get_comments(phone_number):
            return [{"id": "cm_fr_2", "body": "Need a proof of address", "created_at": "2026-05-22T10:00:00Z"}]
        with patch.object(PhoneServiceAPI, "get_phone_number_comments", side_effect=fake_get_comments), \
             _patch_phone_service():
            self.env["voip.did.number"]._handle_status_event({
                "phone_number": "+33100000002", "state": "pending",
                "event": "order_in_progress", "error": None,
            })
        messages = did.message_ids.mapped("body")
        self.assertTrue(any("Need a proof of address" in m for m in messages))

    def test_ordering_state_does_not_fetch_comments(self):
        """A number still in "ordering" has no Telnyx sub-order yet, so no fetch."""
        did = self._create_did(did_number="+33100000003", state="ordering")
        fetch_calls = []

        def fake_get_comments(phone_number):
            fetch_calls.append(phone_number)
            return []
        with patch.object(PhoneServiceAPI, "get_phone_number_comments", side_effect=fake_get_comments):
            did._fetch_and_post_sub_order_comments()
        self.assertEqual(fetch_calls, [])

    def test_comment_fetch_failure_does_not_break_status_event(self):
        """A failed comment fetch must not abort the status handler."""
        did = self._create_did(did_number="+33100000004", state="pending")

        def boom(phone_number):
            raise UserError("comments unavailable")
        with patch.object(PhoneServiceAPI, "get_phone_number_comments", side_effect=boom), \
             _patch_phone_service(), \
             self.assertLogs(DID_NUMBER_LOGGER, level="WARNING"):
            self.env["voip.did.number"]._handle_status_event({
                "phone_number": "+33100000004", "state": "active",
                "event": "order_in_progress", "error": None,
            })
        did.invalidate_recordset()
        self.assertEqual(did.state, "active")

    def test_cron_polls_comments_for_pending_numbers(self):
        """The status-sync cron also fetches comments for in-review numbers, since
        a comment can arrive without a coinciding status event."""
        did = self._create_did(did_number="+33100000005", state="pending")

        def fake_get_comments(phone_number):
            return [{"id": "cm_fr_5", "body": "Pending review comment", "created_at": "2026-05-22T10:00:00Z"}]
        with patch.object(PhoneServiceAPI, "get_phone_number_comments", side_effect=fake_get_comments), \
             patch.object(PhoneServiceAPI, "get_phone_number_statuses", return_value={}), \
             _patch_phone_service():
            self.env["voip.did.number"]._cron_sync_number_statuses()
        messages = did.message_ids.mapped("body")
        self.assertTrue(any("Pending review comment" in m for m in messages))

    def test_update_requirement_group_targets_own_number(self):
        """did_a.update_requirement_group() must call the API with did_a's own phone number."""
        did_a = self._create_did(did_number="+33100000001", state="pending")
        did_b = self._create_did(did_number="+49100000001", state="pending")
        group_a = self._create_requirement_group(telnyx_id="rg_fr_001")
        did_a.requirement_group_id = group_a
        update_calls = []

        def fake_update(phone_number, group_id):
            update_calls.append((phone_number, group_id))
        with patch.object(
            PhoneServiceAPI, "assign_requirement_group",
            side_effect=fake_update,
        ), _patch_phone_service():
            did_a.update_requirement_group()
        self.assertEqual(update_calls, [("+33100000001", "rg_fr_001")])
        for phone_number, _group_id in update_calls:
            self.assertNotEqual(phone_number, did_b.did_number, "did_b's number must never be touched")

    def test_generate_verification_url_passes_phone_number(self):
        """generate_verification_url must pass the DID's phone number to the number-centric API."""
        did = self._create_did(did_number="+33100000001", state="pending")
        group = self._create_requirement_group(telnyx_id="rg_verify_001")
        did.requirement_group_id = group
        req = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(6, 0, group.ids)],
            "telnyx_requirement_id": "req_verify_001",
            "name": "ID verification",
            "field_type": "action",
            "action_first_name": "Jane",
            "action_last_name": "Doe",
            "did_number_id": did.id,
        })
        captured = {}

        def fake_generate(requirement_id, phone_number, first_name, last_name):
            captured.update({
                "requirement_id": requirement_id, "phone_number": phone_number,
                "first_name": first_name, "last_name": last_name,
            })
            return {"requirement_action": {"value": "https://example.com/verify/xyz"}}
        with patch.object(PhoneServiceAPI, "generate_requirement_verification_url", side_effect=fake_generate), \
             _patch_phone_service():
            result = req.generate_verification_url()
        self.assertTrue(result)
        self.assertEqual(captured["phone_number"], "+33100000001",
                         "phone_number passed to the API must be the DID's own number")
        self.assertEqual(req.action_verification_url, "https://example.com/verify/xyz")

    def test_generate_verification_url_raises_without_did(self):
        """If the requirement has no DID number, generate_verification_url must raise."""
        group = self._create_requirement_group(telnyx_id="rg_verify_002")
        req = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(6, 0, group.ids)],
            "telnyx_requirement_id": "req_verify_002",
            "name": "ID verification",
            "field_type": "action",
            "action_first_name": "Jane",
            "action_last_name": "Doe",
        })
        with _patch_phone_service(), self.assertRaises(UserError):
            req.generate_verification_url()


@tagged("voip")
class TestProvisioningHeal(TestPhoneServiceNotificationsBase):
    """The provisioning safety net re-drives numbers that reached `active`
    without a working line (e.g. the `active` event landed before the PBX
    tenant was ready), which no state transition would otherwise retry."""

    def _assign_user(self, did):
        user = new_test_user(self.env, login=f"heal_{did.id}", name="Heal User")
        did.with_context(voip_skip_pbx_sync=True).destination_ref = user
        user.res_users_settings_id.with_context(voip_skip_pbx_sync=True).voip_provider_id = (
            self.env["voip.pbx.service"].voip_provider
        )
        return user

    def test_external_provider_number_is_not_flagged(self):
        did = self._create_did(did_number="+3287000097", state="active")
        user = self._assign_user(did)
        user.res_users_settings_id.with_context(voip_skip_pbx_sync=True).voip_provider_id = (
            self.env["voip.provider"].create({"name": "External Provider", "mode": "prod"})
        )

        self.assertFalse(
            did._filter_under_provisioned(),
            "the heal cron must preserve an explicit external-provider choice",
        )

    def test_healthy_active_number_is_not_flagged(self):
        did = self._create_did(did_number="+3287000098")
        self._assign_user(did)
        self._handle_order_event({"phone_number": did.did_number, "state": "active", "event": None})
        did.invalidate_recordset()
        self.assertEqual(did.state, "active")
        self.assertEqual(did.user_id.voip_pbx_user_id, 10)
        self.assertFalse(
            did._filter_under_provisioned(),
            "a fully provisioned number must not be re-provisioned by the heal cron",
        )

    def test_heal_cron_provisions_number_stuck_active(self):
        did = self._create_did(did_number="+3287000099")
        user = self._assign_user(did)

        # The `active` event lands while the PBX tenant is still provisioning:
        # the pbx layer raises, the failure is swallowed, and the number is
        # left active with no line and no further transition to retry it.
        # (_handle_status_event is called directly: _handle_order_event would
        # stack its own success patch over the failing one.)
        def pbx_unavailable(route, params, **kw):
            if route.startswith("/api/phone_service/1/pbx/"):
                raise UserError("The phone service is temporarily unavailable.")
            return pbx_router(route, params)

        with patch.object(
            PhoneServiceAPI, "_call_phone_service",
            side_effect=pbx_unavailable,
        ), self.assertLogs(DID_NUMBER_LOGGER, level="WARNING") as log_cm:
            self.env["voip.did.number"]._handle_status_event(
                {"phone_number": did.did_number, "state": "active", "event": None})
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn(did.did_number, log_cm.output[0])
        self.assertIn("status changed to active", log_cm.output[0])
        did.invalidate_recordset()
        self.assertEqual(did.state, "active")
        self.assertFalse(user.voip_pbx_user_id)
        self.assertEqual(
            did._filter_under_provisioned(), did,
            "an active number with no line must be detected as under-provisioned",
        )

        # The safety-net cron re-drives provisioning now that the PBX is reachable.
        with _patch_phone_service():
            self.env["voip.did.number"]._cron_heal_provisioning()
        did.invalidate_recordset()

        self.assertFalse(did._filter_under_provisioned())
        self.assertEqual(user.voip_pbx_user_id, 10)
        self.assertEqual(did.pbx_incall_id, 50)
        settings = user.res_users_settings_id
        self.assertEqual(settings.voip_provider_id, self.env["voip.pbx.service"].voip_provider)
        self.assertTrue(settings.voip_username)
        self.assertTrue(settings.voip_secret)

    def test_heal_cron_provisions_user_while_number_is_pending(self):
        did = self._create_did(did_number="+3287000096", state="pending")
        user = self._assign_user(did)

        self.assertFalse(user.voip_pbx_user_id)

        with _patch_phone_service():
            self.env["voip.did.number"]._cron_heal_provisioning()

        self.assertEqual(user.voip_pbx_user_id, 10)
        self.assertTrue(user.res_users_settings_id.voip_username)
        self.assertTrue(user.res_users_settings_id.voip_secret)
        self.assertFalse(did.pbx_incall_id)
        self.assertFalse(did.pbx_incall_extension_id)

    def test_heal_cron_restores_missing_pbx_line(self):
        did = self._create_did(did_number="+3287000095", state="pending")
        user = self._assign_user(did)
        with _patch_phone_service():
            did._sync_user_provisioning(user)
        user.voip_pbx_line_id = False

        with _patch_phone_service():
            self.env["voip.did.number"]._cron_heal_provisioning()

        self.assertEqual(user.voip_pbx_line_id, 20)
