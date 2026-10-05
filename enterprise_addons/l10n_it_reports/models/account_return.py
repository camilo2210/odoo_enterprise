from itertools import chain
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.fields import Domain
from odoo.tools import date_utils
from odoo.exceptions import UserError


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        if country_code == 'IT' and (ec_sales_return_type := self.env.ref('l10n_it_reports.it_ec_sales_list_return_type', raise_if_not_found=False)):

            months_offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            previous_period_start, previous_period_end = ec_sales_return_type._get_period_boundaries(main_company, fields.Date.context_today(self) - relativedelta(months=months_offset))
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, ec_sales_return_type.report_id)
            ec_sales_list_tags_info = self.env['l10n_it_reports.ec.sales.report.handler']._get_ec_sales_tax_tags()
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
    is_quarter_month = fields.Boolean(compute='_compute_is_quarter_month')
    country_code = fields.Char(related='company_id.country_id.code', depends=['company_id.country_id'])

    @api.depends('date_to')
    def _compute_is_quarter_month(self):
        for record in self:
            if record.date_to:
                month = record.date_to.month
                record.is_quarter_month = month in [3, 6, 9, 12]
            else:
                record.is_quarter_month = False

    @api.depends('type_id', 'state', 'country_code', 'is_quarter_month')
    def _compute_visible_states(self):
        super()._compute_visible_states()

        for record in self:
            if record.country_code != 'IT':
                continue

            new_states = []
            for state_dict in record.visible_states:
                mutated_state = state_dict.copy()
                if mutated_state['name'] == 'submitted' and not record.is_quarter_month:
                    mutated_state['label'] = self.env._('Close')

                new_states.append(mutated_state)

            record.visible_states = new_states

    def _prepare_submission(self):
        """This action will be called by the POST button on a tax report account move.
           As posting this move will generate the XML report, it won't call `action_post`
           immediately, but will open the wizard that configures this XML file.
           Validating the wizard will resume the `action_post` and take these options in
           consideration when generating the XML report.
        """
        res = super()._prepare_submission()
        # The following process is only required if we are posting an Italian tax closing move.
        if not (
            self.country_code == "IT"
            and self.closing_move_ids
            and "l10n_it_reports_monthly_tax_report_options" not in self.env.context
            and self.is_quarter_month
        ):
            return res

        closing_max_date = max(self.closing_move_ids.mapped('date'))
        last_posted_tax_closing = self.env['account.move'].search(Domain([
            *self.env['account.move']._check_company_domain(self.company_id),
            ('closing_return_id', '!=', False),
            ('move_type', '=', 'entry'),
            ('state', '=', 'posted'),
            ('date', '<', closing_max_date),
        ]) & Domain.OR([
            Domain('fiscal_position_id.country_id.code', '=', 'IT'),
            Domain([
                ('fiscal_position_id', '=', False),
                ('company_id.account_fiscal_country_id.code', '=', 'IT'),
            ])
        ]), order='date desc', limit=1)
        quarterly = self.env.company.account_return_periodicity == 'trimester'
        if last_posted_tax_closing:
            # If there is a posted tax closing, we only check that there is no gap in the months.
            max_expected_gap = 3 if quarterly else 1
            if (
                last_posted_tax_closing.date + relativedelta(months=max_expected_gap) < closing_max_date
                and last_posted_tax_closing.date < closing_max_date - relativedelta(months=max_expected_gap)
            ):
                raise UserError(_("You cannot post the tax closing of %(month)s without posting the previous month tax closing first.", month=closing_max_date.strftime("%m/%Y")))
        else:
            # If no tax closing has ever been posted, we have to check if there are Italian taxes in a previous month (meaning a missing tax closing).
            previous_move = self.env['account.move'].search_fetch(Domain([
                *self.env['account.move']._check_company_domain(self.company_id),
                ('closing_return_id', '=', False),
                ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
                ('date', '<', date_utils.start_of(closing_max_date, 'quarter' if quarterly else 'month')),
            ]) & Domain.OR([
                Domain('fiscal_position_id.country_id.code', '=', 'IT'),
                Domain([
                    ('fiscal_position_id', '=', False),
                    ('company_id.account_fiscal_country_id.code', '=', 'IT'),
                ])
            ]), order='date asc', field_names=['date'], limit=1)
            if previous_move:
                report = self.env.ref('l10n_it.tax_monthly_report_vat')
                current = previous_move.date.replace(day=1)
                while current <= closing_max_date.replace(day=1):
                    date_from = date_utils.start_of(current, 'month')
                    date_to = date_utils.end_of(current, 'month')
                    at_date_options = report.get_options({
                        'selected_variant_id': report.id,
                        'date': {
                            'date_from': date_from,
                            'date_to': date_to,
                        },
                    })
                    at_date_report_lines = report._get_lines(at_date_options)
                    colname_to_idx = {col.get('expression_label'): idx for idx, col in enumerate(at_date_options.get('columns', []))}
                    balance_col_idx = colname_to_idx.get('balance')
                    debit_col_idx = colname_to_idx.get('debit')
                    credit_col_idx = colname_to_idx.get('credit')
                    if any(
                        (
                            balance_col_idx is not None
                            and line.columns[balance_col_idx]['no_format']
                        )
                        or (
                            balance_col_idx is None
                            and debit_col_idx is not None
                            and credit_col_idx is not None
                            and line.columns[debit_col_idx]['no_format'] != line.columns[credit_col_idx]['no_format']
                        )
                        for line in at_date_report_lines
                        if line['name'].startswith('VP')
                    ):
                        raise UserError(_("You cannot post the tax closing of that month because older months have taxes to report but no tax closing posted. Oldest month is %(month)s", month=current.strftime("%m/%Y")))
                    current += relativedelta(months=1)
        # If the process has not been stopped yet, we open the wizard for the xml export.
        view_id = self.env.ref('l10n_it_reports.monthly_tax_report_xml_export_wizard_view').id
        ctx = self.env.context.copy()
        ctx.update({
            'l10n_it_moves_to_post': self.ids,
            'l10n_it_reports_monthly_tax_report_options': {
                'date': {'date_to': closing_max_date},
            },
        })

        return {
            'name': _('Post a tax report entry'),
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'res_model': 'l10n_it_reports.monthly.tax.report.xml.export.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': ctx,
        }

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        if self.type_external_id == 'l10n_it_reports.it_tax_return_type':
            tax_tags = self.type_id.report_id.line_ids.expression_ids._get_matching_tags()
            domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        elif self.type_external_id == 'l10n_it_reports.it_withh_tax_return_type':
            withholding_purchase_report_line = self.env.ref('l10n_it.withh_purchase_tax_report_it_line', raise_if_not_found=False)
            if withholding_purchase_report_line:
                tax_tags = withholding_purchase_report_line.expression_ids._get_matching_tags()
                domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        elif self.type_external_id == 'l10n_it_reports.it_enasarco_tax_return_type':
            enasarco_purchase_report_line = self.env.ref('l10n_it.enasarco_purchase_tax_report_it_line', raise_if_not_found=False)
            if enasarco_purchase_report_line:
                tax_tags = enasarco_purchase_report_line.expression_ids._get_matching_tags()
                domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        return domain

    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        months_per_period = return_type._get_periodicity_months_delay(company)
        if return_type_external_id == 'l10n_it_reports.it_tax_return_type':
            return date_to + relativedelta(days=16)
        if return_type_external_id == 'l10n_it_reports.it_ec_sales_list_return_type' and months_per_period in (1, 3):
            return date_to + relativedelta(days=25)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)
