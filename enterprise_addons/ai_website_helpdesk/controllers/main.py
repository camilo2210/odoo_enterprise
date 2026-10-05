# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from odoo.addons.website_helpdesk.controllers.main import WebsiteHelpdesk


class AIWebsiteHelpdesk(WebsiteHelpdesk):
    @http.route()
    def website_helpdesk_knowledge_base(self, team, **kwargs):
        if not team.show_knowledge_base:
            return request.redirect(team.website_url, code=302)
        ai_agent = request.env.ref('ai.ai_agent_1', raise_if_not_found=False)
        channel_id = request.env.ref('im_livechat.im_livechat_channel_data', raise_if_not_found=False)
        return request.render("ai_website_helpdesk.ai_helpdesk_knowledge", {
            "team": team,
            "ai_agent": ai_agent and ai_agent.id,
            "channel_id": channel_id and channel_id.id,
        })
