import json
import logging

from odoo import fields, models, modules
from odoo.tools import SQL, config, split_every

_logger = logging.getLogger(__name__)


class EsgCarbonEmissionReport(models.Model):
    _inherit = 'esg.carbon.emission.report'

    ai_esg_to_assign_emission_factor_cron = fields.Boolean()

    @property
    def WRITE_ACCOUNT_EMISSION_FIELDS(self):
        return {
            *super().WRITE_ACCOUNT_EMISSION_FIELDS,
            'ai_esg_to_assign_emission_factor_cron',
        }

    def _other_emission_select(self):
        return SQL('''%s,
            NULL as ai_esg_to_assign_emission_factor_cron
        ''', super()._other_emission_select())

    def _move_lines_select(self):
        return SQL('''%s,
            aml.ai_esg_to_assign_emission_factor_cron as ai_esg_to_assign_emission_factor_cron
        ''', super()._move_lines_select())

    def write(self, vals):
        if vals.get('esg_emission_factor_id'):
            vals['ai_esg_to_assign_emission_factor_cron'] = False
        return super().write(vals)

    def _ai_get_emission_sources(self, scope):
        self.ensure_one()
        emission_sources = self.env['esg.emission.source'].search([('scope', '=', scope), ('emission_factor_ids', '!=', False)])._ai_read(['complete_name'])[0]
        response = 'You **always** have to use the keys (ids) as values for the Get Emission Factor tool.\n'
        response += f'# Emission Sources:\n{json.dumps(emission_sources)}\n'
        return response

    def _ai_get_emission_factor(self, source_ids):
        self.ensure_one()
        emission_factors = self.env['esg.emission.factor'].search([('source_id', 'in', source_ids)])._ai_read([
            'name', 'uom_name', 'currency_name', 'region', 'company_name'
        ])[0]
        response = 'You **always** have to use the keys (ids) as values for the Assign Emission Factor tool.\n'
        response += f'# Emission Factors:\n{json.dumps(emission_factors)}\n'
        return response

    def _ai_assign_emission_factor(self, emission_factor_id):
        self.ensure_one()
        emission_factor = self.env['esg.emission.factor'].browse(emission_factor_id)
        self.esg_emission_factor_id = emission_factor
        return self.env._('Emission factor of emission line %(line_name)s updated to %(factor_name)s', line_name=self.name, factor_name=emission_factor.name)

    def _cron_ai_assign_emission_factors(self):
        auto_commit = not (config['test_enable'] or modules.module.current_test)
        lines_to_assign = self.search([('ai_esg_to_assign_emission_factor_cron', '=', True)])
        lines_to_assign_size = len(lines_to_assign)
        last_user = self.env['account.move.line'].search([('ai_esg_to_assign_emission_factor_cron', '=', True)], limit=1).write_uid
        batch_size = 1  # We will increase the batch size once the AI server action becomes batchable
        has_error_trace = False
        action = self.env.ref('ai_esg.emission_factors_ai_auto_assignment')
        has_run = False
        _logger.info('Starting AI assignation - %s emission lines to assign.', lines_to_assign_size)

        for lines_to_process_ids in split_every(batch_size, lines_to_assign.ids):
            lines_to_process = self.browse(lines_to_process_ids).filtered(lambda line: line.ai_esg_to_assign_emission_factor_cron)
            if not lines_to_process:
                continue
            n_processed = len(lines_to_process)
            _logger.info('Processing next batch of %s emission lines.', n_processed)
            try:
                # Lock the processed lines to prevent concurrent updates
                self.env.cr.execute(
                    'SELECT 1 FROM esg_carbon_emission_report WHERE id IN %s FOR NO KEY UPDATE',
                    (tuple(lines_to_process.ids),)
                )
                action.with_context(
                    active_model=self._name,
                    active_ids=lines_to_process.ids,
                ).run()
            except Exception as e:  # noqa: BLE001
                has_error_trace = True
                _logger.info('The following error occurred during the AI assignation of emission factors: "%s".', e)
            finally:
                has_run = True
                lines_to_process.ai_esg_to_assign_emission_factor_cron = False
                if auto_commit:
                    self.env['ir.cron']._commit_progress(processed=n_processed, remaining=lines_to_assign_size - n_processed)
                    lines_to_assign_size -= n_processed

        _logger.info('AI assignation of emission lines finished.')
        if has_run and last_user.email_formatted and lines_to_assign:
            if has_error_trace:
                mail_template = self.env.ref('ai_esg.mail_template_data_ai_esg_assign_emission_factors_failure')
            else:
                mail_template = self.env.ref('ai_esg.mail_template_data_ai_esg_assign_emission_factors_success')
            mail_template.send_mail(
                lines_to_assign.ids[0],
                force_send=True,
                email_values={
                    'email_to': last_user.email_formatted,
                    'auto_delete': True,
                },
            )

        return True

    def action_ai_assign_emission_factors(self):
        valid_emissions = self.filtered(lambda line: line.id < 0)
        if not valid_emissions:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': self.env._('No valid emissions were selected. Please select emissions linked to journal items.'),
                },
            }
        valid_emissions.ai_esg_to_assign_emission_factor_cron = True
        self.env.ref('ai_esg.ir_cron_ai_esg_assign_emission_factors_to_emission_line')._trigger()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._(
                    'AI is assigning emission factors to the selected emissions. This may take a few minutes. It runs in the background, so you can leave this page and you\'ll be notified by email when it\'s finished.'
                ),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
