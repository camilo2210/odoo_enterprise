from collections import defaultdict
from itertools import chain

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        if country_code == 'NL' and (ec_sales_return_type := self.env.ref('l10n_nl_reports.nl_ec_sales_list_return_type', raise_if_not_found=False)):

            months_offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            previous_period_start, previous_period_end = ec_sales_return_type._get_period_boundaries(main_company, fields.Date.context_today(self) - relativedelta(months=months_offset))
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, ec_sales_return_type.report_id)
            ec_sales_list_tags_info = self.env['l10n_nl_reports.ec.sales.report.handler']._get_ec_sales_tax_tags()
            ec_sales_list_tag_ids = list(chain(*ec_sales_list_tags_info.values()))

            need_ec_sales_list = bool(self.env['account.move.line'].search_count([
                ('tax_tag_ids', 'in', ec_sales_list_tag_ids),
                *self.env['account.move.line']._check_company_domain(company_ids.ids),
                ('date', '>=', previous_period_start),
                ('date', '<=', previous_period_end),
            ], limit=1))

            if need_ec_sales_list:
                ec_sales_return_type._try_create_return_for_period(previous_period_start, main_company, tax_unit)

        return rslt


class AccountReturn(models.Model):
    _inherit = 'account.return'

    l10n_nl_sbr_status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('error', 'Error'),
        ],
        string='SBR Status',
        help='Tracks SBR submission status for Kanban UI color coding.',
    )

    def _l10n_nl_return_handler_map(self):
        return {
            'l10n_nl_reports.nl_tax_return_type': 'l10n_nl_reports.tax.report.handler',
            'l10n_nl_reports.nl_ec_sales_list_return_type': 'l10n_nl_reports.ec.sales.report.handler',
        }

    @api.depends('state', 'l10n_nl_sbr_status')
    def _compute_visible_states(self):
        super()._compute_visible_states()
        for account_return in self.filtered(lambda ar: ar.type_external_id in self._l10n_nl_return_handler_map()):
            new_states = []
            for state in account_return.visible_states:
                state['custom_class'] = ''
                if (
                    state['name'] == 'submitted'
                    and account_return.state == 'submitted'
                    and account_return.l10n_nl_sbr_status != 'accepted'
                ):
                    state['custom_class'] = f'nl-sbr-{account_return.l10n_nl_sbr_status}'
                new_states.append(state)
            account_return.visible_states = new_states

    def _compute_show_submit_button(self):
        super()._compute_show_submit_button()
        for account_return in self.filtered(lambda ar: ar.type_external_id in self._l10n_nl_return_handler_map()):
            account_return.show_submit_button = (
                account_return.show_submit_button
                or account_return.next_state == 'paid' and account_return.l10n_nl_sbr_status == 'error'
            )

    def _prepare_submission(self):
        self._check_all_branches_allowed()
        return_handler_map = self._l10n_nl_return_handler_map()
        if self.type_external_id in return_handler_map:
            options = self._get_closing_report_options()
            return self.env[return_handler_map[self.type_external_id]].open_xbrl_wizard(options)
        return super()._prepare_submission()

    def action_refresh_sbr_status(self):
        self.env['l10n_nl_reports.sbr.status.service']._cron_process_submission_status()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_reset_tax_return_common(self):
        if self.type_external_id == 'l10n_nl_reports.nl_tax_return_type' and self.l10n_nl_sbr_status == 'accepted':
            raise UserError(
                self.env._("This tax return has already been accepted by Digipoort and cannot be modified or reset.")
            )
        return super().action_reset_tax_return_common()

    def action_reset_2_states(self):
        if self.type_external_id == 'l10n_nl_reports.nl_ec_sales_list_return_type' and self.l10n_nl_sbr_status == 'accepted':
            raise UserError(
                self.env._("This sales return has already been accepted by Digipoort and cannot be modified or reset.")
            )
        return super().action_reset_2_states()

    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        months_per_period = return_type._get_periodicity_months_delay(company)
        if return_type_external_id == 'l10n_nl_reports.nl_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            return date_to + relativedelta(months=1)
        if return_type_external_id == 'l10n_nl_reports.nl_ec_sales_list_return_type' and months_per_period in (1, 3):
            return date_to + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _get_pay_wizard(self):
        if self.type_id == self.env.ref('l10n_nl_reports.nl_tax_return_type'):
            vat_pay_wizard = self.env['l10n_nl_reports.vat.pay.wizard'].create({
                'company_id': self.company_id.id,
                'partner_bank_id': self.type_id.payment_partner_bank_id.id,
                'currency_id': self.amount_to_pay_currency_id.id,
                'amount_to_pay': self.total_amount_to_pay,
                'return_id': self.id,
            })

            return {
                'type': 'ir.actions.act_window',
                'name': self.env._("VAT Payment"),
                'res_model': 'l10n_nl_reports.vat.pay.wizard',
                'res_id': vat_pay_wizard.id,
                'views': [(False, 'form')],
                'target': 'new',
            }

        return super()._get_pay_wizard()

    def _postprocess_vat_closing_entry_results(self, company, options, results):
        # OVERRIDE
        """Handle corrective tax returns and rounding on the tax report for the Netherlands."""
        if self.type_external_id == 'l10n_nl_reports.nl_tax_correction_return_type':
            # Balance out the amounts of the previous closing entries for a correction.
            previous_closing_lines = self.env['account.move.line'].search([
                ('move_id.closing_return_id.company_id', '=', company.id),
                ('move_id.closing_return_id.date_from', '>=', options['date']['date_from']),
                ('move_id.closing_return_id.date_to', '<=', options['date']['date_to']),
                ('move_id.closing_return_id.type_id', 'in', (
                    self.env.ref('l10n_nl_reports.nl_tax_return_type').id,
                    self.env.ref('l10n_nl_reports.nl_tax_correction_return_type').id,
                )),
            ])
            results_account_ids = {r['account_id'] for r in results}

            balance_per_line = defaultdict(int)
            # Sum all amounts of the previous closings per account and tax name.
            for line in previous_closing_lines:
                if line.account_id.id in results_account_ids:
                    balance_per_line[line.account_id.id, line.name] += line.balance

            tax_group_id = None
            # Add the previously computed sums to the query results to balance them out.
            for result in results:
                # Keep the last tax group to add extra lines at the end.
                tax_group_id = result['tax_group_id']
                balance = balance_per_line[result['account_id'], result['tax_name']]
                if not company.currency_id.is_zero(balance):
                    result['amount'] += balance
                    balance_per_line.pop((result['account_id'], result['tax_name']))
            # Filter out lines amounting in zero.
            results = [result for result in results if not company.currency_id.is_zero(result['amount'])]

            # Process the remaining lines that could not be matched.
            for (account_id, name), balance in balance_per_line.items():
                if company.currency_id.is_zero(balance):
                    continue
                results.append({
                    'tax_name': name,
                    'amount': balance,
                    'tax_group_id': tax_group_id,
                    'account_id': account_id,
                })

        if self.type_external_id in ('l10n_nl_reports.nl_tax_return_type', 'l10n_nl_reports.nl_tax_correction_return_type'):
            # Apply the rounding from the Dutch tax report by adding a line to the end of the query results
            # representing the sum of the roundings on each line of the tax report.
            rounding_accounts = {
                'profit': company.l10n_nl_rounding_difference_profit_account_id,
                'loss': company.l10n_nl_rounding_difference_loss_account_id,
            }

            vat_results_summary = [
                ('total', self.env.ref('l10n_nl.tax_report_rub_btw_5g').id, 'tax'),
            ]

            return self._vat_closing_entry_results_rounding(company, options, results, rounding_accounts, vat_results_summary)

        return super()._postprocess_vat_closing_entry_results(company, options, results)

    def _get_closing_report_options(self):
        options = super()._get_closing_report_options()

        if self.type_id.id == self.env.ref('l10n_nl_reports.nl_tax_correction_return_type').id:
            options['l10n_nl_is_correction'] = True

        return options

    def _on_post_submission_event(self):
        # Don't process anything until the return has been accepted by the SBR.
        if self.type_external_id == 'l10n_nl_reports.nl_tax_return_type' and self.l10n_nl_sbr_status != 'accepted':
            return
        return super()._on_post_submission_event()
