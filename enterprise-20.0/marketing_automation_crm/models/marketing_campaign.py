# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.tools import convert


class MarketingCampaign(models.Model):
    _inherit = 'marketing.campaign'

    @property
    def _ENROLL_ACTION_TARGET_MODELS(self):
        return super()._ENROLL_ACTION_TARGET_MODELS | {'crm.lead'}

    # --------------------------------------
    # Prepare actions data
    # --------------------------------------

    def _prepare_ir_actions_server_crm_schedule_call_data(self):
        # If lead has customer, that has salesperson, this function creates an activity phone call for that salesperson, on a lead.
        return {
            'xml_id': 'marketing_automation_crm.ir_actions_server_crm_schedule_call',
            'values': {
                'model_id': self.env['ir.model']._get_id('crm.lead'),
                'state': 'next_activity',
                'name': _('Next activity: Call'),
                'activity_type_id': self.env.ref('mail.mail_activity_data_call').id,
                'activity_date_deadline_range': 2,
                'activity_date_deadline_range_type': 'days',
                'activity_user_type': 'generic',
                'activity_user_field_name': 'user_id',
            }
        }

    def _prepare_ir_actions_server_crm_priority_three_data(self):
        # If lead replies mail, give it priority number 3.
        return {
            'xml_id': 'marketing_automation_crm.ir_actions_server_crm_priority_three',
            'values': {
                'name': _('Replied High Priority'),
                'model_id': self.env['ir.model']._get_id('crm.lead'),
                'state': 'object_write',
                'selection_value': self.env.ref('crm.selection__crm_lead__priority__3').id,
                'evaluation_type': 'value',
                'update_field_id': self.env.ref('crm.field_crm_lead__priority').id,
                'update_path': 'priority',
                'update_boolean_value': 'true',
                'update_m2m_operation': 'add'
            }
        }

    def _prepare_ir_actions_server_crm_priority_zero_data(self):
        # If lead doesn't reply mail, give it priority 0.
        return {
            'xml_id': 'marketing_automation_crm.ir_actions_server_crm_priority_zero',
            'values': {
                'name': _('Not Opened, Low Priority'),
                'model_id': self.env['ir.model']._get_id('crm.lead'),
                'state': 'object_write',
                'selection_value': self.env.ref('crm.selection__crm_lead__priority__0').id,
                'evaluation_type': 'value',
                'update_field_id': self.env.ref('crm.field_crm_lead__priority').id,
                'update_path': 'priority',
                'update_boolean_value': 'true',
                'update_m2m_operation': 'add'
            }
        }

    # --------------------------------------
    # Sample Templates Creation
    # --------------------------------------

    @api.model
    def get_campaign_templates_info(self):
        campaign_templates_info = super().get_campaign_templates_info()
        campaign_templates_info.update({
             'crm': {
                'label': _("CRM"),
                'templates': {
                    'scheduled_calls': {
                        'title': _('Schedule Calls'),
                        'description': _('If lead is created for existing contact, schedule a call with their salesperson.'),
                        'function': '_get_marketing_template_scheduled_calls_values',
                    },
                    'prioritize_hot_leads': {
                        'title': _('Prioritize Hot Leads'),
                        'description': _('Send an email to new leads and assign them a high priority if they open it.'),
                        'function': '_get_marketing_template_prioritize_hot_leads_values',
                    }
                }
            }
        })
        return campaign_templates_info

    def _get_marketing_template_scheduled_calls_values(self):
        campaign = self.env['marketing.campaign'].create({
            'name': _('Schedule Calls'),
            'enroll_type': 'domain',
            'enroll_domain': [("user_id", "!=", False)],
            'enroll_unique_field_id': self.env['ir.model.fields']._get('crm.lead', 'email_from').id,
            'model_id': self.env['ir.model']._get_id('crm.lead'),
        })
        create_xmls = {
            'ir.actions.server': [
                self._prepare_ir_actions_server_crm_schedule_call_data(),
            ],
        }
        self._create_records_with_xml_ids(create_xmls)
        self.env['marketing.activity'].create({
            'trigger_type': 'begin',
            'activity_type': 'action',
            'interval_type': 'hours',
            'interval_number': 2,
            'server_action_id': self.env.ref('marketing_automation_crm.ir_actions_server_crm_schedule_call').id,
            'name': _('Schedule Call'),
            'campaign_id': campaign.id,
        })
        return campaign

    def _get_marketing_template_prioritize_hot_leads_values(self):
        convert.convert_file(
            self.sudo().env,
            'marketing_automation',
            'data/templates/mail_template_body_welcome_template.xml',
            idref={}, mode='init',
        )
        rendered_template = self.env['ir.qweb']._render(self.env.ref('marketing_automation.mail_template_body_welcome_template').id,
                                                        {'db_host': self.get_base_url(), 'company_website': self.env.company.website})
        prerequisites = {
            'mailing.mailing': [{
                'subject': _('Send welcome Email'),
                'body_arch': rendered_template,
                'body_html': rendered_template,
                'email_from': self.env.company.email_formatted,
                'mailing_model_id': self.env['ir.model']._get_id('crm.lead'),
                'mailing_type': 'mail',
                'reply_to_mode': 'update',
                'state': 'done',
                'use_in_marketing_automation': True,
            }],
        }
        for model_name, values in prerequisites.items():
            records = self.env[model_name].create(values)
            for idx, record in enumerate(records):
                prerequisites[model_name][idx] = record

        campaign = self.env['marketing.campaign'].create({
            'name': _('Prioritize Hot Leads'),
            'enroll_type': 'domain',
            'enroll_domain': [("user_id", "!=", False)],
            'enroll_unique_field_id': self.env['ir.model.fields']._get('crm.lead', 'email_from').id,
            'model_id': self.env['ir.model']._get_id('crm.lead'),
        })

        create_xmls = {
            'ir.actions.server': [
                self._prepare_ir_actions_server_crm_priority_three_data(),
                self._prepare_ir_actions_server_crm_priority_zero_data(),
            ],
        }
        self._create_records_with_xml_ids(create_xmls)

        parent_id = self.env['marketing.activity'].create([{
            'trigger_type': 'begin',
            'activity_type': 'mail',
            'interval_type': 'hours',
            'mass_mailing_id': prerequisites['mailing.mailing'][0].id,
            'interval_number': 1,
            'name': _('Send Email'),
            'campaign_id': campaign.id,
        }])
        self.env['marketing.activity'].create([{
            'trigger_type': 'mail_reply',
            'activity_type': 'action',
            'interval_type': 'hours',
            'interval_number': 3,
            'name': _('If replied, assign 3 stars'),
            'parent_id': parent_id.id,
            'triggering_activity_id': parent_id.id,
            'campaign_id': campaign.id,  # use the campaign_id here too,
            'server_action_id': self.env.ref('marketing_automation_crm.ir_actions_server_crm_priority_three').id,
        }, {
            'trigger_type': 'mail_not_open',
            'activity_type': 'action',
            'interval_type': 'hours',
            'interval_number': 6,
            'name': _('If not opened, priority = 0'),
            'parent_id': parent_id.id,
            'triggering_activity_id': parent_id.id,
            'campaign_id': campaign.id,  # use the campaign_id here too,
            'server_action_id': self.env.ref('marketing_automation_crm.ir_actions_server_crm_priority_zero').id,
        }])
        return campaign
