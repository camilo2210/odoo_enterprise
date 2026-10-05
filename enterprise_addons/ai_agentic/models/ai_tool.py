# Part of Odoo. See LICENSE file for full copyright and licensing details.
from markupsafe import Markup

from odoo import api, fields, models
from odoo.addons.ai.utils.ai_utils import (
    UserInputResponse,
    is_ai_internal_model,
    make_confirmation_request_preview,
    make_create_preview,
    make_records_update_preview,
)
from odoo.addons.ai.utils.ai_fields_tools import parse_ai_prompt_values
from odoo.addons.base_automation.models.base_automation import TIME_TRIGGERS

SELF_UPDATE_SKILL_XMLID = 'ai_agentic.ai_skill_self_update'


def check_automation_skill_is_loaded(env, tool_context):
    if not (automation_skill := env.ref('ai_agentic.ai_skill_automations', raise_if_not_found=False)):
        raise ValueError("The Automations skill is required to write on base.automation records")
    if not automation_skill.id in (tool_context['state'] or []).get('loaded_skills', []):
        raise ValueError("The Automations skill needs to be loaded to update automations")


class AITool(models.AbstractModel):
    _inherit = 'ai.tool'

    @api.model
    def _check_agent_model_access(self, model_name, operation='read'):
        if operation == 'read' and model_name in {'base.automation', 'ir.model', 'ir.model.fields', 'ir.model.fields.selection'}:
            return
        return super()._check_agent_model_access(model_name, operation)

    def _check_tool_scope(self, tool_context, tool_xmlid, model_names):
        tool = self.env.ref(tool_xmlid, raise_if_not_found=False)
        self_update_skill = self.env.ref(SELF_UPDATE_SKILL_XMLID, raise_if_not_found=False)
        if not tool or not self_update_skill or not tool_context.get('agent_id'):
            return
        agent_skills = self._get_calling_agent(tool_context)._get_available_skills().sudo()
        if agent_skills.filtered(lambda s: tool in s.tool_ids) != self_update_skill:
            return
        out_of_scope = [m for m in dict.fromkeys(model_names) if not is_ai_internal_model(m)]
        if out_of_scope:
            raise ValueError(
                f"The Self Update skill only lets you read and change the AI configuration "
                f"models, not {', '.join(out_of_scope)}. "
                "Link a skill that provides this tool to use it on other records."
            )

    def _ai_tool_update_records(self, tool_context, explanation, preview_menus, updates):
        self._check_tool_scope(
            tool_context, 'ai.ir_actions_server_update_records',
            [update['model_name'] for update in updates],
        )
        return super()._ai_tool_update_records(tool_context, explanation, preview_menus, updates)

    @api.model
    def _get_preview_links(self, mode, record_by_model, action_by_model=None):
        links = []
        if mode == 'write' and record_by_model.get('ai.agent'):
            record_by_model = {model: records for model, records in record_by_model.items() if model != 'ai.agent'}
            links.append(Markup('<span>%s</span>') % self.env._("self-updated its configuration"))
        return links + super()._get_preview_links(mode, record_by_model, action_by_model)

    def _ai_tool_create_records(self, tool_context, explanation, preview_menu_id, model_name, values):
        self._check_tool_scope(tool_context, 'ai.ir_actions_server_create_records', [model_name])
        return super()._ai_tool_create_records(tool_context, explanation, preview_menu_id, model_name, values)

    def _is_automation_skill_required(self, tool_context):
        # A hook to be overridable
        return True

    def _is_base_automation_server_action(self, tool_context):
        # A hook to be overridable
        return True

    def _ai_tool_run_automation(self, tool_context, base_automation_id):
        """Run a time-based automation NOW, exactly as its schedule would: the
        headless agent run lands in the automation's own chat."""
        automation = self.env['base.automation'].browse(base_automation_id)
        if not automation.trigger in TIME_TRIGGERS:
            raise ValueError(
                f"'{automation.name}' is not a time based trigger, test it by "
                "creating or updating a record that matches its trigger instead."
            )
        if not tool_context.get('tool_request_confirmed'):
            tool_context['user_input_request'] = {
                'type': 'confirmation',
                'body': self.env['ir.qweb']._render('ai.ai_records_preview', {
                    'template': 'create',
                    'explanation': self.env._('Run this automation now?'),
                    'sections': [{'items': [{'label': self.env._('Automation'), 'value': automation.name}]}],
                }),
                'choices': [{'label': self.env._("Run"), 'value': UserInputResponse.CONFIRM_ONCE}, {'label': self.env._("Not now"), 'value': UserInputResponse.DECLINE}],
                'allow_free_text': False,
            }
            return None
        automation.action_ai_run_now()
        tool_context["preview_links"] = [
            Markup('<div class="o_mail_notification">%s</div>') % self.env._("has run %s", automation._get_html_link()),
        ]
        return {
            'response': self.env._(
                '"%s" ran. The full transcript is in its own chat, under the Automation tab.',
                automation.name,
            ),
            'summary': {'icon': 'flash_on', 'text': self.env._("Ran the trigger %(name)s", name=automation.name)}
        }

    def _ai_tool_create_update_automation(self, tool_context, automation_id=None, name=None, description=None, active=None, trigger=None, ai_action_prompt=None, explanation=None):
        if not automation_id and not (name and description and trigger and ai_action_prompt):
            raise ValueError("'name', 'description', 'trigger' and 'ai_action_prompt' are required when creating an automation")
        automation = self._get_automation_to_update(tool_context, automation_id)
        automation_vals = self._compute_automation_header_vals(automation, name, description, active)
        trigger_type = (trigger or {}).get('type') or automation.trigger
        model_name = automation.model_name
        if trigger:
            trigger_vals, model_name = self._compute_trigger_vals(automation, trigger, trigger_type)
            automation_vals.update(trigger_vals)
        automation_vals.update(self._compute_trigger_prompt_vals(automation, ai_action_prompt, model_name, model_changed='model_id' in automation_vals))
        if not automation:
            if trigger_type != 'on_schedule':
                automation_vals['last_run'] = fields.Datetime.to_string(fields.Datetime.now())
            automation_vals['ai_agent_id'] = tool_context['agent_id']
        if not tool_context['tool_request_confirmed']:
            tool_context['user_input_request'] = make_confirmation_request_preview(
                self.env, self._render_automation_preview(automation, automation_vals, explanation),
            )
            return None
        if automation:
            automation.write(automation_vals)
            mode = 'update'
            summary = {'icon': 'edit', 'text': self.env._("Updated a Trigger")}
        else:
            automation = automation.create(automation_vals)
            mode = 'create'
            summary = {'icon': 'edit_square', 'text': self.env._("Created a Trigger")}
        tool_context["preview_links"] = self._get_preview_links(mode, {automation._name: automation})
        return {
            'response': f"Successfully {mode}d automation with id {automation.id}",
            'client_tool': {'name': 'reload', 'oneway': True},
            'summary': summary,
        }

    def _get_automation_to_update(self, tool_context, automation_id):
        if not automation_id:
            return self.env['base.automation']
        if not (automation := self.env['base.automation'].browse(automation_id).exists()):
            raise ValueError(f"The automation with id '{automation_id}' does not exist")
        if automation.ai_agent_id.id != tool_context['agent_id']:
            raise ValueError("You can only update your own automations.")
        return automation

    def _compute_automation_header_vals(self, automation, name, description, active):
        vals = {}
        if name and name != automation.name:
            vals['name'] = name
        if description and description != automation.description:
            vals['description'] = description
        if active is not None and active != automation.active:
            vals['active'] = active
        return vals

    def _compute_trigger_vals(self, automation, trigger, trigger_type):
        vals, model_name = self._compute_trigger_type_vals(automation, trigger, trigger_type)
        vals.update(self._compute_trigger_domain_vals(automation, trigger, trigger_type, model_name))
        vals.update(self._compute_observed_fields_vals(automation, trigger, trigger_type, model_name))
        vals.update(self._compute_time_trigger_vals(automation, trigger, trigger_type))
        return vals, model_name

    def _compute_trigger_type_vals(self, automation, trigger, trigger_type):
        vals = {}
        if trigger.get('type') and trigger_type != automation.trigger:
            if trigger_type not in automation._fields['trigger']._selection and trigger_type != 'on_schedule':
                raise ValueError(f"Unsupported trigger type '{trigger_type}'")
            vals['trigger'] = 'on_time' if trigger_type == 'on_schedule' else trigger_type
        if (model_name := trigger.get('target_model')) and model_name != automation.model_name:
            if model_name not in self.env:
                raise ValueError(f"Model {model_name} not found")
            vals['model_id'] = self.env['ir.model']._get_id(model_name)
        elif trigger_type == 'on_schedule':
            model_name = 'ai.automation.trigger'
            if model_name != automation.model_name:
                vals['model_id'] = self.env['ir.model']._get_id(model_name)
        return vals, model_name or automation.model_name

    def _compute_trigger_domain_vals(self, automation, trigger, trigger_type, model_name):
        vals = {}
        unsupported = {
            'filter_pre_domain': {'on_time', 'on_time_created', 'on_time_updated', 'on_create', 'on_unlink', 'on_change', 'on_webhook'},
            'filter_domain': {'on_webhook'},
        }
        for fname, forbidden_triggers in unsupported.items():
            if not (domain := trigger.get(fname) or automation[fname]):
                continue
            if trigger_type in forbidden_triggers:
                raise ValueError(f"'{fname}' is not supported with trigger of type '{trigger_type}'")
            if domain != automation[fname]:
                vals[fname] = str(self._parse_domain(model_name, domain))
            elif model_name != automation.model_name:
                # make sure it's still valid with the current model
                self._parse_domain(model_name, domain)
        return vals

    def _compute_observed_fields_vals(self, automation, trigger, trigger_type, model_name):
        vals = {}
        fnames = trigger.get('observed_fields') or []
        if isinstance(fnames, str):
            fnames = [fnames]
        if trigger_type in {'on_create_or_write', 'on_change'}:
            ids_by_fname = self.env['ir.model.fields']._get_ids(model_name)
            observed_field_ids = []
            for fname in fnames:
                if not (fid := ids_by_fname.get(fname)):
                    raise ValueError(f"field '{fname}' does not exist on '{model_name}'")
                observed_field_ids.append(fid)
            if trigger_type == 'on_change':
                if not fnames and not automation.on_change_field_ids:
                    raise ValueError("Trigger of type 'on_change' requires at least one observed field")
                if observed_field_ids != automation.on_change_field_ids.ids:
                    vals['on_change_field_ids'] = observed_field_ids
            elif fnames and observed_field_ids != automation.trigger_field_ids.ids:
                vals['trigger_field_ids'] = observed_field_ids
        elif trigger_type == 'on_time':
            fname = fnames[0] if fnames else False
            if not fname:
                if not automation.trg_date_id:
                    raise ValueError("Trigger of type 'on_time' requires a date(time) field to observe")
                if (trg_name := automation.trg_date_id.name) not in self.env[model_name]._fields:
                    raise ValueError(f"Observed field {trg_name} does not exist on '{model_name}'")
            else:
                if fname not in self.env[model_name]._fields:
                    raise ValueError(f"Observed field {fname} does not exist on '{model_name}'")
                trg_date_id = self.env['ir.model.fields']._get(model_name, fname).id
                if trg_date_id != automation.trg_date_id.id:
                    vals['trg_date_id'] = trg_date_id
        elif trigger_type == 'on_schedule':
            trg_date_id = self.env['ir.model.fields']._get('ai.automation.trigger', 'prev_trigger_date').id
            if trg_date_id != automation.trg_date_id.id:
                vals['trg_date_id'] = trg_date_id
        elif fnames:
            raise ValueError(f"'observed_fields' is not supported with trigger of type '{trigger_type}'")
        return vals

    def _compute_time_trigger_vals(self, automation, trigger, trigger_type):
        vals = {}
        if not (date_params := trigger.get('date_offset_or_interval')):
            return vals
        if trigger_type not in {'on_time', 'on_time_created', 'on_time_updated', 'on_schedule'}:
            raise ValueError(f"'date_offset_or_interval' is not supported with trigger of type '{trigger_type}'")
        if trigger_type == 'on_time':
            if (direction := date_params.get('direction')) and direction != automation.trg_date_range_mode:
                vals['trg_date_range_mode'] = direction
            elif not automation.trg_date_range_mode:
                vals['trg_date_range_mode'] = 'after'
        elif trigger_type == 'on_schedule':
            if automation.trg_date_range_mode != 'after':
                vals['trg_date_range_mode'] = 'after'
            if not (next_trigger_date := date_params.get('next_trigger_date')) and not automation.ai_next_trigger_date:
                raise ValueError("`on_schedule` requires a `next_trigger_date`")
            if next_trigger_date != automation.ai_next_trigger_date:
                vals['ai_next_trigger_date'] = next_trigger_date
        if (amount := date_params.get('amount')) and amount != automation.trg_date_range:
            vals['trg_date_range'] = amount
        elif not automation.trg_date_range:
            vals['trg_date_range'] = 5
        if (unit := date_params.get('unit')) and unit != automation.trg_date_range_type:
            vals['trg_date_range_type'] = unit
        elif not automation.trg_date_range_type:
            vals['trg_date_range_type'] = "minutes"
        return vals

    def _compute_trigger_prompt_vals(self, automation, ai_action_prompt, model_name, model_changed):
        vals = {}
        action_prompt = ai_action_prompt or automation.ai_action_prompt
        if action_prompt == automation.ai_action_prompt and not model_changed:
            return vals
        __, context_fields, __ = parse_ai_prompt_values(self.env, action_prompt, None)
        for field_path in context_fields:
            try:
                self.env[model_name].mapped(field_path)
            except KeyError as e:
                raise ValueError(f"Invalid field {e} in '{field_path}' in prompt")
        if action_prompt != automation.ai_action_prompt:
            vals['ai_action_prompt'] = action_prompt
        return vals

    def _render_automation_preview(self, automation, vals, explanation):
        if not automation:
            return make_create_preview(self.env, explanation, 'base.automation', [{
                'field_values': [{'field': field, 'value': value} for field, value in vals.items()],
            }])
        return self.env['ir.qweb']._render('ai.ai_records_preview', {
            'template': 'update',
            'explanation': explanation,
            'sections': [{
                'label': self.env._("Automation Rule %(name)s", name=automation.name),
                'items': make_records_update_preview(automation, vals),
            }],
        })
