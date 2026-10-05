import json

from odoo import models
from odoo.exceptions import MissingError
from odoo.addons.ai.utils.ai_image_tools import retrieve_image_parts_from_path


class AIComposer(models.Model):
    _inherit = 'ai.composer'

    def _get_initial_context(self, res_model=None, res_id=None, text_selection=None, text_of_editable=None, reference_image_path=None):
        parts = super()._get_initial_context(res_model, res_id, text_selection, text_of_editable, reference_image_path)
        if self.interface_key != "chatter_ai_button" or (res_model != 'product.template' and res_model != 'product.product'):
            return parts

        if not (record := self.env[res_model].browse(res_id)).exists():
            raise MissingError(self.env._("The record linked to this session has not been found."))

        parts += retrieve_image_parts_from_path(self.env, f'/web/image/{record._name}/{record.id}/image_1024')
        parts.append({
            'type': 'text',
            'text': json.dumps({
                'product_name': record.name,
                'product_description': record.description,
                'product_description_sale': record.description_sale,
                'product_type': record.type,
            })
        })
        return parts
