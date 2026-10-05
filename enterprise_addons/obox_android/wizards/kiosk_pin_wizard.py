from odoo import _, fields, models
from odoo.exceptions import ValidationError

PIN_MIN_LENGTH = 4


class OboxKioskPinWizard(models.TransientModel):
    _name = "obox.kiosk.pin.wizard"
    _description = "Obox Kiosk PIN"

    obox_id = fields.Many2one("obox.obox", required=True, readonly=True)
    kiosk_pin = fields.Char(string="Kiosk PIN", required=True)
    kiosk_pin_confirm = fields.Char(string="Confirm PIN", required=True)

    def action_confirm(self):
        self.ensure_one()
        pin = (self.kiosk_pin or "").strip()

        if pin != (self.kiosk_pin_confirm or "").strip():
            raise ValidationError(_("The two PIN codes do not match."))
        if not pin.isdigit():
            raise ValidationError(_("The PIN must contain digits only."))
        if len(pin) < PIN_MIN_LENGTH:
            raise ValidationError(_("The PIN must be at least %(min)s digits long.", min=PIN_MIN_LENGTH))

        self.obox_id.kiosk_pin = pin
        return {"type": "ir.actions.act_window_close"}
