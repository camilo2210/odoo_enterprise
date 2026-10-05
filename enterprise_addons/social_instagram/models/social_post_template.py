# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.image import binary_to_image


class SocialPostTemplate(models.Model):
    _inherit = 'social.post.template'

    def _get_default_access_token(self):
        return str(uuid.uuid4())

    instagram_message = fields.Text(
        'Instagram Message', compute='_compute_message_by_media',
        store=True, readonly=False)
    instagram_image_ids = fields.Many2many(
        'social.post.image', 'template_instagram_image_ids_rel', string='Instagram Images',
        help='Will attach images to your posts.',
        compute='_compute_images_by_media', store=True, readonly=False, bypass_search_access=True)
    instagram_first_comment = fields.Text(
        'Instagram First Comment', compute='_compute_first_comment_by_media',
        store=True, readonly=False)
    instagram_post_as_story = fields.Boolean("Instagram Post Story")

    instagram_access_token = fields.Char('Access Token', default=lambda self: self._get_default_access_token(), copy=False,
        help="Used to allow access to Instagram to retrieve the post image")
    has_instagram_account = fields.Boolean('Has Instagram Account', compute='_compute_has_instagram_account')
    display_instagram_preview = fields.Boolean('Display Instagram Preview', compute='_compute_display_instagram_preview')
    instagram_preview = fields.Html('Instagram Preview', compute='_compute_instagram_preview')

    @api.constrains('instagram_message', 'instagram_image_ids')
    def _check_has_instagram_message_or_image(self):
        for post in self:
            if (post.has_instagram_account
                and not post.instagram_message
                and not post.instagram_image_ids):
                raise UserError(_("Please specify either a Instagram Message or upload some Instagram Images."))

    @api.constrains('instagram_post_as_story', 'instagram_image_ids')
    def _check_instagram_post_as_story(self):
        for post in self:
            if post.instagram_post_as_story and len(post.instagram_image_ids) != 1:
                raise UserError(_("Oops! Instagram stories can only contain a single picture."))

    @api.depends('account_ids.media_id.media_type')
    def _compute_has_instagram_account(self):
        for post in self:
            post.has_instagram_account = 'instagram' in post.account_ids.media_id.mapped('media_type')

    @api.depends('instagram_message', 'has_instagram_account', 'instagram_image_ids')
    def _compute_display_instagram_preview(self):
        for post in self:
            post.display_instagram_preview = (post.instagram_message or post.instagram_image_ids) and post.has_instagram_account

    @api.depends(lambda self: ['instagram_message', 'instagram_image_ids', 'display_instagram_preview', 'social_post_mentions', 'instagram_first_comment', 'instagram_post_as_story'] + self._get_post_message_modifying_fields())
    def _compute_instagram_preview(self):
        """ We want to display various error messages if the image is not appropriate.
        See #_get_instagram_image_error() for more information. """

        for post in self:
            if not post.display_instagram_preview:
                post.instagram_preview = False
                continue
            faulty_images, error_code = post._get_instagram_image_error()
            post.instagram_preview = self.env['ir.qweb']._render('social_instagram.instagram_preview', {
                **post._prepare_preview_values("instagram"),
                'faulty_images': faulty_images,
                'error_code': error_code,
                'image_urls': [
                    f'/web/image/social.post.image/{image._origin.id or image.id}/raw'
                    for image in post.instagram_image_ids.sorted(lambda image: (image.sequence, image._origin.id or image.id))
                ],
                'message': post._prepare_post_content(
                    post.instagram_message,
                    'instagram',
                    **{field: post[field] for field in post._get_post_message_modifying_fields()}),
                'instagram_first_comment': post.instagram_first_comment,
                'instagram_post_as_story': post.instagram_post_as_story,
            })

    def _get_instagram_image_error(self):
        """ Allows verifying that the post within self contains a valid Instagram image.

        Returns: faulty image names along with error_code
        Errors:              Causes:
        - 'missing'          If there is no image
        - 'wrong_extension'  If the image in not in the JPEG format
        - 'incorrect_ratio'  If the image in not between 4:5 and 1.91:1 ratio'
        - 'max_limit'        If the number of images is greater than 10 (Carousels are limited to 10 images)
        - 'corrupted'        If the image is corrupted
        - False              If everything is correct.

        Those various rules are imposed by Instagram.
        See: https://developers.facebook.com/docs/instagram-api/reference/ig-user/media

        We want to avoid any kind of dynamic resizing / format change to make sure what the user
        uploads and sees in the preview is as close as possible to what they will get as a result on
        Instagram. """

        self.ensure_one()
        error_code = False
        faulty_images = self.env['social.post.image']
        jpeg_images = self.instagram_image_ids.filtered(lambda image: image.mimetype == 'image/jpeg')
        non_jpeg_images = self.instagram_image_ids - jpeg_images
        if not self.instagram_image_ids:
            error_code = 'missing'
        else:
            if (len(jpeg_images) > 10 and not self.instagram_post_as_story) or (len(jpeg_images) > 1 and self.instagram_post_as_story):
                error_code = 'max_limit'
            if non_jpeg_images:
                error_code = 'wrong_extension'
                faulty_images += non_jpeg_images
            if jpeg_images and not non_jpeg_images:
                for jpeg_image in jpeg_images:
                    try:
                        image = binary_to_image(jpeg_image.raw)
                    except UserError:
                        # image could not be loaded
                        error_code = 'corrupted'
                        return jpeg_image.name, error_code

                    image_ratio = image.width / image.height if image.height else 0
                    if not self.instagram_post_as_story and (image_ratio < 0.8 or image_ratio > 1.91):
                        error_code = 'incorrect_ratio'
                        faulty_images += jpeg_image

        return faulty_images.mapped('name'), error_code

    @api.model
    def _message_fields(self):
        """Return the message field per media."""
        return {**super()._message_fields(), 'instagram': 'instagram_message'}

    @api.model
    def _images_fields(self):
        """Return the images field per media."""
        return {**super()._images_fields(), 'instagram': 'instagram_image_ids'}

    @api.model
    def _first_comment_fields(self):
        """Return the "first comment" field per media."""
        return {**super()._first_comment_fields(), 'instagram': 'instagram_first_comment'}

    def _prepare_social_post_values(self):
        """Return the values to generate a social post from the social post template."""
        self.ensure_one()
        return {
            **super()._prepare_social_post_values(),
            'instagram_post_as_story': self.instagram_post_as_story,
        }
