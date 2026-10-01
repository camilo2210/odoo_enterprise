from odoo import _, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    self_ordering_obox_id = fields.Many2one('obox.obox', domain="[('supports_kiosk', '=', True)]")

    def action_open_wizard(self):
        result = super().action_open_wizard()

        if not self.self_ordering_obox_id:
            return result

        self.self_ordering_obox_id._open_kiosk(self)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'message': _("Opening the kiosk on %s", self.self_ordering_obox_id.name),
            },
        }
