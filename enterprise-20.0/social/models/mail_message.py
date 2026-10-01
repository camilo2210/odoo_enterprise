# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class MailMessage(models.Model):
    _inherit = "mail.message"

    def _message_reaction(self, content, action, partner, guest, store=None):
        """When the social manager reacts to a message in a social channel, send the reaction on the social media."""
        self.ensure_one()

        if (
            self.model == 'discuss.channel'
            and self.res_id
            and self.message_id
            and (channel := self.env['discuss.channel'].browse(self.res_id))
            and (mail_guest := channel._social_get_mail_guest_recipient())
        ):
            channel._send_social_reaction(content, action, mail_guest, self.message_id)
        return super()._message_reaction(content, action, partner, guest, store)
