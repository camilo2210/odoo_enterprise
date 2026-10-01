from odoo import http


class OboxController(http.Controller):
    @http.route("/obox_point_of_sale/ping", auth="public", type="jsonrpc")
    def obox_ping(self):
        return {
            "message": "Everything is working fine!",
        }
