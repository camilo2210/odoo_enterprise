# Part of Odoo. See LICENSE file for full copyright and licensing details.
import random

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.tools import BinaryBytes, file_open

from odoo.addons.ai.utils.ai_utils import markdown_format

AVATAR_NUMBERS = (1, 2, 3)  # silhouettes per color, shared between naked and role variants
AVATAR_COLORS = ('Purple', 'Blue', 'Red', 'Teal', 'Yellow')
AVATAR_ROLES = ('Worker', 'Headset', 'Sales', 'Librarian', 'Hoodie', 'Detective', 'Artist', 'Architect')

NO_CUSTOM_INSTRUCTIONS_NOTE = """
    This agent has no custom instructions yet and runs on a generic default role.
    - Spend the turn on the user's actual request first. Greetings, questions, lookups and one-off tasks (even bulk ones) are WORK — never persist a setup for them.
    - If the message reveals a lasting ROLE — a business domain the agent should specialize in ("we sell tables to companies", "help me qualify inbound leads"), a recurring workflow, or a stated behavior preference ("you are my …", "always …"), you need to first establish its operating framework from the information the user already provided:
      * WHO it works for and targets: industry, product line, geo, customer type.
      * WHAT it should do on each run: sources or steps, quality criteria, roughly how many results.
      If not enough information is provided, ask questions through `ai_tool_ask_user_question` to get the full overview. A turn that only asks questions makes no changes. Any mention of the update should describe what you will change once the user answers, never imply that you have already changed it.
      Once you have the full picture, load the Self Update skill and use it on the exact `ai.agent` id in `<odoo_current_context>` FIRST — persisting its `name`, `subtitle` and full operating framework as `system_prompt` — and only THEN continue the actual work in the same turn. Never invent details the user did not state (e.g. do not write "table manufacturing" when the user only said "we sell tables").
    - A complete one-line behavior preference ("you are my helpdesk triage assistant, always answer briefly") needs NO clarifying questions: commit it immediately as-is.
    - The role belongs to YOU, not to the user: once the update call has succeeded, announce the commit in first person about yourself ("I've set myself up as your lead prospector"), never as something happening to the user ("I've set up your new role"). Use that past tense only after the call returned successfully in this turn.
"""

SELF_UPDATE_SKILLS_PROTOCOL = """
    - If the user asks you to remember a preference or rule, permanently change how you behave, or learn a new skill (e.g. "remember…", "from now on…", "always/never…", "note that…", "stop doing X", "learn how to…"), treat it as a self-configuration request: load the Self Update skill to persist it, instead of only acknowledging it or reaching for a generic create/email tool.
    - For a missing capability, use a matching skill from other_skills. Add it in the agent configuration update, load it after the normal confirmation, and continue. If none exists, state that it is unavailable and stop.
    - A recurring business workflow ("when/whenever a <record> is created/updated, do …", "every day at …, do …") is a request to CREATE an Automation in Odoo. Treat it as a task needing the automation skill — never as a preference to merely remember or acknowledge.
    - The once-per-request limit does not block newly linked skills: after a successful Create Records or Update Records call links skills to the current agent, call `load_skills` with those new skill ids immediately. That follow-up is allowed even if `load_skills` was already used earlier in this request. Never load a skill merely because another agent was changed.
"""


