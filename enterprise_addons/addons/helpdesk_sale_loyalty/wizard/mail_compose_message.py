from odoo import models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def action_send_mail(self):
        res = super().action_send_mail()
        if self.env.context.get('from_helpdesk_ticket'):
            ticket = self.env['helpdesk.ticket'].browse(self.env.context.get('from_helpdesk_ticket'))
            ticket.message_post(body=self.body, attachment_ids=self.attachment_ids.ids)
        return res
