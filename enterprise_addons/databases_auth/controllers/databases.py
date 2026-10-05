import json
import logging
import requests
import werkzeug.exceptions

from odoo import http, tools
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.http.requestlib import fragment_to_query_string

_logger = logging.getLogger(__name__)

ACCOUNTS_URL = 'https://accounts.odoo.com'


class DatabasesController(http.Controller):

    @http.route('/databases/auth', type='http', auth='user', readonly=False)
    @fragment_to_query_string
    def databases_set_direct_connect(self, **kw):
        user = self.env.user
        if not user.has_group('databases.group_databases_user'):
            _logger.warning("'/databases/auth' access forbidden to %s", user)
            raise werkzeug.exceptions.Forbidden()

        if not kw.get('state'):
            raise werkzeug.exceptions.BadRequest()
        # 1) db token: Was it made by this db and for this user?
        state = json.loads(kw['state'])
        token = state['t']
        payload = tools.verify_hash_signed(self.env(su=True), 'signup', token)
        if not payload:
            raise werkzeug.exceptions.Forbidden()
        _, user_ids, _, _ = payload
        if user != self.env['res.users'].browse(user_ids):
            # This is not the same account: don't link them
            _logger.warning("'/databases/auth' %s attempt to use a token for %s", user, user_ids)
            raise werkzeug.exceptions.Forbidden()

        # 2) access token: does the provider validate it?
        access_token = kw.get('access_token')
        try:
            response = requests.get(f'{ACCOUNTS_URL}/oauth2/tokeninfo', params={'access_token': access_token}, timeout=10)
            response.raise_for_status()
            validation = response.json()
        except requests.RequestException as e:
            _logger.warning("'/databases/auth' request error: %s", e)
            raise ValidationError(self.env._("An error occured during the validation request to the OAuth provider."))
        if validation.get("error"):
            _logger.warning("'/databases/auth' access_token could't be validated for %s, error provided: %s", user, validation['error'])
            raise ValidationError(self.env._("The OAuth provider couldn't verify your identity."))

        # 3) access token: was it generated for us? (avoid Confused Deputy Problem)
        if validation['audience'] != self.env['ir.config_parameter'].sudo().get_str('database.uuid'):
            # That token wasn't made for us
            _logger.warning("'/databases/auth' %s use token with wrong audience: %s", user, validation['audience'])
            raise werkzeug.exceptions.Forbidden()

        # 4) access_token: was it generated for this user?
        if user.email != validation['email']:
            # This is not the same account: don't link them
            _logger.warning("'/databases/auth' %s validation email don't match", user)
            raise werkzeug.exceptions.Forbidden()

        # everything alright: write oauth and continue the flow
        user.databases_sso_uid = validation['user_id']

        db_id = int(state['r'])
        database = self.env['project.project'].browse(db_id).exists()
        if not database or not (user.database_user_ids & database.database_user_ids):
            # This user shouldn't get access to this db: don't let it even see the url
            _logger.warning("'/databases/auth' %s attempt to connect to %s", user, database)
            raise werkzeug.exceptions.Forbidden()

        if database.database_hosting == "saas":
            database._set_oauth_to_remote_db(user)  # allow smooth connection

        return request.redirect(database._get_connect_url(), local=False)
