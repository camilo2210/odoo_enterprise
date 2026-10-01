import json
import logging
from werkzeug.urls import url_encode

from odoo import fields, models

from ..controllers.databases import ACCOUNTS_URL

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    databases_sso_uid = fields.Char(string='Databases OAuth User ID', help="OAuth user_id", copy=False)

    def _get_action_retrieve_oauth(self, db_id):
        # When the user clicks on this action, it simulates a reset password and a sign up through oauth.
        # The password doesn't get reset but the oauth gets set.
        # The user can now connect with both methods.

        # Note: this shouldn't ever happen from the standard flow but we may never know 🤷‍♂️
        assert self == self.env.user, "A user shouldn't be able to trigger the oauth flow for another user"

        partner = self.partner_id
        _logger.info('Retrieve databases_sso_uid for %s', self)
        params = dict(
            response_type='token',
            client_id=self.env['ir.config_parameter'].sudo().get_str('database.uuid'),
            redirect_uri=f'{partner.get_base_url()}/databases/auth',
            scope='userinfo',
            state=json.dumps({
                'r': int(db_id),  # ensure no one pass anything else than an int
                't': partner.sudo()._generate_signup_token(),
            }),
        )
        return {
            'type': 'ir.actions.act_url',
            'url': f"{ACCOUNTS_URL}/oauth2/auth?{url_encode(params)}",
            'target': 'new',
        }
