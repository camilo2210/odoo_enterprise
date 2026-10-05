# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SocialPostTemplate(models.Model):
    _inherit = 'social.post.template'

    facebook_message = fields.Text(
        'Facebook Message', compute='_compute_message_by_media',
        store=True, readonly=False)
    facebook_image_ids = fields.Many2many(
        'social.post.image', 'template_facebook_image_ids_rel', string='Facebook Images',
        help='Will attach images to your posts.', compute='_compute_images_by_media',
        store=True, readonly=False, bypass_search_access=True)
    facebook_first_comment = fields.Text(
        'Facebook First Comment', compute='_compute_first_comment_by_media',
        store=True, readonly=False)
    facebook_post_as_story = fields.Boolean("Facebook Post Story")

    facebook_preview = fields.Html('Facebook Preview', compute='_compute_facebook_preview')
    has_facebook_account = fields.Boolean('Has Facebook Account', compute='_compute_has_facebook_account')
    display_facebook_preview = fields.Boolean('Display Facebook Preview', compute='_compute_display_facebook_preview')

    @api.constrains('facebook_message', 'facebook_image_ids')
    def _check_has_facebook_message_or_image(self):
        for post in self:
            if (post.has_facebook_account
                and not post.facebook_message
                and not post.facebook_image_ids):
                raise UserError(_("Please specify either a Facebook Message or upload some Facebook Images."))

    @api.constrains('facebook_post_as_story', 'facebook_image_ids')
    def _check_facebook_post_as_story(self):
        for post in self:
            if post.facebook_post_as_story and len(post.facebook_image_ids) != 1:
                raise UserError(_("Oops! Facebook stories can only contain a single picture."))

    @api.depends('account_ids.media_id.media_type')
    def _compute_has_facebook_account(self):
        for post in self:
            post.has_facebook_account = 'facebook' in post.account_ids.media_id.mapped('media_type')

    @api.depends('facebook_message', 'has_facebook_account', 'facebook_image_ids')
    def _compute_display_facebook_preview(self):
        for post in self:
            post.display_facebook_preview = (post.facebook_message or post.facebook_image_ids) and post.has_facebook_account

    @api.depends(lambda self: ['facebook_message', 'facebook_image_ids', 'display_facebook_preview', 'facebook_first_comment', 'social_post_mentions', 'facebook_post_as_story'] + self._get_post_message_modifying_fields())
    def _compute_facebook_preview(self):
        for post in self:
            if not post.display_facebook_preview:
                post.facebook_preview = False
                continue

            image_urls = []
            link_preview = {}
            if post.facebook_image_ids:
                image_urls = [
                    f'/web/image/social.post.image/{image._origin.id or image.id}/raw'
                    for image in post.facebook_image_ids.sorted(lambda image: (image.sequence, image._origin.id or image.id))
                ]
            elif url := self.env["social.post"]._extract_url_from_message(post.facebook_message):
                preview = self.env["mail.link.preview"].sudo()._search_or_create_from_url(url)
                link_preview["url"] = url
                link_preview["domain"] = urlparse(url).hostname
                if image_url := preview.og_image:
                    image_urls.append(image_url)
                if title := preview.og_title:
                    link_preview['title'] = title
                if description := preview.og_description:
                    link_preview['description'] = description

            post.facebook_preview = self.env['ir.qweb']._render('social_facebook.facebook_preview', {
                **post._prepare_preview_values("facebook"),
                'message': post._prepare_post_content(
                    post.facebook_message,
                    'facebook',
                    **{field: post[field] for field in post._get_post_message_modifying_fields()}),
                'facebook_first_comment': post.facebook_first_comment,
                'facebook_post_as_story': post.facebook_post_as_story,
                'image_urls': image_urls,
                'link_preview': link_preview,
            })

    @api.model
    def _message_fields(self):
        """Return the message field per media."""
        return {**super()._message_fields(), 'facebook': 'facebook_message'}

    @api.model
    def _images_fields(self):
        """Return the images field per media."""
        return {**super()._images_fields(), 'facebook': 'facebook_image_ids'}

    @api.model
    def _first_comment_fields(self):
        """Return the "first comment" field per media."""
        return {**super()._first_comment_fields(), 'facebook': 'facebook_first_comment'}

    def _prepare_social_post_values(self):
        """Return the values to generate a social post from the social post template."""
        self.ensure_one()
        return {
            **super()._prepare_social_post_values(),
            'facebook_post_as_story': self.facebook_post_as_story,
        }
