# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models, fields, api
from odoo.http import request
from odoo.exceptions import AccessError

import logging
import requests

from odoo.tools import SQL
from odoo.tools.misc import hmac

_logger = logging.getLogger(__name__)


class SocialAccount(models.Model):
    """ A social.account represents an actual account on the related social.media.
    Ex: A Facebook Page or a Twitter Account.

    These social.accounts will then be used to send generic social.posts to multiple social.accounts.
    They are also used to display a 'dashboard' of statistics on the 'Feed' view.

    Account statistic fields are 'computed' manually through the _compute_statistics method
    that is overridden by each actual social module implementations (social_facebook, social_twitter, ...).
    The statistics computation is run manually when visualizing the Feed. """

    _name = 'social.account'
    _description = 'Social Account'

    def _get_default_company(self):
        """When the user is redirected to the callback URL of the different media,
        the company in the environment is always the company of the current user and not
        necessarily the selected company.

        So, before the authentication process, we store the selected company in the
        user session (see <social.media>::action_add_account) to be able to retrieve it
        here.
        """
        if request and 'social_company_id' in request.session:
            company_id = request.session['social_company_id']
            if not company_id:  # All companies
                return False
            if company_id in self.env.companies.ids:
                return company_id
        return self.env.company

    name = fields.Char('Name', required=True)
    social_account_handle = fields.Char("Handle / Short Name",
        help="Contains the social media handle of the person that created this account. E.g: '@odoo.official' for the 'Odoo' X account")
    active = fields.Boolean("Active", default=True)
    media_id = fields.Many2one('social.media', string="Social Media", required=True, readonly=True, index=True,
        help="Related Social Media (Facebook, X, ...).", ondelete='cascade')
    media_type = fields.Selection(related='media_id.media_type')
    user_link = fields.Char("User Link", compute='_compute_stats_link')
    stats_link = fields.Char("Stats Link", compute='_compute_stats_link',
        help="Link to the external Social Account statistics")
    image = fields.Image("Image", max_width=128, max_height=128, readonly=True)
    is_media_disconnected = fields.Boolean('Link with external Social Media is broken')

    audience = fields.Integer("Audience", readonly=True,
        help="General audience of the Social Account (Page Likes, Account Follows, ...).")
    audience_trend = fields.Float("Audience Trend", readonly=True, digits=(3, 0),
        help="Percentage of increase/decrease of the audience over a defined period.")
    engagement = fields.Integer("Engagement", readonly=True,
        help="Number of people engagements with your posts (Likes, Comments, ...).")
    engagement_trend = fields.Float("Engagement Trend", readonly=True, digits=(3, 0),
        help="Percentage of increase/decrease of the engagement over a defined period.")
    stories = fields.Integer("Stories", readonly=True,
        help="Number of stories created from your posts (Shares, Reposts, ...).")
    stories_trend = fields.Float("Stories Trend", readonly=True, digits=(3, 0),
        help="Percentage of increase/decrease of the stories over a defined period.")
    has_trends = fields.Boolean("Has Trends?",
        help="Defines whether this account has statistics tends or not.")
    has_account_stats = fields.Boolean("Has Account Stats", default=True,
        help="""Defines whether this account has Audience/Engagements/Stories stats.
        Account with stats are displayed on the dashboard.""")
    company_id = fields.Many2one('res.company', 'Company', default=_get_default_company,
                                 domain=lambda self: [('id', 'in', self.env.companies.ids)],
                                 help="Link an account to a company to restrict its usage or keep empty to let all companies use it.")

    has_livechat = fields.Boolean(related="media_id.has_livechat")
    is_livechat_webhook_registered = fields.Boolean("Is Livechat Webhook Registered")
    livechat_channel_id = fields.Many2one("im_livechat.channel", string="Livechat Channel", ondelete="set null", index="btree_not_null")
    livechat_awaiting_discuss_channel_ids = fields.Many2many("discuss.channel", string="Livechat Awaiting Discuss Channels",
        compute="_compute_livechat_awaiting_discuss_channel_ids")
    livechat_awaiting_discuss_channel_count = fields.Integer("Livechat Awaiting Discuss Channels Count",
        compute="_compute_livechat_awaiting_discuss_channel_ids")

    def _compute_statistics(self):
        """ Every social module should override this method if it 'has_account_stats'.
        As the values depend on third party data, it's compute triggered manually that stores the data on the
        various stats fields (audience, engagement, stories) as well as related trends fields (if 'has_trends'). """
        pass

    def _compute_stats_link(self):
        """ Every social module should override this method.
        The 'stats_link' is an external link to the actual social.media statistics for this account.
        Ex: https://www.facebook.com/Odoo-Social-557894618055440/insights """
        for account in self:
            account.stats_link = False
            account.user_link = False

    def _compute_livechat_awaiting_discuss_channel_ids(self):
        discuss_channels = dict(self.env['discuss.channel']._read_group(
            domain=[
                ('livechat_social_account_id', 'in', self.ids),
                ('livechat_failure', '=', 'no_agent'),
                ('livechat_end_dt', '=', False),
            ],
            groupby=['livechat_social_account_id'],
            aggregates=["id:recordset"],
        ))
        for account in self:
            account.livechat_awaiting_discuss_channel_ids = discuss_channels.get(account, False)
            account.livechat_awaiting_discuss_channel_count = len(account.livechat_awaiting_discuss_channel_ids)

    @api.depends('media_id')
    def _compute_display_name(self):
        """ ex: [Facebook] Odoo Social, [Twitter] Mitchell Admin, ... """
        for account in self:
            account.display_name = f"[{account.media_id.name}] {account.name if account.name else ''}"

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._compute_statistics()
        return res

    @api.model
    def refresh_statistics(self):
        """ Will re-compute the statistics of all active accounts. """
        all_accounts = self.env['social.account'].search([('has_account_stats', '=', True)]).sudo()
        # As computing the statistics is a recurring task, we ignore occasional "read timeouts"
        # from the third-party services, as it would most likely mean a temporary slow connection
        # and/or a slow response from their side.
        try:
            all_accounts._compute_statistics()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.warning("Failed to refresh social account statistics.", exc_info=True)
        return [account._get_social_account_values() for account in all_accounts]

    @api.model
    def fetch_statistics(self):
        return [
            account._get_social_account_values()
            for account in self.search([('has_account_stats', '=', True)])
        ]

    def _get_social_account_values(self):
        """Return the values used by the JS for the given social account."""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'is_media_disconnected': self.is_media_disconnected,
            'audience': self.audience,
            'audience_trend': self.audience_trend,
            'engagement': self.engagement,
            'engagement_trend': self.engagement_trend,
            'stories': self.stories,
            'stories_trend': self.stories_trend,
            'has_trends': self.has_trends,
            'media_id': [self.media_id.id],
            'media_type': self.media_id.media_type,
            'stats_link': self.stats_link,
            'has_image': bool(self.image),
        }

    @api.model
    def search_mention_suggestions(self, search_term, media_type):
        """This method is created so that each social_module is able to override the method.

        :param search_term: Search term used to search for a specific user.
        :return: An array of results following this structure: {
            'name': username,
            'description': "A description of the profile if it exists",
            'profile_image_url': "url/to/profile/image",
            **other_infos: "This will be used by the mention system later on."
        }
        """
        return []

    def _compute_trend(self, value, delta_30d):
        return 0.0 if value - delta_30d <= 0 else (delta_30d / (value - delta_30d)) * 100

    def _filter_by_media_types(self, media_types):
        return self.filtered(lambda account: account.media_type in media_types)

    def _get_multi_company_error_message(self):
        """Return an error message if the social accounts information can not be updated by the current user."""
        if not self.env.user.has_group('base.group_multi_company'):
            return

        cids = request.cookies.get('cids')
        if cids:
            allowed_company_ids = {int(cid) for cid in cids.split('-')}
        else:
            allowed_company_ids = {self.env.company.id}

        accounts_other_companies = self.filtered(
            lambda account: account.company_id and account.company_id.id not in allowed_company_ids)

        if accounts_other_companies:
            return _(
                'Create other accounts for %(media_names)s for this company or ask %(company_names)s to share their accounts',
                media_names=', '.join(accounts_other_companies.mapped('media_id.name')),
                company_names=', '.join(accounts_other_companies.mapped('company_id.name')),
            )

    def _action_disconnect_accounts(self, disconnection_info=None):
        _logger.warning("Social account disconnected: %s. Reason: %s",
                        ", ".join(self.mapped("display_name")),
                        disconnection_info or "Not provided",
                        stack_info=True)
        self.sudo().write({'is_media_disconnected': True})

    def action_register_webhook(self):
        """Register the webhook (is managed by submodules)."""
        self.ensure_one()
        if not self.env.user.has_group("social.group_social_manager"):
            raise AccessError(_("Only social manager can register webhook."))

    def action_delete_webhook(self):
        """Unregister from the webhook, API calls are managed by submodules."""
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("social.group_social_manager"):
            raise AccessError(_("Only social manager can register webhook."))
        self.livechat_channel_id = False

    def action_view_social_need_action(self):
        self.ensure_one()
        return {
            **self.env['ir.actions.act_window']._for_xml_id('im_livechat.discuss_channel_action_from_livechat_channel'),
            'domain': [('id', 'in', self.livechat_awaiting_discuss_channel_ids.ids)],
            'context': self.env.context,
        }

    def _social_try_lock_message_id(self, message_id):
        """Take a SQL lock on the given social message id.

        Return False if another transaction holds the lock
        (inspired from @message_process).
        """
        self.ensure_one()
        self.env.cr.execute(
            SQL('SELECT pg_try_advisory_xact_lock(hashtext(%s))',
                repr(('Social Message Lock', message_id, self.id))),
        )
        return self.env.cr.fetchone()[0]

    @api.model
    def _get_attachment_token(self, attachment):
        """Build the access token, so the social media can download the attachment.

        We cannot use the standard download route with the access token of the attachments
        because we will need to call `generate_access_token`, and the API will
        try to fetch before the tokens exists in database, so we use our custom route.
        """
        attachment.check_access('read')
        return hmac(
            self.env(su=True),
            "social-download-attachment",
            attachment.id,
        )
