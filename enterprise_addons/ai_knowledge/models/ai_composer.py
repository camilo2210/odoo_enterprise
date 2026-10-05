from odoo import api, fields, models


class AIComposer(models.Model):
    """AI Composer Model Configurations
    It extends the base usage with AI assistant for knowledge functionality
    """

    _name = "ai.composer"
    _inherit = ["ai.composer"]

    interface_key = fields.Selection(
        selection_add=[("html_field_knowledge", "Write a new Knowledge article")],
        ondelete={"html_field_knowledge": "cascade"},
    )

    @api.depends('interface_key')
    def _compute_hide_model_selection(self):
        super()._compute_hide_model_selection()
        for rule in self:
            rule.hide_model_selection = rule.hide_model_selection or rule.interface_key in ['html_field_knowledge']
