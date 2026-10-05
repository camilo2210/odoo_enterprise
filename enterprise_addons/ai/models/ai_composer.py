# Part of Odoo. See LICENSE file for full copyright and licensing details.

import random

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.ai.utils.ai_image_tools import retrieve_image_parts_from_path
from odoo.addons.mail.tools.discuss import Store


INTERFACE_KEYS = [
    ("html_field_record", "Write in an HTML field"),
    ("mail_composer", "Write an email"),
    ("html_field_text_select", "Rewrite content"),
    ("chatter_ai_button", "Get help on a record"),
    ("html_prompt_shortcut", "Convert a prompt in an email"),
    ("systray_ai_button", "Ask AI for help"),
    ("voice_transcription_component", "Summary Buttons for Voice Transcription Component"),
    ("file_viewer_ai_button", "Get help on a file attachment"),
    ('media_dialog', "Generate images inside the media manager"),
]


class AIComposer(models.Model):
    _name = "ai.composer"
    _description = "AI model configurations (Default Prompt) for text drafting."
    _explanation = "Configures AI-assisted drafting components (e.g., email rewriting, HTML field assistance) by linking them with specific AI agents and base prompts."

    _unique_agent_interface_model = models.UniqueIndex(
        "(interface_key, focused_model_id) NULLS NOT DISTINCT",
        "A rule with this Action and Model combination already exists.",
    )

    def _get_default_agent(self):
        return self.env["ir.model.data"]._xmlid_to_res_id("ai.ai_default_agent")

    name = fields.Char(
        "Rule Name", help="The identifier for the interface component to agent rule", required=True,
    )
    interface_key = fields.Selection(selection=INTERFACE_KEYS, string="Action", required=True)
    focused_model_id = fields.Many2one('ir.model', string="Model", ondelete='cascade')
    ai_agent_id = fields.Many2one('ai.agent', string="Agent", default=_get_default_agent)
    default_prompt = fields.Text("Context")
    is_system_default = fields.Boolean('Is the rule a system default or user created', default=False, readonly=True, copy=False)
    available_prompt_ids = fields.One2many('ai.prompt.button', 'composer_id', string="Available User Prompts")

    hide_prompt_button_page = fields.Boolean(compute="_compute_hide_prompt_button_page")
    hide_model_selection = fields.Boolean(compute="_compute_hide_model_selection")

    @api.ondelete(at_uninstall=False)
    def _unlink_except_default_rules(self):
        if any(rule.is_system_default for rule in self):
            raise UserError(self.env._('System default prompts cannot be removed.'))

    @api.depends('interface_key')
    def _compute_hide_prompt_button_page(self):
        for rule in self:
            rule.hide_prompt_button_page = rule.interface_key in ['html_prompt_shortcut']

    @api.depends('interface_key')
    def _compute_hide_model_selection(self):
        for rule in self:
            rule.hide_model_selection = rule.interface_key in ['html_prompt_shortcut', 'systray_ai_button']

    @api.model
    def _get_composer_from_key_and_model(self, key, res_model):
        """get the composer linked to the given interface_key and model. If no composer is defined
        for them, return the default one for the given interface key
        Usage of sudo because searching based on a ir.model which can't be access by internal users
        """
        return self.sudo().search([
            ('interface_key', '=', key),
            '|',
            ('focused_model_id.model', '=', res_model),
            ('focused_model_id', '=', False),
        ], order='focused_model_id DESC NULLS LAST', limit=1).sudo(False)

    def _get_random_prompts(self, nb_prompts=3, filter_chatter_prompts=False):
        self.ensure_one()
        prompts = self.available_prompt_ids
        # Don't show prompts related to chatter if the model does not inherit from mail.thread
        # (note: name is misleading, 'chatter_ai_button' means 'from the systray in a form view')
        if filter_chatter_prompts and self.interface_key == "chatter_ai_button":
            chatter_prompts = {
                self.env.ref('ai.ai_prompt_summarize_chatter', raise_if_not_found=False),
                self.env.ref('ai.ai_prompt_write_followup_chatter', raise_if_not_found=False),
            }
            prompts = [p for p in prompts if p not in chatter_prompts]
        return self.env['ai.prompt.button'].browse(p.id for p in random.sample(prompts, min(nb_prompts, len(prompts))))

    def _get_initial_context(self, res_model=None, res_id=None, text_selection=None, text_of_editable=None, reference_image_path=None):
        """ Get the initial context (list of message parts) for the session based on the composer's
        interface_key, skills and current record.
        """
        self.ensure_one()
        context_parts = []

        def add_text_part(text):
            context_parts.append({'type': 'text', 'text': text})

        if self.interface_key == "mail_composer":
            # add previous mail.thread messages
            if not res_model or not res_id or not isinstance(self.env[res_model], self.pool['mail.thread']):
                raise ValueError("The record must inherit from 'mail.thread'")
            record = self.env[res_model].browse(res_id)
            add_text_part(f"# Previous Messages of the record's chatter\n{record._ai_serialize_messages_data()}")

        elif self.interface_key == "html_field_text_select":
            add_text_part(f"# Selected text (the part to rewrite)\n{text_selection}")

        elif self.interface_key == "file_viewer_ai_button":
            # add file
            if not res_model == 'ir.attachment' or not res_id or not (attachment := self.env[res_model].search([('id', '=', res_id)])):
                raise ValueError("The record must be a valid attachment")
            context_parts.extend(attachment._ai_read()[1])

        elif self.interface_key == "media_dialog" and reference_image_path:
            context_parts.extend(retrieve_image_parts_from_path(self.env, reference_image_path))

        # if the AI is called from the HTML editor, we pass the editable's text in the context so the AI generates even more accurate drafts
        if self.interface_key in {"html_field_composer", "html_field_record", "html_field_text_select"}:
            if text_of_editable := (text_of_editable or '').strip():
                add_text_part(f"# Complete text\n{text_of_editable}")

        if context_parts:
            context_parts.insert(0, {'type': 'text', 'text': '<initial_session_context>Below is some initial info that might be useful'})
            add_text_part('</initial_session_context>')

        return context_parts

    @api.model
    def retrieve_transcription_composer(self, record_model):
        ai_composer = self._get_composer_from_key_and_model("voice_transcription_component", record_model)
        return {
            'id': ai_composer.id,
            'ai_agent_id': ai_composer.ai_agent_id.id,
            'default_prompt': ai_composer.default_prompt or "",
            'available_prompt_ids': [{'id': p.id, 'name': p.name, 'prompt': p.prompt, 'sequence': p.sequence} for p in ai_composer.available_prompt_ids],
        }

    def _store_composer_fields(self, res: Store.FieldList):
        res.attr("interface_key")

    def _get_agent(self, res_model: str | None = None, res_id: int | None = None):
        self.ensure_one()
        return self.ai_agent_id
