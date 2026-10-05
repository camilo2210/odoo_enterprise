# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class SocialPost(models.Model):
    _inherit = 'social.post'

    linkedin_image_ids = fields.Many2many(relation='linkedin_image_ids_rel')
    linkedin_scheduled_date = fields.Datetime(
        string='LinkedIn Scheduled for',
        compute='_compute_scheduled_date_by_media',
        store=True, readonly=False, copy=False)

    @api.depends('live_post_ids.linkedin_post_id')
    def _compute_stream_posts_count(self):
        super()._compute_stream_posts_count()

    @api.model
    def _scheduled_date_fields(self):
        return {**super()._scheduled_date_fields(), 'linkedin': 'linkedin_scheduled_date'}

    def _get_stream_post_domain(self):
        domain = super()._get_stream_post_domain()
        linkedin_post_ids = [linkedin_post_id for linkedin_post_id in self.live_post_ids.mapped('linkedin_post_id') if linkedin_post_id]
        if linkedin_post_ids:
            return Domain.OR([domain, [('linkedin_post_urn', 'in', linkedin_post_ids)]])
        else:
            return domain
