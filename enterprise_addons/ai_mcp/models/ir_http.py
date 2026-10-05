from werkzeug.datastructures import WWWAuthenticate
from werkzeug.exceptions import Unauthorized

from odoo import models
from odoo.http import request

from odoo.addons.ai_mcp.utils.oauth_utils import protected_resource_metadata_url


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _auth_method_bearer(cls, routing):
        try:
            super()._auth_method_bearer(routing)
        except Unauthorized as error:
            if not routing.get("bearer_scope") == "mcp":
                raise

            params = {"resource_metadata": protected_resource_metadata_url(request.env)}
            if request.httprequest.headers.get("Authorization", "").lower().startswith("bearer "):
                params["error"] = "invalid_token"

            raise Unauthorized(www_authenticate=WWWAuthenticate('Bearer', params)) from error
