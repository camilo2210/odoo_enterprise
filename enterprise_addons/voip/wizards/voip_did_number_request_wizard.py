from odoo import fields, models


class VoipDidNumberRequestWizard(models.TransientModel):
    _name = "voip.did.number.request.wizard"
    _description = "Phone Number Request"

    recipient_ids = fields.Many2many(
        "res.users",
        string="Send to",
        compute="_compute_recipient_ids",
    )
    body_html = fields.Html("Comment")

    def _get_recipients(self):
        return self.env.ref("voip.group_voip_admin").all_user_ids

    def _compute_recipient_ids(self):
        self.recipient_ids = self._get_recipients()

    def action_send_request(self):
        self.ensure_one()
        template = self.env.ref("voip.mail_template_phone_number_request")
        for recipient in self._get_recipients():
            template.with_context(
                recipient_id=recipient.partner_id.id,
                recipient_lang=recipient.lang,
                recipient_name=recipient.name,
            ).send_mail(
                self.id,
                force_send=True,
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": self.env._("Request sent"),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
