from odoo import api, fields, models


class IotDevice(models.Model):
    _name = 'iot.device'
    _description = 'IOT Device'

    iot_id = fields.Many2one('iot.box', string='IoT Box', required=True, index=True, ondelete='cascade')
    name = fields.Char('Name')
    identifier = fields.Char(string='Identifier', readonly=True)
    type = fields.Selection([
            ('printer', 'Printer'),
            ('camera', 'Camera'),
            ('keyboard', 'Keyboard'),
            ('scanner', 'Barcode Scanner'),
            ('device', 'Device'),
            ('payment', 'Payment Terminal'),
            ('scale', 'Scale'),
            ('display', 'Display'),
            ('fiscal_data_module', 'Fiscal Data Module'),
            ('unsupported', 'Unsupported'),
        ],
        readonly=True,
        default='device',
        string='Type',
        help="Type of device.",
    )
    connection = fields.Selection([
            ('network', 'Network'),
            ('direct', 'USB'),
            ('bluetooth', 'Bluetooth'),
            ('serial', 'Serial'),
            ('hdmi', 'HDMI'),
        ],
        readonly=True,
        string="Connection",
        help="Type of connection.",
    )
    printer_id = fields.Many2one("printer.printer", "Related Printer", compute="_compute_printer_id", store=True)
    iot_ip = fields.Char(related="iot_id.ip")
    company_id = fields.Many2one('res.company', 'Company', related="iot_id.company_id")
    connected_status = fields.Selection([
            ('disconnected', 'Disconnected'),
            ('connected', 'Connected'),
        ],
        default='disconnected',
        readonly=True
    )
    keyboard_layout = fields.Many2one('iot.keyboard.layout', string='Keyboard Layout')
    display_url = fields.Char(
        "Display URL",
        help=(
            "URL of the page that will be displayed by the device, "
            "leave empty to use the customer facing display of the POS."
        ),
        default="http://localhost:8069/status",
    )
    is_scanner = fields.Boolean(
        string="Is Scanner",
        compute="_compute_is_scanner",
        inverse="_set_scanner",
        help="Manually switch the device type between keyboard and scanner"
    )
    display_orientation = fields.Selection(
        selection=[
            ('normal', 'Normal'),
            ('right', 'Right'),
            ('left', 'Left'),
            ('inverted', 'Inverted'),
        ],
        string='Display Orientation',
        help='Select the orientation of the display for the Kiosk mode',
        default='normal',
    )

    @api.depends("name", "iot_id", "connection")
    @api.depends_context("formatted_display_name")
    def _compute_display_name(self):
        connection_display_values = dict(self._fields['connection']._description_selection(self.env))
        for device in self:
            if device.env.context.get("formatted_display_name"):
                connection = connection_display_values.get(device.connection, device.connection) if device.connection else ''
                device.display_name = f"{device.name} \t --{connection}-- \t --{device.iot_id.name}--"
            else:
                device.display_name = f"{device.name}"

    @api.depends('type')
    def _compute_is_scanner(self):
        for device in self:
            device.is_scanner = device.type == 'scanner'

    def _set_scanner(self):
        for device in self:
            device.type = 'scanner' if device.is_scanner else 'keyboard'

    @api.model
    def create(self, vals_list):
        """Override to create a `printer.printer` record when an IoT device
        of type printer is created."""
        records = super().create(vals_list)
        printer = self.env["printer.printer"]
        for record in records:
            if (
                record.type == "printer"
                and not printer.search([("iot_device_id", "=", record.id)], limit=1)
            ):
                printer.create([{
                    "name": record.name,
                    "iot_device_id": record.id,
                    "type": "iot",
                }])

        return records

    @api.depends("type")
    def _compute_printer_id(self):
        printer = self.env["printer.printer"]
        for device in self:
            device.printer_id = printer.search([("iot_device_id", "=", device.id)], limit=1)


class IotKeyboardLayout(models.Model):
    _name = 'iot.keyboard.layout'
    _description = 'Keyboard Layout'

    name = fields.Char('Name')
    layout = fields.Char('Layout')
    variant = fields.Char('Variant')
