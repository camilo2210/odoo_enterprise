# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests

from datetime import datetime
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models
from odoo.addons.social_facebook.utils import meta_run_request_batch

from odoo.tools.urls import urljoin as url_join


_logger = logging.getLogger(__name__)


class SocialAccount(models.Model):
    _inherit = 'social.account'

    instagram_account_id = fields.Char('Instagram Account ID', readonly=True,
        help="Instagram Account ID provided by the Facebook API, this should never be set manually.")
    instagram_facebook_account_id = fields.Char('Instagram Facebook Account ID', readonly=True,
        help="""Facebook Account ID provided by the Facebook API, this should never be set manually.
        The Instagram ("Professional") account is always linked to a Facebook account.""")
    instagram_access_token = fields.Char(
        'Instagram Access Token', readonly=True,
        help="""Instagram Access Token provided by the Facebook API, this should never be set manually.
        It's used to authenticate requests when posting to or reading information from this account.""",
        groups=fields.NO_ACCESS)

    def _compute_stats_link(self):
        """ Instagram does not provide a 'desktop' version of the insights.
        Statistics are only available through the mobile app, which means we don't have any website URL to provide. """
        instagram_accounts = self._filter_by_media_types(['instagram'])

        super(SocialAccount, (self - instagram_accounts))._compute_stats_link()

        for account in instagram_accounts:
            account.stats_link = False
            account.user_link = f"https://www.instagram.com/{account.social_account_handle}"

    def _compute_statistics(self):
        """ Facebook Instagram API does not provide any data in the 'stories' department.
        Probably because the 'share' mechanic is not the same / not existing for Instagram posts. """
        instagram_accounts = self._filter_by_media_types(['instagram'])

        super(SocialAccount, (self - instagram_accounts))._compute_statistics()

        if not instagram_accounts:
            return

        queries = []
        for account in instagram_accounts:
            queries.append({
                'url': account.instagram_account_id,
                'params': {
                    'access_token': account._get_instagram_access_token(),
                    'fields': 'followers_count',
                },
            })

            queries.append({
                'url': f"{account.instagram_account_id}/insights",
                'params': {
                    'access_token': account._get_instagram_access_token(),
                    'metric': 'follower_count',
                    'period': 'day',
                    'date_preset': 'last_30d',
                },
            })

            # Instagram (Facebook) only accepts requests for a range of maximum 30 days.
            # We loop 12 times over 30 days to build the last 360 days of data (~ 1 year).
            for index in range(12):
                until = datetime.now() - relativedelta(days=(index * 30))
                since = until - relativedelta(days=30)

                queries.append({
                    'url': f"{account.instagram_account_id}/insights",
                    'params': {
                        'access_token': account._get_instagram_access_token(),
                        'metric': 'total_interactions',
                        'period': 'day',
                        'since': int(since.timestamp()),
                        'until': int(until.timestamp()),
                        'metric_type': 'total_value',
                    },
                })

        responses = iter(meta_run_request_batch(self.env, queries))

        for account in instagram_accounts:
            account_global_stats = next(responses)

            statistics_30d_followers_count = next(responses)
            if statistics_30d_followers_count:
                statistics_30d_followers_count = sum(
                    value.get('value', 0)
                    for data in statistics_30d_followers_count.get('data', ())
                    for value in data.get('values', ())
                )

            statistics_360d_total_interactions = [
                int(response and sum(
                    v.get('total_value', {}).get('value', 0)
                    for v in response.get('data', ()))
                )
                for __, response in zip(range(12), responses)
            ]

            audience = account_global_stats and int(account_global_stats.get('followers_count', 0))
            account.write({
                'audience': audience,
                'audience_trend': self._compute_trend(audience, statistics_30d_followers_count),
                'engagement': sum(statistics_360d_total_interactions),
                'engagement_trend': self._compute_trend(
                    sum(statistics_360d_total_interactions),
                    statistics_360d_total_interactions[0])
            })

    def _get_instagram_access_token(self):
        """Return the access token to use for API calls."""
        self.ensure_one()
        self.check_access("read")
        return self.sudo().instagram_access_token

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.filtered(
            lambda a: a.media_type == 'instagram'
        )._create_default_stream_instagram()
        return res

    def _create_default_stream_instagram(self):
        stream_type_instagram_posts = self.env.ref(
            'social_instagram.stream_type_instagram_posts')

        self.env['social.stream'].create([{
            'media_id': account.media_id.id,
            'stream_type_id': stream_type_instagram_posts.id,
            'account_id': account.id
        } for account in self])

    @api.model
    def search_mention_suggestions(self, search_term, media_type):
        """Search a business by name.

        Unfortunately Instagram doesn't allow to search for every user on the platform.
        And the endpoint that used to allow it is now deprecated: https://api.instagram.com/v1/users/search
        But you can still search for users linked to a business (Content Creators, Store accounts, etc.).
        See: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery/
        The business discovery requires the exact handle of the account in order for us to have all
        the necessary infos.
        """
        if media_type != "instagram":
            return super().search_mention_suggestions(search_term, media_type)

        instagram_account = self.env['social.account'].search([("media_type", "=", media_type)])
        user_search_endpoint = url_join(
            self.env['social.media']._INSTAGRAM_ENDPOINT,
            f'/v17.0/{instagram_account.instagram_account_id}')
        params = {
            'fields': f'business_discovery.username({search_term}){{username, name, profile_picture_url, biography}}',
            'access_token': instagram_account._get_instagram_access_token()
        }
        response = requests.get(
            user_search_endpoint,
            params=params,
            timeout=5
        )

        response_json = response.ok and response.json()
        if not response_json:
            _logger.error("Failed to receive a JSON response when searching users with %s, received instead: %s", search_term, response.text)
            return []

        if response_json.get('error'):
            _logger.error(response_json.get('error'))
            return []

        business_discovery = response_json.get('business_discovery', {})
        business_discovery["description"] = business_discovery.get("biography", "")
        business_discovery["profile_image_url"] = business_discovery.get("profile_picture_url", "")

        return [business_discovery]

    def _is_meta_account(self):
        self.ensure_one()
        return self.media_type == 'instagram' or super()._is_meta_account()

    def _meta_access_token(self):
        if self.media_type == 'instagram':
            return self._get_instagram_access_token()

        return super()._meta_access_token()

    def _meta_get_unsupported_file_link(self):
        if self.media_type == 'instagram':
            return Markup('%(message)s <a href="https://www.instagram.com/direct" target="_blank">%(link)s</a>') % {
                "message": self.env._("Oops, we couldn't show this file."),
                "link": self.env._("See in Instagram"),
            }
        return super()._meta_get_unsupported_file_link()
