# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests
from werkzeug.urls import url_encode

from odoo import _, models, fields
from odoo.exceptions import UserError
from odoo.tools.urls import urljoin as url_join


class SocialMedia(models.Model):
    _inherit = 'social.media'

    _LINKEDIN_ENDPOINT = 'https://api.linkedin.com/rest/'
    _LINKEDIN_PAGE_SCOPES = 'r_organization_followers rw_organization_admin w_organization_social w_organization_social_feed r_organization_social r_organization_social_feed'
    _LINKEDIN_PERSONAL_SCOPES = 'r_basicprofile r_member_profileAnalytics w_member_social r_organization_social_feed'

    media_type = fields.Selection(selection_add=[('linkedin', 'LinkedIn')])

    def _action_add_account(self):
        self.ensure_one()

        if self.media_type != 'linkedin':
            return super()._action_add_account()

        linkedin_use_own_account = self.env['ir.config_parameter'].sudo().get_str('social.linkedin_use_own_account')
        linkedin_app_id = self.env['ir.config_parameter'].sudo().get_str('social.linkedin_app_id')
        linkedin_client_secret = self.env['ir.config_parameter'].sudo().get_str('social.linkedin_client_secret')

        if linkedin_app_id and linkedin_client_secret and linkedin_use_own_account:
            return self._add_linkedin_accounts_from_configuration(linkedin_app_id)
        else:
            return self._add_linkedin_accounts_from_iap()

    def _add_linkedin_accounts_from_configuration(self, linkedin_app_id):
        link_personal = bool(self.env.context.get('linkedin_link_personal'))
        state = f"{self._get_csrf_token()}-{int(link_personal)}"
        params = {
            'response_type': 'code',
            'client_id': linkedin_app_id,
            'redirect_uri': self._get_linkedin_redirect_uri(),
            'state': state,
            'scope': self._LINKEDIN_PERSONAL_SCOPES if link_personal else self._LINKEDIN_PAGE_SCOPES,
        }
        return 'https://www.linkedin.com/oauth/v2/authorization?%s' % url_encode(params)

    def _add_linkedin_accounts_from_iap(self):
        social_iap_endpoint = self.env['ir.config_parameter'].sudo().get_str(
            'social.social_iap_endpoint') or self.env['social.media']._DEFAULT_SOCIAL_IAP_ENDPOINT

        link_personal = bool(self.env.context.get('linkedin_link_personal'))
        state = f"{self._get_csrf_token()}-{int(link_personal)}"
        iap_add_accounts_url = requests.get(url_join(social_iap_endpoint, 'api/social/linkedin/1/add_accounts'), params={
            'state': state,
            'scope': self._LINKEDIN_PERSONAL_SCOPES if link_personal else self._LINKEDIN_PAGE_SCOPES,
            'o_redirect_uri': self._get_linkedin_redirect_uri(),
            'db_uuid': self.env['ir.config_parameter'].sudo().get_str('database.uuid')
        }, timeout=5).text

        if iap_add_accounts_url == 'unauthorized':
            raise UserError(_(
                "Oops! You currently don't have an active subscription. No worries, though! "
                "You can easily get one here: %s.\n"
                "Grab a subscription and unlock a world of amazing features!", 'https://www.odoo.com/buy'))
        elif iap_add_accounts_url == 'linkedin_missing_configuration' or iap_add_accounts_url == 'missing_parameters':
            raise UserError(_("The url that this service requested returned an error. Please contact the author of the app."))

        return iap_add_accounts_url

    def _get_linkedin_redirect_uri(self):
        return url_join(self.get_base_url(), '/social/linkedin/start_auth_process')
