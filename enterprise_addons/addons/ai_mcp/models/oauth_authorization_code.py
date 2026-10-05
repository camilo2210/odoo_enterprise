from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessDenied
from odoo.addons.ai_mcp.utils.oauth_utils import (
    _generate_hash, _generate_secret, _verify_hash, check_mcp_oauth_user_access,
    OAUTH_SECRET_INDEX_SIZE, verifier_matches_challenge,
)
from odoo.tools import SQL


class OauthAuthorizationCode(models.Model):
    _name = 'oauth.authorization.code'
    _description = 'OAuth 2.1 Authorization Code'

    # The client_id can't be a Many2one because CIMD clients has no oauth.client records.
    client_id = fields.Char(required=True)
    redirect_uri = fields.Char(required=True)
    code_challenge = fields.Char(required=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    expiration_date = fields.Datetime(required=True)
    apikey_expiration_date = fields.Datetime(
        help="Expiration date the user consented to for the API key this code will be redeemed for. "
             "Empty for an API key that never expires.",
    )

    def init(self):
        super().init()
        table = SQL.identifier(self._table)
        self.env.cr.execute(SQL(
            """
            ALTER TABLE %(table)s
              ADD COLUMN IF NOT EXISTS code_hash varchar NOT NULL,
              ADD COLUMN IF NOT EXISTS code_index varchar(%(index_size)s) NOT NULL
            CHECK (char_length(code_index) = %(index_size)s)
            """,
            table=table,
            index_size=OAUTH_SECRET_INDEX_SIZE,
        ))
        self.env.cr.execute(SQL(
            "CREATE INDEX IF NOT EXISTS %s ON %s (code_index)",
            SQL.identifier(self._table + "_code_index_index"),
            table,
        ))

    def _generate(self, client_id, redirect_uri, code_challenge, user, apikey_expiration_date, code_ttl_seconds=120):
        code = _generate_secret()
        self.env.cr.execute(SQL(
            """
            INSERT INTO %(table)s
                (code_hash, code_index, client_id, redirect_uri, code_challenge, user_id, expiration_date, apikey_expiration_date)
            VALUES
                (%(code_hash)s, %(code_index)s, %(client_id)s, %(redirect_uri)s, %(code_challenge)s, %(user_id)s, %(expiration_date)s, %(apikey_expiration_date)s)
            """,
            table=SQL.identifier(self._table),
            code_hash=_generate_hash(code),
            code_index=code[:OAUTH_SECRET_INDEX_SIZE],
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            user_id=user.id,
            expiration_date=fields.Datetime.now() + timedelta(seconds=code_ttl_seconds),
            apikey_expiration_date=apikey_expiration_date,
        ))
        return code

    @api.model
    def _redeem(self, code, client_id, redirect_uri, code_verifier, client_name) -> dict:
        authorization_code = self._retrieve_record(code, client_id, redirect_uri)
        if not authorization_code:
            raise AccessDenied(self.env._("Invalid authorization code"))
        if not verifier_matches_challenge(code_verifier, authorization_code.code_challenge):
            authorization_code.sudo().unlink()
            raise AccessDenied(self.env._("Invalid PKCE code_verifier"))

        user = authorization_code.user_id
        apikey_expiration_date = authorization_code.apikey_expiration_date
        authorization_code.sudo().unlink()
        check_mcp_oauth_user_access(user)

        # This method is called from a controller with auth='public'. However, the api key
        # is generated using the user of the environment. Thus, we need to do with_user(user)
        access_token = self.env['res.users.apikeys'].with_user(user)._generate(
            'mcp', client_name, apikey_expiration_date,
        )

        result = {'access_token': access_token, 'token_type': 'Bearer', 'scope': 'mcp'}
        if apikey_expiration_date:
            result['expires_in'] = int((apikey_expiration_date - fields.Datetime.now()).total_seconds())
        return result

    @api.model
    def _retrieve_record(self, code, client_id, redirect_uri):
        self.env.cr.execute(SQL(
            """
            SELECT id, code_hash
              FROM %(table)s
             WHERE code_index = %(code_index)s
                   AND client_id = %(client_id)s
                   AND redirect_uri = %(redirect_uri)s
                   AND expiration_date > %(now)s
            """,
            table=SQL.identifier(self._table),
            code_index=code[:OAUTH_SECRET_INDEX_SIZE],
            client_id=client_id,
            redirect_uri=redirect_uri,
            now=fields.Datetime.now(),
        ))
        matching_id = next(
            (row_id for row_id, code_hash in self.env.cr.fetchall() if _verify_hash(code, code_hash)),
            None,
        )
        return self.sudo().browse(matching_id)

    @api.autovacuum
    def _gc_expired_codes(self):
        self.sudo().search([('expiration_date', '<', fields.Datetime.now())]).unlink()
