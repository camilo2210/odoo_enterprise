# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Domain

from odoo.addons.im_livechat.controllers.messaging_menu import LivechatMessagingMenuController


class SocialLivechatMessagingMenuController(LivechatMessagingMenuController):
    def _get_menu_tab_domain(self, tab_id):
        domain = super()._get_menu_tab_domain(tab_id)
        if tab_id == "livechat" and self.env.user.has_group("im_livechat.im_livechat_group_user"):
            # show the channel waiting for an operator (if someone sent a message while nobody was connected)
            domain |= Domain([
                ("livechat_social_account_id", "!=", False),
                ("livechat_failure", "=", "no_agent"),
                ("livechat_end_dt", "=", False),
                ("livechat_channel_id.user_ids", "in", self.env.user.ids),
            ])
        return domain
