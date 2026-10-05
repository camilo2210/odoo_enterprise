# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

from ..utils.urbanpiper_translation import get_urbanpiper_translation
from ..utils.urbanpiper_image_url import get_urbanpiper_image_url


class PosCategory(models.Model):
    _inherit = 'pos.category'

    def _prepare_urbanpiper_data(self, urbanpiper_store, is_required_other_category=False):
        """
        # Part of Menu Sync
        Prepare UrbanPiper category payload for menu sync.

        Builds category data for the current category and its parent
        (UrbanPiper supports only one level). Optionally appends an
        "Other" category for products without a POS category.
        """
        categories = self | self.parent_id  # No need to recurse as UrbanPiper only supports one level of child categories

        def format_data(category):
            name_translations = category.get_field_translations('name')
            data = {
                'ref_id': str(category.id),
                'name': category.with_context(lang='en_US').name,
                'sort_order': category.sequence,
                'active': True,
                'translations': get_urbanpiper_translation({'name': name_translations}),
            }
            if img_url := get_urbanpiper_image_url(urbanpiper_store, category):
                data['img_url'] = img_url
            if category.parent_id in categories:
                data['parent_ref_id'] = str(category.parent_id.id)
            return data

        data_list = [format_data(catg) for catg in categories]
        if is_required_other_category:
            # Append a fallback category for products without a POS category
            other_catg_data = {
                'ref_id': '0',
                'name': 'Other',
                'sort_order': 999,
                'active': True,
            }
            data_list.append(other_catg_data)
        return data_list
