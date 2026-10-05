# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AIComposer(models.Model):
    _inherit = 'ai.composer'

    interface_key = fields.Selection(
        selection_add=[
            ("campaign_builder_ai", "Create and edit a marketing campaign"),
        ],
        ondelete={
            "campaign_builder_ai": "cascade",
        },
    )

    @api.depends("interface_key")
    def _compute_hide_model_selection(self):
        super()._compute_hide_model_selection()
        for rule in self:
            rule.hide_model_selection = rule.hide_model_selection or rule.interface_key in ['campaign_builder_ai']

    @api.depends("interface_key")
    def _compute_hide_prompt_button_page(self):
        super()._compute_hide_prompt_button_page()
        for rule in self:
            rule.hide_prompt_button_page = rule.hide_prompt_button_page or rule.interface_key in ['campaign_builder_ai']
