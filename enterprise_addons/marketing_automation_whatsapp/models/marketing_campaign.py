from ast import literal_eval
from odoo import api, fields, models


class MarketingCampaign(models.Model):
    _inherit = 'marketing.campaign'

    whatsapp_template_count = fields.Integer('# Whatsapp', compute='_compute_whatsapp_template_count')

    @api.depends('marketing_activity_ids')
    def _compute_whatsapp_template_count(self):
        for campaign in self:
            campaign.whatsapp_template_count = len(campaign.marketing_activity_ids.whatsapp_template_id)

    def action_view_whatsapp_templates(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("marketing_automation_whatsapp.whatsapp_template_action_marketing_automation")

        action['domain'] = [
            ('id', 'in', self.marketing_activity_ids.whatsapp_template_id.ids)
        ]
        return action

    def action_create_step(self, step_type):
        if step_type == 'whatsapp':
            action = self.env['ir.actions.act_window']._for_xml_id(
                'marketing_automation.marketing_activity_open_marketing_activity_form_view')
            action['context'] = {
                **literal_eval(action['context'] or '{}'),
                'default_activity_type': 'whatsapp',
                'default_campaign_id': self.id,
                'default_model_id': self.model_id.id,
            }
            return action
        return super().action_create_step(step_type)
