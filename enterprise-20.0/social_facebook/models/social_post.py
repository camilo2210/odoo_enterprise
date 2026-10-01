# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.addons.social_facebook.utils import meta_run_request_batch
from odoo.exceptions import UserError
from odoo.fields import Domain


class SocialPost(models.Model):
    _inherit = 'social.post'

    facebook_image_ids = fields.Many2many(relation='facebook_image_ids_rel')
    facebook_scheduled_date = fields.Datetime(
        string='Facebook Scheduled for',
        compute='_compute_scheduled_date_by_media',
        store=True, readonly=False, copy=False)

    @api.depends('live_post_ids.facebook_post_id')
    def _compute_stream_posts_count(self):
        super()._compute_stream_posts_count()

    @api.model
    def _scheduled_date_fields(self):
        return {**super()._scheduled_date_fields(), 'facebook': 'facebook_scheduled_date'}

    def _get_stream_post_domain(self):
        domain = super()._get_stream_post_domain()
        facebook_post_ids = [facebook_post_id for facebook_post_id in self.live_post_ids.mapped('facebook_post_id') if facebook_post_id]
        if facebook_post_ids:
            return Domain.OR([domain, [('facebook_post_id', 'in', facebook_post_ids)]])
        return domain

    def _format_images_facebook(self, facebook_account_id, facebook_access_token):
        self.ensure_one()

        responses = meta_run_request_batch(self.env, [{
            'url': f"{facebook_account_id}/photos",
            'method': "POST",
            'params': {
                'published': 'false',
                'access_token': facebook_access_token,
            },
            'files': {'source': ('source', image.raw, image.mimetype)},
        } for image in self.facebook_image_ids])

        formatted_images = []
        for post_result in responses:
            if post_result:
                formatted_images.append({'media_fbid': post_result.get('id')})
            else:
                raise UserError(_("We could not upload your image, try reducing its size and posting it again."))
        return formatted_images
