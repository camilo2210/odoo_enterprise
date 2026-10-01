# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, Command, fields, models

SCHEDULE_TRIGGER = "on_schedule"
SCHEDULE_MODEL = 'ai.automation.trigger'
SCHEDULE_FIELD = 'prev_trigger_date'


def _is_schedule_automation(automation):
    automation.ensure_one()
    return automation.ai_agent_id and automation.model_name == SCHEDULE_MODEL and automation.trigger == 'on_time'


class BaseAutomation(models.Model):
    _inherit = "base.automation"

    ai_agent_id = fields.Many2one(
        "ai.agent",
        string="AI Agent",
        ondelete='restrict',
        help="Agent that runs the AI actions of this automation rule. Its tool calls are "
             "auto-confirmed and each run is kept in a chat for inspection.",
        context={"active_test": False},
    )
    ai_automation_trigger_ids = fields.One2many(
        "ai.automation.trigger",
        "automation_id",
        string="AI Automation Triggers",
    )
    ai_next_trigger_date = fields.Datetime(
        compute="_compute_ai_next_trigger_date",
        inverse="_inverse_ai_next_trigger_date",
    )
    ai_action_prompt = fields.Html(
        compute="_compute_ai_action_prompt",
        inverse="_inverse_ai_action_prompt",
    )

    @api.model
    def default_get(self, fields):
        """A scheduled trigger runs on its own `ai.automation.trigger` row, not
        on a business model: preset the target model so the rest computes."""
        defaults = super().default_get(fields)
        if self.env.context.get('ai_preset_trigger') == SCHEDULE_TRIGGER and 'model_id' in fields:
            defaults['model_id'] = self.env['ir.model']._get_id(SCHEDULE_MODEL)
            defaults['trg_date_id'] = self.env['ir.model.fields']._get(SCHEDULE_MODEL, SCHEDULE_FIELD).id
        return defaults

    @api.depends('model_id')
    def _compute_trigger(self):
        super()._compute_trigger()
        if preset_trigger := self.env.context.get('ai_preset_trigger'):
            self.trigger = 'on_time' if preset_trigger == SCHEDULE_TRIGGER else preset_trigger

    @api.depends('trigger', 'model_id')
    def _compute_trg_date_id(self):
        schedule_automations = self.filtered(_is_schedule_automation)
        schedule_automations.trg_date_id = self.env['ir.model.fields']._get(SCHEDULE_MODEL, SCHEDULE_FIELD)
        super(BaseAutomation, self - schedule_automations)._compute_trg_date_id()

    @api.depends('ai_automation_trigger_ids.next_trigger_date', 'ai_agent_id', 'model_name', 'trigger')
    def _compute_ai_next_trigger_date(self):
        for rule in self:
            if _is_schedule_automation(rule):
                rule.ai_next_trigger_date = rule.ai_automation_trigger_ids[:1].next_trigger_date
            else:
                rule.ai_next_trigger_date = False

    def _inverse_ai_next_trigger_date(self):
        for rule in self:
            if _is_schedule_automation(rule) and rule.ai_next_trigger_date:
                if trigger := rule.ai_automation_trigger_ids:
                    trigger.next_trigger_date = rule.ai_next_trigger_date
                else:
                    self.env['ai.automation.trigger'].create({
                        'automation_id': rule.id,
                        'next_trigger_date': rule.ai_next_trigger_date,
                    })

    @api.depends('action_server_ids.ai_action_prompt', 'ai_agent_id')
    def _compute_ai_action_prompt(self):
        for automation in self:
            if automation.ai_agent_id:
                automation.ai_action_prompt = automation.action_server_ids.ai_action_prompt
            else:
                automation.ai_action_prompt = False

    def _inverse_ai_action_prompt(self):
        for automation in self:
            if automation.ai_agent_id and automation.ai_action_prompt:
                if action := automation.action_server_ids:
                    action.ai_action_prompt = automation.ai_action_prompt
                else:
                    automation.action_server_ids = [Command.create({
                        'ai_action_prompt': automation.ai_action_prompt,
                        'model_id': automation.model_id.id,
                        'name': automation._get_ai_action_name(),
                        'state': 'ai',
                        'usage': 'base_automation',
                    })]

    @api.depends('ai_agent_id', 'model_id')
    def _compute_action_server_ids(self):
        for rule in (agent_rules := self.filtered(lambda rule: rule.ai_agent_id and rule.model_id)):
            # agent automations are tied to one server action of type AI.
            action_to_keep = rule.action_server_ids.filtered(lambda action: action.state == 'ai' and action.model_id == rule.model_id)[:1]
            rule.action_server_ids = [Command.delete(action.id) for action in rule.action_server_ids - action_to_keep]
        super(BaseAutomation, self - agent_rules)._compute_action_server_ids()

    def write(self, vals):
        res = super().write(vals)
        if {'model_id', 'model_name', 'trigger', 'ai_agent_id'} & vals.keys():
            (self - self.filtered(_is_schedule_automation)).ai_automation_trigger_ids.unlink()
        return res

    def _process(self, records, domain_post=None, trigger=''):
        """Advance the schedule before running: a failing agent run then costs one
        slot instead of being retried — and re-billed — on every cron pass."""
        super()._process(records, domain_post=domain_post, trigger=trigger)
        if trigger != 'manual' and records._name == SCHEDULE_MODEL:
            records.sudo()._advance_next_trigger_date()

    def _get_ai_action_name(self):
        self.ensure_one()
        return self.env._("%(agent)s: %(automation)s", agent=self.ai_agent_id.name, automation=self.name)

    def action_ai_run_now(self):
        """Run the automation scheduler now."""
        self.ensure_one()
        if self.model_name != SCHEDULE_MODEL:
            self.env.ref('base_automation.ir_cron_data_base_automation_check').method_direct_trigger()
            return
        self.sudo()._process(self.ai_automation_trigger_ids, trigger='manual')
