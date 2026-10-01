# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AIComposer(models.Model):
    _inherit = 'ai.composer'

    interface_key = fields.Selection(
        selection_add=[
            ("website_seo_ai", "Optimize the SEO of their website pages"),
            ('website_builder_ai', 'Edit a website page'),
        ],
        ondelete={
            "website_seo_ai": "cascade",
            "website_builder_ai": "cascade",
        },
    )

    @api.depends("interface_key")
    def _compute_hide_model_selection(self):
        super()._compute_hide_model_selection()
        for rule in self:
            rule.hide_model_selection = rule.hide_model_selection or rule.interface_key in (
                "website_seo_ai", "website_builder_ai")

    @api.depends("interface_key")
    def _compute_hide_prompt_button_page(self):
        super()._compute_hide_prompt_button_page()
        for rule in self:
            rule.hide_prompt_button_page = rule.hide_prompt_button_page or rule.interface_key in ("website_seo_ai", "website_builder_ai")

    def _get_initial_context(self, res_model=None, res_id=None, text_selection=None,
                             text_of_editable=None, reference_image_path=None):
        parts = super()._get_initial_context(
            res_model=res_model, res_id=res_id, text_selection=text_selection,
            text_of_editable=text_of_editable, reference_image_path=reference_image_path,
        )
        if self.interface_key != 'website_builder_ai':
            return parts

        parts.append({'type': 'text', 'text': self.env['ai.website.service']._create_snippets_list()})
        return parts
