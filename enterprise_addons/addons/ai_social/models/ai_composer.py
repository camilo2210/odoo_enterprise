import json

from odoo import api, fields, models


class AIComposer(models.Model):
    _name = "ai.composer"
    _inherit = ["ai.composer"]

    interface_key = fields.Selection(
        selection_add=[("text_field_social", "Write a social post")],
        ondelete={"text_field_social": "cascade"},
    )

    @api.depends("interface_key")
    def _compute_hide_model_selection(self):
        super()._compute_hide_model_selection()
        for rule in self:
            rule.hide_model_selection = (
                rule.hide_model_selection or rule.interface_key == "text_field_social"
            )

    def _get_initial_context(self, res_model=None, res_id=None, text_selection=None, text_of_editable=None, reference_image_path=None):
        """Allow to add information about the social post, without saving the form."""
        parts = super()._get_initial_context(res_model, res_id, text_selection, text_of_editable, reference_image_path)
        if self.interface_key != "text_field_social":
            return parts

        if post_data := self.env.context.get('ai_social_post_values'):
            parts.append({'type': 'text', 'text': json.dumps(post_data)})

        return parts
