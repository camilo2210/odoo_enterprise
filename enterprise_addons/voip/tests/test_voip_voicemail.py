from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common, tagged
from odoo.tests.common import new_test_user

VOICEMAIL_MESSAGE_LOGGER = "odoo.addons.voip.models.voip_voicemail_message"


@tagged("voip", "post_install", "-at_install")
class TestVoipMailbox(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env,
            login="mailbox_user",
            name="Mailbox User",
            email="user@example.com",
        )
        cls.voip_admin = new_test_user(
            cls.env,
            login="mailbox_admin",
            groups="voip.group_voip_admin",
        )
        cls.Mailbox = cls.env["voip.voicemail"].with_context(voip_skip_pbx_sync=True)

    def test_personal_mailbox_preserves_email_and_cannot_change_type(self):
        mailbox = self.Mailbox._ensure_for_user(self.user)
        self.assertEqual(mailbox.mailbox_type, "personal")
        self.assertEqual(mailbox.email, "user@example.com")

        mailbox.email = "custom@example.com"
        self.Mailbox._ensure_for_user(self.user)
        self.assertEqual(mailbox.email, "custom@example.com")
        self.assertEqual(mailbox._get_recipient_email(), "custom@example.com")

        mailbox.email = False
        self.assertEqual(mailbox._get_recipient_email(), "user@example.com")
        with self.assertRaises(ValidationError):
            mailbox.user_id = False
        with self.assertRaises(ValidationError):
            mailbox.unlink()

    def test_shared_mailbox_only_uses_its_explicit_email(self):
        mailbox = self.Mailbox.create({"name": "Support"})
        self.assertEqual(mailbox.mailbox_type, "shared")
        self.assertFalse(mailbox._get_recipient_email())

        mailbox.email = "support@example.com"
        self.assertEqual(mailbox._get_recipient_email(), "support@example.com")
        mailbox.unlink()

    def test_voip_admin_cannot_create_personal_mailbox_manually(self):
        with self.assertRaises(ValidationError):
            self.Mailbox.with_user(self.voip_admin).create({
                "name": self.user.name,
                "user_id": self.user.id,
            })

    def test_message_event_for_unknown_voicemail_does_not_leak_caller_info(self):
        payload = {
            "message_id": "msg-1",
            "voicemail_id": 999999,
            "message": {
                "caller_id_num": "+19999999999",
                "caller_id_name": "Jane Doe",
            },
        }
        with self.assertLogs(VOICEMAIL_MESSAGE_LOGGER, level="WARNING") as log_cm:
            self.env["voip.voicemail.message"]._handle_message_created_event(
                "evt-unknown-voicemail", payload, fields.Datetime.now(),
            )
        self.assertTrue(any("unknown PBX voicemail" in line for line in log_cm.output))
        joined_output = "\n".join(log_cm.output)
        self.assertNotIn("+19999999999", joined_output)
        self.assertNotIn("Jane Doe", joined_output)

    def test_incomplete_message_event_is_logged_without_payload(self):
        with self.assertLogs(VOICEMAIL_MESSAGE_LOGGER, level="WARNING") as log_cm:
            self.env["voip.voicemail.message"]._handle_message_created_event(
                "evt-incomplete", {}, fields.Datetime.now(),
            )
        self.assertEqual(len(log_cm.output), 1)
        self.assertIn("evt-incomplete", log_cm.output[0])
        self.assertNotIn("{}", log_cm.output[0])
