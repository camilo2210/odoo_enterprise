# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import route
from odoo.addons.ai_livechat.controllers.ai_livechat_thread import AILivechatThreadController


class CorsLivechatController(AILivechatThreadController):

    @route(
        "/ai/cors/start_session_advance",
        type="jsonrpc",
        methods=["POST"],
        auth="force_guest",
        save_session=False,
        cors="*",
    )
    def cors_start_session_advance(
        self, guest_token, channel_id, mail_message_id,
        current_view_info=None, ai_session_config=None, ai_session_identifier=None, debug=False,
    ):
        return self.start_session_advance(
            channel_id,
            mail_message_id,
            current_view_info=current_view_info,
            ai_session_config=ai_session_config,
            ai_session_identifier=ai_session_identifier,
            debug=debug,
        )

    @route(
        "/ai/cors/resume_pending_interaction",
        type="jsonrpc",
        methods=["POST"],
        auth="force_guest",
        save_session=False,
        cors="*",
    )
    def cors_resume_pending_interaction(
        self, guest_token, channel_id, session_id, resume_token,
        response, current_view_info=None, ai_session_config=None, ai_session_identifier=None, debug=False,
    ):
        return self.resume_pending_interaction(
            channel_id,
            session_id,
            resume_token,
            response=response,
            current_view_info=current_view_info,
            ai_session_config=ai_session_config,
            ai_session_identifier=ai_session_identifier,
            debug=debug,
        )
