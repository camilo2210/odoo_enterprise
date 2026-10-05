# Part of Odoo. See LICENSE file for full copyright and licensing details.

from typing import Any
from odoo import models


class IrWebsocket(models.AbstractModel):
    _inherit = "ir.websocket"

    def _subscribe(self, data: dict[str, Any]):
        token = data.get("iot_token")
        if token and self.env["iot.box"]._get_by_token(token):
            data["channels"].append(self.env["iot.channel"].get_iot_channel())
            if not data["last"]:
                data["last"] = self.env["bus.bus"].sudo()._bus_last_id()
        return super()._subscribe(data)
