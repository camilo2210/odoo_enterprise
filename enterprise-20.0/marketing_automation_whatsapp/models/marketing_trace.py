from odoo import api, fields, models


class MarketingTrace(models.Model):
    _inherit = 'marketing.trace'

    whatsapp_message_id = fields.Many2one(
        'whatsapp.message', string='Marketing Template',
        index='btree_not_null', readonly=False)

    def _get_activity_trigger_type_ordered_list(self):
        if self.activity_id.whatsapp_template_id:
            return ['whatsapp_open', 'whatsapp_click', 'whatsapp_reply']
        return super()._get_activity_trigger_type_ordered_list()

    @api.depends('whatsapp_message_id')
    def _compute_links_click_datetime(self):
        wa_trace = self.filtered(lambda x: x.whatsapp_message_id)
        wa_trace.links_click_datetime = False
        super(MarketingTrace, self - wa_trace)._compute_links_click_datetime()
        for trace in wa_trace:
            trace.links_click_datetime = trace.whatsapp_message_id.links_click_datetime
