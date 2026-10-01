# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        if self.source in ('mobile', 'kiosk') and self.mobile and self.preset_id.whatsapp_receipt_template_id:
            try:
                self.action_sent_receipt_on_whatsapp(self.mobile, template=self.preset_id.whatsapp_receipt_template_id)
            except (ValidationError, UserError) as e:
                _logger.warning("Error while sending whatsapp receipt for self order %s : %s", self.name, e.args[0])
        return res
