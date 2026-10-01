# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import requests
import urllib.parse

from datetime import datetime
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models
from odoo.addons.social_facebook.utils import meta_run_request_batch
from odoo.exceptions import UserError
from odoo.tools.urls import urljoin as url_join

_logger = logging.getLogger(__name__)


class SocialAccount(models.Model):
    _inherit = 'social.account'

    facebook_account_id = fields.Char('Facebook Account ID', readonly=True,
        help="Facebook Page ID provided by the Facebook API, this should never be set manually.")
    facebook_access_token = fields.Char('Facebook Access Token', readonly=True,
        help="""Facebook Page Access Token provided by the Facebook API, this should never be set manually.
            It's used to authenticate requests when posting to or reading information from this account.""",
        groups=fields.NO_ACCESS)

    def _compute_stats_link(self):
        """ External link to this Facebook Page's 'insights' (fancy name for the page statistics). """
        facebook_accounts = self._filter_by_media_types(['facebook']).filtered('facebook_account_id')
        super(SocialAccount, (self - facebook_accounts))._compute_stats_link()

        for account in facebook_accounts:
            account.stats_link = f"https://www.facebook.com/{account.facebook_account_id}/insights"
            account.user_link = '/social_facebook/redirect_to_profile/%s?name=%s&account_ids=[%s]' % (
                account.facebook_account_id,
                urllib.parse.quote(account.name),
                account.id,
            )

    def _compute_statistics(self):
        """ This method computes this Facebook Page's statistics and trends.
        - The engagement is a computed total of the last year of data for this account.
        - The audience is the all time total of fans (people liking) this page, as visible on the page stats.
          We actually need a separate request to fetch that information.
        - The trends are computed using the delta of the last 30 days compared to the (total - value of last 30 days).
          ex:
          - We gained 40 engagements in the last 3 months.
          - We have 60 engagements in total (last year of data).
          - The trend is 200% -> (40 / (60 - 40)) * 100 """

        facebook_accounts = self._filter_by_media_types(['facebook'])
        super(SocialAccount, (self - facebook_accounts))._compute_statistics()

        accounts_to_compute = facebook_accounts.filtered('facebook_account_id')

        queries = []

        for account in accounts_to_compute:
            # Get `fan_count`
            queries.append({
                'url': account.facebook_account_id,
                'params': {
                    'access_token': account._get_facebook_access_token(),
                    'fields': 'fan_count',
                },
            })

            # Get the stats of the last 30 days
            queries.append({
                'url': f"{account.facebook_account_id}/insights",
                'params': {
                    'access_token': account._get_facebook_access_token(),
                    'metric': 'page_post_engagements,page_follows',
                    'period': 'day',
                    'date_preset': 'last_30d',
                },
            })

            # Facebook only accepts requests for a range of maximum 90 days.
            # We loop 4 times over 90 days to build the last 360 days of data (~ 1 year).
            for i in range(4):
                until = datetime.now() - relativedelta(days=(i * 90))
                since = until - relativedelta(days=90)

                queries.append({
                    'url': f"{account.facebook_account_id}/insights",
                    'params': {
                        'access_token': account._get_facebook_access_token(),
                        'metric': 'page_post_engagements,page_follows',
                        'period': 'day',
                        'since': int(since.timestamp()),
                        'until': int(until.timestamp()),
                    },
                })

        responses = iter(meta_run_request_batch(self.env, queries))

        for account in accounts_to_compute:
            page_global_stats = next(responses)

            statistics_30d = self._parse_statistics_facebook(next(responses))
            statistics_360d = {'page_post_engagements': 0, 'page_fans': 0}

            for __ in range(4):
                result = self._parse_statistics_facebook(next(responses))
                statistics_360d['page_post_engagements'] += result['page_post_engagements']
                statistics_360d['page_fans'] += result['page_fans']

            fan_count = page_global_stats and int(page_global_stats['fan_count']) or 0
            account.write({
                'audience': fan_count,
                'audience_trend': self._compute_trend(fan_count, statistics_30d['page_fans']),
                'engagement': statistics_360d['page_post_engagements'],
                'engagement_trend': self._compute_trend(statistics_360d['page_post_engagements'], statistics_30d['page_post_engagements']),
            })

    def _get_facebook_access_token(self):
        """Return the access token to use for API calls."""
        self.ensure_one()
        self.check_access("read")
        return self.sudo().facebook_access_token

    def _parse_statistics_facebook(self, response):
        """ Check https://developers.facebook.com/docs/graph-api/reference/v17.0/insights for more information
        about the endpoint used.
        e.g of data structure returned by the endpoint:
        [{
            'name':  'page_post_engagements',
            'values': [{
                'value': 10,
                'end_time': '2025-08-20T07:00:00+0000'
            }, {
                'value': 20,
                'end_time': '2025-08-21T07:00:00+0000'
            }]
        }{
            'name':  'page_follows',
            'values': [{
                'value': 15,
                'end_time': '2025-08-20T07:00:00+0000'
            }, {
                'value': 25,
                'end_time': '2025-08-21T07:00:00+0000'
            }]
        }]

        That method returns the delta of the statistics in the given
        period of time (not the total value for the lifetime of the page).
        """
        statistics = {'page_fans': 0, 'page_post_engagements': 0}
        if not response or not response.get('data'):
            return statistics

        json_data = response.get('data')
        page_follows = {}
        for metric in json_data:
            metric_name = metric.get('name')
            values = metric.get('values') or []
            if metric_name == 'page_post_engagements':
                statistics['page_post_engagements'] += sum(v.get('value', 0) for v in values)
            elif metric_name == 'page_follows':
                page_follows.update({
                    v['end_time']: v['value']
                    for v in values
                    if 'end_time' in v and 'value' in v
                })

        if page_follows:
            # "Newest - Oldest"
            # Datetime is in "YYYY-MM-dd" format, so min / max work on string
            statistics['page_fans'] = page_follows[max(page_follows)] - page_follows[min(page_follows)]

        return statistics

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.filtered(lambda account: account.media_type == 'facebook')._create_default_stream_facebook()
        return res

    def _create_default_stream_facebook(self):
        """ This will create a stream of type 'Page Posts' for each added accounts.
        It helps with onboarding to have your posts show up on the 'Feed' view as soon as you have configured your accounts."""

        if not self:
            return

        page_posts_stream_type = self.env.ref('social_facebook.stream_type_page_posts')
        streams_to_create = []
        for account in self:
            streams_to_create.append({
                'media_id': account.media_id.id,
                'stream_type_id': page_posts_stream_type.id,
                'account_id': account.id
            })
        self.env['social.stream'].create(streams_to_create)

    @api.model
    def search_mention_suggestions(self, search_term, media_type):
        """Search a page based on its name (e.g: "LNA's test page").
        We can only search for pages as Facebook doesn't allow us a user search.
        We use the batched requests system to enable us to get all the pictures for each result of the search.
        As /pages/search doesn't provide any image related field.

        The batched requests is a system provided by the Facebook API to enable people to do multiple requests
        in a singular one. https://developers.facebook.com/docs/graph-api/batch-requests/
        The idea is to provide via a POST a list of requests that you want to do, each with its method and relative URL.
        An example of batch requests: [
            {"method":"POST", "relative_url":"PAGE-ID/feed", "body":"message=Test status update"}, <- Update the feed
            {"method":"GET", "relative_url":"PAGE-ID/feed"} <- Get the latest value of the feed
        ]
        These requests are processed in the order of the array provided.
        """
        if media_type != 'facebook':
            return super().search_mention_suggestions(search_term, media_type)

        facebook_account = self.env['social.account'].search([("media_type", "=", media_type)], limit=1)

        response = requests.get(
            url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, '/pages/search'),
            params={'q': search_term, 'fields': 'id,link,name', 'access_token': facebook_account._get_facebook_access_token()},
            timeout=5)

        pages_search_response_json = response.ok and response.json()
        if not pages_search_response_json:
            _logger.error("Failed to receive a JSON response when searching pages with %s, received instead: %s", search_term, response.text)
            return []
        # limit of 8 result in the search similar to mentions in the chatter.
        facebook_page_ids = [facebook_page['id'] for facebook_page in pages_search_response_json.get('data', []) if facebook_page.get('id')][:8]

        batched_requests = [{'method': 'GET', 'relative_url': f'{page_id}/picture?redirect=0&type=square'} for page_id in facebook_page_ids]
        batch_response = requests.post(
            self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED,
            json={"batch": batched_requests},
            params={'access_token': facebook_account._get_facebook_access_token(), 'include_headers': False},
            timeout=5)
        if not batch_response.ok and batch_response.json():
            _logger.error("Failed to retrieve the profile pictures using the batched requests, received instead: %s", response.text)
            return []
        images_search_response_data = [json.loads(response.get('body', '{}')).get('data') for response in batch_response.json()]

        results = [
            {
                "id": page_data["id"],
                "link": page_data["link"],
                "name": page_data["name"],
                "profile_image_url": profile_image_data['url'],
            } for page_data, profile_image_data in zip(pages_search_response_json.get('data'), images_search_response_data)
        ]
        return results

    ###############
    # Common Meta #
    ###############

    def _is_meta_account(self):
        self.ensure_one()
        return self.media_type == 'facebook'

    def _meta_access_token(self):
        if self.media_type == 'facebook':
            return self._get_facebook_access_token()

    def _meta_get_unsupported_file_link(self):
        self.ensure_one()
        if self.media_type == 'facebook':
            return Markup('%(message)s <a href="https://www.facebook.com/messages" target="_blank">%(link)s</a>') % {
                "message": self.env._("Oops, we couldn't show this file."),
                "link": self.env._("See in Facebook"),
            }
        raise NotImplementedError()

    def action_register_webhook(self):
        """Register to the webhook events we need when creating the livechat channel."""
        self.ensure_one()
        # perform manager check before making API calls
        super().action_register_webhook()

        if self._is_meta_account():
            response = requests.post(
                url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, "/me/subscribed_apps"),
                params={"subscribed_fields": "messages,message_reactions,message_echoes", "access_token": self._meta_access_token()},
                timeout=5,
            )
            if response.ok and response.json().get('success'):
                _logger.info('Social: webhook registered for account #%s', self.id)
                self.is_livechat_webhook_registered = True
            else:
                raise UserError(self.env._("Failed to register the webhook: %s", response.text))

    def action_delete_webhook(self):
        self.ensure_one()
        # perform manager check before making API calls
        ret = super().action_delete_webhook()

        if self._is_meta_account():
            response = requests.delete(
                url_join(self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED, "/me/subscribed_apps"),
                params={"access_token": self._meta_access_token()},
                timeout=5,
            )
            if (response.ok and response.json().get('success')) or "App is not installed" in response.text:
                _logger.info('Social: webhook deleted for account #%s', self.id)
                self.is_livechat_webhook_registered = False
            else:
                raise UserError(self.env._("Failed to delete the webhook: %s", response.text))

        return ret