class AIAgent(models.Model):
    _inherit = 'ai.agent'

    # Computed, not stored: the LLM only ever writes this once (self-update),
    # never reads it back, and the avatar image already encodes the role.
    avatar_role = fields.Selection(
        [(role, role) for role in AVATAR_ROLES],
        string="Avatar Role",
        compute='_compute_avatar_role',
        inverse='_inverse_avatar_role',
        readonly=False,
        help="Job role the agent depicts. Setting it redraws the avatar in the agent's own color.",
    )
    automation_ids = fields.One2many(
        'base.automation',
        'ai_agent_id',
        string="Triggers",
        help="Automation rules that run this agent by themselves.",
        context={"active_test": False},
    )
    custom_skill_ids = fields.Many2many(
        'ai.skill',
        compute='_compute_custom_skill_ids',
        inverse='_inverse_custom_skill_ids',
        string="Custom Skills",
        help="Skills configured by the user, excluding built-in native skills.",
    )
    system_prompt_rendered = fields.Html(
        string="Rendered Instructions", compute='_compute_system_prompt_rendered', sanitize_style=True,
        help="Read-only rendering of the Markdown instructions, shown in the agent panel.",
    )

    @api.depends('system_prompt')
    def _compute_system_prompt_rendered(self):
        for agent in self:
            agent.system_prompt_rendered = markdown_format(agent.system_prompt or '')

    @api.depends('skill_ids.is_native_skill')
    def _compute_custom_skill_ids(self):
        for agent in self:
            agent.custom_skill_ids = agent.skill_ids.filtered(lambda skill: not skill.is_native_skill)

    def _inverse_custom_skill_ids(self):
        for agent in self:
            agent.skill_ids = agent.custom_skill_ids | agent.skill_ids.filtered('is_native_skill')

    def _avatar_attachment(self):
        self.ensure_one()
        return self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'res.partner'),
            ('res_field', '=', 'image_1920'),
            ('res_id', '=', self.partner_id.id),
        ], limit=1)

    def _apply_avatar(self, key):
        self.ensure_one()
        with file_open(f'ai/static/avatars/{key}.png', 'rb') as f:
            self.image_128 = BinaryBytes(f.read())
        self._avatar_attachment().name = key

    @api.depends('image_128')
    def _compute_avatar_role(self):
        for agent in self:
            role = (agent._avatar_attachment().name or '').rpartition('-')[2]
            agent.avatar_role = role if role in AVATAR_ROLES else False

    def _inverse_avatar_role(self):
        for agent in self.filtered('avatar_role'):
            base = '-'.join(agent._avatar_attachment().name.split('-')[:2])
            agent._apply_avatar(f"{base}-{agent.avatar_role}")

    def write(self, vals):
        prompt = vals.get('system_prompt')
        if prompt and '\\n' in prompt and '\n' not in prompt:
            # The LLM sometimes double-escapes newlines in its tool arguments
            vals.update(system_prompt=prompt.replace('\\r\\n', '\n').replace('\\n', '\n'))
        return super().write(vals)

    def _store_agent_fields(self, res):
        super()._store_agent_fields(res)
        res.attr("has_automation_channels", self.env.user.has_group('base.group_system') and bool(
            self.env['discuss.channel'].sudo().search_count([
                ('ai_agent_id', '=', self.id), ('from_ai_automation', '=', True),
            ], limit=1)))

    def _get_setup_protocol(self):
        self_update_skill = self.env.ref('ai_agentic.ai_skill_self_update', raise_if_not_found=False)
        if not self_update_skill or self_update_skill not in self._get_available_skills():
            return ""
        if (self.system_prompt or '').strip():
            return ""
        # a blank agent self-configures via Self Update when it detects a role signal
        return NO_CUSTOM_INSTRUCTIONS_NOTE

    def _get_available_skills(self):
        skills = super()._get_available_skills()
        if self.env.context.get('ai_automation_run'):
            self_update_skill = self.env.ref('ai_agentic.ai_skill_self_update', raise_if_not_found=False)
            if self_update_skill:
                skills -= self_update_skill
        return skills

    def _get_skills_protocol(self):
        protocol = super()._get_skills_protocol()
        self_update_skill = self.env.ref('ai_agentic.ai_skill_self_update', raise_if_not_found=False)
        if self_update_skill and self_update_skill in self._get_available_skills():
            protocol += SELF_UPDATE_SKILLS_PROTOCOL
        return protocol

    def _create_ai_automation_channel(self, channel_name, kickoff_body):
        """Create the inspection channel of an automation run: OdooBot posts
        the kickoff and leaves, so the agent stays the only member and the
        chat wears its avatar."""
        self.ensure_one()
        channel = self.with_user(SUPERUSER_ID)._create_ai_chat_channel(channel_name)
        bot_partner = channel.env.user.partner_id
        channel.from_ai_automation = True
        channel.message_post(
            body=kickoff_body,
            author_id=bot_partner.id,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        channel.channel_member_ids.filtered(lambda m: m.partner_id == bot_partner).unlink()
        # Join the audience allowed to inspect runs (admins), so they get it live.
        channel.sudo()._add_members(
            partners=self.env.ref("base.group_system").all_user_ids.partner_id,
            post_joined_message=False,
        )
        return channel

    @api.model
    def action_create_agent(self):
        agent = self.create({'name': _("My agent")})
        # Pick a random silhouette and tag its attachment so the color/number
        # stick through a later role redraw.
        agent._apply_avatar(f"Avatar{random.choice(AVATAR_NUMBERS)}-{random.choice(AVATAR_COLORS)}")
        return agent.open_agent_chat()

    def open_agent_chat(self):
        self.ensure_one()
        session = self.env['ai.session'].sudo().search([
            ('create_uid', '=', self.env.uid),
            ('agent_id', '=', self.id),
            ('ai_composer_id', '=', False),
            ('channel_id.has_message', '=', False),
        ], order='id DESC', limit=1)
        if session:
            channel = session.channel_id
        else:
            channel = self._create_ai_chat_channel()
            self.env['ai.session'].sudo().create({
                'agent_id': self.id,
                'channel_id': channel.id,
            })
        action = self.env['ir.actions.actions']._for_xml_id('mail.action_discuss')
        action['context'] = {
            'active_id': f'discuss.channel_{channel.id}',
            'scoped_ai_agent_id': self.id,
        }
        return action


class AISkill(models.Model):
    _inherit = 'ai.skill'

    agent_ids = fields.Many2many(
        'ai.agent',
        relation='ai_agent_ai_skill_rel',
        column1='ai_skill_id',
        column2='ai_agent_id',
        string="Agents",
    )
