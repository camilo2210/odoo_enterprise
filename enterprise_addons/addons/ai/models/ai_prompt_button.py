from logging import getLogger

from odoo import api, fields, models
from odoo.tools import is_html_empty

from odoo.addons.ai.utils.ai_fields_tools import parse_ai_prompt_values

_logger = getLogger(__name__)


class AIPromptButton(models.Model):
    _name = "ai.prompt.button"
    _inherit = ["mail.render.mixin"]
    _description = "Default action prompt that can be attached to AI UI rules for quick access by the user."

    name = fields.Char(
        "Title", help="The text shown on the button", required=True
    )
    prompt = fields.Html(
        help="The prompt that will be sent to the AI when the button is clicked",
        render_engine='qweb', render_options={'post_process': True}, prefetch=True,
        translate=True, sanitize=True, sanitize_output_method='xml'
    )
    sequence = fields.Integer(string="Sequence", default=10)
    composer_id = fields.Many2one("ai.composer", index='btree_not_null')

    @api.depends('composer_id.focused_model_id.model')
    def _compute_render_model(self):
        for button in self:
            button.render_model = button.composer_id.focused_model_id.model

    def _render_prompt(self, rendering_record_id=None):
        self.ensure_one()

        rendering_record = None
        # sudo: ir_model records can't be accessed by base.group_user. If the user doesn't have access to the record,
        # the search method will return an empty recordset.
        if render_model := self.sudo().render_model:
            rendering_record = self.env[render_model].search([('id', '=', rendering_record_id)])
        if not is_html_empty(self.prompt) and rendering_record:
            # Perform any qweb rendering other than replacing field references.
            prompt = self._render_field(field="prompt", res_ids=rendering_record.ids)[rendering_record.id]
            # Replace field references
            prompt, field_names, __ = parse_ai_prompt_values(env=self.env, prompt=prompt, comodel=None)
            field_values, message_parts = rendering_record._get_ai_context(field_names)
            prompt += f"\n# field values\n{field_values}"
            message_parts.insert(0, {'type': 'text', 'text': prompt})
        else:
            message_parts = [{'type': 'text', 'text': self.prompt if not is_html_empty(self.prompt) else self.name}]
        return message_parts
