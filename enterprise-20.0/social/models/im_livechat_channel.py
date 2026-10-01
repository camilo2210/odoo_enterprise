# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ImLivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    social_account_ids = fields.One2many(
        "social.account",
        "livechat_channel_id",
        string="Social Accounts",
        domain="[('has_livechat', '=', True)]")
    social_discuss_channel_need_action_ids = fields.Many2many(
        "discuss.channel",
        string="Social Need Action",
        help="Discuss channel for which no operator could have been found",
        compute="_compute_social_discuss_channel_need_action_ids")
    social_discuss_channel_need_action_count = fields.Integer(
        "Social Need Action Count",
        compute="_compute_social_discuss_channel_need_action_ids")
    social_away_message = fields.Text("Social Away Message")
    has_active_accounts = fields.Boolean('Are Accounts Available?', compute='_compute_has_active_accounts')

    def _compute_social_discuss_channel_need_action_ids(self):
        discuss_channels = dict(self.env['discuss.channel']._read_group(
            domain=[
                ('livechat_social_account_id', '!=', False),
                ('livechat_failure', '=', 'no_agent'),
                ('livechat_channel_id', 'in', self.ids),
                ('livechat_end_dt', '=', False),
            ],
            groupby=['livechat_channel_id'],
            aggregates=["id:recordset"],
        ))
        for channel in self:
            channel.social_discuss_channel_need_action_ids = discuss_channels.get(channel, False)
            channel.social_discuss_channel_need_action_count = len(channel.social_discuss_channel_need_action_ids)

    def _compute_has_active_accounts(self):
        self.has_active_accounts = bool(self.env['social.account'].search_count([], limit=1))

    def action_view_social_need_action(self):
        self.ensure_one()
        return {
            **self.env['ir.actions.act_window']._for_xml_id('im_livechat.discuss_channel_action_from_livechat_channel'),
            'domain': [('id', 'in', self.social_discuss_channel_need_action_ids.ids)],
            'context': self.env.context,
        }

    def _get_channel_name(self, /, *, visitor_user=None, guest=None, agent, chatbot_script, operator_model, livechat_social_account=None, **kwargs):
        """Compute the channel name for social channel."""
        if livechat_social_account:
            return f"{guest.sudo().name} ({livechat_social_account.sudo().name})"
        return super()._get_channel_name(
            visitor_user=visitor_user,
            guest=guest,
            agent=agent,
            chatbot_script=chatbot_script,
            operator_model=operator_model,
            livechat_social_account=livechat_social_account,
            **kwargs,
        )

    def _social_get_session_args(self, previous_operator_id=False):
        # set the arguments used to build the session, like it's done in `/im_livechat/get_session`
        return {}

    def _social_livechat_on_media_message(self, discuss_channel, message):
        """Called when the media user sends a message."""
