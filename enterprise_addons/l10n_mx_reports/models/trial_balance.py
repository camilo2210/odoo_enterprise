from lxml import etree
from lxml.objectify import fromstring
from collections import defaultdict

from odoo import _, fields, models, tools
from odoo.exceptions import UserError, RedirectWarning

CFDIBCE_XSLT_CADENA = 'l10n_mx_reports/data/xslt/1.3/BalanzaComprobacion_1_2.xslt'
CFDICATALOGO_XSLT_CADENA = 'l10n_mx_reports/data/xslt/1.3/CatalogoCuentas_1_2.xslt'


class AccountTrialBalanceReportHandler(models.AbstractModel):
    _inherit = 'account.trial.balance.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        # OVERRIDE
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        if self.env.company.account_fiscal_country_id.code == 'MX':
            # We cannot generate date options using this filter as this filter is inserted after.
            # It is only used to add an additional filter on the view but will be automatically fallback to a year period so it should not be an issue.
            # L10nMXTrialBalanceReportFilters is adding the l10n_mx_month_13 option key when the 'l10n_mx_month_13' filter is used.
            if 'l10n_mx_month_13' not in options['filter_date']['filters']:
                options['filter_date']['filters']['l10n_mx_month_13'] = {
                    **options['filter_date']['filters']['year'],
                    'key': 'l10n_mx_month_13',
                    'fallback': 'year',
                    'label': self.env._("Month 13"),
                    'always_shown': True,
                }
            options['l10n_mx_month_13'] = previous_options.get('l10n_mx_month_13', False)
            # Properly supporting comparisons with a Month 13 period is too complicated, so we turn the Month 13 filter off if the user does a comparison.
            # When doing a comparison, any Month 13 entries are included in the following (January) period.
            if options.get('comparison', {}).get('filter') != 'no_comparison':
                options['l10n_mx_month_13'] = False
            if options['l10n_mx_month_13']:
                self._l10n_mx_set_options_month_13(options)
            else:
                self._l10n_mx_set_options_non_month_13(options)

            options['buttons'] += [
                {'name': _("SAT (XML)"), 'action': 'open_sat_wizard', 'action_param': 'action_l10n_mx_generate_sat_xml', 'file_export_type': _("SAT (XML)"), 'sequence': 15},
                {'name': _("COA SAT (XML)"), 'action': 'export_file', 'action_param': 'action_l10n_mx_generate_coa_sat_xml', 'file_export_type': _("COA SAT (XML)"), 'sequence': 16},
            ]

        options['custom_display_config'] = {
            'components': {
                'AccountReportFilters': 'L10nMXTrialBalanceReportFilters',
            },
        }

    def open_sat_wizard(self, options, action):
        return {
            "name": self.env._("Export SAT"),
            "view_mode": "form",
            "views": [(False, "form")],
            "res_model": "l10n_mx_reports.sat.export.wizard",
            "type": "ir.actions.act_window",
            "target": "new",
            "context": {
                **self.env.context,
                "l10n_mx_reports_report_options": options,
            },
        }

    def _check_accounts_code_sat_validity(self, accounts, options, report_action):
        if options.get('l10n_mx_sat_ignore_errors'):
            return
        report = self.env['account.report'].browse(options['report_id'])
        incorrect_code_accounts = accounts.filtered('l10n_mx_is_sat_invalid')
        if incorrect_code_accounts:
            account_names = '\n'.join(_('\t- %(name)s', name=account.name) for account in incorrect_code_accounts)
            error_msg = _("Some of your accounts do not respect Odoo's code guidelines.\n\n%(account_names)s", account_names=account_names),
            action_vals = report.export_file({**options, 'l10n_mx_sat_ignore_errors': True}, report_action)
            raise RedirectWarning(error_msg, action_vals, _("Generate report"))

    def action_l10n_mx_generate_sat_xml(self, options):
        if self.env.company.account_fiscal_country_id.code != 'MX':
            raise UserError(_("Only Mexican company can generate SAT report."))

        sat_values = self._l10n_mx_get_sat_values(options)
        file_name = f"{sat_values['vat']}{sat_values['year']}{sat_values['month']}B{sat_values['type']}"
        cfdi = self.env['ir.qweb']._render('l10n_mx_reports.cfdibalance', sat_values)
        sat_report = self._l10n_mx_edi_add_digital_stamp(CFDIBCE_XSLT_CADENA, cfdi)

        return {
            'file_name': f"{file_name}.xml",
            'file_content': self.env['l10n_mx_edi.document']._convert_xml_to_attachment_data(sat_report),
            'file_type': 'xml',
        }

    def _l10n_mx_edi_add_digital_stamp(self, path_xslt, cfdi):
        """Add digital stamp certificate attributes in XML report"""
        tree = fromstring(cfdi)
        certificate_sudo = self.env.company.sudo().l10n_mx_edi_certificate_ids.filtered('is_valid')[:1]
        if not certificate_sudo:
            return tree

        with tools.file_open(path_xslt) as f:
            cadena_transformer = etree.parse(f)
            cadena = str(etree.XSLT(cadena_transformer)(tree))
            tree.attrib['Sello'] = certificate_sudo._sign(cadena)
            tree.attrib['noCertificado'] = ('%x' % int(certificate_sudo.serial_number))[1::2]
            tree.attrib['Certificado'] = certificate_sudo.pem_certificate.to_base64()
        return tree

    def _get_account_id2line(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        sat_options = self._l10n_mx_get_sat_options(options)
        report_lines = report._get_lines(sat_options)
        account_id2line = {}
        for line in report_lines:
            account_id = report._get_res_id_from_line_id(line.id, 'account.account')
            if account_id and not account_id2line.get(account_id):
                account_id2line[account_id] = line

        return account_id2line

    def _l10n_mx_get_sat_values(self, options):
        def get_column(column_type, external_label):
            col_group_index = next(group for group, group_vals in enumerate(options['column_groups']) if group_vals['forced_options']['trial_balance_column_type'] == column_type)
            return next(col for col in cols if col.column_group_index == col_group_index and col.expression_label == external_label)

        account_id2line = self._get_account_id2line(options)
        all_account_ids = tuple(account_id2line)
        accounts = self.env['account.account'].browse(all_account_ids)
        accounts = accounts.filtered('l10n_mx_is_sat_exportable')
        self._check_accounts_code_sat_validity(accounts, options, 'action_l10n_mx_generate_sat_xml')

        account_lines_dict = defaultdict(lambda: defaultdict(int))
        for account_id, line in account_id2line.items():
            account = accounts.browse(account_id).with_prefetch(all_account_ids)
            if account.account_type == 'equity_unaffected' or not account.l10n_mx_is_sat_exportable:
                continue

            is_credit_account = any(account.account_type.startswith(account_type) for account_type in ['liability', 'equity', 'income'])
            balance_sign = -1 if is_credit_account else 1
            cols = line.columns or []
            initial = balance_sign * (get_column('initial_balance', 'balance').no_format or 0.0)
            debit = get_column('period', 'debit').no_format or 0.0
            credit = get_column('period', 'credit').no_format or 0.0
            end = balance_sign * (get_column('end_balance', 'balance').no_format or 0.0)
            account_lines_dict[account.code]['initial'] += initial
            account_lines_dict[account.code]['debit'] += debit
            account_lines_dict[account.code]['credit'] += credit
            account_lines_dict[account.code]['end'] += end
        account_lines = [{
            'number': account_code,
            'initial': '%.2f' % account_lines_dict[account_code]['initial'],
            'debit': '%.2f' % account_lines_dict[account_code]['debit'],
            'credit': '%.2f' % account_lines_dict[account_code]['credit'],
            'end': '%.2f' % account_lines_dict[account_code]['end'],
        } for account_code in sorted(account_lines_dict.keys())]

        sat_options = self._l10n_mx_get_sat_options(options)
        report_date = fields.Date.to_date(sat_options['date']['date_from'])
        last_update = (
            self.env['account.move.line']
            .search(
                [
                    ('company_id', '=', self.env.company.id),
                    ('date', '>=', sat_options['date']['date_from']),
                    ('date', '<=', sat_options['date']['date_to']),
                    ('move_id.state', '=', 'posted'),
                ],
                order='write_date desc',
                limit=1,
            )
            .write_date
        )
        last_update = last_update if last_update else sat_options["date"]["date_to"]
        return {
            'vat': self.env.company.vat or '',
            'month': '13' if options.get('l10n_mx_month_13') else str(report_date.month).zfill(2),
            'year': report_date.year,
            'type': options.get('submit_type', 'N'),
            "lastupdate": fields.Date.to_date(last_update).strftime("%Y-%m-%d"),
            'accounts': account_lines,
        }

    def action_l10n_mx_generate_coa_sat_xml(self, options):
        if self.env.company.account_fiscal_country_id.code != 'MX':
            raise UserError(_("Only Mexican company can generate SAT report."))

        coa_values = self._l10n_mx_get_coa_values(options)
        file_name = f"{coa_values['vat']}{coa_values['year']}{coa_values['month']}CT"
        cfdi = self.env['ir.qweb']._render('l10n_mx_reports.cfdicoa', coa_values)
        coa_report = self._l10n_mx_edi_add_digital_stamp(CFDICATALOGO_XSLT_CADENA, cfdi)

        return {
            'file_name': f"{file_name}.xml",
            'file_content': self.env['l10n_mx_edi.document']._convert_xml_to_attachment_data(coa_report),
            'file_type': 'xml',
        }

    def _l10n_mx_get_coa_values(self, options):
        # Checking if debit/credit tags are installed
        debit_balance_account_tag = self.env.ref('l10n_mx.tag_debit_balance_account', raise_if_not_found=False)
        credit_balance_account_tag = self.env.ref('l10n_mx.tag_credit_balance_account', raise_if_not_found=False)
        if not debit_balance_account_tag or not credit_balance_account_tag:
            raise UserError(_("Missing Debit or Credit balance account tag in database."))

        account_id2line = self._get_account_id2line(options)
        all_account_ids = tuple(account_id2line)
        accounts = self.env['account.account'].browse(all_account_ids)
        accounts = accounts.filtered('l10n_mx_is_sat_exportable')
        self._check_accounts_code_sat_validity(accounts, options, 'action_l10n_mx_generate_coa_sat_xml')

        accounts_template_data = []
        no_tag_accounts = self.env['account.account']
        for account in accounts:
            nature = False
            if debit_balance_account_tag in account.tag_ids:
                nature = 'D'
            if credit_balance_account_tag in account.tag_ids:
                nature = 'A'
            if not nature:
                no_tag_accounts |= account

            accounts_template_data.append({
                'code': account.code and account.code[:6],
                'number': account.code,
                'name': account.name,
                'level': len(account.parent_ids.filtered('l10n_mx_is_sat_exportable')),
                'nature': nature,
                'parent_code': account.parent_id.l10n_mx_is_sat_exportable and account.parent_id.code,
            })

        if no_tag_accounts:
            raise RedirectWarning(
                _("Some accounts present in your trial balance don't have a Debit or a Credit balance account tag."),
                {
                    'name': _("Accounts without tag"),
                    'type': 'ir.actions.act_window',
                    'views': [(False, 'list'), (False, 'form')],
                    'res_model': 'account.account',
                    'target': 'current',
                    'domain': [('id', 'in', no_tag_accounts.ids)],
                },
                _('Show list')
            )

        report_date = fields.Date.to_date(self._l10n_mx_get_sat_options(options)['date']['date_from'])
        return {
            'vat': self.env.company.vat or '',
            'month': str(report_date.month).zfill(2),
            'year': report_date.year,
            'accounts': accounts_template_data,
        }

    def _l10n_mx_get_sat_options(self, options):
        sat_options = options.copy()
        del sat_options['comparison']
        return self.env['account.report'].browse(options['report_id']).get_options(
            previous_options={
                **sat_options,
                'hierarchy': True,  # We need the hierarchy activated to get group lines
            }
        )

    def _l10n_mx_set_options_month_13(self, options):
        """ Configure the options dict if the 'Month 13' option is active.

            We change the report period to the last day of the current fiscal year,
            because the Month 13 Trial Balance makes no sense on any other day.

            Our objective is to have everything before the closing entry under Initial Balance,
            and just the closing entry under Current Period.

            So:
            - we stretch the initial balance's period to also cover the report period,
              but excluding Month 13 entries during the report period; and
            - we restrict the current period to Month 13 entries.
        """
        options['column_headers'][0][1]['name'] = self.env._('Month 13')

        # Change the report date so that it coincides with the end of the fiscal year,
        # if that is not already the case.
        report_date_to = fields.Date.to_date(options['date']['date_to'])
        last_day_of_fiscalyear = self.env.company.compute_fiscalyear_dates(report_date_to)['date_to']
        last_day_of_fiscalyear_str = fields.Date.to_string(last_day_of_fiscalyear)
        options['date']['date_from'] = last_day_of_fiscalyear_str
        options['date']['date_to'] = last_day_of_fiscalyear_str
        options['date']['string'] = '%s, %s' % (self.env._('Month 13'), last_day_of_fiscalyear.year)

        # Retrieve the options dictionaries corresponding to each column group.
        initial_col_group_index = options['columns'][0]['column_group_index']
        current_col_group_index = options['columns'][1]['column_group_index']

        initial_col_group_data = options['column_groups'][initial_col_group_index]
        current_col_group_data = options['column_groups'][current_col_group_index]

        # Set the options dict for the initial balance col group.
        # We need to stretch the period all the way to the end of the report period,
        # and exclude the Month 13 entries within the report period.
        initial_col_group_data['forced_options']['date']['date_to'] = last_day_of_fiscalyear_str
        initial_col_group_data['forced_domain'] += [
            '|',
            ('move_id.l10n_mx_closing_move', '=', False),
            ('date', '<', last_day_of_fiscalyear_str),
        ]

        # Set the options dict for the current period col group.
        # We need to include only Month 13 entries.
        current_col_group_data['forced_options']['date']['date_from'] = last_day_of_fiscalyear_str
        current_col_group_data['forced_options']['date']['date_to'] = last_day_of_fiscalyear_str
        current_col_group_data['forced_domain'] += [('move_id.l10n_mx_closing_move', '=', True)]

    def _l10n_mx_set_options_non_month_13(self, options):
        """ Configure the options dict if the 'Month 13' option is inactive.

            In this case, the idea is to pretend that Month 13 entries fall between the last day of the fiscal year
            and the first day of the next fiscal year.

            So, we only take into account Month 13 entries that fall before the first day of the fiscal year within
            the report end date.
        """
        report_date_to = fields.Date.to_date(options['date']['date_to'])
        first_day_of_fiscalyear = self.env.company.compute_fiscalyear_dates(report_date_to)['date_from']
        first_day_of_fiscalyear_str = fields.Date.to_string(first_day_of_fiscalyear)

        forced_domain = options.setdefault('forced_domain', [])
        forced_domain += [
            '|',
            ('move_id.l10n_mx_closing_move', '=', False),
            '&', ('move_id.l10n_mx_closing_move', '=', True), ('date', '<', first_day_of_fiscalyear_str),
        ]
