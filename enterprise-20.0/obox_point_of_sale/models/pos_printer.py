from odoo import api, models, fields


class PosPrinter(models.Model):
    _inherit = "pos.printer"

    obox_device_id = fields.Many2one("obox.device", domain=[("type", "=", "printer")])
    printer_type = fields.Selection(
        selection_add=[("obox", "Obox")],
        ondelete={"obox": "set default"}
    )
    proxy_obox_id = fields.Many2one(
        'obox.obox',
        string="Proxy device",
        help="""
        In the Self Ordering context, customer are not on the same
        network as the printer, so we need to use an Obox device as a
        proxy to send print jobs to the printer.""",
    )

    @api.onchange("printer_type")
    def _onchange_printer_type(self):
        for record in self:
            if record.printer_type == "obox":
                record.use_lna = True

    @api.onchange("obox_device_id")
    def _onchange_obox_device_id(self):
        for record in self:
            if not record.obox_device_id:
                record.printer_ip = ""
            else:
                record.printer_ip = f"{record.obox_device_id.obox_id.local_ip}/usb/v1/printer/{record.obox_device_id.identifier}"

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        return fields + ['proxy_obox_id']
