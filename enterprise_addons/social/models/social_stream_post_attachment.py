from odoo import models, fields


class SocialStreamPostAttachment(models.Model):
    """
    A social.stream.post.attachment represents the content that was shared with a social.stream.post.
    It includes the type of content, the URL, and the thumbnail associated with the relevant social media.
    """

    _name = 'social.stream.post.attachment'
    _description = 'Social Stream Post Attachment'

    attachment_content_type = fields.Selection([('image', 'Image'), ('video', 'Video')], default='image', required=True)
    content_url = fields.Char('Content URL', required=True, readonly=True)
    stream_post_id = fields.Many2one('social.stream.post', string='Stream Post', required=True, index=True, ondelete='cascade')
    thumbnail_url = fields.Char('Thumbnail URL')
