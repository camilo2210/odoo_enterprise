# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import datetime
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools import OrderedSet, SQL, frozendict

from .models import MODELS_NO_AI


_logger = logging.getLogger(__name__)

NB_RECORDS_TO_COMPUTE_ON_FIELD_CREATION = 50


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'
    _explanation = "AI extensions for model fields, allowing fields to be computed or populated by an AI model based on a system prompt."

    ai = fields.Boolean(string="Autofill", help="AI computed field", default=False)
    ai_domain = fields.Char(string="AI field domain", compute="_compute_ai_domain", store=True, compute_sudo=True)

    # should not be visible by a user
    # one should go through "system_prompt"
    prompt_custom = fields.Html(
        sanitize=True,
        sanitize_output_method='xml')

    # Computed to allow customization and a value from the registry
    system_prompt = fields.Html(
        sanitize=True,
        sanitize_output_method='xml',
        string="Prompt",
        compute="_compute_system_prompt",
        inverse="_inverse_system_prompt",
        compute_sudo=True,
        help="Prompt given to the AI model to compute the field value"
    )

    supports_ai = fields.Boolean(compute="_compute_supports_ai")

    def _get_registry_prompt(self):
        model = self.env.get(self.model_id.model)
        field = model is not None and model._fields.get(self.name)
        return field and getattr(field, "ai", False)

    @api.depends('model_id')
    def _compute_system_prompt(self):
        for rec in self:
            rec.system_prompt = rec.prompt_custom or rec._get_registry_prompt()

    def _inverse_system_prompt(self):
        for rec in self:
            registry_prompt = rec._get_registry_prompt()
            prompt = rec.system_prompt
            if prompt and prompt == registry_prompt:
                prompt = False
            rec.prompt_custom = prompt

    @api.constrains('ai', 'model_id')
    def _constrains_ai_model_id(self):
        for rec in self:
            if rec.ai and not rec.supports_ai:
                raise ValidationError(self.env._t("The model '%s' doesn't support ai", rec.model_id.name))

    @api.depends("model_id")
    def _compute_supports_ai(self):
        for rec in self:
            rec.supports_ai = rec.model_id.model not in MODELS_NO_AI

    @api.onchange("model_id")
    def _on_change_model_reset_ai(self):
        for rec in self:
            if not rec.supports_ai:
                rec.ai = False

    @api.depends('ai', 'model', 'model_id')
    def _compute_ai_domain(self):
        for model, ir_fields in self.filtered('ai').grouped('model').items():
            last_record_id = self.env[model].with_context(active_test=False).search([], order='id desc', limit=1).id
            ir_fields.ai_domain = str([('id', '>', max(0, last_record_id - NB_RECORDS_TO_COMPUTE_ON_FIELD_CREATION))])

    @api.model
    @api.ormcache(cache='stable')
    def _get_all_ai_parameters(self):
        ai_fields = self.sudo().search_fetch([('ai', '=', True)], ["ai", "system_prompt", "ai_domain", "ttype"])
        return frozendict((
            (f.model_id.model, f.name),
            frozendict({"prompt": f.system_prompt, "ai_domain": f.ai_domain, "ttype": f.ttype, "id": f.id})
            ) for f in ai_fields)

    @api.model
    def _get_field_ai_parameters(self, modelname_or_field: str | fields.Field, field_name: str | None = None):
        if not isinstance(modelname_or_field, str):
            model_name = modelname_or_field.model_name
            field_name = modelname_or_field.name
        else:
            model_name = modelname_or_field
        all = self._get_all_ai_parameters()
        return all.get((model_name, field_name), {})

    @api.model_create_multi
    def create(self, vals_list):
        """Trigger the AI field cron when creating a record
        """
        ir_model_fields = super().create(vals_list)
        if any(f.ai and f.system_prompt for f in ir_model_fields) and (ai_fields_cron := self.env.ref('ai_fields.ir_cron_fill_ai_fields', raise_if_not_found=False)):
            ai_fields_cron._trigger()

        return ir_model_fields

    def write(self, vals):
        """Trigger the AI field cron when making a field ai or when adding/changing its prompt
        """
        res = super().write(vals)
        if ((vals.get('system_prompt') or vals.get('ai')) and
            (ai_fields_cron := self.env.ref('ai_fields.ir_cron_fill_ai_fields', raise_if_not_found=False))
            ):
            ai_fields_cron._trigger()
        return res

    def _get_writable_properties(self):
        return [*super()._get_writable_properties(), "system_prompt", "prompt_custom", "ai", "ai_domain"]

    def _instanciate_attrs(self, field_data):
        attrs = super()._instanciate_attrs(field_data)
        if attrs and field_data.get('ai'):
            attrs['ai'] = field_data.get('system_prompt') or ''
        return attrs

    def _reflect_field_params(self, field, model_id):
        field_params = super()._reflect_field_params(field, model_id)
        ai = getattr(field, 'ai', None)
        field_params['ai'] = isinstance(ai, str)  # can be empty string on field creation
        return field_params

    def _cron_fill_ai_fields(self, batch_size=10):
        # currently only openAI is supported (gemini does not support web grounding with structured outputs),
        # so make sure the openAI key is set

        support_ttypes = ('char', 'text', 'html')
        ai_params = self._get_all_ai_parameters()
        field_ids = [p["id"] for p in ai_params.values() if p["prompt"] and p["ttype"] in support_ttypes]

        property_fields = self.search(
            Domain('ttype', '=', 'properties_definition') & Domain('store', '=', True),
            order='id'
        )
        fields = self.browse(field_ids + property_fields.ids)
        remaining_fields = len(fields)

        total_done = 0  # number of records processed
        total_remaining = 0  # number of records remaining for the fields processed
        for field in fields:
            done, remaining, has_time_left = (
                self._ai_fill_records_with_empty_property(field, batch_size, remaining_fields)
                if field.ttype == 'properties_definition' else
                self._ai_fill_records_with_empty_field(field, batch_size, remaining_fields)
            )
            total_done += done
            total_remaining += remaining
            if not remaining:
                remaining_fields -= 1
            if not has_time_left:
                break
        if not remaining_fields:
            # make sure to not rescheduled the cron
            self.env['ir.cron']._commit_progress(remaining=0)
        else:
            if not total_done:
                # all records were locked, reschedule the cron soon hoping they will be unlocked.
                # not done when only part of the records were locked because in that case the cron will
                # be considered as partially done and rescheduled asap.
                self.env['ir.cron']._commit_progress(remaining=0)
                _logger.info('AI Fields cron rescheduled soon because all records were locked')
                self.env.ref('ai_fields.ir_cron_fill_ai_fields')._trigger(self.env.cr.now() + datetime.timedelta(minutes=1))
            elif total_remaining:
                _logger.info('AI Fields cron skipped %s records', total_remaining)

    def _ai_fill_records_with_empty_field(self, field, batch_size, remaining_fields):
        field.ensure_one()
        has_time_left = True
        model = self.env[field.model]
        query = model._search(ast.literal_eval(field.ai_domain) or [], order='id')
        query.add_where(SQL("%(field)s IS NULL", field=model._field_to_sql(model._table, field.name, query)))
        ids = OrderedSet(query)
        total_done = 0
        while ids and has_time_left and (records := model.browse(ids).try_lock_for_update(limit=batch_size)):
            records._fill_ai_field(model._fields[field.name])
            ids -= set(records._ids)
            done = len(records)
            has_time_left = bool(self.env['ir.cron']._commit_progress(len(records), remaining=remaining_fields))
            total_done += done
        return total_done, len(ids), has_time_left

    def _ai_fill_records_with_empty_property(self, field, batch_size, remaining_fields):
        field.ensure_one()
        to_process = []
        definition_orm_field = self.env[field.model]._fields[field.name]
        # Update the properties with a parent
        # Need to split definition query from record query because of the domain in the definition
        self.env.cr.execute(SQL(
            """
            SELECT m.id AS parent_id, definition
              FROM %(definition_table)s m, jsonb_array_elements(%(definition_name)s) definition
             WHERE definition IS NOT NULL
               AND COALESCE(definition->>'name', '') != ''
               AND definition->>'ai' = 'true'
               AND COALESCE(definition->>'system_prompt', '') != ''
               -- because we can add records at the end of the prompt, for security
               -- reason, we can not compute their values in the CRON
               AND definition->>'type' != 'many2one'
               AND definition->>'type' != 'many2many'
          ORDER BY m.id
            """,
            definition_name=SQL.identifier(field.name),
            definition_table=SQL.identifier(self.env[field.model]._table),
        ))
        for values in self.env.cr.dictfetchall():  # For all AI definitions.....
            definition = values["definition"]
            parent_id = values["parent_id"]

            # A definition can technically be linked to many properties fields
            for properties_orm_field in definition_orm_field.properties_fields:
                model = self.env[properties_orm_field.model_name]
                ai_domain = Domain.AND([
                    definition.get("ai_domain") or [],
                    [[properties_orm_field.definition_record, "=", parent_id]],
                ])
                # Can not use the ORM because we need IS NULL (VS False, empty string, etc...)
                query = model._search(ai_domain, order='id DESC')
                query.add_where(SQL(
                    "(%(field)s IS NULL OR %(field)s->%(property_name)s IS NULL)",
                    field=model._field_to_sql(model._table, properties_orm_field.name, query),
                    property_name=definition['name'],
                ))
                ids = OrderedSet(query)
                if ids:
                    to_process.append((model, properties_orm_field.name, definition, ids))

        has_time_left = True
        total_done = 0
        for model, fname, definition, ids in to_process:
            while has_time_left and (records := model.browse(ids).try_lock_for_update(limit=batch_size)):
                records._fill_ai_property(fname, definition)
                ids -= set(records._ids)
                done = len(records)
                has_time_left = bool(self.env['ir.cron']._commit_progress(done, remaining=remaining_fields))
                total_done += done
        return total_done, sum(len(ids) for *__, ids in to_process), has_time_left
