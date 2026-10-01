from odoo import _, Command, models
from odoo.tools import SQL


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def action_submit(self):
        # OVERRIDE account_reports
        self.ensure_one()
        if self.type_external_id != 'l10n_cl_reports.cl_f29_tax_return_type':
            return super().action_submit()

        return self.env['l10n_cl_reports_f29.return.submission.wizard']._open_submission_wizard(account_return=self)

    def _generate_tax_closing_entries_create_values(self, options):
        # EXTENDS account_reports
        closing_move_to_create = super()._generate_tax_closing_entries_create_values(options)

        if self.type_external_id == 'l10n_cl_reports.cl_f29_tax_return_type':
            for move in closing_move_to_create:
                move['ref'] = _("F29 Tax Closing Entry - %(date_to)s", date_to=self.date_to)

        return closing_move_to_create

    def _create_tax_payable_receivable_line(self, total, payable_account_id, receivable_account_id):
        # EXTENDS account_reports
        command = super()._create_tax_payable_receivable_line(total, payable_account_id, receivable_account_id)

        if self.type_external_id == 'l10n_cl_reports.cl_f29_tax_return_type':
            command[2]['name'] = _('F29 (547) Total Taxes for the Period')

        return command

    def _compute_tax_closing_entry(self, company, options):
        # OVERRIDE account_reports
        if self.type_external_id != 'l10n_cl_reports.cl_f29_tax_return_type':
            return super()._compute_tax_closing_entry(company, options)

        date_scope = 'strict_range'
        AccountChartTemplate = self.env['account.chart.template'].with_company(company)
        currency = company.currency_id
        move_vals_lines = []
        closing_accounts = self._get_tax_closing_accounts(company)
        _advance_account, receivable_account, _payable_account = closing_accounts

        query = SQL(
            '''
            WITH account_move_line_data AS (%(aml_query)s)
            SELECT
                aml.grid,
                aml.account_id,
                SUM(aml.balance) AS balance
            FROM account_move_line_data aml
            GROUP BY 1, 2
            ''',
            aml_query=self.env['l10n_cl.tax.report.handler']._f29_get_aml_query(options, date_scope),
        )

        self.env.cr.execute(query)
        grid_results = {res['grid']: res for res in self.env.cr.dictfetchall()}

        # 048
        report = self.env['account.report'].browse(options['report_id'])
        options_domain = report._get_options_domain(options, date_scope)
        account_048 = AccountChartTemplate.ref('account_210730')
        balance_048 = self.env['account.move.line']._read_group(
            domain=[options_domain, ('account_id', '=', account_048.id)],
            aggregates=['balance:sum'],
        )[0][0]

        # 755
        date_to = options['date']['date_to']
        expr_755 = self.env.ref('l10n_cl_reports_f29.f29_04_child_1_bool_l3_010')
        external_value_755 = self.env['account.report.external.value'].search([
            ('target_report_expression_id', '=', expr_755.id),
            ('company_id', '=', company.id),
            ('date', '=', date_to),
        ], limit=1)

        # 062
        expr_062 = self.env.ref('l10n_cl_reports_f29.f29_04_child_9_tax_l2_075')
        external_value_062 = self.env['account.report.external.value'].search([
            ('target_report_expression_id', '=', expr_062.id),
            ('company_id', '=', company.id),
            ('date', '=', date_to),
        ], limit=1)

        balance_538 = sum(grid_results[grid]['balance'] for grid in ('503', '110', '512', '509') if grid in grid_results)
        exempt_balance = -abs(sum(grid_results[grid]['balance'] for grid in ('020', '142') if grid in grid_results))

        balance_062 = external_value_062.value / 100.0 * (exempt_balance + balance_538)

        line_val_dict = {
            '538': {
                'name': _("VAT Tax Debit"),
                'balance': abs(sum(grid_results[grid]['balance'] for grid in ('502', '111', '510', '513') if grid in grid_results)),
                'account_id': next((grid_results[grid]['account_id'] for grid in ('502', '111', '510', '513') if grid in grid_results), 0),
            },
            '537': {
                'name': _("VAT Tax Credit"),
                'balance': -abs(sum(grid_results[grid]['balance'] for grid in ('520', '762', '525', '528', '532', '535') if grid in grid_results)),
                'account_id': next((grid_results[grid]['account_id'] for grid in ('520', '762', '525', '528', '532', '535') if grid in grid_results), 0),
            },
            '151': {
                'name': _("Withholding Fees Over Rents Law 21133"),
                'balance': abs(grid_results.get('151', {}).get('balance', 0.0)),
                'account_id': grid_results.get('151', {}).get('account_id', 0),
            },
            '048': {
                'name': _("Workers' Tax"),
                'balance': abs(balance_048),
                'account_id': account_048.id,
            },
            '062': {
                'name': _("PPM Rate (IMPORTANT: Must remain 0 if PPM Base is negative)"),
                'balance': abs(balance_062),
                'account_id': AccountChartTemplate.ref('account_110740').id,
            },
            '596': {
                'name': _("Withholding Subject Change"),
                'balance': -abs(grid_results.get('039', {}).get('balance', 0.0)),
                'account_id': grid_results.get('039', {}).get('account_id', 0),
            },
        }

        line_val_dict |= {
            '755': {
                'name': _("VAT Tax Postponement"),
                'balance': -external_value_755.value * (line_val_dict['538']['balance'] - abs(line_val_dict['537']['balance'])),
                'account_id': AccountChartTemplate.ref('account_210760').id,
            },
            '077': {
                'name': _("Remaining Tax Credit"),
                'balance': min(line_val_dict['538']['balance'] - line_val_dict['537']['balance'], 0.0),
                'account_id': receivable_account,
            },
        }

        for sii_code, line_data in line_val_dict.items():
            if line_data['account_id'] and not currency.is_zero(line_data['balance']):
                line_data['name'] = _("F29 (%(code)s) %(name)s", code=sii_code, name=line_data['name'])
                move_vals_lines.append(Command.create({
                    **line_data,
                    'company_id': company.id,
                }))

        if not move_vals_lines:
            # let the generic function handle empty tax reports
            return super()._compute_tax_closing_entry(company, options)

        tax_group_subtotal = {
            closing_accounts: -sum(com[2]['balance'] for com in move_vals_lines)
        }

        return move_vals_lines, tax_group_subtotal

    def _evaluate_period_amount_to_pay_from_tax_closing_accounts(self, payable_accounts, receivable_accounts):
        # OVERRIDE account_reports
        self.ensure_one()
        if self.type_external_id != 'l10n_cl_reports.cl_f29_tax_return_type':
            return super()._evaluate_period_amount_to_pay_from_tax_closing_accounts(payable_accounts, receivable_accounts)

        line_name = _('F29 (547) Total Taxes for the Period')
        total_taxes_line = self.closing_move_ids.line_ids.filtered(lambda line: line.name == line_name)
        return -total_taxes_line.balance if total_taxes_line else 0.0
