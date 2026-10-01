# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import route
from odoo.addons.ai_livechat.controllers.main import AILivechatController


class CorsLivechatController(AILivechatController):

    @route("/ai_livechat/cors/forward_operator", type="jsonrpc", auth="force_guest", save_session=False, cors="*")
    def cors_forward_operator(self, guest_token, channel_id):
        return self.forward_operator(channel_id)
