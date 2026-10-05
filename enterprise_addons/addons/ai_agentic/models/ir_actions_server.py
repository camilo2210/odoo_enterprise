# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import html as lxml_html

from odoo import models
from odoo.addons.ai.models.ir_actions_server import AI_ACTIONS_PROMPT
from odoo.tools.mail import html_sanitize, html_to_inner_content
from odoo.addons.ai_agentic.models.base_automation import SCHEDULE_MODEL


AI_AGENT_RUN_RULES = (
"""Execute EVERY step of the instructions. Any available tool may be used for any step: naming a tool for one step never makes the other tools off-limits, and a tool name that does not exist refers to the closest available one. Never report a step as skipped because a tool was not named for it.
To log a note in a record's chatter, create a `mail.message` record with the create tool: `model` = the record's model, `res_id` = its id, `body` = the note HTML, `message_type` = 'comment' and the internal note subtype. Only post a chatter note when the instructions explicitly ask for one: never log one on your own initiative to explain or justify what you did - that reasoning belongs in the final message of this run, nowhere else.
To SEND an email, create a `mail.mail` record instead: `email_to` = the recipient's address (search `res.partner`/`res.users` when only a name is given), `subject` and `body_html` = the HTML content. It is queued and sent automatically, while a `mail.message` is an internal note that never emails anyone.
Tools taking preview menu parameters (`preview_menus`, `preview_menu_id`) have no menu context in this run: always leave them empty, a guessed menu id fails the whole call.
The "User info" of the context is the account running this automation, not a person the instructions refer to: never assign a field (user, partner, ...) to it, and leave `partner_id` unset when the instructions name no contact.
If a person or record named in the instructions cannot be found, leave that value unset and say so in the final message, rather than substituting the current user or inventing an id.
The final message is the run's report: a factual summary of what was done, listing the records created or updated by display name with the values written, what was found, and anything skipped and why. When the instructions define an output format, follow it."""
)

AI_AGENT_RUN_SELF_EQUIP_NOTE = (
"""# Missing capability
If a step needs a capability none of your loaded tools provide (updating records, posting a chatter message, ...):
- If a skill listed in your available skills covers it, call `load_skills` with its id and continue the step with its tools.
- Otherwise, report the step as skipped, stating exactly which capability was missing."""
)


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    def _run_action_ai_multi(self, eval_context=None):
        records = self._ai_get_records(eval_context)
        if not records and (agent := self._ai_resolve_agent()):
            self._ai_action_run_agent(records, agent)
            return
        super()._run_action_ai_multi(eval_context)

    def _ai_action_run(self, record):
        if not self.ai_tool_ids and (agent := self._ai_resolve_agent()):
            return self._ai_action_run_agent(record, agent)
        return super()._ai_action_run(record)

    def _run(self, records, eval_context):
        if self.state == 'multi' and not records and self._ai_resolve_agent():
            return self._run_action_multi(eval_context=eval_context)
        return super()._run(records, eval_context)

    def _ai_resolve_trigger(self):
        """Return the recurring trigger this action hangs off, if any."""
        self.ensure_one()
        root = self
        while root.parent_id:
            root = root.parent_id
        return (
            self.base_automation_id
            or root.base_automation_id
            or self.env['ir.cron'].sudo().search([('ir_actions_server_id', '=', root.id)], limit=1)
        )

    def _ai_resolve_agent(self):
        return self._ai_resolve_trigger().ai_agent_id

    def _ai_run_channel_name(self, record):
        """Name the run's chat after the record the action ran on. A scheduled
        trigger has no record and its action is an implementation detail, so name
        it after the rule the user actually created."""
        self.ensure_one()
        if record and record._name != "ai.automation.trigger":
            return f"{self.name}: {record.display_name}"
        trigger = self._ai_resolve_trigger()
        if trigger._name == 'base.automation' and trigger.model_name == SCHEDULE_MODEL:
            return trigger.name
        return self.name

    def _ai_render_kickoff_body(self, record, action_prompt):
        """Kickoff note of an automation run: the action prompt with its field
        fields (`/field` command) replaced by their value on the run's record.
        Scheduled runs have no record and keep the raw prompt; so does any
        rendering failure, which must never break the run."""
        self.ensure_one()
        tree = lxml_html.fromstring(self.ai_action_prompt)
        for field in tree.xpath('//span[@data-ai-field]'):
            field.text = html_to_inner_content(record._find_value_from_field_path(field.attrib.get('data-ai-field')))
            field.drop_tag()
        return html_sanitize(lxml_html.tostring(tree, encoding='unicode'))

    def _ai_action_run_agent(self, record, agent):
        """Run the action's prompt through an agent session; `record` is empty
        for scheduled runs."""
        self.ensure_one()
        agent = agent.sudo()
        action_prompt, context_fields = self._ai_prepare_prompt_values(record)
        instruction = f"{AI_ACTIONS_PROMPT}\n{AI_AGENT_RUN_RULES}\n\n# Action request\n{action_prompt}"
        files_parts = []
        if record:
            self.sudo(record.env.su)._can_execute_action_on_records(record)
            record_context, files_parts = record._get_ai_context(context_fields)
            instruction += f'\n\n# Context\n## Current record\n{{"model": "{record._name}", "id": {record.id}}}'
            if record_context != '{}':
                instruction += f"\n## ORM Snapshot\n{record_context}"
        if automation := self.base_automation_id:
            instruction += (
                f'\n\n# This chat is a run of the automation "{automation.name}" '
                f'(`base.automation` id {automation.id}). If the user later gives feedback or corrections about '
                "this run's behavior or results, apply it to THAT automation (usually its action prompt) so "
                "future runs change - never to your own agent instructions, unless explicitly asked."
            )
        instruction += f"\n\n{AI_AGENT_RUN_SELF_EQUIP_NOTE}"

        channel_name = self._ai_run_channel_name(record)
        channel = agent._create_ai_automation_channel(channel_name, self._ai_render_kickoff_body(record, action_prompt))
        session = self.env['ai.session'].sudo().create({
            'agent_id': agent.id,
            'channel_id': channel.id,
            'res_model': record._name if record else False,
            'res_id': record.id if record else False,
            'auto_confirm': True,
        })
        request_context = {
            'allowed_company_ids': self.env.companies.ids,
            'active_company_ids': self.env.companies.ids,
            'ai_automation_run': True,
        }
        for key in ('lang', 'tz', 'cron_id'):
            if self.env.context.get(key):
                request_context[key] = self.env.context[key]
        session = session.with_context(request_context)
        session._submit_agent_request(
            [{'type': 'text', 'text': instruction}, *files_parts],
        )
        return None, []

    def _generate_action_name(self):
        self.ensure_one()
        if self.state == 'ai' and self.base_automation_id.ai_agent_id:
            return self.base_automation_id._get_ai_action_name()
        return super()._generate_action_name()

    def _name_depends(self):
        return super()._name_depends() + ["base_automation_id.name", "base_automation_id.ai_agent_id.name"]
