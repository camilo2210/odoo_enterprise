# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Domain

from odoo.addons.mail.controllers.discuss.messaging_menu import DiscussMessagingMenuController


class WhatsappMessagingMenuController(DiscussMessagingMenuController):
    def _get_menu_tab_domain(self, tab_id):
        if tab_id == "whatsapp":
            return Domain(
                [("channel_type", "=", "whatsapp"), ("self_member_id.is_pinned", "=", True)],
            )
        return super()._get_menu_tab_domain(tab_id)

    def _get_menu_tab_filter_domain(self, tab_id, filter_id):
        if tab_id == "whatsapp" and filter_id == "whatsapp_unread":
            return Domain("self_member_id.is_unread", "=", True)
        return super()._get_menu_tab_filter_domain(tab_id, filter_id)
