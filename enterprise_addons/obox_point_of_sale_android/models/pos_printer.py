from odoo import api, models


class PosPrinter(models.Model):
    _inherit = "pos.printer"

    @api.onchange("obox_device_id")
    def _onchange_obox_device_id(self):
        super()._onchange_obox_device_id()
        for record in self:
            if record.obox_device_id:
                record.printer_ip = f"{record.obox_device_id.obox_id.local_address}/usb/v1/printer/{record.obox_device_id.identifier}"
