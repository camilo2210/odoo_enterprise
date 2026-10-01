from odoo.addons.bus.tests.common import BusResult
from odoo.addons.mail.tests.common import MailCommon
from odoo.tests.common import HttpCase


class TestVoipImStatus(MailCommon, HttpCase):
    def test_online_manual_status_resends_active_call(self):
        user = self.env["res.users"].create({
            "name": "VOIP Presence User",
            "login": "voip_presence_user",
            "email": "voip_presence_user@example.com",
        })
        self.env["mail.presence"]._update_presence(user)
        self.env["voip.call"].create({
            "phone_number": "1234567890",
            "state": "ongoing",
            "user_id": user.id,
        })
        user.manual_im_status = "offline"
        self.authenticate(user.login, user.login)

        with self.assertBus([
            BusResult(
                (user, "presence"),
                "mail.record/insert",
                {
                    "res.users": [
                        {
                            "should_display_in_call_im_status": True,
                            "id": user.id,
                            "im_status": "online",
                        }
                    ],
                },
            ),
        ]):
            self.make_jsonrpc_request(
                "/mail/set_manual_im_status",
                {"status": "online"},
            )
