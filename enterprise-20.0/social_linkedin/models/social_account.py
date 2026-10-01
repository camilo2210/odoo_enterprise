# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests
from datetime import datetime, timedelta
from urllib.parse import quote

from odoo import _, models, fields, api
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes
from odoo.tools.urls import urljoin as url_join

from odoo.addons.social.controllers.main import SocialValidationException
from odoo.addons.social_linkedin.utils import urn_to_id, id_to_urn

_logger = logging.getLogger(__name__)


class SocialAccount(models.Model):
    _inherit = 'social.account'

    linkedin_account_urn = fields.Char('LinkedIn Account URN', readonly=True, help='LinkedIn Account URN')
    linkedin_account_id = fields.Char('LinkedIn Account ID', compute='_compute_linkedin_account_id')
    linkedin_access_token = fields.Char('LinkedIn access token', readonly=True, help='The access token is used to perform request to the REST API',
        groups=fields.NO_ACCESS)
    linkedin_is_personal_account = fields.Boolean('LinkedIn Is Personal Account', compute='_compute_linkedin_is_personal_account')

    @api.depends('linkedin_account_urn')
    def _compute_linkedin_account_id(self):
        """Depending on the used LinkedIn endpoint, we sometimes need the full URN, sometimes only the ID part.

        e.g.: "urn:li:person:12365" -> "12365"
        """
        for social_account in self:
            if social_account.linkedin_account_urn:
                social_account.linkedin_account_id = urn_to_id(social_account.linkedin_account_urn)
            else:
                social_account.linkedin_account_id = False

    @api.depends('linkedin_is_personal_account')
    def _compute_stats_link(self):
        linkedin_accounts = self._filter_by_media_types(['linkedin'])
        super(SocialAccount, (self - linkedin_accounts))._compute_stats_link()

        for account in linkedin_accounts:
            if not account.linkedin_is_personal_account:
                account.user_link = f'https://www.linkedin.com/company/{account.linkedin_account_id}'
                account.stats_link = f'{account.user_link}/admin/analytics/visitors/'
            else:
                account.user_link = False
                account.stats_link = False

    def _compute_statistics(self):
        linkedin_accounts = self._filter_by_media_types(['linkedin'])
        super(SocialAccount, (self - linkedin_accounts))._compute_statistics()

        for account in linkedin_accounts:
            all_stats_dict = account._compute_statistics_linkedin()
            month_stats_dict = account._compute_statistics_linkedin(last_30d=True)
            # compute trend
            for stat_name in list(all_stats_dict.keys()):
                all_stats_dict['%s_trend' % stat_name] = self._compute_trend(all_stats_dict.get(stat_name, 0), month_stats_dict.get(stat_name, 0))
            # store statistics
            account.write(all_stats_dict)

    @api.depends('linkedin_account_urn')
    def _compute_linkedin_is_personal_account(self):
        for account in self:
            urn = account.linkedin_account_urn or ''
            account.linkedin_is_personal_account = urn and not urn.startswith("urn:li:organization:")

    def _get_linkedin_access_token(self):
        """Return the access token to use for API calls."""
        self.ensure_one()
        self.check_access("read")
        return self.sudo().linkedin_access_token

    def _get_social_account_values(self):
        self.ensure_one()
        return {
            **super()._get_social_account_values(),
            'linkedin_is_personal_account': self.linkedin_is_personal_account,
        }

    def _linkedin_fetch_followers_count(self, last_30d=False):
        """Fetch number of followers from the LinkedIn API."""
        self.ensure_one()
        follower_count = 0

        if self.linkedin_is_personal_account:
            # https://learn.microsoft.com/en-us/linkedin/marketing/community-management/members/follower-statistics
            endpoint = url_join(self.env['social.media']._LINKEDIN_ENDPOINT, 'memberFollowersCount')
            if last_30d:
                end = datetime.now() + timedelta(days=1)
                start = datetime.now() - timedelta(days=30)
                endpoint += f'?q=dateRange&dateRange=(start:(year:{start.year},month:{start.month},day:{start.day}),end:(year:{end.year},month:{end.month},day:{end.day}))'
            else:
                endpoint += '?q=me'

            response = requests.get(
                endpoint,
                headers=self._linkedin_bearer_headers(),
                timeout=3)

            if response.ok:
                follower_count = sum(
                    el.get('memberFollowersCount', 0)
                    for el in response.json().get('elements', [])
                )
            else:
                _logger.error('Failed to get the personal account followers: %s', response.text)

        elif last_30d:
            # The LinkedIn API time interval take timestamp in milliseconds
            end = int((datetime.now() + timedelta(days=1)).timestamp() * 1000)
            start = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
            endpoint = url_join(self.env['social.media']._LINKEDIN_ENDPOINT, 'organizationalEntityFollowerStatistics')
            endpoint += f'?timeIntervals=(timeRange:(start:{start},end:{end}),timeGranularityType:MONTH)'
            params = {
              "q": "organizationalEntity",
              "organizationalEntity": self.linkedin_account_urn,
            }
            response = requests.get(
                endpoint,
                params=params,
                headers=self._linkedin_bearer_headers(),
                timeout=3)

            if response.ok:
                follower_count = sum(
                    sum(el.get('followerGains', {}).values())
                    for el in response.json().get('elements', [])
                )
            else:
                _logger.error('Failed to get the page followers trend: %s', response.text)

        else:
            endpoint = url_join(self.env['social.media']._LINKEDIN_ENDPOINT, f'networkSizes/{self.linkedin_account_urn}')
            # removing X-Restli-Protocol-Version header for this endpoint as it is not required according to LinkedIn Doc.
            # using this header with an endpoint that doesn't support it will cause the request to fail
            headers = self._linkedin_bearer_headers()
            headers.pop('X-Restli-Protocol-Version', None)
            response = requests.get(
                endpoint,
                params={'edgeType': 'COMPANY_FOLLOWED_BY_MEMBER'},
                headers=headers,
                timeout=3)

            if response.ok:
                follower_count = response.json().get('firstDegreeSize', 0)
            else:
                _logger.error('Failed to get the page followers: %s', response.text)

        return follower_count

    def _compute_statistics_linkedin(self, last_30d=False):
        """Fetch statistics from the LinkedIn API.

        :param last_30d: If `True`, return the statistics of the last 30 days
                      Else, return the statistics of all the time.

            If we want statistics for the month, we need to choose the granularity
            "month". The time range has to be bigger than the granularity and
            if we have result over 1 month and 1 day (e.g.), the API will return
            2 results (one for the month and one for the day).
            To avoid this, we simply move the end date in the future, so we have
            result  only for this month, in one simple dict.
        """
        self.ensure_one()

        if self.linkedin_is_personal_account:
            return {
                'audience': self._linkedin_fetch_followers_count(last_30d),
                'engagement': 0,
                'stories': 0,
            }

        endpoint = url_join(self.env['social.media']._LINKEDIN_ENDPOINT, 'organizationalEntityShareStatistics')
        params = {
            'q': 'organizationalEntity',
            'organizationalEntity': self.linkedin_account_urn,
        }

        if last_30d:
            # The LinkedIn API take timestamp in milliseconds
            end = int((datetime.now() + timedelta(days=1)).timestamp() * 1000)
            start = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
            endpoint += f'?timeIntervals=(timeRange:(start:{start},end:{end}),timeGranularityType:MONTH)'

        response = requests.get(
            endpoint,
            params=params,
            headers=self._linkedin_bearer_headers(),
            timeout=5)

        if response.status_code != 200:
            return {}

        data = (response.json().get('elements') or [{}])[0].get('totalShareStatistics', {})

        return {
            'audience': self._linkedin_fetch_followers_count(last_30d),
            'engagement': data.get('clickCount', 0) + data.get('likeCount', 0) + data.get('commentCount', 0),
            'stories': data.get('shareCount', 0) + data.get('shareMentionsCount', 0),
        }

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        linkedin_accounts = res.filtered(lambda account: account.media_type == 'linkedin')
        if linkedin_accounts:
            linkedin_accounts._create_default_stream_linkedin()

        return res

    def _linkedin_bearer_headers(self, linkedin_access_token=None):
        if linkedin_access_token is None:
            linkedin_access_token = self._get_linkedin_access_token()
        return {
            'Authorization': 'Bearer %s' % linkedin_access_token,
            'cache-control': 'no-cache',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202511',
        }

    def _get_linkedin_accounts(self, linkedin_access_token, link_personal=False):
        """Make an API call to get all LinkedIn pages linked to the actual access token."""
        # https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/profile-api
        if link_personal:
            response = requests.get(
                "https://api.linkedin.com/v2/me",
                headers=self._linkedin_bearer_headers(linkedin_access_token),
                timeout=5,
            )
            if not response.ok:
                raise SocialValidationException(_('An error occurred when fetching your account: “%s”.', response.text))

            user = response.json()
            user_name = ' '.join(filter(bool, (user.get('localizedLastName'), user.get('localizedFirstName'))))
            user_values = {
                'name': user_name,
                'linkedin_account_urn': f"urn:li:person:{user.get('id')}",
                'linkedin_access_token': linkedin_access_token,
                'social_account_handle': user.get('vanityName'),
            }
            user_image_id = user.get('profilePicture', {}).get('displayImage', '').split(':')[-1]
            image_url_by_id = self._linkedin_request_images([user_image_id], linkedin_access_token)
            if image_url := image_url_by_id.get(user_image_id):
                image_data = requests.get(image_url, timeout=10).content
                user_values['image'] = image_data and BinaryBytes(image_data)
            return [user_values]

        response = self._linkedin_request(
            'organizationAcls',
            params={
                'q': 'roleAssignee',
                'role': 'ADMINISTRATOR',
                'state': 'APPROVED',
            },
            linkedin_access_token=linkedin_access_token,
        )
        if not response.ok:
            raise SocialValidationException(_('An error occurred when fetching your pages: “%s”.', response.text))

        account_ids = [
            urn_to_id(organization['organization'])
            for organization in response.json().get('elements', [])
        ]

        response = self._linkedin_request(
            'organizations',
            object_ids=account_ids,
            fields=('id', 'name', 'localizedName', 'vanityName', 'logoV2:(original)'),
            linkedin_access_token=linkedin_access_token,
        )
        if not response.ok:
            raise SocialValidationException(_('An error occurred when fetching your pages data: “%s”.', response.text))

        organization_results = response.json().get('results', {})

        images_urns = [
            values.get('logoV2', {}).get('original')
            for values in organization_results.values()
        ]
        image_url_by_id = self._linkedin_request_images(images_urns, linkedin_access_token)

        accounts = []
        for account_id, organization in organization_results.items():
            image_id = urn_to_id(organization.get('logoV2', {}).get('original'))
            image_url = image_id and image_url_by_id.get(image_id)
            image_data = BinaryBytes(requests.get(image_url, timeout=10).content) if image_url else False  # FIXME check response status
            accounts.append({
                'name': organization.get('localizedName'),
                'linkedin_account_urn': f"urn:li:organization:{account_id}",
                'linkedin_access_token': linkedin_access_token,
                'social_account_handle': organization.get('vanityName'),
                'image': image_data,
            })
        return accounts

    def _create_linkedin_accounts(self, access_token, media, link_personal=False):
        linkedin_accounts = self._get_linkedin_accounts(access_token, link_personal=link_personal)
        if not linkedin_accounts:
            message = _('You need a Business Account to post on LinkedIn with Odoo Social.\n Please create one and make sure it is linked to your account')
            documentation_link = 'https://business.linkedin.com/marketing-solutions/linkedin-pages'
            documentation_link_label = _('Read More about Business Accounts')
            documentation_link_icon_class = 'oi_linkedin'
            raise SocialValidationException(message, documentation_link, documentation_link_label, documentation_link_icon_class)

        social_accounts = self.sudo().with_context(active_test=False).search([
            ('media_id', '=', media.id),
            ('linkedin_account_urn', 'in', [l.get('linkedin_account_urn') for l in linkedin_accounts])])

        error_message = social_accounts._get_multi_company_error_message()
        if error_message:
            raise SocialValidationException(error_message)

        existing_accounts = {
            account.linkedin_account_urn: account
            for account in social_accounts
            if account.linkedin_account_urn
        }

        accounts_to_create = []
        for account in linkedin_accounts:
            if account['linkedin_account_urn'] in existing_accounts:
                existing_accounts[account['linkedin_account_urn']].write({
                    'active': True,
                    'linkedin_access_token': account.get('linkedin_access_token'),
                    'social_account_handle': account.get('username'),
                    'is_media_disconnected': False,
                    'image': account.get('image')
                })
            else:
                account.update({
                    'media_id': media.id,
                    'is_media_disconnected': False,
                    'has_trends': True,
                    'has_account_stats': True,
                })
                accounts_to_create.append(account)

        self.sudo().create(accounts_to_create)

    def _create_default_stream_linkedin(self):
        """Create a stream for each organization page."""
        page_posts_stream_type = self.env.ref('social_linkedin.stream_type_linkedin_company_post')

        # Add stream for each page, but skip personal account
        streams_to_create = [{
            'media_id': account.media_id.id,
            'stream_type_id': page_posts_stream_type.id,
            'account_id': account.id,
        } for account in self if account.linkedin_account_urn and not account.linkedin_is_personal_account]

        if streams_to_create:
            self.env['social.stream'].create(streams_to_create)

    ################
    # External API #
    ################

    def _linkedin_request(self, endpoint, params=None, linkedin_access_token=None,
                          object_ids=None, complex_object_ids=None, fields=None, method=None,
                          json=None, session=None, headers=None):
        """Make a request to the LinkedIn API.

        :param endpoint: the endpoint to request
        :param params: the GET parameters
        :param linkedin_access_token: the access token to use
            (if it's not yet saved on the social account)
        :param object_ids: the LinkedIn objects ids to pass as GET parameters
        :param complex_object_ids: some LinkedIn objects are more complex (e.g. for likes, etc)
             >>> "(a:xxxx, b:yyyy)"
        :param fields: the field to read on the LinkedIn model
        :param method: the HTTP verb
        :param json: the JSON to post
        :param session: the requests session if any
        :param headers: custom headers to add to the request
        """
        if not linkedin_access_token:
            self.ensure_one()

        if method is None:
            method = "POST" if json else "GET"

        url = url_join(self.env['social.media']._LINKEDIN_ENDPOINT, endpoint)

        # need to be added manually, so requests doesn't escape them
        get_params = []
        if object_ids:
            get_params.append("ids=List(%s)" % ','.join(map(quote, object_ids)))
        if complex_object_ids:
            urns = ",".join(
                "(" + ",".join(f"{name}:{quote(urn)}" for name, urn in obj.items()) + ")"
                for obj in complex_object_ids
            )
            get_params.append(f"ids=List({urns})")
        if fields:
            get_params.append('fields=%s' % ','.join(fields))
        if get_params:
            url += "?" + "&".join(get_params)

        headers = headers or {}
        headers.update(self._linkedin_bearer_headers(linkedin_access_token))

        return (session or requests).request(
            method,
            url,
            params=params,
            json=json,
            headers=headers,
            timeout=5,
        )

    @api.model
    def search_mention_suggestions(self, search_term, media_type):
        """
        This override for LinkedIn is a bit more complex to process since their API uses a really specific
        system.

        First, we search users that have the same vanityName as the one provided by the
        mention. A `vanityName` is the public identifying a specific Linkedin
        Profile/Page, e.g. `https://www.linkedin.com/in/vanityName/` for a user and
        `https://www.linkedin.com/company/vanityName/` for a company.

        If we find a match then we use the info provided by the API and search for the
        profile image to display the correct user on the widget.
        If we don't find a match there, the search is then done for organizations as it
        may not be a user's `vanityName`.
        """
        if media_type != "linkedin":
            return super().search_mention_suggestions(search_term, media_type)

        if not search_term:
            return False
        linkedin_account = self.env['social.account'].search([("media_type", "=", media_type)], limit=1)
        response = linkedin_account._linkedin_request(
            "vanityUrl",
            params={
                'q': "vanityUrlAsOrganization",
                'vanityUrl': f"https://www.linkedin.com/in/{search_term}",
                'organization': linkedin_account.linkedin_account_urn
            },
            linkedin_access_token=linkedin_account._get_linkedin_access_token()
        )

        # No user found or the endpoint errored out, let's search on organizations
        if not response.ok:
            response = linkedin_account._linkedin_request(
                "organizations",
                params={
                    'q': "vanityName",
                    'vanityName': search_term
                },
                fields=("id", "localizedDescription", "localizedName", "logoV2:(original)"),
                linkedin_access_token=linkedin_account._get_linkedin_access_token(),
            )
            if not response.ok:
                _logger.error("The request encountered an issue and couldn't retrieve the organization linked to %s", search_term)
                return []

            elements_returned_json = response.json().get('elements', [{}])
            if not elements_returned_json or not (elements_returned_json := elements_returned_json[0]):
                return []

            member_id = f"urn:li:organization:{elements_returned_json.get('id')}"
        else:
            member_id = response.json().get('elements', [{}])[0].get('member')
            if member_id is None:
                _logger.warning("No member has been returned for %s", search_term)
                return []

            # TODO @THJO: when the endpoint is deprecated update it (remove or change).
            response = requests.get(
                f"https://api.linkedin.com/v2/people/(id:{urn_to_id(member_id)})",
                headers=linkedin_account._linkedin_bearer_headers(),
                timeout=5)
            elements_returned_json = response.json()

        element_found = {
            'name': search_term,
            'full_name': " ".join([elements_returned_json.get('localizedFirstName', ''), elements_returned_json.get('localizedLastName', ''), elements_returned_json.get('localizedName', '')]).strip() or search_term,
            'description': elements_returned_json.get("localizedHeadline", '') or elements_returned_json.get("localizedDescription", ''),
            'member': member_id,
            'vanity_name': search_term,
        }
        image_id = elements_returned_json.get('profilePicture', {}).get('displayImage') or elements_returned_json.get('logoV2', {}).get('original')
        if image_id is not None:
            image_url_by_id = linkedin_account._linkedin_request_images([image_id], linkedin_access_token=linkedin_account._get_linkedin_access_token())
            element_found['profile_image_url'] = image_url_by_id.get(urn_to_id(image_id))
        return [element_found]

    def _linkedin_request_images(self, images_ids, linkedin_access_token=None):
        """Make an API call to get the downloadable URL of the images.

        :param images_ids: Image ids (li:image or digital asset)
        :param linkedin_access_token: Access token to use
        """
        images_urns = [id_to_urn(image_id, "li:image") for image_id in images_ids if image_id]
        if not images_urns:
            return {}
        response = self._linkedin_request(
            'images',
            object_ids=images_urns,
            fields=('downloadUrl',),
            linkedin_access_token=linkedin_access_token,
        )
        return {
            urn_to_id(image_urn): image_values['downloadUrl']
            for image_urn, image_values in response.json().get('results', {}).items()
            if 'downloadUrl' in image_values
        } if response.ok else {}

    def _linkedin_upload_image(self, image_data):
        """Upload an image on LinkedIn.

        :param image_data: Raw bytes of the image
        """
        self.ensure_one()
        # 1 - Register your image to be uploaded
        data = {
            "initializeUploadRequest": {
                "owner": self.linkedin_account_urn,
            },
        }
        response = requests.post(
                url_join(self.env['social.media']._LINKEDIN_ENDPOINT, 'images?action=initializeUpload'),
                headers=self._linkedin_bearer_headers(),
                json=data, timeout=10)

        if not response.ok:
            _logger.error('Could not upload the image: %r.', response.text)

        response = response.json()
        if 'value' not in response or 'uploadUrl' not in response['value']:
            raise UserError(_("We could not upload your image, try reducing its size and posting it again (error: Failed during upload registering)."))

        # 2 - Upload image binary file
        upload_url = response['value']['uploadUrl']
        image_urn = response['value']['image']

        headers = self._linkedin_bearer_headers()
        headers['Content-Type'] = 'application/octet-stream'

        response = requests.request('POST', upload_url, data=image_data, headers=headers, timeout=15)

        if not response.ok:
            raise UserError(_("We could not upload your image, try reducing its size and posting it again."))

        return image_urn
