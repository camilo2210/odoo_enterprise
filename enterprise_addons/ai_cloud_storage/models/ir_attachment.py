from odoo import models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _retrieve_image_src_and_mimetype(self):
        self.ensure_one()
        if info := self._get_download_info():
            return {'url': info['url'], 'mimetype': self.mimetype}
        return super()._retrieve_image_src_and_mimetype()
