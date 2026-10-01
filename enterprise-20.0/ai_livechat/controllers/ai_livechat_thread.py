from odoo.addons.ai.controllers.thread import AIThreadController


class AILivechatThreadController(AIThreadController):
    def _get_channel_ai_session(self, channel):
        if session := super()._get_channel_ai_session(channel):
            return session
        if channel.channel_type == 'livechat':
            return self.env['ai.session'].sudo().create({
                'agent_id': channel.sudo().ai_agent_id.id, 'channel_id': channel.id,
            })
        return session
