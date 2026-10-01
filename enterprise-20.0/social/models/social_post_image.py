# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SocialPostImage(models.Model):
    """Image that is used to send in post, can be re-ordered."""

    _name = "social.post.image"
    _description = "Social Post Image"
    _order = 'sequence, id'

    attachment_id = fields.Many2one(
        "ir.attachment", string="Attachment",
        required=True, ondelete='cascade', index=True)
    sequence = fields.Integer("Sequence", default=10)

    name = fields.Char("Name", related="attachment_id.name")
    raw = fields.Binary("Raw", related="attachment_id.raw")
    mimetype = fields.Char("Mimetype", related="attachment_id.mimetype")
    file_size = fields.Integer("File Size", related="attachment_id.file_size")

    @api.model_create_multi
    def create(self, vals_list):
        images = super().create(vals_list)
        images.attachment_id.check_access('read')

        if any(field in vals for field in ('name', 'raw', 'mimetype', 'file_size') for vals in vals_list):
            images.attachment_id.check_access('write')

        return images

    def write(self, vals):
        res = super().write(vals)
        if 'attachment_id' in vals:
            self.attachment_id.check_access('read')

        if any(field in vals for field in ('name', 'raw', 'mimetype', 'file_size')):
            self.attachment_id.check_access('write')

        return res

    @api.onchange("attachment_id")
    def _onchange_attachment_id(self):
        self.attachment_id.check_access('read')
