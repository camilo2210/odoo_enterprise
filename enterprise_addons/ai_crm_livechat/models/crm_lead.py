# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, Command, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    @api.model
    def _ai_prepare_lead_creation_values(self, vals):
        values = super()._ai_prepare_lead_creation_values(vals)
        if channel := self.env.context.get('discuss_channel'):
            values['origin_channel_id'] = channel.id
            livechat_source = self.env['utm.mixin']._utm_ref('utm.utm_source_livechat')
            values['source_id'] = livechat_source.id
            ai_agent = channel.sudo().ai_agent_id  # sudo because ai_agent_id has group no_access
            if ai_agent:
                values['utm_reference'] = f'{ai_agent._name},{ai_agent.id}'

            # avoid another bridge module just for that
            if 'website' in self.pool._init_modules and (visitor := channel.livechat_visitor_id):
                values['visitor_ids'] = [Command.link(visitor.id)]
        return values
