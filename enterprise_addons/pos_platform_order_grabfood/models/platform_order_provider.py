# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import secrets

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.urls import urljoin

from odoo.addons.pos_platform_order import utils
from odoo.addons.pos_platform_order_grabfood.controllers.main import GrabFoodController
from odoo.addons.pos_platform_order_grabfood.controllers.auth import GrabFoodAuthController
from odoo.addons.pos_platform_order_grabfood.utils.grabfood_request import GrabFoodClient


class PlatformOrderProvider(models.Model):
    _inherit = 'platform.order.provider'

    code = fields.Selection(
        selection_add=[('grabfood', "GrabFood")], ondelete={'grabfood': 'set default'}
    )

    # --- GrabFood Credentials ---
    grabfood_client_id = fields.Char(
        string="GrabFood Client ID",
        help="GrabFood Client ID for the account.",
        required_if_provider='grabfood',
        copy=False,
    )
    grabfood_client_secret = fields.Char(
        string="GrabFood Client Secret",
        help="GrabFood Client Secret for the account.",
        required_if_provider='grabfood',
        copy=False,
    )

    # --- Odoo Partner Credentials (for GrabFood to call Odoo) ---
    grabfood_partner_client_id = fields.Char(
        string="GrabFood Partner Client ID",
        help="GrabFood Partner Client ID for the account.",
        readonly=True, copy=False,
    )
    grabfood_partner_client_secret = fields.Char(
        string="GrabFood Partner Client Secret",
        help="GrabFood Partner Client Secret for the account.",
        readonly=True, copy=False,
    )

    # --- Technical OAuth Fields ---
    grabfood_access_token = fields.Char(
        string="GrabFood Access Token",
        help="Technical field to store the GrabFood access token.",
        copy=False, readonly=True,
    )
    grabfood_token_expiry = fields.Datetime(
        string="GrabFood Token Expiry",
        help="Technical field to store the GrabFood token expiry date.",
        copy=False, readonly=True,
    )
    grabfood_jwt_secret = fields.Char(
        string="GrabFood JWT Secret",
        help="Technical field to store the JWT secret for GrabFood authentication.",
        copy=False, readonly=True,
    )

    # --- Technical Webhook Endpoint Fields ---
    grabfood_get_menu_endpoint = fields.Char("GrabFood Get Menu Endpoint", compute='_compute_grabfood_endpoints')
    grabfood_submit_order_endpoint = fields.Char("GrabFood Submit Order Endpoint", compute='_compute_grabfood_endpoints')
    grabfood_push_order_state_endpoint = fields.Char("GrabFood Push Order State Endpoint", compute='_compute_grabfood_endpoints')
    grabfood_oauth_token_endpoint = fields.Char("GrabFood Oauth Token Endpoint", compute='_compute_grabfood_endpoints')
    grabfood_menu_sync_endpoint = fields.Char("GrabFood Menu Sync Endpoint", compute='_compute_grabfood_endpoints')
    grabfood_push_menu_endpoint = fields.Char("GrabFood Push Menu Endpoint", compute='_compute_grabfood_endpoints')
    grabfood_integration_status_endpoint = fields.Char("GrabFood Integration Status Endpoint", compute='_compute_grabfood_endpoints')

    def _compute_grabfood_endpoints(self):
        base_url = self.env.company.get_base_url()
        grabfood_endpoints_val = {
            'grabfood_get_menu_endpoint': urljoin(base_url, GrabFoodController._menu_webhook_url),
            'grabfood_submit_order_endpoint': urljoin(base_url, GrabFoodController._order_webhook_url),
            'grabfood_push_order_state_endpoint': urljoin(base_url, GrabFoodController._order_state_webhook_url),
            'grabfood_oauth_token_endpoint': urljoin(base_url, GrabFoodAuthController._oauth_url),
            'grabfood_menu_sync_endpoint': urljoin(base_url, GrabFoodController._menu_sync_webhook_url),
            'grabfood_push_menu_endpoint': urljoin(base_url, "/grabfood/menus"),
            'grabfood_integration_status_endpoint': urljoin(base_url, "/grabfood/status"),
        }
        for provider in self:
            if provider.code != 'grabfood':
                for field in grabfood_endpoints_val:
                    provider[field] = False
                continue
            provider.update(grabfood_endpoints_val)

    def _grabfood_handle_oauth_response(self, response_json):
        self.ensure_one()
        access_token = response_json.get('access_token')
        expires_in = response_json.get('expires_in')

        if access_token and expires_in:
            self.write({
                'grabfood_access_token': access_token,
                'grabfood_token_expiry': fields.Datetime.now() + datetime.timedelta(seconds=expires_in),
            })

    def action_grabfood_test_connection(self):
        self.ensure_one()
        if not self.grabfood_client_id or not self.grabfood_client_secret:
            raise UserError(self.env._("Please provide both GrabFood Client ID and Client Secret before testing the connection."))

        result = GrabFoodClient.test_connection(self)

        if result.get('success'):
            title = self.env._('Connection Successful')
            message = self.env._('Successfully connected to GrabFood API.')
            notification_type = 'success'
        else:
            title = self.env._('Connection Failed')
            message = result.get('message', self.env._('Unknown error occurred.'))
            notification_type = 'danger'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': False,
            },
        }

    def action_grabfood_generate_access_token(self):
        for provider in self:
            provider.write({
                'grabfood_partner_client_id': utils._get_external_id(provider),
                'grabfood_partner_client_secret': secrets.token_hex(16),
            })
        return True
