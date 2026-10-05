# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.urls import urljoin as url_join


class HrReferralLinkToShare(models.TransientModel):
    _name = 'hr.referral.link.to.share'
    _description = 'Referral Link To Share'

    job_id = fields.Many2one(
        'hr.job',
        default=lambda self: self.env.context.get('active_id', None),
    )
    channel = fields.Selection([
        ('direct', 'Link'),
        ('facebook', 'Facebook'),
        ('twitter', 'X'),
        ('linkedin', 'Linkedin')], default='direct')
    url = fields.Char(readonly=True, compute='_compute_url', compute_sudo=True)

    @api.depends('channel')
    def _compute_url(self):
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

        jobs_without_campaign = [
            wizard.job_id for wizard in self
            if wizard.job_id and not wizard.job_id.utm_campaign_id
        ]
        if jobs_without_campaign:
            utm_campaign = []
            for job in jobs_without_campaign:
                utm_campaign.append({'name': _('Referral: %(name)s', name=job.name)})
            utm_campaign_ids = self.env['utm.campaign'].create(utm_campaign).ids
            for utm_campaign_id, job in zip(utm_campaign_ids, jobs_without_campaign):
                job.utm_campaign_id = utm_campaign_id

        link_trackers_values = []
        for wizard in self:
            utm_source = self.env.ref(
                channel_to_source.get(wizard.channel),
                raise_if_not_found=False,
            )
            utm_medium = self.env['utm.mixin']._utm_ref(channel_to_medium.get(wizard.channel))
            url = url_join(self.get_base_url(), '/jobs') if not wizard.job_id else wizard.job_id.full_url
            link_trackers_values.append({
                'title': _('Referral: %(url)s', url=url),
                'url': url,
                'campaign_id': wizard.job_id.utm_campaign_id.id,
                'medium_id': utm_medium.id if utm_medium else False,
                'source_id': utm_source.id if utm_source else False,
                'utm_reference': f'{self.env.user._name},{self.env.user.id}',
            })

        link_trackers = self.env['link.tracker'].search_or_create(link_trackers_values)

        for wizard, link_tracker in zip(self, link_trackers):
            if wizard.channel == 'direct':
                wizard.url = link_tracker.short_url
            elif wizard.channel == 'facebook':
                wizard.url = 'https://www.facebook.com/sharer/sharer.php?u=%s' % link_tracker.short_url
            elif wizard.channel == 'twitter':
                new_line_code = '%0A'
                hashtag_code = '%23'
                text_message = self.env._(
                    "🚀 An exciting opportunity for a %(job_name)s at my company. "
                    "If you're looking for a new challenge, check it out!👇%(new_line_code)s"
                    "🔗%(short_url)s%(new_line_code)s"
                    "%(hashtag_code)sHiring %(hashtag_code)sJobOpening %(hashtag_code)sCareerOpportunity",
                    job_name=self.job_id.name,
                    short_url=link_tracker.short_url,
                    new_line_code=new_line_code,
                    hashtag_code=hashtag_code,
                )
                wizard.url = f'https://twitter.com/intent/tweet?tw_p=tweetbutton&text={text_message}'
            elif wizard.channel == 'linkedin':
                wizard.url = 'https://www.linkedin.com/sharing/share-offsite?url=%s' % link_tracker.short_url
