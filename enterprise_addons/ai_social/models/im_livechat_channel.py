# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ImLivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    ai_social_livechat_agent_id = fields.Many2one(
        "ai.agent",
        string="AI Agent",
        domain="[('is_system_agent', '=', False)]",
        index="btree_not_null",
    )
    ai_social_livechat_enabled_condition = fields.Selection(
        string="Enable ChatBot",
        selection=[
            ("always", "Always"),
            ("only_if_no_operator", "Only when no operator is available"),
            ("only_if_operator", "Only when an operator is available"),
        ],
        required=True,
        default="always",
    )

    def _social_get_session_args(self, previous_operator_id=False):
        session_args = super()._social_get_session_args(previous_operator_id)
        session_args['ai_agent_id'] = False
        if not self.ai_social_livechat_agent_id:
            return session_args

        add_ai_agent = self.ai_social_livechat_enabled_condition == "always"
        if not add_ai_agent:
            operator_available = self._get_operator(
                country_id=False,
                lang=False,
                previous_operator_id=previous_operator_id,
            )

            if self.ai_social_livechat_enabled_condition == "only_if_operator":
                add_ai_agent = operator_available
            elif self.ai_social_livechat_enabled_condition == "only_if_no_operator":
                add_ai_agent = not operator_available

        if add_ai_agent:
            session_args['ai_agent_id'] = self.ai_social_livechat_agent_id.id
        return session_args

    def _social_livechat_on_media_message(self, discuss_channel, message):
        super()._social_livechat_on_media_message(discuss_channel, message)
        ai_agent = discuss_channel.ai_agent_id
        if not ai_agent:
            return

        ai_session_sudo = self.env['ai.session'].sudo().search(
            [('channel_id', '=', discuss_channel.id), ('agent_id', '=', ai_agent.id)],
            order='create_date DESC',
            limit=1,
        )
        if not ai_session_sudo:
            ai_session_sudo = self.env['ai.session'].sudo().create({
                'agent_id': ai_agent.id,
                'channel_id': discuss_channel.id,
            })

        # A new message supersedes any model request still awaiting its callback.
        ai_session_sudo.with_context(discuss_channel=discuss_channel)._submit_agent_request(
            message._convert_to_parts(),
        )
