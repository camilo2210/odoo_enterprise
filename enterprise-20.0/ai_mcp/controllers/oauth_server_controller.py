import datetime
from werkzeug.exceptions import BadRequest, default_exceptions

from odoo import fields, http
from odoo.http import request
from odoo.exceptions import AccessDenied, ValidationError

from odoo.addons.ai_mcp.utils.oauth_utils import (
    check_mcp_oauth_user_access,
    fetch_client_metadata_document,
    is_redirect_uri_registered,
    normalize_localhost_to_ip,
    oauth_base_url,
    merge_params_in_redirect_url,
)


class OauthServerController(http.Controller):

    # ------------------------------------------------------
    # Protected resource metadata
    # ------------------------------------------------------

    @http.route('/.well-known/oauth-protected-resource/mcp', type='http', auth='public', methods=['GET'])
    def protected_resource_metadata(self):
        base_url = oauth_base_url(self.env)
        return request.make_json_response({
            'resource': f'{base_url}/mcp',
            'authorization_servers': [f'{base_url}/oauth/mcp'],
        })

    # ------------------------------------------------------
    # Authorization server metadata
    # ------------------------------------------------------

    @http.route('/.well-known/oauth-authorization-server/oauth/mcp', type='http', auth='public', methods=['GET'])
    def authorization_server_metadata(self):
        base_url = oauth_base_url(self.env)
        metadata = {
            'issuer': f'{base_url}/oauth/mcp',
            'authorization_endpoint': f'{base_url}/oauth/authorize',
            'token_endpoint': f'{base_url}/oauth/token',
            'revocation_endpoint': f'{base_url}/oauth/revoke',
            'response_types_supported': ['code'],
            'grant_types_supported': ['authorization_code'],
            'code_challenge_methods_supported': ['S256'],
            'token_endpoint_auth_methods_supported': ['none'],
            'scopes_supported': ['mcp'],
            'client_id_metadata_document_supported': True,
            'authorization_response_iss_parameter_supported': True,  # Forces ChatGPT to use a stable CIMD URL. Without this, the CIMD URL passed by ChatGPT changes each time it goes through the OAuth flow which prevents whitelisting.
        }

        if self.env['ir.config_parameter'].sudo().get_bool('enable_dcr'):
            metadata['registration_endpoint'] = f'{base_url}/oauth/register/mcp'
        return request.make_json_response(metadata)

    # ------------------------------------------------------
    # Client Registration
    # ------------------------------------------------------

    @http.route('/oauth/register/mcp', type='http', auth='public', methods=['POST'], csrf=False)
    def register(self):
        if not self.env['ir.config_parameter'].sudo().get_bool('enable_dcr'):
            self._raise_oauth_error(
                'access_denied',
                "Dynamic client registration is disabled on this server.",
                status=403,
            )

        payload = request.get_json_data()
        redirect_uris = payload.get('redirect_uris')
        client_name = payload.get('client_name') or 'Unnamed OAuth client'
        auth_method = payload.get('token_endpoint_auth_method', 'none')
        if auth_method != 'none':
            self._raise_oauth_error('invalid_client_metadata', f"Unsupported token_endpoint_auth_method {auth_method}")

        try:
            client = request.env['oauth.client'].sudo().create({
                'client_name': client_name,
                'redirect_uris': '\n'.join(redirect_uris or []),
            })
        except ValidationError:
            self._raise_oauth_error('invalid_client_metadata')

        return request.make_json_response({
            'client_id': client.client_id,
            'client_name': client_name,
            'redirect_uris': redirect_uris,
            'token_endpoint_auth_method': auth_method,
            'grant_types': ['authorization_code'],
            'response_types': ['code'],
        }, status=201)

    # ------------------------------------------------------
    # Authorization Code Generation
    # ------------------------------------------------------

    @http.route('/oauth/authorize', type='http', auth='user', methods=['GET'])
    def authorize(self, **params):
        client_data = self._retrieve_client_data(params.get('client_id'))
        params['redirect_uri'] = normalize_localhost_to_ip(params.get('redirect_uri'))
        self._validate_authorize_request(client_data, params)
        try:
            check_mcp_oauth_user_access(self.env.user)
            response = request.render('ai_mcp.consent', {
                'client_name': client_data.get('client_name') or 'Unknown Client',
                'params': {
                    'client_id': params['client_id'],
                    'redirect_uri': params['redirect_uri'],
                    'response_type': params['response_type'],
                    'code_challenge': params['code_challenge'],
                    'code_challenge_method': params['code_challenge_method'],
                    'state': params.get('state', ''),
                },
                'durations': request.env['res.users.apikeys.description']._selection_duration(),
                'default_duration': request.env['res.users.apikeys.description']._default_duration(),
                'today': fields.Date.today(),
            })
            # Anti-clickjacking: the login screen and consent screen must never be
            # embeddable in an iframe by a third-party page - only opened as a normal top-level navigation or new tab.
            response.headers.update({
                'X-Frame-Options': 'DENY',
                'Content-Security-Policy': "frame-ancestors 'none'",
            })
            return response
        except AccessDenied as e:
            self._raise_oauth_error("authorization_failed", description=str(e))

    def _validate_authorize_request(self, client_data, params: dict) -> None:
        if not is_redirect_uri_registered(params.get('redirect_uri'), client_data['redirect_uris']):
            self._raise_oauth_error("authorization_failed", description="redirect_uri is not registered for this client")
        if params.get('response_type') != 'code':
            self._raise_oauth_error("authorization_failed", description="Only response_type=code is supported")
        if params.get('code_challenge_method') != 'S256' or not params.get('code_challenge'):
            self._raise_oauth_error("authorization_failed", description="PKCE with S256 is required (OAuth 2.1)")

    @http.route('/oauth/authorize/submit_consent', type='http', auth='user', methods=['POST'])
    def submit_consent(self, **params):
        client_data = self._retrieve_client_data(params.get('client_id'))
        params['redirect_uri'] = normalize_localhost_to_ip(params.get('redirect_uri'))
        self._validate_authorize_request(client_data, params)
        try:
            check_mcp_oauth_user_access(self.env.user)
        except AccessDenied as e:
            self._raise_oauth_error("authorization_failed", description=str(e))

        if params.get('allow') != 'true':
            redirect_url = merge_params_in_redirect_url(
                params['redirect_uri'],
                {'error': 'access_denied', 'state': params.get('state', '')},
            )
            return request.redirect(redirect_url, local=False)

        duration = int(params['duration'])
        expiration_date = (
            fields.Datetime.to_datetime(fields.Date.today() + datetime.timedelta(days=duration))
            if duration
            else None
        )

        try:
            request.env['res.users.apikeys']._check_expiration_date(expiration_date)
        except ValidationError as e:
            self._raise_oauth_error("authorization_failed", description=str(e))

        code = request.env['oauth.authorization.code']._generate(
            client_id=client_data['client_id'],
            redirect_uri=params['redirect_uri'],
            code_challenge=params['code_challenge'],
            user=request.env.user,
            apikey_expiration_date=expiration_date,
        )
        redirect_url = merge_params_in_redirect_url(
            params['redirect_uri'],
            {'code': code, 'state': params.get('state', ''), 'iss': f'{oauth_base_url(self.env)}/oauth/mcp'},
        )
        return request.redirect(redirect_url, local=False)

    # ------------------------------------------------------
    # Exchanging an Authorization Code for an Access Token
    # ------------------------------------------------------

    @http.route('/oauth/token', type='http', auth='public', methods=['POST'], csrf=False)
    def token(self, **params):
        client_data = self._retrieve_client_data(params.get('client_id'))

        if params.get('grant_type') != 'authorization_code':
            self._raise_oauth_error('unsupported_grant_type')

        params['redirect_uri'] = normalize_localhost_to_ip(params.get('redirect_uri'))
        try:
            result = request.env['oauth.authorization.code']._redeem(
                code=params.get('code'),
                client_id=client_data['client_id'],
                redirect_uri=params.get('redirect_uri'),
                code_verifier=params.get('code_verifier'),
                client_name=client_data['client_name'],
            )
        except (AccessDenied, ValidationError) as e:
            self._raise_oauth_error('invalid_grant', description=str(e))

        return request.make_json_response(
            result,
            headers={'Cache-Control': 'no-store'},  # The API Key should never be stored by the browser cache, CDN, intermediate proxies.
        )

    # ------------------------------------------------------
    # Revoke Access Tokens
    # ------------------------------------------------------

    @http.route('/oauth/revoke', type='http', auth='public', methods=['POST'], csrf=False)
    def revoke(self, **params):
        response = request.make_json_response({})
        try:
            # sudo => A user can only revoke their own keys. So, we use sudo() to let anyone revoke a leaked api key.
            request.env['res.users.apikeys'].sudo().revoke(params.get('token'))
        except AccessDenied:
            # If the access token doesn't exist, don't raise as per the RFC.
            return response
        return response

    # ------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------

    def _retrieve_client_data(self, client_id: str | None):
        if client_id and client_id.startswith('https://'):
            try:
                return fetch_client_metadata_document(self.env, client_id)
            except ValidationError as e:
                self._raise_oauth_error("invalid_client", description=str(e), status=401)

        client_record = request.env['oauth.client'].sudo().search([('client_id', '=', client_id)], limit=1)
        if not client_record or not client_record.active:
            self._raise_oauth_error('invalid_client', "Invalid client credentials", status=401)

        client_data = {
            'client_name': client_record.client_name,
            'client_id': client_record.client_id,
            'redirect_uris': [uri.strip() for uri in client_record.redirect_uris.splitlines() if uri.strip()],
        }
        return client_data

    def _raise_oauth_error(self, error: str, description: str | None = None, status: int = 400) -> None:
        body = {'error': error}
        if description:
            body['error_description'] = description
        exception_cls = default_exceptions.get(status, BadRequest)
        raise exception_cls(response=request.make_json_response(body, status=status))
