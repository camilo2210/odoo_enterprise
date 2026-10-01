from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    iot_box_id = fields.Many2one(
        "iot.box",
        string="IoT Box",
        help="The IoT Box that your Six terminal is connected to.",
        default=lambda self: self._get_existing_iot_box_id()
    )
    iot_box_ip = fields.Char(related="iot_box_id.ip")
    six_terminal_id = fields.Char(related="iot_box_id.six_terminal_id", readonly=False)

    def _get_existing_iot_box_id(self):
        return self.iot_device_id.iot_id

    @api.onchange("iot_box_id")
    def _on_change_iot_box_id(self):
        if self.iot_device_id and self.iot_device_id.iot_id != self.iot_box_id:
            self.iot_device_id = None

    def _get_terminal_provider_selection(self):
        return super()._get_terminal_provider_selection() + [('six_iot', 'SIX')]
