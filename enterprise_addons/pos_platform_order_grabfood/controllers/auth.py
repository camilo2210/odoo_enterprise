# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import functools
import jwt
import secrets

from odoo import http
from odoo.fields import Domain
from odoo.http import request
from odoo.tools import consteq
from odoo.addons.pos_platform_order import utils


def _generate_jwt_token(provider, expires_in=604800) -> str:
    """
    Generate a JWT token for the GrabFood provider.
    """
    secret_key = provider.grabfood_jwt_secret
    if not secret_key:
        secret_key = secrets.token_hex(16)
        provider.grabfood_jwt_secret = secret_key

    issued_at = datetime.datetime.now(datetime.timezone.utc)
    expiration_time = issued_at + datetime.timedelta(seconds=expires_in)

    payload = {
        "sub": provider.grabfood_partner_client_id,
        "key": provider.grabfood_partner_client_secret,
        "iat": issued_at,
        "exp": expiration_time
    }

    encoded_jwt = jwt.encode(payload, secret_key, algorithm='HS256')
    return encoded_jwt


def require_oauth(func):
    """
    Decorator to require authentication for a controller method.
    It checks if the request has a valid JWT token in the Authorization header.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        access_token = request.httprequest.headers.get('Authorization')
        if not access_token or not access_token.startswith('Bearer '):
            return http.Response(status=401)
        token = access_token[7:]  # Remove 'Bearer ' prefix

        secret_keys = request.env['platform.order.provider'].sudo().search(Domain.AND(
            [Domain('code', '=', 'grabfood'), Domain('grabfood_jwt_secret', '!=', False)])).mapped('grabfood_jwt_secret')
        if not secret_keys:
            return http.Response(status=401)

        secret_key = None
        for key in secret_keys:
            try:
                jwt.decode(token, key, algorithms=['HS256'])
                secret_key = key
            except jwt.ExpiredSignatureError:
                continue
            except jwt.InvalidSignatureError:
                continue
            except jwt.InvalidTokenError:
                continue

        if not secret_key:
            return http.Response(status=401)

        return func(*args, **kwargs)

    return wrapper


class GrabFoodAuthController(http.Controller):
    _oauth_url = '/grabfood/oauth/token'

    @http.route(_oauth_url, type='http', auth='public', methods=['POST'], csrf=False)
    def grabfood_oauth_token(self):
        """
        Endpoint to handle GrabFood OAuth token requests.
        This endpoint is called by GrabFood to retrieve the access token.
        """
        data = request.get_json_data()
        partner_client_id = data.get('client_id')
        partner_client_secret = data.get('client_secret')
        if not partner_client_id or not partner_client_secret:
            return request.make_json_response({
                'error': 'Invalid client credentials'
            }, status=400)

        # Search for the platform order provider
        res_ids = utils._parse_external_ids(request.env, partner_client_id)
        if not res_ids:
            return request.make_json_response({
                'error': 'Invalid client credentials'
            }, status=401)
        provider = request.env['platform.order.provider'].sudo().browse(res_ids)
        if not provider or not consteq(provider.grabfood_partner_client_secret, partner_client_secret):
            return request.make_json_response({
                'error': 'Invalid client credentials'
            }, status=401)

        expires_in = 7 * 24 * 60 * 60  # 7 days in seconds
        return request.make_json_response({
            'access_token': _generate_jwt_token(provider, expires_in),
            'token_type': 'Bearer',
            'expires_in': expires_in,
        }, status=200)
