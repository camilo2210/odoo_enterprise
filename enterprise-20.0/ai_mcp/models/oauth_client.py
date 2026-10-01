import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.ai_mcp.utils.oauth_utils import normalize_localhost_to_ip, validate_redirect_uris


class OauthClient(models.Model):
    _name = 'oauth.client'
    _description = 'OAuth Client Application'
    _rec_name = 'client_name'

    client_name = fields.Char(required=True)
    client_id = fields.Char(
        string="Client ID", required=True, copy=False, readonly=True,
        default=lambda self: uuid.uuid4().hex,
    )
    redirect_uris = fields.Text(
        required=True,
        help="One redirect URI per line. Must be HTTPS, except for http:// loopback URIs.",
    )
    active = fields.Boolean(
        default=True,
        help="Archiving a client makes the authorization server block any new authorization or token request made with its client_id.",
    )

    _client_id_unique = models.Constraint(
        'UNIQUE (client_id)',
        "Another client is already registered with this client ID.",
    )
    _redirect_uris_not_empty = models.Constraint(
        "CHECK (redirect_uris <> '')",
        "At least one redirect URI is required.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['redirect_uris'] = self._normalize_and_validate_redirect_uris(vals.get('redirect_uris'))
        return super().create(vals_list)

    def write(self, vals):
        if 'client_id' in vals:
            raise UserError(self.env._("The client ID is generated once at registration and can never be changed."))
        if 'redirect_uris' in vals:
            vals['redirect_uris'] = self._normalize_and_validate_redirect_uris(vals['redirect_uris'])
        return super().write(vals)

    def _normalize_and_validate_redirect_uris(self, redirect_uris: str | None) -> str:
        redirect_uris_list = [
            normalize_localhost_to_ip(uri.strip())
            for uri in (redirect_uris or '').splitlines() if uri.strip()
        ]
        validate_redirect_uris(self.env, redirect_uris_list)
        return '\n'.join(redirect_uris_list)
