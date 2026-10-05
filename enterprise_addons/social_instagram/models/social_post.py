# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class SocialPost(models.Model):
    _inherit = 'social.post'

    instagram_image_ids = fields.Many2many(relation='instagram_image_ids_rel')
    instagram_scheduled_date = fields.Datetime(
        string='Instagram Scheduled for',
        compute='_compute_scheduled_date_by_media',
        store=True, readonly=False, copy=False)

    @api.depends('live_post_ids.instagram_post_id')
    def _compute_stream_posts_count(self):
        super()._compute_stream_posts_count()

    @api.model
    def _scheduled_date_fields(self):
        return {**super()._scheduled_date_fields(), 'instagram': 'instagram_scheduled_date'}

    def _check_post_access(self):
        """ See #_get_instagram_image_error() for more information. """
        super()._check_post_access()

        for post in self:
            if 'instagram' in post.media_ids.mapped('media_type'):
                faulty_images, image_error_code = post._get_instagram_image_error()
                if image_error_code == 'missing':
                    raise ValidationError(_('At least one image is required when posting on Instagram.'))
                elif image_error_code == 'wrong_extension':
                    raise ValidationError(
                        _(
                            "The following images are not in the correct format (jpg/jpeg).\n\n%(images)s",
                            images="\n".join(f"- {faulty_image}" for faulty_image in faulty_images),
                        ),
                    )
                elif image_error_code == 'incorrect_ratio':
                    raise ValidationError(
                        _(
                            "The following images do not meet the required aspect ratio (between 1.91:1 and 4:5).\n\n%(images)s",
                            images="\n".join(f"- {faulty_image}" for faulty_image in faulty_images),
                        ),
                    )
                elif image_error_code == 'corrupted':
                    raise ValidationError(_('Your image appears to be corrupted, please try loading it again.'))
                elif image_error_code == 'max_limit':
                    raise ValidationError(_('You can only post up to 10 images at once.'))

    def _get_stream_post_domain(self):
        domain = super()._get_stream_post_domain()
        instagram_post_ids = [instagram_post_id for instagram_post_id in self.live_post_ids.mapped('instagram_post_id') if instagram_post_id]
        if instagram_post_ids:
            return Domain.OR([domain, [('instagram_post_id', 'in', instagram_post_ids)]])
        else:
            return domain

    @api.model
    def _cron_publish_scheduled(self):
        super()._cron_publish_scheduled()

        domain = Domain([
            ('account_id.media_type', '=', 'instagram'),
            ('state', '=', 'posting'),
            ('instagram_post_id', '=like', 'containerID-%'),
        ]) & (
            Domain('post_id.instagram_scheduled_date', '=', False)
            | Domain('post_id.instagram_scheduled_date', '<=', fields.Datetime.now())
        )

        instagram_live_posts = self.env['social.live.post'].search(domain)

        for live_post in instagram_live_posts:
            live_post._post_instagram()
