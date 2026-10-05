# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from collections import defaultdict
from textwrap import dedent
from typing import Unpack

import lxml.html

from odoo import Command, _, api, fields, models
from odoo.exceptions import MissingError, UserError, ValidationError
from odoo.tools import BinaryBytes, SQL, file_open, is_html_empty
from odoo.tools.misc import mute_logger

from odoo.addons.iap import InsufficientCreditError
from odoo.addons.mail.tools.discuss import Store

from odoo.addons.ai.models.ai_agent_source import AIAgentSource
from odoo.addons.ai.utils.ai_citation import (
    apply_numeric_citations,
    get_sources_ids_from_text,
)
from ..utils.ai_utils import (
    get_text_from_parts,
    markdown_format,
)
from ..utils.agent_instructions_prompts import (
    DEFAULT_SYSTEM_PROMPT,
    get_global_protocol,
    RAG_SOURCES_FORMAT,
    RESTRICT_TO_SOURCES,
    SKILLS_PROTOCOL,
)
from ..utils.types import AIMessageParts, CompletionOptions

_logger = logging.getLogger(__name__)


DEFAULT_TOOLS = [
    "ai.ir_actions_server_load_skills",
]


class AIAgent(models.Model):
    _name = 'ai.agent'
    _description = "AI Agent"
    _order = 'sequence, name'

    def _default_skill_ids(self):
        # a new agent starts with the built-in (native) skills on
        return self.env['ai.skill'].search([('is_native_skill', '=', True)])

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10, help="Built-in agents ship with a sequence below 10 to be listed first; custom agents default after them.")
    name = fields.Char(string="Agent Name", related='partner_id.name', required=True, readonly=False)
    subtitle = fields.Char(string="Description")
    system_prompt = fields.Text(string="System Prompt", help="Customize to control relevance and formatting.")

    restrict_to_sources = fields.Boolean(
        string="Restrict to Sources",
        help="If checked, the agent will only respond based on the provided sources.")
    image_128 = fields.Image("Image", related="partner_id.image_1920", max_width=128, max_height=128, readonly=False)
    avatar_128 = fields.Image("Avatar", related="partner_id.avatar_128")
    skill_ids = fields.Many2many(
        'ai.skill',
        string="Skills",
        default=lambda self: self._default_skill_ids(),
        help="A skill includes instructions and tools that guide Odoo AI in helping the user complete their tasks.",
    )
    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)

    is_system_agent = fields.Boolean('System Agent', default=False)

    sources_ids = fields.One2many(
        'ai.agent.source',
        'agent_id',
        string="Sources",
        domain=[('parent_id', '=', False)],
    )
    embedding_model = fields.Char()
    allowed_agent_ids = fields.Many2many('ai.agent', 'ai_agent_delegation_rel', 'parent_id', 'child_id', string="Allowed Agents")

    @api.model_create_multi
    def create(self, vals_list):
        install_mode = self.env.context.get('install_mode')
        embedding_model = None if install_mode else self.env["ai.embedding"]._get_default_embedding_model()
        for vals in vals_list:
            self._check_values_allowed(vals)
            partner = self.env['res.partner'].create({
                'name': vals.get('name'),
                'active': False,
            })
            vals['partner_id'] = partner.id
            if not install_mode:
                vals["embedding_model"] = embedding_model
        ai_agents = super().create(vals_list)
        agents_no_image = ai_agents.filtered(lambda agent: not agent.image_128)
        if agents_no_image:
            agents_no_image.image_128 = self._get_default_image()
        return ai_agents

    def write(self, vals):
        self._check_values_allowed(vals)
        if 'image_128' in vals and not vals['image_128']:
            vals['image_128'] = self._get_default_image()
        old_skills = {agent.id: agent.skill_ids for agent in self}

        result = super().write(vals)

        if agents_with_unlinked_skills := self.filtered(lambda agent: old_skills[agent.id] - agent.skill_ids):
            sessions = self.env['ai.session'].search([('agent_id', 'in', agents_with_unlinked_skills.ids)])
            sessions._clean_session_state()
        return result

    @api.model
    def _get_default_image(self):
        with file_open('ai/static/description/icon.png', 'rb') as f:
            return BinaryBytes(f.read())

    def _check_values_allowed(self, vals):
        if 'partner_id' in vals:
            raise ValidationError(_("The partner linked to an AI agent can't be changed"))

    @api.ondelete(at_uninstall=False)
    def _unlink_sources(self):
        """Delete sources (and their attachments) when an agent is deleted."""
        for agent in self:
            all_source_records = agent._get_all_source_records()
            if all_source_records:
                all_source_records.unlink()

    @api.ondelete(at_uninstall=False)
    def _unlink_empty_ai_chat_channels(self):
        """Remove empty AI chats before deleting their agent."""
        self.env['discuss.channel'].sudo().search([
            ('ai_agent_id', 'in', self.ids),
            ('channel_type', '=', 'ai_chat'),
            ('has_message', '=', False),
        ]).unlink()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_system_agent(self):
        """Prevent deletion of system agents."""
        system_agents = self.filtered('is_system_agent')
        if system_agents:
            raise UserError(_("System agents cannot be deleted."))

    def _get_all_source_records(self):
        """
        Get all source records for the agent.

        :return: recordset of all source records
        :rtype: ai.agent.source recordset
        """
        self.ensure_one()
        return self.sources_ids._get_descendants() | self.sources_ids

    @api.model
    def action_launch_ai_chat(self, interface_key, res_model=None, res_id=None, channel_title=None, text_selection=None, text_of_editable=None, reference_image_path=None):
        if res_model:
            res_id = int(res_id)
            # don't allow to create chat linked to a record the user cannot access
            self.env[res_model].browse(res_id).check_access('read')

        ai_composer = self.env['ai.composer']._get_composer_from_key_and_model(interface_key, res_model)
        if not (agent := ai_composer._get_agent(res_model, res_id)).exists():
            raise MissingError(self.env._("AI not reachable, AI Agent not found."))

        if not channel_title and res_model:
            channel_title = self.env[res_model].browse(res_id).display_name
        channel = agent._create_ai_chat_channel(channel_title)
        create_vals = {
            'agent_id': agent.id,
            'ai_composer_id': ai_composer.id,
            'channel_id': channel.id,
            'res_model': res_model,
            'res_id': res_id,
        }
        if context_message := ai_composer._get_initial_context(res_model, res_id, text_selection, text_of_editable, reference_image_path):
            create_vals['event_ids'] = [
                Command.create({
                    'metadata': {
                        'role': 'user',
                        'content': context_message,
                    },
                })
            ]
        self.env['ai.session'].sudo().create(create_vals)

        model_has_thread = res_model and isinstance(self.env[res_model], self.pool['mail.thread'])
        store = Store()
        store.add(
            channel,
            lambda res: (
                res.attr('are_prompts_from_local_storage', False),
                res.from_method('_store_channel_fields'),
                res.many('ai_prompt_buttons', ['id', 'name', 'prompt', 'sequence'], value=ai_composer._get_random_prompts(3, not model_has_thread)),
            )
        )

        return {
            'ai_channel_id': channel.id,
            'data': store,
            'model_has_thread': model_has_thread
        }

    def _build_rag_context(self, prompt):
        self.ensure_one()
        non_folder_sources = self._get_all_source_records().filtered(lambda s: not s.is_folder and s.is_active)
        if not non_folder_sources:
            return None
        context = ""
        embedding_model = self.embedding_model
        try:
            response = self.env['ai.embedding']._get_embeddings(
                input=[{'content': prompt}],
                model=embedding_model,
                mode='query',
            )
        except InsufficientCreditError:
            return None

        embedding = response['embeddings'][0]
        target_per_model = non_folder_sources._get_target_per_model()
        similar_embeddings = self.env['ai.embedding']._get_similar_chunks(
            query_embedding=embedding,
            target_per_model=target_per_model,
            embedding_model=embedding_model,
            top_n=5,
        )
        if not similar_embeddings:
            return None
        agent_sources = self.env['ai.agent.source'].with_context(
            skip_res_field_check=True,
        ).search([
            ('agent_id', '=', self.id),
        ])
        source_map = defaultdict(AIAgentSource)
        for source in agent_sources:
            if target := source._get_target_records():
                source_map[target._name, target.id] = source
        for embedding in similar_embeddings:
            if agent_source := source_map.get((embedding.res_model, embedding.res_id)):
                context += (
                    f"(Source Chunk {agent_source.name})\n"
                    f"(source_id: {agent_source.id})\n"
                    f"{embedding.content}\n\n"
                )
        return context

    def _get_llm_response_with_sources(self, llm_text_response):
        """
        Parses inline citations (e.g., [SOURCE:210]) from each LLM message,
        replaces them with clickable sequential superscript numbers, and enriches
        the message content with a numbered list of corresponding source names
        and links.

        :param llm_text_response: The text response from the LLM
        :type llm_text_response: str
        :return: The text response with the sources added if any
        :rtype: str
        """
        link_attrs = 'target="_blank" rel="noreferrer noopener"'

        unique_sources_ids = get_sources_ids_from_text(llm_text_response)
        source_data = {}
        accessible_sources = self.env['ai.agent.source']
        if unique_sources_ids:
            sources = self.env['ai.agent.source'].search([
                ('id', 'in', unique_sources_ids),
                ('agent_id', '=', self.id),
            ])
            accessible_sources = sources.filtered(lambda s: s.user_has_access)
            for source in accessible_sources:
                source_data[source.id] = source

            return apply_numeric_citations(llm_text_response, source_data, link_attrs=link_attrs)

        return llm_text_response

    def _eval_ai_prompts(self, rendered_html, remove_prompts=False, ai_context=""):
        """Evaluate AI prompts in the given HTML content"""
        if is_html_empty(rendered_html):
            return rendered_html

        Wrapper = rendered_html.__class__
        root = lxml.html.fromstring(rendered_html)

        prompt_containers = root.xpath("//div[hasclass('o_editor_prompt')]")

        root_is_prompt = root in prompt_containers

        if root_is_prompt:
            root = lxml.html.fromstring(f'<div>{rendered_html}</div>')
            prompt_containers = root.xpath("//div[hasclass('o_editor_prompt')]")

        if not prompt_containers:
            return Wrapper(rendered_html)

        for container in prompt_containers:
            prompt_content_elements = container.xpath(
                ".//div[hasclass('o_editor_prompt_content')]"
            )

            if remove_prompts:
                container.getparent().remove(container)
                continue

            if not prompt_content_elements:
                container.getparent().remove(container)
                continue

            assert (
                len(prompt_content_elements) == 1
            ), "There should be only one prompt content element inside a prompt container."
            prompt_text = prompt_content_elements[0].text_content().strip()

            if not prompt_text:
                container.getparent().remove(container)
                continue

            input_parts = [{'type': 'text', 'text': prompt_text}]
            response_parts = self._generate_single_response(input_parts, extra_instructions=ai_context)
            container.getparent().replace(container, lxml.html.fromstring(markdown_format(get_text_from_parts(response_parts))))

        return Wrapper(lxml.html.tostring(root, encoding="unicode", method="html"))

    def _create_ai_chat_channel(self, channel_name=None):
        # The method is called in three safe scenarios:
        # - Testing: An admin is creating a channel (from the test button in the AI app) to test an AI agent's configuration.
        # - Internal Features: An internal user is creating a channel for features like `ai_composer`.
        # - Public Access: A public/portal user is creating a channel (through livechat for example).
        #   The access to the agent is verified by the `_is_user_access_allowed` method.
        # In all cases, the channel is created between the AI agent and the current user, so using sudo() for channel creation is safe.

        guest = self.env["mail.guest"]._get_guest_from_context()
        with mute_logger("odoo.sql_db"):
            self.env.cr.execute(SQL(
                "SELECT pg_advisory_xact_lock(%s, %s) NOWAIT;",
                guest.id if self.env.user._is_public() else self.env.user.partner_id.id,
                self.id
            ))

        channel = self.env['discuss.channel'].sudo().create({
            "ai_agent_id": self.id,
            "channel_member_ids": [
                Command.create({"guest_id": guest.id} if self.env.user._is_public() else {"partner_id": self.env.user.partner_id.id}),
                Command.create({"partner_id": self.partner_id.id}),
            ],
            "channel_type": "ai_chat",
            # sudo() => visitor can set the name of the channel
            "name": channel_name if channel_name else "",
        })
        return channel

    def _generate_single_response(
        self,
        message: AIMessageParts,
        extra_instructions: str | None = None,
        schema=None,
        **completion_options: Unpack[CompletionOptions],
    ) -> AIMessageParts:
        """Get a one-shot LLM response using this agent's configuration.

        Convenience wrapper around ai.session._get_direct_response() that uses the agent's system_prompt.

        :param message: the user message
        :param extra_instructions: Additional context appended to system_prompt
        """
        self.ensure_one()
        prompt = get_text_from_parts(message)
        if rag := self._build_rag_context(prompt):
            message = [part for part in message if part['type'] != 'text']
            message.insert(0, {
                'type': 'text',
                'text': f"# User message\n{prompt}\n# RAG\n{rag}",
            })

        return self.env['ai.session']._get_direct_response(
            instructions=self._get_instructions(extra_instructions),
            message=message,
            schema=schema,  # schema with tools?
            # sudo: tool_ids has group_system on skills
            tools=self._get_default_tools(),
            agent_id=self.id,
            usage=self._get_usage_string(),
            **completion_options,
        )

    def _get_instructions(self, extra_instructions=None, restrict_to_resources_override=None):
        """Build the full instruction prompt for an agent.

        The prompt is composed of separate protocol sections so each layer of
        instructions has a clear scope:
        - global_protocol: shared by every agent; contains safety rules and general
            behavior instructions.
        - agent_protocol: specific to the agent; defines its personality, style, and
            role-specific behavior.
        - usage_context: specific to the current usage surface, such as conversation
            mode or assistance while drafting a message, article, image, ...
        - knowledge_protocol: added when sources are configured; defines how the
            agent should use RAG knowledge and source restrictions.
        - skills_protocol: added when skills are available; defines how the agent
            should load skills, use their instructions, and interact with their tools.

        The final output is wrapped in explicit start/end markers and consumed as
        the system-level instruction block for the agent.
        """
        self.ensure_one()

        def section(name, content):
            content = dedent(content or "").strip()
            if not content:
                return ""
            return f"<{name}>\n{content}\n</{name}>\n\n"

        instructions = "[[START OF INSTRUCTIONS]]\n\n"
        instructions += section("global_protocol", get_global_protocol(self.env.context.get('debug'), self.env.tz))
        instructions += section("agent_protocol", self.system_prompt or DEFAULT_SYSTEM_PROMPT)
        instructions += section("agent_setup_state", self._get_setup_protocol())

        if extra_instructions:
            instructions += section("usage_context", extra_instructions)

        if self.sources_ids:
            knowledge_protocol_parts = [RAG_SOURCES_FORMAT]
            restrict_to_resources = (
                self.restrict_to_sources if restrict_to_resources_override is None else restrict_to_resources_override
            )
            if restrict_to_resources:
                knowledge_protocol_parts.append(RESTRICT_TO_SOURCES)

            instructions += section(
                "knowledge_protocol",
                "\n\n".join(knowledge_protocol_parts),
            )

        available_skills = self._get_available_skills()
        if available_skills:
            instructions += section("skills_protocol", self._get_skills_protocol())

            skills = []
            for skill in available_skills:
                skills.append(f'<skill id="{skill.id}" name="{skill.name}" type="{skill.type}">{skill.description}</skill>')

            instructions += section("available_skills", "\n".join(skills))

        other_skills = self.env['ai.skill'].sudo().search([('id', 'not in', available_skills.ids)])
        if other_skills:
            others = [f'<skill id="{skill.id}" name="{skill.name}" type="{skill.type}">{skill.description}</skill>'
                      for skill in other_skills]
            instructions += section("other_skills", "\n".join(others))

        instructions += "[[END OF INSTRUCTIONS]]"
        return instructions

    def _get_available_skills(self):
        """Skills that may be advertised and loaded in the current context."""
        self.ensure_one()
        return self.skill_ids

    def _get_setup_protocol(self):
        """Self-configuration guidance, provided by the modules shipping the
        tools for it (`ai_agentic`)."""
        return ""

    def _get_skills_protocol(self):
        """The skill loading rules; extended by the modules adding skills whose
        loading needs rules of its own."""
        return SKILLS_PROTOCOL

    def _get_default_tools(self):
        self.ensure_one()
        tools = self.env["ir.actions.server"]

        for tool_xmlid in DEFAULT_TOOLS:
            if tool := self.env.ref(tool_xmlid, raise_if_not_found=False):
                tools |= tool
        return tools

    def _is_user_access_allowed(self):
        self.ensure_one()
        return self.env.user._is_internal()

    @api.ormcache('self.env.uid', 'self.env.company.id')
    def _get_available_menus(self):
        """Get all menus accessible to the current user as CSV data."""
        all_menus = self.env["ir.ui.menu"].load_web_menus(False)
        root_menu_ids = set(all_menus["root"]["children"])

        # Collect all non-root action menus
        action_menus = []
        for menu_id, web_menu in all_menus.items():
            if menu_id == "root" or (
                web_menu.get("actionModel") != "ir.actions.client"
                and menu_id in root_menu_ids
            ):
                continue

            # Only process menus with valid actions
            if web_menu["actionModel"] in [
                "ir.actions.act_window",
                "ir.actions.client",
                "ir.actions.report",
            ]:
                menu = self.env["ir.ui.menu"].browse(web_menu["id"])
                app_menu = self.env["ir.ui.menu"].browse(web_menu["appID"])

                if not menu.exists():
                    continue

                action = self.sudo().env[web_menu["actionModel"]].browse(web_menu["actionID"])

                if action.exists():
                    action_menus.append(
                        {
                            "menu": menu,
                            "web_menu": web_menu,
                            "action": action,
                            "app_menu": app_menu,
                        }
                    )

        # Menus are already ordered by sequence from load_web_menus(), but we still need to sort
        # by complete_name within each app to maintain proper hierarchy display
        action_menus.sort(key=lambda m: (m["app_menu"].sequence, m["menu"].complete_name))

        csv_result = "menu_id|action_id|action_type|complete_name|model|action_explanation|available_view_types|default_view_type\n"

        for menu_data in action_menus:
            menu = menu_data["menu"]
            action = menu_data["action"]

            model_name = (action.res_model if action.type != "ir.actions.report" else action.model)
            action_explanation = action.explanation or ""

            available_view_types = ([view[1] for view in action.views] if action.type == "ir.actions.act_window" and action.views else [])
            default_view_type = (available_view_types[0] if available_view_types else "null")
            if action.type == "ir.actions.act_window" and action.view_id:
                default_view_type = action.view_id.type

            csv_result += (
                f"{menu.id}|"
                f"{action.id}|"
                f"{action.type}|"
                f"{menu.complete_name}|"
                f"{model_name or ''}|"
                f"{action_explanation.replace('|', ' ').replace('\\n', ' ')}|"
                f"{','.join(available_view_types)}|"
                f"{default_view_type}\n"
            )
        return f"# Available Menus\n{csv_result}"

    def _store_agent_fields(self, res: Store.FieldList):
        res.extend(["partner_id", "subtitle", "name"])
        xml_id = self.env['ir.model.data'].search_read(
            [('model', '=', 'ai.agent'), ('res_id', '=', self.id)], ['complete_name'], limit=1)
        res.attr("xml_id", xml_id[0]['complete_name'] if xml_id else False)
        res.attr("sources_ids")

    def _get_usage_string(self):
        self.ensure_one()
        agent_xmlid = self.get_metadata()[0].get('xmlid')
        return f'agent:{agent_xmlid or 'custom'}'
