# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class LinkTracker(models.Model):
    _inherit = 'link.tracker'

    def action_open_referral_link_tracker(self):
        is_manager = self.env.user.has_group('hr_referral.group_hr_referral_manager')
        if is_manager:
            all_jobs_with_campaign_ids = self.env['hr.job'].search([('utm_campaign_id', '!=', False)])
            domain = [('campaign_id', 'in', all_jobs_with_campaign_ids.utm_campaign_id.ids or [0])]
        else:
            domain = [('utm_reference', '=', f'res.users,{self.env.user.id}')]

        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Referral Link Tracker'),
            'res_model': 'link.tracker',
            'view_mode': 'list,form,graph',
            'domain': domain,
            'context': {'search_default_groupby_campaign_id': 1} if is_manager else {},
        }
