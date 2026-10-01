# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests

from werkzeug.urls import url_encode

from odoo import _, models, fields, tools
from odoo.exceptions import UserError
from odoo.tools.urls import urljoin as url_join


class SocialMedia(models.Model):
    _inherit = 'social.media'

    _FACEBOOK_ENDPOINT = 'https://graph.facebook.com'
    _FACEBOOK_ENDPOINT_VERSIONED = f'{_FACEBOOK_ENDPOINT}/v17.0'

    media_type = fields.Selection(selection_add=[('facebook', 'Facebook')])

    def _action_add_account(self):
        """ Builds the URL to Facebook with the appropriate page rights request, then redirects the client.
        Redirect is done in 'self' since Facebook will then return back to the app with the 'redirect_uri' param.

        Redirect URI from Facebook will land on this module controller's 'facebook_account_callback' method.

        Facebook will display an error message if the callback URI is not correctly defined in the Facebook APP settings. """

        self.ensure_one()

        if self.media_type != 'facebook':
            return super()._action_add_account()

        facebook_app_id = self.env['ir.config_parameter'].sudo().get_str('social.facebook_app_id')
        facebook_client_secret = self.env['ir.config_parameter'].sudo().get_str('social.facebook_client_secret')
        if facebook_app_id and facebook_client_secret:
            return self._add_facebook_accounts_from_configuration(facebook_app_id)
        else:
            return self._add_facebook_accounts_from_iap()

    def _add_facebook_accounts_from_configuration(self, facebook_app_id):
        base_facebook_url = 'https://www.facebook.com/v17.0/dialog/oauth?%s'
        scopes = [
                'pages_manage_ads',
                'pages_manage_engagement',
                'pages_manage_metadata',
                'pages_manage_posts',
                'pages_messaging',
                'pages_read_engagement',
                'pages_read_user_content',
                'public_profile',
                'read_insights',
        ]
        if not self.env['ir.config_parameter'].sudo().get_bool('social.facebook_no_business_management'):
            scopes.append("business_management")
        params = {
            'client_id': facebook_app_id,
            'redirect_uri': url_join(self.get_base_url(), '/social/facebook/start_auth_process'),
            'response_type': 'token',
            'scope': ','.join(scopes),
        }
        return base_facebook_url % url_encode(params)

    def _add_facebook_accounts_from_iap(self):
        social_iap_endpoint = self.env['ir.config_parameter'].sudo().get_str(
            'social.social_iap_endpoint') or self.env['social.media']._DEFAULT_SOCIAL_IAP_ENDPOINT

        iap_add_accounts_url = requests.get(url_join(social_iap_endpoint, 'api/social/facebook/1/add_accounts'),
            params={
                'db_uuid': self.env['ir.config_parameter'].sudo().get_str('database.uuid'),
                'returning_url': url_join(self.get_base_url(), '/social/facebook/start_auth_process'),
                'client_host_url': self.get_base_url(),
                'webhook_shared_secret': self._get_webhook_shared_secret(),
                'deletion_shared_secret': self._get_social_facebook_deletion_shared_secret(),
            },
            timeout=5
        ).text

        if iap_add_accounts_url == 'unauthorized':
            raise UserError(_(
                "Oops! You currently don't have an active subscription. No worries, though! "
                "You can easily get one here: %s.\n"
                "Grab a subscription and unlock a world of amazing features!", 'https://www.odoo.com/buy'))

        return iap_add_accounts_url

    def _get_social_facebook_deletion_shared_secret(self):
        """Shared secret between the database and IAP, derived from the database secret."""
        return tools.hmac(self.env(su=True), 'social_facebook-deletion_shared_secret', None)
