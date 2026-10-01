# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, models


class SocialAccount(models.Model):
    _inherit = 'social.account'

    def _compute_statistics(self):
        """ Overridden to bypass third-party API calls. """
        return

    def _create_default_stream_facebook(self):
        """ Overridden to bypass third-party API calls. """
        return

    def _create_default_stream_twitter(self):
        """ Overridden to bypass third-party API calls. """
        return

    def _create_default_stream_youtube(self):
        """ Overridden to bypass third-party API calls. """
        return

    def _refresh_youtube_token(self):
        """ Overridden to bypass third-party API calls. """
        return

    def _create_default_stream_instagram(self):
        """ Overridden to bypass third-party API calls. """
        return

    @api.model
    def search_mention_suggestions(self, search_term, media_type):
        """ Return a fake result to show the feature. """
        partner = self.env.ref('social_demo.res_partner_2', raise_if_not_found=False)
        common_result = {
            'name': search_term,
            'profile_image_url': f'/web/image/res.partner/{partner.id}/avatar_128',
            'description': "A Full description of the user",
        }
        match media_type:
            case "twitter":
                return self.twitter_users_search(search_term)
            case "linkedin":
                return [{
                    **common_result,
                    'full_name': partner.name,
                    'member': "12345678",
                    'vanity_name': search_term,
                }]
            case "facebook":
                return [{
                    **common_result,
                    'id': "12345678",
                }]
            case "instagram":
                return [common_result]
            case _:
                return []

    def twitter_users_search(self, query):
        """ Returns some fake suggestion """
        partner = self.env.ref('base.res_partner_2', raise_if_not_found=False)
        return [{
            'name': partner.name,
            'profile_image_url': f'/web/image/res.partner/{partner.id}/avatar_128',
            'username': partner.name.replace(' ', '').lower(),
            'description': "https://example.com",
        }]
