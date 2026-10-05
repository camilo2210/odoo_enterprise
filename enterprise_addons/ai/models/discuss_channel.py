# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.addons.mail.tools.discuss import Store
from odoo.fields import Domain


class DiscussChannel(models.Model):
    """Chat Session
    Representing a conversation between users.
    It extends the base method for usage with AI assistant.
    """

    _name = "discuss.channel"
    _inherit = ["discuss.channel"]

    channel_type = fields.Selection(
        selection_add=[("ai_chat", "AI chat")],
        ondelete={"ai_chat": "cascade"},
    )
    # Having ai_agent_id written by users can compromise the security of channels. For example, adding ai_agent_id
    # to a channel will make it garbage collected, a channel member can unlink an ai agent from the channel, etc.
    # Thus, the field has group fields.NO_ACCESS so that the field can only be written in controlled flows.
    ai_agent_id = fields.Many2one("ai.agent", index="btree_not_null", groups=fields.NO_ACCESS)
    ai_session_ids = fields.One2many('ai.session', inverse_name='channel_id')

    _ai_channel_type_check = models.Constraint(
        "CHECK(ai_agent_id IS NULL or channel_type = 'ai_chat' or channel_type = 'livechat')",
        'AI Agent can only be set for ai_chat or livechat channels.',
    )

    def _compute_display_name(self):
        super()._compute_display_name()
        for channel in self:
            if channel.channel_type == "ai_chat" and not channel.name:
                # sudo: discuss.channel: users can read the AI agent of their AI chat.
                channel.display_name = channel.sudo().ai_agent_id.name

    @api.depends("channel_type", "image_128", "uuid", "ai_agent_id.partner_id.avatar_128")
    def _compute_avatar_128(self):
        # An AI chat wears its agent's avatar (the base _generate_avatar only
        # covers 'channel'/'group', so ai_chat would otherwise be blank).
        # sudo: ai_agent_id has group fields.NO_ACCESS.
        base_channels = self.env["discuss.channel"]
        for channel in self:
            if (
                channel.channel_type == "ai_chat"
                and not channel.image_128
                and (agent := channel.sudo().ai_agent_id)
            ):
                channel.avatar_128 = agent.partner_id.avatar_128
            else:
                base_channels |= channel
        super(DiscussChannel, base_channels)._compute_avatar_128()

    @api.autovacuum
    def _remove_ai_chat_channels(self):
        # sudo() => ai_agent_id has group fields.NO_ACCESS and the method is only called from cron jobs.
        self.sudo().search(
            Domain('channel_type', '=', 'ai_chat')
            & (
                Domain('last_interest_dt', '<', '-30d')
                | (Domain('last_interest_dt', '<', '-1d') & Domain('has_message', '=', False))
            )
        ).unlink()

    def _store_channel_fields(self, res: Store.FieldList):
        super()._store_channel_fields(res)
        self._store_ai_fields(res)

    def _sync_field_names(self, res):
        super()._sync_field_names(res)
        self._store_ai_fields(res[None])

    def _store_ai_fields(self, res: Store.FieldList):
        def is_ai_agent_channel(c):
            return c.channel_type in c._ai_agent_channel_types()
        res.one(
            "ai_agent_id",
            "_store_agent_fields",
            predicate=is_ai_agent_channel,
            sudo=True,
        )
        res.many(
            "ai_session_ids",
            "_store_session_fields",
            predicate=is_ai_agent_channel,
            sudo=True,
        )
        res.one(
            "suggestedAiChannel",
            [],
            value=lambda channel: channel._get_suggested_ai_channel(),
            predicate=lambda channel: channel.channel_type == "ai_chat" and not channel.has_message,
        )
        res.attr("create_date", predicate=lambda c: c.channel_type == "ai_chat")

    def _get_suggested_ai_channel(self):
        self.ensure_one()
        session = self.sudo().ai_session_ids[:1]
        if (
            not session
            or session.create_uid.id != self.env.user.id
            or session.ai_composer_id.interface_key not in {"chatter_ai_button", "systray_ai_button"}
        ):
            return self.env["discuss.channel"]
        return self.env["ai.session"].sudo().search([
            ("id", "<", session.id),
            ("ai_composer_id.interface_key", "=", session.ai_composer_id.interface_key),
            ("res_model", "=", session.res_model),
            ("res_id", "=", session.res_id),
            ("create_uid", "=", self.env.user.id),
            ("channel_id.has_message", "=", True),
        ], order="id desc", limit=1).channel_id.sudo(False)

    def _ai_agent_channel_types(self):
        return ["ai_chat"]
