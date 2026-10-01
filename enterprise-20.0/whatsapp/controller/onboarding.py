import logging

from markupsafe import Markup
from urllib.parse import urlencode
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi, get_proxy_endpoint, get_proxy_error_message
from odoo.addons.whatsapp.tools.whatsapp_exception import WhatsAppError
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.tools.urls import urljoin as url_join

_logger = logging.getLogger(__name__)


class Onboarding(http.Controller):
    """Onboard a WhatsApp Business Account through Meta Embedded Signup.

    API Documentation:
    https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/overview
    """

    OAUTH_RETURN_URL = '/whatsapp/oauth/return'

    @http.route(OAUTH_RETURN_URL, type='http', methods=['GET'], auth='user', website=True)
    def whatsapp_return_from_authorization(
        self, authorization_code=None, csrf_token=None, error=None, whatsapp_app_id=None,
    ):
        """Complete the WhatsApp account onboarding flow.

        :param str authorization_code: Authorization code returned by the WhatsApp proxy.
        :param str csrf_token: CSRF token to validate.
        :param str error: Error code returned by the WhatsApp proxy, if any,
            ``subscription_error`` or ``configuration_error``, turned into a
            message by ``get_proxy_error_message``.
        :param str whatsapp_app_id: Identifier of Odoo's Meta application, the
            one the proxy signs customers in with, such as ``123456789012345``,
            stored on the account as ``app_uid``.
        :raise AccessError: If the user is not a WhatsApp administrator.
        :raise Forbidden: If the CSRF token is invalid.
        :return: An error page linking to the WhatsApp account list on failure,
            or a redirect to the newly onboarded account on success.
        """
        if not request.env.user.has_group('whatsapp.group_whatsapp_admin'):
            raise AccessError(request.env._("You are not allowed to access this page."))

        if not request.validate_csrf(csrf_token):
            _logger.warning("WhatsApp onboarding CSRF token verification failed.")
            raise Forbidden()

        action = request.env.ref('whatsapp.whatsapp_account_action')
        action_url = f'/odoo/action-{action.id}/'

        if error:
            return self._render_authorization_error(action_url, get_proxy_error_message(request.env, error))

        if not authorization_code or not whatsapp_app_id:
            return self._render_authorization_error(
                action_url,
                request.env._("The WhatsApp proxy did not return the required information."),
            )

        try:
            wa_account = self._onboard_whatsapp_account(authorization_code, whatsapp_app_id)
        except WhatsAppError as onboarding_error:
            return self._render_authorization_error(
                action_url,
                onboarding_error.error_message or str(onboarding_error),
            )
        return request.redirect(f'{action_url}{wa_account.id}')

    def _render_authorization_error(self, action_url, error_message):
        """Return the onboarding error page linking back to the WhatsApp accounts."""
        return request.render('whatsapp.authorization_error', {
            'account_url': action_url,
            'error_message': error_message,
        })

    def _onboard_whatsapp_account(self, authorization_code, whatsapp_app_id):
        """Onboard a WhatsApp account using the Embedded Signup flow.

        Flow:
        - Exchange the authorization code for an access token.
        - Fetch the onboarded WhatsApp Business Account.
        - Fetch the onboarded phone number.
        - Create or update the WhatsApp account.
        - Configure the webhook.

        API Documentation:
        https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-customers-as-a-tech-provider
        """
        wa_api = WhatsAppApi(request.env['whatsapp.account'])
        access_token = wa_api._fetch_and_store_access_token(authorization_code)
        waba_id = wa_api._fetch_onboarded_waba_id()
        phone_number_data = wa_api._fetch_onboarded_phone_number_data(waba_id)
        wa_account = self._create_or_update_whatsapp_account(
            access_token,
            waba_id,
            phone_number_data,
            whatsapp_app_id,
        )

        try:
            wa_account._configure_webhook()
        except WhatsAppError as error:
            wa_account.message_post(
                body=request.env._(
                    "Webhook subscription failed after onboarding.%(br)s"
                    "Please subscribe it manually.%(br)s"
                    "Error: %(error)s",
                    br=Markup("<br/>"),
                    error=error,
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        return wa_account

    def _create_or_update_whatsapp_account(self, access_token, waba_id, phone_number_data, whatsapp_app_id):
        """Create or update the WhatsApp account matching the onboarded phone number."""
        wa_account_values = {
            'account_uid': waba_id,
            'active': True,
            'app_uid': whatsapp_app_id,
            'is_oauth_onboarded': True,
            'is_phone_registered': phone_number_data.get('status') == 'CONNECTED',
            'name': phone_number_data.get('verified_name') or phone_number_data.get('display_phone_number'),
            'phone_number': phone_number_data.get('display_phone_number'),
            'phone_uid': phone_number_data['id'],
            'token': access_token,
        }
        wa_account = request.env['whatsapp.account'].with_context(active_test=False).search([
            ('phone_uid', '=', phone_number_data['id']),
        ])
        if wa_account:
            wa_account.write(wa_account_values)
        else:
            wa_account = request.env['whatsapp.account'].create(wa_account_values)
        return wa_account

    @http.route('/whatsapp/start_onboarding', type='jsonrpc', auth='user')
    def start_onboarding(self):
        """Start the WhatsApp account onboarding flow.

        Redirect to the proxy, which invokes the Facebook login dialog for the
        user to grant access to their WhatsApp Business Account.

        API Documentation:
        https://developers.facebook.com/documentation/facebook-login/guides/advanced/manual-flow#logindialog
        """
        if not request.env.user.has_group('whatsapp.group_whatsapp_admin'):
            raise AccessError(request.env._("You are not allowed to access this page."))

        params = {
            'csrf_token': request.csrf_token(),
            'db_uuid': request.env['ir.config_parameter'].sudo().get_str('database.uuid'),
            'return_url': url_join(request.httprequest.url_root, self.OAUTH_RETURN_URL),
        }
        authorization_url = f'{get_proxy_endpoint(request.env)}/authorize?{urlencode(params)}'
        return {
            'target': 'self',
            'type': 'ir.actions.act_url',
            'url': authorization_url,
        }
