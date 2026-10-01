# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import hmac
import logging
from datetime import datetime

from odoo import _, http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from odoo.tools import hmac as hmac_tool

from odoo.addons.sale_tiktok import utils

_logger = logging.getLogger(__name__)


class TikTokController(http.Controller):
    @http.route("/tiktok/return_from_authorization", type="http", methods=["GET"], auth="user")
    def tiktok_return_from_authorization(self, code=None, state=None, **_kwargs):
        if not request.env.user.has_group("sales_team.group_sale_manager"):
            raise AccessError(_("You are not allowed to access this page."))
        if not state:
            raise ValidationError(_("Missing OAuth state."))
        try:
            payload = json.loads(state)
        except json.JSONDecodeError as exc:
            raise ValidationError(_("Invalid OAuth state.")) from exc
        shop_id = payload.get("shop_id")
        timestamp = payload.get("timestamp")
        signature = payload.get("signature")

        if not timestamp or not signature:
            raise ValidationError(_("Malformed OAuth state."))
        expected = hmac_tool(request.env, "tiktok-authorization-request", f"{shop_id}|{timestamp}")
        if not hmac.compare_digest(signature, expected):
            raise AccessError(_("Invalid authorization signature"))

        shop = (
            request
            .env["tiktok.shop"]
            .browse(shop_id)
            .exists()
            .with_context(allowed_company_ids=request.env.user._get_company_ids())
        )
        if not shop:
            raise request.not_found(_("Shop not found."))
        try:
            # Fetch authorization code
            token = utils.request_access_token(shop, authorization_code=code)
            shop.write({
                "access_token": token["access_token"],
                "access_token_expire_datetime": datetime.fromtimestamp(
                    token["access_token_expire_in"]
                ),
                "refresh_token": token["refresh_token"],
                "refresh_token_expire_datetime": datetime.fromtimestamp(
                    token["refresh_token_expire_in"]
                ),
                "name": token.get("seller_name"),
            })

            # Resolve TikTok shop identity
            if not shop.tiktok_shop_ref:
                response = utils.make_tiktok_api_request(shop, "get_authorized_shop")
                authorized = response.get("shops", [])
                existing = request.env["tiktok.shop"].search([("app_key", "=", shop.app_key)])

                existing_keys = {
                    (s.tiktok_shop_ref, s.tiktok_cipher)
                    for s in existing
                    if s.tiktok_shop_ref and s.tiktok_cipher
                }
                candidates = [
                    s for s in authorized if (s.get("id"), s.get("cipher")) not in existing_keys
                ]

                # If multiple candidates remain, we select the first one.
                # Users must revoke unused authorizations in TikTok to disambiguate.
                chosen = candidates[0]
                country = request.env["res.country"].search(
                    [("code", "=", chosen["region"])], limit=1
                )
                shop.write({
                    "tiktok_shop_ref": chosen["id"],
                    "tiktok_cipher": chosen["cipher"],
                    "name": chosen.get("name") or shop.name,
                    "country_id": country.id if country else False,
                })

            # Craft the URL of the TikTok Shop form view
            return request.redirect(f"/odoo/action-sale_tiktok.action_tiktok_shop_list/{shop.id}")
        except (utils.TikTokApiError, IndexError) as error:
            error_message = str(error) or _("An unexpected error occurred during authorization.")
            _logger.exception("Failed to authorize TikTok shop %s: %s", shop.id, error_message)
            return request.redirect(
                f"/odoo/action-sale_tiktok.action_tiktok_shop_authorization_error/{shop.id}"
            )
