# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    def _ai_get_preview_metadata(self):
        """Extend preview metadata with linked product prices."""
        metadata = super()._ai_get_preview_metadata()
        channels_with_product = self.filtered('product_id')
        if not channels_with_product:
            return metadata

        product_id_by_channel_id = {
            channel.id: channel.product_id.id
            for channel in channels_with_product
        }
        combo_info = (
            channels_with_product.mapped('product_id').sudo()._resolve_product_combination_info()
        )
        for entry in metadata:
            entry.update(combo_info.get(product_id_by_channel_id.get(entry['id']), {}))
        return metadata
