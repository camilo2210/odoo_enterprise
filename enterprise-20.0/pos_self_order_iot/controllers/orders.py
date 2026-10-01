from odoo import http
from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController
from werkzeug.exceptions import Unauthorized


class PosSelfOrderControllerIot(PosSelfOrderController):
    @http.route("/pos-self-order/get-iot-box-data/", auth="public", type="jsonrpc", website=True)
    def get_iot_box_data(self, access_token, iot_box_id):
        pos_config = self._verify_pos_config(access_token)
        iot_data = pos_config.env["iot.box"].sudo().browse(iot_box_id)
        if not iot_data:
            return {"error": "Self Order: No IoT Box found"}
        return iot_data.read(["ip", "identifier"])

    @http.route("/pos-self-order/iot-box-websocket-channel/", auth="public", type="jsonrpc")
    def iot_box_websocket_channel(self, access_token, message=None, message_type="iot_action"):
        try:
            pos_config = self._verify_pos_config(access_token)
        except Unauthorized:
            # If pos is closed, we don't want a traceback, and we don't care
            # about sending messages to the iot box: we return an empty ws channel
            return ""
        iot_channel = pos_config.env['iot.channel']
        if message:
            iot_channel.send_message(message, message_type)

        return iot_channel.get_iot_channel()
