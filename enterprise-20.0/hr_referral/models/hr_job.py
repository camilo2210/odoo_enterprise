# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class HrJob(models.Model):
    _inherit = "hr.job"

    job_open_date = fields.Date('Job Start Recruitment Date', default=fields.Date.context_today,
        groups="hr.group_hr_user,hr_recruitment.group_hr_recruitment_user")  # never use ?
    utm_campaign_id = fields.Many2one('utm.campaign', 'Campaign', ondelete='restrict')
    max_points = fields.Integer(compute='_compute_max_points')
    direct_clicks = fields.Integer(compute='_compute_clicks')
    facebook_clicks = fields.Integer(compute='_compute_clicks')
    twitter_clicks = fields.Integer("X Clicks", compute='_compute_clicks')
    linkedin_clicks = fields.Integer(compute='_compute_clicks')

    def _compute_clicks(self):
        grouped_data = self.env['link.tracker']._read_group([
            ('utm_reference', '=', f'{self.env.user._name},{self.env.user.id}'),
            ('campaign_id', 'in', self.mapped('utm_campaign_id').ids),
            ('medium_id', '!=', False),
            ('source_id', '!=', False),
            ], ['campaign_id', 'medium_id', 'source_id'], ['count:sum'])
        medium_direct = self.env['utm.mixin']._utm_ref('utm.utm_medium_direct')
        medium_social_media = self.env['utm.mixin']._utm_ref('utm.utm_medium_social_media')
        source_referral_link = self.env['utm.mixin']._utm_ref('utm.utm_source_referral')
        source_facebook = self.env.ref(
            'hr_referral.utm_source_referral_link_facebook',
            raise_if_not_found=False,
        )
        source_twitter = self.env.ref(
            'hr_referral.utm_source_referral_link_twitter',
            raise_if_not_found=False,
        )
        source_linkedin = self.env.ref(
            'hr_referral.utm_source_referral_link_linkedin',
            raise_if_not_found=False,
        )
        mapped_data = {job.utm_campaign_id: {} for job in self}
        for campaign, medium, source, count in grouped_data:
            mapped_data[campaign][medium, source] = count
        for job in self:
            data = mapped_data[job.utm_campaign_id]
            job.direct_clicks = data.get((medium_direct, source_referral_link), 0)
            job.facebook_clicks = data.get((medium_social_media, source_facebook), 0)
            job.twitter_clicks = data.get((medium_social_media, source_twitter), 0)
            job.linkedin_clicks = data.get((medium_social_media, source_linkedin), 0)

    def _compute_max_points(self):
        for job in self:
            stages = self.env['hr.recruitment.stage'].search([('use_in_referral', '=', True), '|', ('job_ids', '=', False), ('job_ids', '=', job.id)])
            job.max_points = sum(stages.mapped('points'))

    def search_or_create_referral_links(self, users=None, channel='direct'):
        '''
        Create/Retrieve a referral link for each user in the given channel.

        This method is made to retrieve/create a referral link for each user
        for one job.

        :param User users: the users for which to retrieve/create the
            referral links. If not given, the current user is used.
        :param str channel: the channel to use for the referral links.
            Default to 'direct'.
        :returns: a dictionary mapping each user to its referral link.
        :rtype: dict
        '''

        # checks and defaults
        self.ensure_one()
        channel_to_medium = {
            'direct': 'utm.utm_medium_direct',
            'facebook': 'utm.utm_medium_social_media',
            'twitter': 'utm.utm_medium_social_media',
            'linkedin': 'utm.utm_medium_social_media',
        }
        channel_to_source = {
            'direct': 'utm.utm_source_referral',
            'facebook': 'hr_referral.utm_source_referral_link_facebook',
            'twitter': 'hr_referral.utm_source_referral_link_twitter',
            'linkedin': 'hr_referral.utm_source_referral_link_linkedin',
        }
        if channel not in channel_to_source:
            return {}
        source = self.env.ref(channel_to_source[channel], raise_if_not_found=False)
        medium = self.env['utm.mixin']._utm_ref(channel_to_medium[channel])
        if not source:
            return {}
        if users is None:
            users = self.env.user
        elif not users:
            return {}
        if not self.utm_campaign_id:
            self.utm_campaign_id = self.env['utm.campaign'].create([{'name': self.name}])

        referral_links_by_user = {}
        trackers = self.env['link.tracker'].search([
            ('url', '=', self.full_url),
            ('campaign_id', '=', self.utm_campaign_id.id),
            ('source_id', '=', source.id),
            ('utm_reference', 'in', [f'res.users,{user_id}' for user_id in users.ids]),
        ])
        trackers_by_user = {tracker.utm_reference: tracker for tracker in trackers}
        trackers_to_create = []
        user_without_tracker = []
        for user in users:
            tracker = trackers_by_user.get(user)
            if tracker:
                referral_links_by_user[user] = tracker.short_url
            else:
                user_without_tracker.append(user)
                trackers_to_create.append({
                    'url': self.full_url,
                    'title': _('Referral %(user)s: %(job_url)s', user=user, job_url=self.full_url),
                    'campaign_id': self.utm_campaign_id.id,
                    'medium_id': medium.id,
                    'source_id': source.id,
                    'utm_reference': f'res.users,{user.id}',
                })
        LinkTrackers = self.env['link.tracker']
        if not LinkTrackers.has_access('create') and\
            self.env.user.has_group('hr_recruitment.group_hr_recruitment_manager'):
            LinkTrackers = LinkTrackers.sudo()

        new_trackers = LinkTrackers.create(trackers_to_create)
        for tracker, user in zip(new_trackers, user_without_tracker):
            referral_links_by_user[user] = tracker.short_url

        return referral_links_by_user

    def get_referral_link(self, channel):
        self.ensure_one()
        wizard = self.env['hr.referral.link.to.share'].create({'job_id': self.id, 'channel': channel})
        return wizard.url

    def action_share_external(self):
        self.ensure_one()
        wizard = self.env['hr.referral.link.to.share'].create({'job_id': self.id})
        return {
            'name': _("Visit Webpage"),
            'type': 'ir.actions.act_url',
            'url': wizard.url,
            'target': 'new',
        }

    def action_referral_campaign(self):
        self.ensure_one()
        return {
            'name': _("Promotion Campaign for %(job)s", job=self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.referral.campaign.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
