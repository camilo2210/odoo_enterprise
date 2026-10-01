import logging
import secrets
from typing import Any

from odoo import api, models


_logger = logging.getLogger(__name__)


class IotChannel(models.AbstractModel):
    _name = 'iot.channel'
    _description = "The Websocket IoT Channel"

    @api.model
    def get_iot_channel(self):
        """Get the IoT websocket channel name (unique for every company).

        :return: The IoT websocket channel used to send the message
        """
        if not self.env.is_system() and not self.env.user._is_internal():
            return
        ir_config_parameter = self.env['ir.config_parameter'].sudo()
        ws_channel = ir_config_parameter.get_str('iot.ws_channel')
        if not ws_channel:
            ws_channel = f"iot_channel-{secrets.token_hex(16)}"
            ir_config_parameter.set_str('iot.ws_channel', ws_channel)

        return ws_channel

    @api.model
    def send_message(self, message: dict[str, Any], message_type='iot_action'):
        """Send a message to a device via websocket.

        :param message: The message to send to the IoT Box
        :param message_type: The type of the message (Default: call an action on a device)
        """
        if not self.env.is_system() and not self.env.user._is_internal():
            return
        loggable_message = {k: v for k, v in message.items() if k != "document"}
        _logger.info("Sending message to IoT channel: %s", loggable_message)
        self.env['bus.bus']._sendone(self.get_iot_channel(), message_type, message)
