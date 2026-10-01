from odoo import api, fields, models


class OboxDevice(models.Model):
    _name = "obox.device"
    _description = "Obox Device"

    name = fields.Char(required=True)
    identifier = fields.Char(required=True, readonly=True)
    obox_id = fields.Many2one("obox.obox", readonly=True, required=True, ondelete="cascade")
    local_ip = fields.Char(related="obox_id.local_ip")
    type = fields.Selection([
            ("printer", "Printer"),
            ("camera", "Camera"),
            ("scale", "Scale"),
        ],
        required=True,
        readonly=True,
    )
    connection_type = fields.Selection([
            ("usb", "USB"),
            ("network", "Network"),
        ],
        compute="_compute_connection_type",
        store=True,
    )

    _unique_identifier = models.Constraint(
        "unique (obox_id, identifier)",
        "Every device connected to an Obox must have a unique identifier.",
    )

    @api.model
    def create(self, vals_list):
        """Override to create a `printer.printer` record when an Obox device
        of type printer is created."""
        records = super().create(vals_list)
        printer = self.env["printer.printer"]
        for record in records:
            if (
                record.type == "printer"
                and not printer.search([("obox_device_id", "=", record.id)], limit=1)
            ):
                printer.create([{
                    "name": record.name,
                    "obox_device_id": record.id,
                    "type": "obox",
                }])

        return records

    @api.depends("identifier")
    def _compute_connection_type(self):
        for device in self:
            device.connection_type = "usb" if device.identifier and device.identifier.startswith("usb") else "network"
