from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, release
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, SQL

DATEFORMAT_SIE4 = '%Y%m%d'
DATEFORMAT_MAIN = DEFAULT_SERVER_DATE_FORMAT


class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options)
        if self.env.company.account_fiscal_country_id.code == 'SE':
            options.setdefault('buttons', []).append({
                'name': _("SIE 4"),
                'sequence': 50,
                'action': 'export_file',
                'action_param': 'export_l10n_se_sie4_file',
                'file_export_type': _("SIE")
            })

    @api.model
    def _get_l10n_se_sie4_dates(self, options, use_sie4_format=False):
        """ Returns a dictionary of date strings from previous year's start to next year's end in the desired format.

        :param options: ``account.report`` options dictionary
        :param use_sie4_format: desired format. ex: without sie4_format '2024-01-01' -> with sie4_format '20240101'
        """
        result_strf = DATEFORMAT_SIE4 if use_sie4_format else DATEFORMAT_MAIN
        datetime_from = datetime.strptime(options['date']['date_from'], DATEFORMAT_MAIN)
        datetime_to = datetime.strptime(options['date']['date_to'], DATEFORMAT_MAIN)
        previous_fiscal_year = self.env['account.fiscal.year'].search([
            ('date_to', '<=', options['date']['date_from'])
        ], order='date_to desc', limit=1)
        prev_date_from = previous_fiscal_year.date_from if previous_fiscal_year else (datetime_from - relativedelta(years=1))
        prev_date_to = previous_fiscal_year.date_to if previous_fiscal_year else (datetime_from - relativedelta(days=1))
        return {
            'prev_date_from': prev_date_from.strftime(result_strf),
            'prev_date_to': prev_date_to.strftime(result_strf),
            'curr_date_from': datetime_from.strftime(result_strf),
            'curr_date_to': datetime_to.strftime(result_strf),
            'next_date_from': (datetime_to + relativedelta(days=1)).strftime(result_strf),
            'next_date_to': (datetime_to + relativedelta(years=1)).strftime(result_strf),
        }

    @api.model
    def _get_l10n_se_sie4_ktyp(self, account_type):
        group_asset = {'asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'}
        group_debt = {'liability_payable', 'liability_credit_card', 'liability_current', 'liability_non_current', 'equity',
                      'equity_unaffected', 'off_balance'}
        group_cost = {'expense', 'expense_depreciation', 'expense_direct_cost'}

        if account_type in group_asset:
            return 'T'
        if account_type in group_debt:
            return 'S'
        if account_type in group_cost:
            return 'K'
        return 'I'  # income type

    @api.model
    def _get_l10n_se_sie4_options(self, report, date_from, date_to):
        return report.get_options({
            'date': {
                'date_from': date_from,
                'date_to': date_to,
            },
            'export_mode': 'file',
        })

    @api.model
    def _export_l10n_se_sie4_identification(self, options):
        dates = self._get_l10n_se_sie4_dates(options, use_sie4_format=True)

        return [
            '#FLAGGA 0',
            '#FORMAT PC8',
            '#SIETYP 4',
            f'#PROGRAM "Odoo" {release.version}',
            f'#GEN {fields.Date.context_today(self).strftime(DATEFORMAT_SIE4)}',
            f'#FNAMN "{options["companies"][0]["name"]}"',
            f'#RAR -1 {dates["prev_date_from"]} {dates["prev_date_to"]}',
            f'#RAR  0 {dates["curr_date_from"]} {dates["curr_date_to"]}',
        ]

    @api.model
    def _export_l10n_se_sie4_chart_of_account(self, options):
        sie4_coa_lines = []
        company_id = options['companies'][0]['id']
        accounts = self.env['account.account'].with_company(company_id).search([
            *self.env['account.account']._check_company_domain(company_id),
        ])

        for account in accounts:
            sie4_coa_lines.extend((
                f'#KONTO {account.code} "{account.name}"',
                f'#KTYP  {account.code} {self._get_l10n_se_sie4_ktyp(account.account_type)}',
            ))

        return sie4_coa_lines

    @api.model
    def _l10n_se_sie4_get_initial_balances_values(self, report, options, filtered_accounts):
        def get_dict_values_from_report_line(line):
            return {
                'balance': line.columns[colname_to_idx['balance']].no_format,
                'debit': line.columns[colname_to_idx['debit']].no_format,
                'credit': line.columns[colname_to_idx['credit']].no_format,
            }
        options = {
            **options,
            'unfold_all': True,
        }
        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        lines = report._get_lines(options)
        initial_balances = {}
        account_by_ids = {account.id: account for account in filtered_accounts}
        for line in lines:
            _model, res_id = report._get_model_info_from_id(line.id)

            if isinstance(res_id, str) and 'balance_line' in res_id:
                account_id = report._get_res_id_from_line_id(line.id, 'account.account')
                account = account_by_ids.get(account_id, False)
                if account:
                    initial_balances[account] = get_dict_values_from_report_line(line)

        return initial_balances

    @api.model
    def _export_l10n_se_sie4_bs_balance(self, options):
        """ Generates the opening/closing balance lines and return them as a list of string line.
        In SIE 4, the opening/closing balance lines are saved with the following keywords:

        - "IB" -> Opening balance
        - "UB" -> Closing balance

        The number to the next of them refers to what year they are referring to.
        "0" means current year, "-1" means previous year.
        Consequently, this also means that "#UB -1" is the exact same as "#IB 0".
        """
        sie4_bs_balance_lines = []
        report = self.env['account.report'].browse(options['report_id'])
        dates = self._get_l10n_se_sie4_dates(options)
        company_id = options['companies'][0]['id']
        bs_accounts = self.env['account.account'].with_company(company_id).search_fetch(
            domain=[
                *self.env['account.account']._check_company_domain(company_id),
                ('include_initial_balance', '=', True),
            ],
            field_names=['id'],
        )
        seen_bs_account_codes = set()
        prev_ib, prev_ub, curr_ib, curr_ub = {}, {}, {}, {}  # dict[str, str] | {account_code: balance_str_line}

        prev_year_options = self._get_l10n_se_sie4_options(report, dates['prev_date_from'], dates['prev_date_to'])
        next_year_options = self._get_l10n_se_sie4_options(report, dates['next_date_from'], dates['next_date_to'])
        prev_ib_values = self.with_company(company_id)._l10n_se_sie4_get_initial_balances_values(report, prev_year_options, bs_accounts)
        curr_ib_values = self.with_company(company_id)._l10n_se_sie4_get_initial_balances_values(report, options, bs_accounts)
        next_ib_values = self.with_company(company_id)._l10n_se_sie4_get_initial_balances_values(report, next_year_options, bs_accounts)

        for ib_values in (prev_ib_values, curr_ib_values, next_ib_values):
            for account, ib_item in ib_values.items():
                if ib_item != {}:
                    seen_bs_account_codes.add(account.code)
                    if ib_values is prev_ib_values:  # for [IB/-1] (previous year opening balance)
                        prev_ib[account.code] = f'#IB  -1 {account.code} {ib_item["balance"]}'
                    elif ib_values is curr_ib_values:  # for [UB/-1] and [IB/0] (previous year closing balance + current year opening balance)
                        prev_ub[account.code] = f'#UB  -1 {account.code} {ib_item["balance"]}'
                        curr_ib[account.code] = f'#IB   0 {account.code} {ib_item["balance"]}'
                    else:  # ib_values is next_ib_values  # for [UB/0] (current year closing balance)
                        curr_ub[account.code] = f'#UB   0 {account.code} {ib_item["balance"]}'

        default_ib_values = ('#IB  -1', '#UB  -1', '#IB   0', '#UB   0')
        for account_code in sorted(seen_bs_account_codes):
            for idx, period_ib in enumerate((prev_ib, prev_ub, curr_ib, curr_ub)):
                if account_code in period_ib:
                    sie4_bs_balance_lines.append(period_ib[account_code])
                else:  # if the mentioned account doesn't exist in other periods, fill it with a default value
                    default_ib_value = default_ib_values[idx]
                    sie4_bs_balance_lines.append(f'{default_ib_value} {account_code} 0.0')

        return sie4_bs_balance_lines

    @api.model
    def _export_l10n_se_sie4_pl_balance(self, options):
        sie4_pl_balance_lines = []
        dates = self._get_l10n_se_sie4_dates(options)
        company_id = options['companies'][0]['id']

        common_domain = [
            *self.env['account.move.line']._check_company_domain(company_id),
            ('account_id.include_initial_balance', '=', False),
            ('display_type', 'not in', ('line_section', 'line_subsection', 'line_note')),
            ('move_id.state', '!=', 'cancel'),
        ]
        prev_year_domain = common_domain + [('date', '>=', dates['prev_date_from']), ('date', '<=', dates['prev_date_to'])]
        curr_year_domain = common_domain + [('date', '>=', dates['curr_date_from']), ('date', '<=', dates['curr_date_to'])]

        prev_account_sum_group = self.env['account.move.line'].with_company(company_id)._read_group(prev_year_domain, ['account_id'], ['balance:sum'])
        curr_account_sum_group = self.env['account.move.line'].with_company(company_id)._read_group(curr_year_domain, ['account_id'], ['balance:sum'])
        prev_code_sum_map = {account.code: str(account_sum) for account, account_sum in prev_account_sum_group}
        curr_code_sum_map = {account.code: str(account_sum) for account, account_sum in curr_account_sum_group}
        seen_account_code = set(prev_code_sum_map.keys()).union(curr_code_sum_map.keys())

        for account_code in sorted(seen_account_code):
            sie4_pl_balance_lines.extend((
                f'#RES -1 {account_code} {prev_code_sum_map.get(account_code, "0.0")}',
                f'#RES  0 {account_code} {curr_code_sum_map.get(account_code, "0.0")}',
            ))

        return sie4_pl_balance_lines

    @api.model
    def _export_l10n_se_sie4_verification(self, options):
        sie4_verification_lines = []
        report = self.env['account.report'].browse(options.get('report_id'))
        company_ids = report.get_report_company_ids(options)
        query = report._get_report_query(options, 'strict_range', [])
        account_alias = 'account_move_line__account_id'
        condition = SQL(
            "%s = %s",
            SQL.identifier('account_move_line', 'account_id'),
            SQL.identifier(account_alias, 'id')
        )
        query.add_join('JOIN', account_alias, 'account_account', condition)
        account_env = self.env['account.account'].with_context(allowed_company_ids=company_ids)
        account_code = account_env._field_to_sql(account_alias, 'code', query)
        sql_query = SQL(
            """
            SELECT
                m.id AS move_id,
                m.name AS move_name,
                m.date AS move_date,
                %(account_code)s AS account_code,
                account_move_line.balance AS balance
            FROM %(table)s
            JOIN account_move m ON m.id = account_move_line.move_id
            WHERE %(where_clause)s
            ORDER BY m.date ASC, m.name ASC, m.id ASC, account_move_line.id ASC
            """,
            account_code=account_code,
            table=query.from_clause,
            where_clause=query.where_clause,
        )
        self.env.flush_all()
        self.env.cr.execute(sql_query)
        last_move_id = None
        verification_idx = 0
        for row in self.env.cr.dictfetchall():
            current_move_id = row['move_id']
            if current_move_id != last_move_id:
                if last_move_id is not None:
                    sie4_verification_lines.append('}')
                verification_idx += 1
                move_date_str = row['move_date'].strftime(DATEFORMAT_SIE4)
                sie4_verification_lines.extend((
                    f'#VER A {verification_idx} {move_date_str} "{row["move_name"]}"',
                    '{'
                ))
                last_move_id = current_move_id
            sie4_verification_lines.append(f'    #TRANS {row["account_code"]} {{}} {row["balance"]}')
        if last_move_id is not None:
            sie4_verification_lines.append('}')
        return sie4_verification_lines

    def export_l10n_se_sie4_file(self, options):
        if options['date']['period_type'] != 'year':
            raise UserError(_("You must set the period type to be in fiscal year in order to export SIE 4 file."))
        if len(options['companies']) > 1:
            selected_companies = self.env['res.company'].search_fetch(
                domain=[('id', 'in', [company_dict['id'] for company_dict in options['companies']])],
                field_names=['chart_template'],
            )
            if len(set(selected_companies.mapped('chart_template'))) >= 2:  # we can only export one chart template
                raise UserError(_("You can't export multiple companies with different templates."))
            else:
                # filter other selected company/ies in the options
                options['companies'] = [company_dict for company_dict in options['companies'] if company_dict['id'] == self.env.company.id]

        content_lines = [
            *self._export_l10n_se_sie4_identification(options),
            *self._export_l10n_se_sie4_chart_of_account(options),
            *self._export_l10n_se_sie4_bs_balance(options),
            *self._export_l10n_se_sie4_pl_balance(options),
            *self._export_l10n_se_sie4_verification(options),
            '',  # to make sure the file ends with a new line
        ]
        return {
            'file_name': f'odoo_sie4_{fields.Date.context_today(self).strftime(DATEFORMAT_SIE4)}.se',
            'file_content': '\n'.join(content_lines).encode('437'),
            'file_type': 'txt',
        }
