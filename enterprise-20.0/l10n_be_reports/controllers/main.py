import hashlib
import json
import re
import requests
import uuid

from urllib.parse import urlencode

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.http import request

TOKEN_ENDPOINT = {
    'test': "https://fediamapi-a.minfin.be/sso/oauth2/access_token",
    'prod': "https://fediamapi.minfin.fgov.be/sso/oauth2/access_token",
    'disabled': "",
}
AUTH_ENDPOINT = {
    'test': "https://fediamapi-a.minfin.be/sso/oauth2/authorize",
    'prod': "https://fediamapi.minfin.fgov.be/sso/oauth2/authorize",
    'disabled': "",
}
IAP_ENDPOINT = {
    'test': "https://l10n-be-intervat.test.odoo.com/api/l10n_be_intervat/1",
    'prod': "https://l10n-be-intervat.api.odoo.com/api/l10n_be_intervat/1",
    'disabled': "",
}


class L10nBeIntervatController(http.Controller):
    @http.route('/l10n_be_intervat/callback', type='http', auth='user')
    def callback(self, **kwargs):
        if not request.env.user.has_group("account.group_account_user"):
            return request.not_found()

        state = json.loads(kwargs.get('state', '{}'))
        company_id = request.env['res.company'].browse(state.get('company_id'))
        return_id = request.env['account.return'].browse(state.get('return_id'))
        if not company_id or not return_id:
            return http.Response(status=404)

        if kwargs.get('error') or not kwargs.get('code'):
            if kwargs.get('error') == 'invalid_scope':
                if company_id.account_representative_id:
                    # This is the case when an accounting firm client tries to submit a declaration on his own. It shouldn't happend,
                    # as it's the firm's role to do that.
                    message = request.env._("""
                        Access error: Only the accounting firm can submit the VAT return to Intervat via the API.
                        To submit it yourself, download the XML file and upload it on Intervat.
                        If you no longer have an accounting firm, remove it from the Intervat setting to enable API submission.
                    """)
                else:
                    # This is the case when an accounting firm tries to submit a client declaration but without any account_representative_id
                    # set in the client company.
                    message = request.env._("""
                        Access error: You do not have permission to give consent for company %s. If you are an accounting firm,
                        make sure the Accounting firm field is set in the Intervat settings. Otherwise, only the client can submit the VAT return through API.
                    """, company_id.vat)
                return_id._message_log(body=message)

                notification_error_message = request.env._("""
                    SPF Finances authorization denied.
                    Initial consent requires an official mandate.
                    Please ask a user with the appropriate rights to perform the first connection for this client.
                    Access will then be unlocked.
                """)
            else:
                notification_error_message = f"{kwargs['error']}: {kwargs['error_description']}"

            request.env.user._bus_send('simple_notification', {
                'type': 'danger',
                'title': request.env._("Authentication Failed"),
                'message': notification_error_message,
                'sticky': True,
            })
        else:
            response = requests.post(
                url=TOKEN_ENDPOINT[company_id.l10n_be_intervat_mode],
                data={
                    'grant_type': 'authorization_code',
                    'redirect_uri': f"{IAP_ENDPOINT[company_id.l10n_be_intervat_mode]}/callback",
                    'code': kwargs.get('code'),
                    'code_verifier': company_id.l10n_be_intervat_code_verifier,
                    'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                    'client_assertion': company_id._l10n_be_generate_jwt(),
                    'client_id': 'odoo',
                },
                headers={
                    'accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            )
            response_json, error = company_id._l10n_be_get_error_from_response(response)
            if error:
                return_id.sudo().write({'l10n_be_submission_error': error['error_message']})
                return_id._message_log(body=self.env._("Authentication Error: \n") + error['error_message'])
                request.env.user._bus_send('simple_notification', {
                    'type': 'danger',
                    'title': request.env._("Authentication Failed"),
                    'message': error['error_message'],
                    'sticky': True,
                })
                return request.redirect(state.get('referrer_url', '/web'))

            company_id._l10n_be_verify_id_token_signature(response_json['id_token'])

            company_id.sudo().write({
                'l10n_be_intervat_access_token': response_json['access_token'],
                'l10n_be_intervat_refresh_token': response_json['refresh_token'],
                'l10n_be_intervat_last_call_date': fields.Datetime.now(),
            })

            request_type = state.get('request_type')
            try:
                if request_type == 'submit':
                    return_id._l10n_be_submit_xml()
                elif request_type == 'fetch':
                    return_id.l10n_be_action_fetch_from_intervat()
            except UserError as e:
                error_title = request.env._("Fetching Error: \n") if request_type == 'fetch' else request.env._("Submission Error: \n")
                error_message = error_title + "\n".join(e.args)
                return_id.sudo.write({'l10n_be_submission_error': "\n".join(e.args)})
                return_id._message_log(body=error_message)
                request.env.user._bus_send('simple_notification', {
                    'type': 'danger',
                    'title': error_title,
                    'message': error_message,
                    'sticky': True,
                })
                return request.redirect(state.get('referrer_url', '/web'))

        return request.redirect(state.get('referrer_url', '/web'))

    @http.route('/l10n_be_intervat/authorize/<int:company_id>/<int:return_id>/<string:request_type>', auth='user')
    def authorize(self, company_id, return_id, request_type):
        company = http.request.env['res.company'].browse(company_id)

        state = {
            'company_id': company.id,
            'return_id': return_id,
            'request_type': request_type,
            'referrer_url': request.httprequest.referrer,
            'company_token': hashlib.sha256(company.l10n_be_intervat_certificate_id.sudo().l10n_be_intervat_jwk_token.encode()).hexdigest(),
            'db_uuid': self.env['ir.config_parameter'].sudo().get_str('database.uuid'),
        }

        ecb_number = re.sub(r'[^0-9]', '', company.account_representative_id.vat or company.vat)
        auth_url_params = urlencode({
            'response_type': 'code',
            'client_id': 'odoo',
            'redirect_uri': f"{IAP_ENDPOINT[company.l10n_be_intervat_mode]}/callback",
            'code_challenge_method': 'S256',
            'code_challenge': company.l10n_be_intervat_code_challenge,
            'scope': 'openid profile documents-read-api vat-manage-api',
            'claims': json.dumps({"ecb": ecb_number}).encode(),
            'nonce': f'{uuid.uuid4()}',
            'state': json.dumps(state).encode(),
        })
        auth_url = f'{AUTH_ENDPOINT[company.l10n_be_intervat_mode]}?{auth_url_params}'
        return request.redirect(auth_url, code=302, local=False)
