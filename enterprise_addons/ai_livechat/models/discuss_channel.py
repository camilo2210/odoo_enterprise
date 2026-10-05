# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    ai_agent_partner_id = fields.Many2one(
        "res.partner",
        compute="_compute_ai_agent_partner_id",
        string="AI Agent",
    )

    @api.depends("ai_agent_id")
    def _compute_ai_agent_partner_id(self):
        for channel in self:
            # sudo: field has groups=fields.NO_ACCESS
            channel.ai_agent_partner_id = channel.sudo().ai_agent_id.partner_id

    def write(self, vals):
        result = super().write(vals)
        if vals.get("livechat_end_dt"):
            # Archive the session when the channel is closed
            closed = self.filtered(lambda channel: channel.channel_type == "livechat")
            self.env["ai.session"].sudo().search([("channel_id", "in", closed.ids)]).active = False
        return result

    def _forward_scripted_chatbot(self, chatbot_script_id):
        # sudo - discuss.channel: let the AI Agent proceed to the forward step (change channel operator, add scripted chatbot
        # as member, remove AI Agent from channel and finally rename channel).
        channel_sudo = self.sudo()
        ai_agent_member = channel_sudo.channel_member_ids.filtered(lambda m: m.livechat_member_type == "bot")

        # add the scripted chatbot to the channel and post a "chatbot invited to the channel" notification
        channel_sudo._add_members(
            create_member_params={'livechat_member_type': 'bot'},
            inviting_partner=ai_agent_member.partner_id,
            partners=chatbot_script_id.operator_partner_id,
        )

        ai_agent_member.unlink()

        # finally, rename the channel to include the scripted chatbot's name
        channel_sudo._update_forwarded_channel_data(
            livechat_failure="no_failure",
            operator_name=chatbot_script_id.title,
        )
        posted_messages = chatbot_script_id.with_context(lang=chatbot_script_id._get_chatbot_language())._post_welcome_steps(self)
        self.self_member_id.last_interest_dt = fields.Datetime.now()
        return posted_messages

    def _update_forwarded_channel_data(self, **kwargs):
        super()._update_forwarded_channel_data(**kwargs)
        self.sudo().ai_agent_id = False

    def _get_allowed_channel_member_create_params(self):
        return super()._get_allowed_channel_member_create_params() + ["ai_agent_id"]

    def _ai_agent_channel_types(self):
        return super()._ai_agent_channel_types() + ["livechat"]

    @api.model
    def _process_extra_channel_params(self, **kwargs):
        non_persisted_channel_params, persisted_channel_params = super()._process_extra_channel_params(**kwargs)
        # sudo() => access is managed through _is_user_access_allowed.
        ai_agent = self.env['ai.agent'].sudo().search([('id', '=', kwargs.get('ai_agent_id'))])
        if ai_agent and ai_agent._is_user_access_allowed():
            non_persisted_channel_params['ai_agent_id'] = ai_agent.id
            persisted_channel_params['ai_agent_id'] = ai_agent.id
        return non_persisted_channel_params, persisted_channel_params
