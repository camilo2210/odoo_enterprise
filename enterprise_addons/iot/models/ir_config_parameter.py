# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def set_str(self, key: str, value: str | None):
        if key == 'web.base.url' and value and not value.startswith('http://localhost'):
            iot_box_identifiers = self.env['iot.box'].search([]).mapped('identifier')
            for identifier in iot_box_identifiers:
                self.env['iot.channel'].send_message({
                    'iot_identifier': identifier,
                    'server_url': value,
                }, 'server_update')

        return super().set_str(key, value)
