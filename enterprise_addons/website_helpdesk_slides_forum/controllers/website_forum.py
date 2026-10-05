# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.website_helpdesk_forum.controllers.website_forum import WebsiteForumHelpdesk


class WebsiteSlidesForumHelpdesk(WebsiteForumHelpdesk):

    def _get_helpdesk_forums_render_values(self, forums):
        values = super()._get_helpdesk_forums_render_values(forums)
        values['hide_forum_slides_link'] = True
        return values
