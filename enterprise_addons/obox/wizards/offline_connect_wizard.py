import secrets

from odoo import fields, models


class OboxOfflineConnectWizard(models.TransientModel):
    _name = "obox.offline.connect.wizard"
    _description = "Connect Obox Offline"

    ip_address = fields.Char(string="IP Address", required=True)
    token = fields.Char(default=lambda self: secrets.token_hex(), readonly=True)
    serial_number = fields.Char(string="Obox Serial Number", required=True)

    def action_connect(self):
        self.ensure_one()
        result = self.env["obox.obox"].connect_offline(self.ip_address, self.serial_number)
        return {
            "type": "ir.actions.client",
            "tag": "obox_offline_connected",
            "params": result,
        }
