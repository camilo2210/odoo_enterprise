# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class SocialPost(models.Model):
    _inherit = 'social.post'

    twitter_image_ids = fields.Many2many(relation="twitter_image_ids_rel")
    twitter_scheduled_date = fields.Datetime(
        string='X Scheduled for',
        compute='_compute_scheduled_date_by_media',
        store=True, readonly=False, copy=False)

    @api.depends('live_post_ids.twitter_tweet_id')
    def _compute_stream_posts_count(self):
        super()._compute_stream_posts_count()

    @api.depends('state')
    def _compute_is_twitter_post_limit_exceed(self):
        self.is_twitter_post_limit_exceed = False
        super(SocialPost, self - self.filtered(lambda post: post.state in ['posting', 'posted']))._compute_is_twitter_post_limit_exceed()

    @api.model
    def _scheduled_date_fields(self):
        return {**super()._scheduled_date_fields(), 'twitter': 'twitter_scheduled_date'}

    def _get_stream_post_domain(self):
        domain = super()._get_stream_post_domain()
        twitter_tweet_ids = [twitter_tweet_id for twitter_tweet_id in self.live_post_ids.mapped('twitter_tweet_id') if twitter_tweet_id]
        if twitter_tweet_ids:
            return Domain.OR([domain, [('twitter_tweet_id', 'in', twitter_tweet_ids)]])
        return domain

    @api.model
    def _prepare_post_content(self, message, media_type, **kw):
        message = super()._prepare_post_content(message, media_type, **kw)
        if message and media_type == 'twitter':
            message = self.env["social.live.post"]._remove_mentions(message)
        return message
