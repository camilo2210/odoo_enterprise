from odoo import models, fields
from odoo.exceptions import UserError


class Printer(models.Model):
    _inherit = "printer.printer"

    type = fields.Selection(selection_add=[("obox", "Obox")], ondelete={"obox": "set default"})
    obox_device_id = fields.Many2one(
        "obox.device",
        string="Obox Printer Device",
        ondelete="cascade",
        domain="[('type', '=', 'printer')]",
    )

    def obox_print(self, document_base64: str):
        if self.type != "obox":
            raise UserError(self.env._("Must be an Obox printer"))
        if self.obox_device_id.type != "printer":
            raise UserError(self.env._("Linked Obox device is not a printer"))
        self.env["obox.queue"].create({
            "action_type": "action",
            "obox_id": self.obox_device_id.obox_id.id,
            "payload": {"url": "/usb/v1/printer/print", "payload": {"identifier": self.obox_device_id.identifier, "document": document_base64}, "method": "POST"},
        })
