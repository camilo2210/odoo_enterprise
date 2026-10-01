from odoo import models


class EventRegistration(models.Model):
    _inherit = 'event.registration'

    def _get_registration_summary(self):
        result = super()._get_registration_summary()

        iot_printers = self.env["iot.device"].search([("type", "=", "printer")])
        result['iot_printers'] = iot_printers.mapped(lambda printer: {
            "id": printer.id,
            "name": printer.name,
            "identifier": printer.identifier,
            "iotIdentifier": printer.iot_id.identifier,
            "ip": printer.iot_id.ip,
        })
        return result
