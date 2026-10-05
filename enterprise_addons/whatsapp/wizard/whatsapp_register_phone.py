from odoo import fields, models
from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi
from odoo.addons.whatsapp.tools.whatsapp_exception import WhatsAppError
from odoo.exceptions import UserError


class WhatsappRegisterPhone(models.TransientModel):
    _name = 'whatsapp.register.phone'
    _description = 'WhatsApp Registration Phone Number Wizard'

    wa_account_id = fields.Many2one('whatsapp.account', required=True, ondelete='cascade')
    pin = fields.Char(string="PIN", copy=False)

    def action_register_phone(self):
        self.ensure_one()
        try:
            WhatsAppApi(self.wa_account_id)._register_phone(self.pin)
        except WhatsAppError as error:
            raise UserError(str(error)) from error
        self.wa_account_id.is_phone_registered = True
        self.pin = False
