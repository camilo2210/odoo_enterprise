# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class PosConfig(models.Model):
    _inherit = "pos.config"

    iot_fdm_se_id = fields.Many2one(
        "iot.device",
        domain="[('type', '=', 'fiscal_data_module'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    def _compute_iot_device_ids(self):
        super()._compute_iot_device_ids()
        for config in self:
            if config.use_iot_box:
                config.iot_device_ids += config.iot_fdm_se_id

    def _check_before_creating_new_session(self):
        if self.iot_fdm_se_id:
            self._check_pos_settings_for_sweden()
        return super()._check_before_creating_new_session()

    def _check_pos_settings_for_sweden(self):
        if self.iot_fdm_se_id and not self.company_id.partner_id._get_additional_identifier('SE_EN'):
            raise ValidationError(
                _("The company require a company registry when you are using the blackbox.")
            )
        if self.iot_fdm_se_id and not self.company_id.vat:
            raise ValidationError(
                _("The company require a VAT number when you are using the blackbox.")
            )
        if self.iot_fdm_se_id and not self.cash_control:
            raise ValidationError(
                _("You cannot use the sweden blackbox without cash control.")
            )

    def get_order_sequence_number(self):
        return self.order_seq_id._next()
