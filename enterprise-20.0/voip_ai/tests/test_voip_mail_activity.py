from odoo.addons.mail.tests.common import MailCommon
from odoo.tests.common import tagged


@tagged("call_artifacts")
class TestVoipAiMailActivity(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.user_employee

    def test_activity_message_shows_both_icons(self):
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        activity = self.env["mail.activity"].create({
            "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
            "res_model_id": self.env["ir.model"]._get("res.partner").id,
            "res_id": partner.id,
            "user_id": self.user.id,
        })
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "user_id": self.user.id,
            "activity_id": activity.id,
        })
        self.env["mail.call.artifact"].create({
            "voip_call_id": call.id,
            "is_stt": False,
            "start_ms": 0,
            "end_ms": 60000,
        })
        self.env["mail.call.artifact"].create({
            "voip_call_id": call.id,
            "is_stt": True,
            "start_ms": 0,
            "end_ms": 60000,
            "transcription_state": "done",
            "transcript": "Hello world",
        })
        activity._action_done(feedback="done")
        message = call.activity_mail_message_id
        call.update_activity_message()
        self.assertIn("graphic_eq", message.body)
        self.assertIn("subtitles", message.body)

    def test_activity_message_uses_summary_as_feedback(self):
        partner = self.env["res.partner"].create({"name": "Feedback Partner"})
        activity = self.env["mail.activity"].create({
            "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
            "res_model_id": self.env["ir.model"]._get("res.partner").id,
            "res_id": partner.id,
            "user_id": self.user.id,
        })
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "user_id": self.user.id,
            "activity_id": activity.id,
            "summary": "AI summary as feedback",
        })
        activity._action_done()
        message = call.activity_mail_message_id
        self.assertNotIn("AI summary as feedback", message.body)
        call.update_activity_message()
        message.invalidate_recordset()
        self.assertIn("AI summary as feedback", message.body)
        self.assertEqual(activity.feedback, "AI summary as feedback")
