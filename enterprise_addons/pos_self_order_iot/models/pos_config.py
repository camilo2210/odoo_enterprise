import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    self_ordering_iot_available_iot_box_ids = fields.One2many(
        'iot.box',
        'pos_id',
        string='Available IoT Boxes',
        domain="[('can_be_kiosk', '=', True)]",
        required=True,
    )

    def _load_self_data_models(self):
        models = super()._load_self_data_models()
        models += ['iot.device', 'iot.box']
        return models

    def action_open_wizard(self):
        """Override the ir.action.act_url to open the kiosk on the selected IoT Boxes (if any)."""
        url_in_new_tab_action = super().action_open_wizard()  # Configure pos session

        # If no IoT Box is selected in the settings, open the kiosk in a new tab
        if not self.self_ordering_iot_available_iot_box_ids:
            return url_in_new_tab_action

        display_devices = [
            device
            for box in self.self_ordering_iot_available_iot_box_ids
            for device in box.device_ids if device.type == 'display'
        ]

        for display in display_devices:
            self.env['iot.channel'].send_message({
                "iot_identifier": display.iot_id.identifier,
                "device_identifier": display.identifier,
                'action': 'open_kiosk',
                'pos_id': self.id,
                'access_token': self.access_token,
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'message': _("Opening the kiosk on %s", ', '.join(self.self_ordering_iot_available_iot_box_ids.mapped('name'))),
            }
        }

    def has_valid_self_payment_method(self):
        res = super().has_valid_self_payment_method()
        if self.self_ordering_mode == 'mobile':
            return res
        return res or any(pm.iot_device_id for pm in self.payment_method_ids)

    @api.model
    def _load_pos_self_data_fields(self, pos_config_id):
        fields = super()._load_pos_self_data_fields(pos_config_id)
        return fields + ['self_ordering_iot_available_iot_box_ids']
