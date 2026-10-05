from odoo import models


class ProductImage(models.Model):
    _inherit = 'product.image'

    def _ai_read(self, fnames=None, files_parts=None, files_checksums=None):
        if fnames:
            return super()._ai_read(fnames, files_checksums)

        if files_checksums is None:
            files_checksums = set()

        __, files_parts, files_checksums = super()._ai_read(fnames, files_parts, files_checksums)
        product_tmpl_id = self.product_tmpl_id if self.product_tmpl_id else self.product_variant_id.product_tmpl_id
        tmpl_vals_list, files_parts, __ = product_tmpl_id._ai_read(['display_name', 'type', 'description', 'description_sale'], files_parts, files_checksums)
        return tmpl_vals_list, files_parts
