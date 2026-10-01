# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _can_bypass_rights_on_media_dialog(self, **attachment_data):
        res_id = attachment_data.get('res_id')
        res_model = attachment_data.get('res_model')
        if res_id and res_model == "knowledge.article":
            article = self.env[res_model].browse(res_id)
            if article and article.user_can_write:
                return True
        return super()._can_bypass_rights_on_media_dialog(**attachment_data)
