import logging

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)


class WebsiteGeneratorController(http.Controller):
    @http.route('/website_generator/result_ready/<int:request_id>/<uuid>', type='http', auth='public', methods=["POST"], csrf=False)
    def webhook_result_ready(self, request_id, uuid):
        # This route is called by the website generator server to notify the client that the result is ready
        ws_request = request.env["website_generator.request"].sudo().browse(request_id)
        if not ws_request or not consteq(ws_request.uuid, uuid):
            raise NotFound()

        request.env.ref("website_generator.cron_get_result")._trigger()
