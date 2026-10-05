# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.website_helpdesk.controllers.main import WebsiteHelpdesk
from odoo.addons.website_slides.controllers.main import WebsiteSlides
from odoo.http import route, request


class WebsiteHelpdeskSlides(WebsiteHelpdesk):

    def _format_search_results(self, search_type, records, options):
        if search_type != 'slides':
            return super()._format_search_results(search_type, records, options)

        if records._name == 'slide.slide':
            return [{
                'template': 'website_helpdesk_slides.search_result',
                'record': slide,
                'score': slide.total_views + slide.comments_count + slide.likes - slide.dislikes,
                'url': slide.website_absolute_url if slide.is_preview or slide.channel_id.is_member else slide.channel_id.website_absolute_url,
                'icon': 'school',
            } for slide in records]
        # slide.channel
        return [{
            'template': 'website_helpdesk_slides.channel_search_result',
            'record': channel,
            'score': channel.total_views + channel.total_votes,
            'url': channel.website_absolute_url,
            'icon': 'school',
        } for channel in records]

class WebsiteSlidesHelpdesk(WebsiteSlides):

    def sitemap_helpdesk_slides_channel(env, rule, qs):
        slug = env['ir.http']._slug
        teams = env['helpdesk.team'].search([])

        for team in teams:
            channels = team.website_slide_channel_ids
            if not channels:
                loc = '/slides'
                if not qs or qs.lower() in loc.lower():
                    yield {'loc': loc}
                continue
            if len(channels) == 1:
                loc = f'/slides/{slug(channels[0])}'
            else:
                loc = '/slides'
            if not qs or qs.lower() in loc.lower():
                last_write = max(channels.mapped('write_date'))
                yield {
                    'loc': loc,
                    'lastmod': last_write.date() if last_write else None,
                }

    @route('/helpdesk/<model("helpdesk.team"):team>/slides', type='http', auth="public", website=True, sitemap=sitemap_helpdesk_slides_channel)
    def helpdesk_slides_channel(self, team=None, **post):
        if not team or not team.website_slide_channel_ids:
            return request.redirect('/slides')
        channels = team.website_slide_channel_ids
        if len(channels) == 1:
            return request.redirect('/slides/%s' % request.env['ir.http']._slug(channels[0]), code=302)
        render_values = super().slides_channel_values(self, **post)
        render_values['channels'] = channels
        return request.render('website_helpdesk_slides.helpdesk_courses', render_values)
