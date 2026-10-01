# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _social_should_send_message(self, **message_values):
        return super()._social_should_send_message(**message_values) or (
            self.livechat_social_account_id
            and (author_id := message_values.get('author_id'))
            and self.env['res.partner'].browse(author_id).agent_ids
        )

    def _add_members(self, **kwargs):
        all_new_members = super()._add_members(**kwargs)

        # when a human joins manually the channel, remove the AI bot
        for channel in self.filtered('livechat_social_account_id'):
            new_members = channel.channel_member_ids & all_new_members
            if any(user._is_internal() for user in new_members.partner_id.user_ids):
                channel._social_remove_ai_agent()
        return all_new_members

    def _social_on_self_sent_message(self):
        """Called when we reply from the social media website."""
        super()._social_on_self_sent_message()
        self._social_remove_ai_agent()
        self.livechat_end_dt = False  # we should not close the channel

    def _social_remove_ai_agent(self):
        self.ensure_one()
        self.sudo().channel_member_ids.filtered(lambda m: m.livechat_member_type == "bot").unlink()
        self.sudo().ai_agent_id = False
