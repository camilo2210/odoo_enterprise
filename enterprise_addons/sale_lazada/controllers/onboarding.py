# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hmac
import logging
from datetime import UTC, datetime, timedelta

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request

from odoo.addons.sale_lazada import utils

_logger = logging.getLogger(__name__)


class LazadaController(http.Controller):
    @http.route(
        '/lazada/return_from_authorization/<model("lazada.shop"):shop>/<int:timestamp>/<string:sign>',
        type="http",
        methods=["GET"],
        auth="user",
    )
    def lazada_return_from_authorization(self, shop, timestamp, sign, code=False):
        """Handle Lazada authorization callback.

        Processes authorization code and retrieves access tokens.

        :param model("lazada.shop"):shop: Shop to authorize
        :param int timestamp: Request timestamp
        :param str sign: Request signature for validation
        :param str code: Authorization code from Lazada
        :return: HTTP redirect response
        :rtype: http.response
        """
        if datetime.fromtimestamp(timestamp, UTC).replace(
            tzinfo=None
        ) < fields.Datetime.now() - timedelta(minutes=30):
            raise AccessError(self.env._("The request is expired."))

        check_sign = utils.get_public_sign(shop, timestamp)
        if not hmac.compare_digest(sign, check_sign):
            raise AccessError(self.env._("The request signature is not valid."))

        state = request.params.get("state", "")
        if not hmac.compare_digest(state, shop.lazada_oauth_state or ""):
            raise AccessError(self.env._("Invalid OAuth state"))
        shop.lazada_oauth_state = False

        try:
            shop_vals = shop._get_shop_vals(code)
            shop.write(shop_vals)
            response = utils.make_lazada_api_request("GetSeller", shop, params={})
            seller_data = response["data"]
            shop.name = self.env._("Lazada Shop - %(name)s", name=seller_data["name"])

            # Craft the URL of the Lazada Shop form view
            shop_url = f"/odoo/action-sale_lazada.action_lazada_shop_list/{shop.id}"
            return request.redirect(shop_url, local=False)

        except utils.LazadaApiError as error:
            # Log the error for debugging
            error_message = str(error) or self.env._(
                "An unexpected error occurred during authorization."
            )
            _logger.exception("Failed to authorize Lazada shop %s: %s", shop.id, error_message)

            return request.redirect(
                f"/odoo/action-sale_lazada.action_lazada_shop_authorization_error/{shop.id}"
            )
