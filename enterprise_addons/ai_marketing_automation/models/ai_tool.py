from odoo import api, models


class AITool(models.AbstractModel):
    _inherit = 'ai.tool'

    @api.model
    def _sort_campaign_steps(self, campaign_id):
        campaign = self.env['marketing.campaign'].browse(campaign_id).exists()
        if not campaign:
            return {'success': False, 'error': f'No campaign with id {campaign_id}.'}
        campaign.action_sort_steps()
        return {'success': True, 'campaign_id': campaign.id}

    @api.model
    def _is_module_installed(self, module_name):
        return {
            'module': module_name,
            'installed': module_name in self.env['ir.module.module']._installed(),
        }

    @api.model
    def _delete_campaign_step(self, activity_id, step_type, cascade_delete=False):
        """Remove a step from a campaign, repairing the workflow around it."""
        activity = self.env['marketing.activity'].browse(activity_id).exists()
        if not activity:
            return {'success': False, 'error': f'No marketing activity with id {activity_id}.'}

        campaign = activity.campaign_id
        activity.action_delete_step(step_type)
        campaign.action_sort_steps()
        return {
            'success': True,
            'campaign_id': campaign.id,
            'remaining_activity_ids': campaign.marketing_activity_ids.ids,
        }

    def _is_base_automation_server_action(self, tool_context):
        if tool_context.get('res_model') == 'marketing.campaign':
            return False

        return super()._is_base_automation_server_action(tool_context)

    def _is_automation_skill_required(self, tool_context):
        if tool_context.get('res_model') == 'marketing.campaign':
            return False

        return super()._is_base_automation_server_action(tool_context)
