# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class AiAgent(models.Model):
    _inherit = "ai.agent"

    ai_social_livechat_channel_ids = fields.One2many(
        comodel_name='im_livechat.channel',
        inverse_name='ai_social_livechat_agent_id',
    )

    def _is_user_access_allowed(self):
        return super()._is_user_access_allowed() or bool(self.ai_social_livechat_channel_ids)

    def _get_social_livechat_channel_from_context(self):
        # Same context key as ai_livechat.models.ai_agent.AIAgent._get_instructions,
        # where `discuss_channel` is used to detect the livechat conversation.
        discuss_channel = self.env.context.get('discuss_channel')
        if not discuss_channel or not isinstance(discuss_channel, self.pool['discuss.channel']):
            return self.env['discuss.channel']
        return discuss_channel

    def _get_default_tools(self):
        """Always add the tool "ask human" for AI social channel."""
        tools = super()._get_default_tools()
        discuss_channel_sudo = self._get_social_livechat_channel_from_context().sudo()
        if (
            discuss_channel_sudo
            and discuss_channel_sudo.channel_type == 'livechat'
            and discuss_channel_sudo.livechat_social_account_id
        ):
            # don't load skills like `ai_skill_information_retrieval_query`
            tools = self.env.ref('ai_social.ir_actions_server_add_human')
        return tools

    def _ai_tool_social_livechat_add_human(self):
        discuss_channel_sudo = self._get_social_livechat_channel_from_context().sudo()
        if (
            not discuss_channel_sudo
            or discuss_channel_sudo.channel_type != 'livechat'
            or not discuss_channel_sudo.livechat_social_account_id
        ):
            _logger.warning("AI Social: human asked in non-social channel")
            return self.env._("Error: Cannot use this tool in this conversation")

        forward_result = discuss_channel_sudo._forward_human_operator()
        if not forward_result['agent']:
            _logger.info("AI Social: no human online")
            discuss_channel_sudo.livechat_status = 'need_help'
            return self.env._("Error: Failed to add a human, no human operator online.")

        return self.env._("A human operator has been added to the conversation. Let the user know that a human will take over.")
