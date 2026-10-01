from odoo import models


class MarketingTrace(models.Model):
    _inherit = "marketing.trace"

    def _get_activity_trigger_type_ordered_list(self):
        if self.activity_id.mass_mailing_id_mailing_type == 'sms':
            return ['sms_open', 'sms_click']
        return super()._get_activity_trigger_type_ordered_list()
