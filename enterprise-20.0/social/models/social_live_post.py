# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
import logging
import requests

from odoo import api, fields, models
from odoo.tools.misc import format_date, format_time, _format_time_ago

_logger = logging.getLogger(__name__)


class SocialLivePost(models.Model):
    """ A social 'live' post, as opposed to a social.post, represents a post that is
    actually on a social.account instance.

    Basically, a social.post that is posted on 4 social.accounts will create 4 instances
    of the social.live.post. """

    _name = 'social.live.post'
    _description = 'Social Live Post'
    _order = 'scheduled_date ASC NULLS FIRST, id ASC'

    post_id = fields.Many2one('social.post', string="Social Post", required=True, index=True, readonly=True, ondelete="cascade")
    account_id = fields.Many2one('social.account', string="Social Account", required=True, index=True, readonly=True, ondelete="cascade")
    account_link = fields.Char("Account Link", related="account_id.user_link")
    message = fields.Char('Message', compute='_compute_message',
        help="Content of the social post message that is post-processed (links are shortened, UTMs, ...)")
    image_ids = fields.Many2many('social.post.image', string='Attached Images', compute='_compute_image_ids')
    live_post_link = fields.Char('Post Link', compute='_compute_live_post_link',
        help="Link of the live post on the target media.")
    failure_reason = fields.Text('Failure Reason', readonly=True,
        help="""The reason why a post is not successfully posted on the Social Media (eg: connection error, duplicated post, ...).""")
    state = fields.Selection([
        ('ready', 'Ready'),
        ('posting', 'Posting'),
        ('posted', 'Posted'),
        ('failed', 'Failed'),
        ('cancel', 'Cancelled')],
        string='Status', default='ready', required=True, readonly=True,
        help="""Most social.live.posts directly go from Ready to Posted/Failed since they result of a single call to the third party API.
        A 'Posting' state is also available for those that are sent through batching (like push notifications) or scheduled.""")
    likes_count = fields.Integer("Likes")
    comments_count = fields.Integer("Comments")
    shares_count = fields.Integer("Shares")
    has_likes = fields.Boolean(compute='_compute_has_metrics')
    has_comments = fields.Boolean(compute='_compute_has_metrics')
    has_shares = fields.Boolean(compute='_compute_has_metrics')
    company_id = fields.Many2one('res.company', 'Company', related='account_id.company_id')
    media_id = fields.Many2one(string='Media', related='account_id.media_id')
    media_type = fields.Selection(string='Media Type', related='account_id.media_type')
    scheduled_date = fields.Datetime('Scheduled Date', compute='_compute_scheduled_date', store=True)
    formatted_published_date = fields.Char('Formatted Published Date', compute='_compute_formatted_published_date')

    @api.depends('media_type')
    def _compute_has_metrics(self):
        self.has_likes = self.has_comments = self.has_shares = False

    @api.depends(lambda self:
        ['post_id.utm_campaign_id', 'account_id.media_type']
        + [f'post_id.{field}' for field in self.env['social.post']._get_post_message_modifying_fields()]
        + [f'post_id.{field}' for field in self.env['social.post']._message_fields().values()])
    def _compute_message(self):
        """ Prepares the message of the parent post, and shortens links to contain UTM data. """
        message_field_per_media = self.env['social.post']._message_fields()
        for live_post in self:
            message_field = message_field_per_media.get(live_post.account_id.media_type)
            if message_field:
                message = self.env['mail.render.mixin'].sudo()._shorten_links_text(
                    live_post.post_id[message_field],
                    live_post._get_utm_values()
                )

                live_post.message = self.env['social.post']._prepare_post_content(
                    message,
                    live_post.account_id.media_type,
                    **{field: live_post.post_id[field] for field in self.env['social.post']._get_post_message_modifying_fields()}
                )
            else:
                live_post.message = False

    @api.depends(lambda self: [f'post_id.{field}' for field in self.env['social.post']._images_fields().values()])
    def _compute_image_ids(self):
        images_field_per_media = self.env['social.post']._images_fields()
        for live_post in self:
            image_field = images_field_per_media.get(live_post.media_type)
            live_post.image_ids = live_post.post_id[image_field] if image_field else False

    @api.depends('account_id.media_id')
    def _compute_live_post_link(self):
        for live_post in self:
            live_post.live_post_link = False

    @api.depends('state', 'account_id')
    def _compute_display_name(self):
        """ ex: [Facebook] Odoo Social: posted, [Twitter] Mitchell Admin: failed, ... """
        state_description_values = dict(self._fields['state']._description_selection(self.env))
        for live_post in self:
            live_post.display_name = f'{live_post.account_id.display_name}: {state_description_values.get(live_post.state)}'

    @api.depends(lambda self: ['post_id.scheduled_date', 'post_id.published_date', *(f'post_id.{f}' for f in self.env['social.post']._scheduled_date_fields().values())])
    def _compute_scheduled_date(self):
        dates_fields = self.env['social.post']._scheduled_date_fields()
        for live_post in self:
            live_post.scheduled_date = live_post.post_id[dates_fields[live_post.media_type]]

    @api.depends('scheduled_date', 'post_id.published_date')
    def _compute_formatted_published_date(self):
        for live_post in self:
            # date shown in the kanban card
            date = live_post.scheduled_date or live_post.post_id.published_date
            if not date:
                live_post.formatted_published_date = False
            elif timedelta() < (delta := fields.Datetime.now() - date) < timedelta(hours=12):
                live_post.formatted_published_date = _format_time_ago(self.env, delta, add_direction=True)
            else:
                live_post.formatted_published_date = f"{format_date(self.env, date, date_format='medium')} ({format_time(self.env, date, time_format='short')})"

    @api.model_create_multi
    def create(self, vals_list):
        res = super(SocialLivePost, self).create(vals_list)
        res.mapped('post_id')._check_post_completion()
        return res

    def write(self, vals):
        res = super(SocialLivePost, self).write(vals)
        if vals.get('state'):
            self.mapped('post_id')._check_post_completion()
        return res

    def action_retry_post(self):
        self._post()

    def action_cancel(self):
        self.state = 'cancel'

    @api.model
    def refresh_statistics(self):
        # as refreshing the statistics is a recurring task, we ignore occasional "read timeouts"
        # from the third party services, as it would most likely mean a temporary slow connection
        # and/or a slow response from their side
        try:
            self.env['social.live.post']._refresh_statistics()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.warning("Failed to refresh the live post statistics.", exc_info=True)

    def _refresh_statistics(self):
        """ Every social module should override this method.

        This is the method responsible for fetching the post data per social media.

        It will be called manually every time we need to refresh the social.stream data:
            - social.stream creation/edition
            - 'Feed' kanban loading
            - 'Refresh' button on 'Feed' kanban
            - ...
        """
        pass

    def _post(self):
        """ Every social module should override this method.
        This will make the actual post on the related social.account through the third party API """
        pass

    def _get_utm_values(self):
        self.ensure_one()

        return {
            'campaign_id': self.post_id.utm_campaign_id.id,
            'medium_id': self.env['utm.mixin']._utm_ref("utm.utm_medium_social_media").id,
            'source_id': self.account_id.media_id._get_utm_source().id,
            'utm_reference': f'{self.post_id._name},{self.post_id.id}',
        }

    def _filter_by_media_types(self, media_types):
        return self.filtered(lambda post: post.account_id.media_id.media_type in media_types)
