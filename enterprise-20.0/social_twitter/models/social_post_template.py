# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from urllib.parse import urlparse

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SocialPostTemplate(models.Model):
    _inherit = 'social.post.template'

    twitter_message = fields.Text(
        'X Message', compute='_compute_message_by_media',
        store=True, readonly=False)
    twitter_image_ids = fields.Many2many(
        'social.post.image', 'template_twitter_image_ids_rel', string='X Images',
        help='Will attach images to your posts.',
        compute='_compute_images_by_media', store=True, readonly=False, bypass_search_access=True)
    twitter_first_comment = fields.Text(
        'X First Comment', compute='_compute_first_comment_by_media',
        store=True, readonly=False)

    twitter_preview = fields.Html('X Preview', compute='_compute_twitter_preview')
    has_twitter_account = fields.Boolean('Has X Account', compute='_compute_has_twitter_account')
    display_twitter_preview = fields.Boolean('Display X Preview', compute='_compute_display_twitter_preview')

    is_twitter_post_limit_exceed = fields.Boolean('X Post Limit Exceeded', compute="_compute_is_twitter_post_limit_exceed")

    @api.constrains('twitter_message', 'twitter_image_ids')
    def _check_has_twitter_message_or_image(self):
        for post in self:
            if (post.has_twitter_account
                and not post.twitter_message
                and not post.twitter_image_ids):
                raise UserError(_("Please specify either an X Message or upload some X Images.", post.id))

    @api.depends('account_ids.media_id.media_type')
    def _compute_has_twitter_account(self):
        for post in self:
            post.has_twitter_account = 'twitter' in post.account_ids.media_id.mapped('media_type')

    @api.depends('has_twitter_account', 'twitter_message', 'twitter_image_ids')
    def _compute_display_twitter_preview(self):
        for post in self:
            post.display_twitter_preview = post.has_twitter_account and (post.twitter_message or post.twitter_image_ids)

    @api.depends('twitter_message', 'has_twitter_account')
    def _compute_is_twitter_post_limit_exceed(self):
        self.is_twitter_post_limit_exceed = False
        for post in self.filtered('has_twitter_account'):
            message_length = self._get_tweet_size(post.twitter_message)
            twitter_account = post.account_ids._filter_by_media_types(['twitter'])
            post.is_twitter_post_limit_exceed = twitter_account.media_id.max_post_length and message_length > twitter_account.media_id.max_post_length

    @api.depends(lambda self: ['twitter_message', 'twitter_image_ids', 'is_twitter_post_limit_exceed', 'has_twitter_account', 'social_post_mentions', 'twitter_first_comment'] + self._get_post_message_modifying_fields())
    def _compute_twitter_preview(self):
        self.twitter_preview = False
        for post in self.filtered('has_twitter_account'):
            twitter_account = post.account_ids._filter_by_media_types(['twitter'])

            image_urls = []
            link_preview = {}
            if post.twitter_image_ids:
                image_urls = [
                    f'/web/image/social.post.image/{image._origin.id or image.id}/raw'
                    for image in post.twitter_image_ids.sorted(lambda image: (image.sequence, image._origin.id or image.id))
                ]
            elif url := self.env["social.post"]._extract_url_from_message(post.twitter_message):
                preview = self.env["mail.link.preview"].sudo()._search_or_create_from_url(url)
                link_preview["url"] = url
                link_preview["domain"] = urlparse(url).hostname
                if image_url := preview.og_image:
                    image_urls.append(image_url)

            post.twitter_preview = self.env['ir.qweb']._render('social_twitter.twitter_preview', {
                **post._prepare_preview_values('twitter'),
                'message': post._prepare_post_content(
                    post.twitter_message,
                    'twitter',
                    **{field: post[field] for field in post._get_post_message_modifying_fields()}),
                'twitter_first_comment': post.twitter_first_comment,
                'image_urls': image_urls,
                'limit': twitter_account.media_id.max_post_length,
                'is_twitter_post_limit_exceed': post.is_twitter_post_limit_exceed,
                'link_preview': link_preview,
            })

    @api.model
    def _message_fields(self):
        """Return the message field per media."""
        return {**super()._message_fields(), 'twitter': 'twitter_message'}

    @api.model
    def _images_fields(self):
        """Return the images field per media."""
        return {**super()._images_fields(), 'twitter': 'twitter_image_ids'}

    @api.model
    def _first_comment_fields(self):
        """Return the "first comment" field per media."""
        return {**super()._first_comment_fields(), 'twitter': 'twitter_first_comment'}

    @api.model
    def _get_tweet_size(self, message):
        """Compute the size of the Tweet based on the Twitter rules.

        The URLs count as 23 chars, and emoji count as 2 chars.

        >>> assert _get_tweet_size("Hello 🙂") == 8
        >>> assert _get_tweet_size("URL: https://odoo.com") == 28
        """
        # replace emoji by 2 chars
        zwj = r"\u200d"  # zero width join, used to "merge" emoji
        variant = r"\ufe0f"  # show the variant of an emoji
        emoji = r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]"
        message = re.sub(f"{emoji}(({zwj}{emoji})|{variant})?", "__", message or "")
        return len(re.sub(r"\bhttps?://[^\s]+", "_" * 23, message))
