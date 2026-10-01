# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from odoo import api, fields, models


class MarketingCampaign(models.Model):
    _inherit = 'marketing.campaign'

    mailing_sms_count = fields.Integer('# SMS Mailings', compute='_compute_mailing_sms_count')

    @api.depends('marketing_activity_ids.mass_mailing_id.mailing_type')
    def _compute_mailing_sms_count(self):
        # TDE NOTE: this could be optimized but is currently displayed only in a form view, no need to optimize now
        for campaign in self:
            campaign.mailing_sms_count = len(campaign.mapped('marketing_activity_ids.mass_mailing_id').filtered(lambda mailing: mailing.mailing_type == 'sms'))

    def action_view_sms(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("marketing_automation_sms.mail_mass_mailing_action_marketing_automation_sms")
        action['domain'] = [
            '&',
            ('use_in_marketing_automation', '=', True),
            ('id', 'in', self.mapped('marketing_activity_ids.mass_mailing_id').ids),
            ('mailing_type', '=', 'sms')
        ]
        action['context'] = dict(self.env.context)
        action['context'].update({
            # defaults
            'default_mailing_model_id': self.model_id.id,
            'default_campaign_id': self.utm_campaign_id.id,
            'default_use_in_marketing_automation': True,
            'default_mailing_type': 'sms',
            'default_state': 'done',
            # action
            'create': False,
        })
        return action

    def action_create_step(self, step_type):
        if step_type == 'sms':
            action = self.env['ir.actions.act_window']._for_xml_id('marketing_automation.marketing_activity_open_marketing_activity_form_view')
            action['context'] = {
                **literal_eval(action['context'] or '{}'),
                'default_activity_type': 'sms',
                'default_campaign_id': self.id,
            }
            return action
        return super().action_create_step(step_type)
