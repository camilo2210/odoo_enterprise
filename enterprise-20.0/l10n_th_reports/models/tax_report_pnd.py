# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.tools import SQL


def _csv_row(*data, delimiter="|"):
    # return a csv formatted file and add newline by the end
    return delimiter.join(data) + '\n'


TITLE_MAP_TH = {
    # PND 3 (Individual)
    'khun': 'คุณ',
    'mr': 'นาย',
    'ms': 'นางสาว',
    'mrs': 'นาง',
    # PND 53 (Company)
    'company_ltd': 'บริษัท',
    'pub_company_ltd': 'บริษัท',
    'ltd_partner': 'ห้างหุ้นส่วนจำกัด',
    'foundation': 'มูลนิธิ',
    'asso': 'สมาคม',
    'joint_venture': 'กิจการร่วมค้า',
    'others': '',
}


class L10n_ThPndReportHandler(models.AbstractModel):
    _name = 'l10n_th.pnd.report.handler'
    _inherit = ["account.tax.report.handler"]
    _description = "Abstract Tax Report PND Handler"

    def _get_custom_groupby_map(self):
        def _income_tax_type_label(key):
            selection_labels = dict(self.env['account.tax']._fields['l10n_th_income_tax_type'].selection)
            return selection_labels.get(key, key or '')

        def _get_partner_display_name(partner):
            if partner.is_company:
                return partner.name
            return f"{TITLE_MAP_TH.get(partner.l10n_th_title, "คุณ")} {partner.name}"

        return {
            'l10n_th_income_tax_type': {
                'model': None,
                'label_builder': lambda keys: {key: _income_tax_type_label(key) for key in keys},
                'domain_builder': lambda value: [('tax_line_id.l10n_th_income_tax_type', '=', value)],
            },
            'move_id': {
                'model': 'account.move',
                'label_builder': lambda keys: {
                    move.id: f"{move.name} - {_get_partner_display_name(move.partner_id)}"
                    for move in self.env['account.move'].browse(key for key in keys if key)
                } | ({None: self.env._("Unknown")} if None in keys else {}),
                'domain_builder': lambda value: [('move_id', '=', value)],
            },
        }

    def _report_engine_pnd(self, options, date_scope, formulas_dict, current_groupby, wht_tag_name, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        country_id = self.env.ref('base.th').id
        wht_tag_ids = self.env['account.account.tag']._get_tax_tags(wht_tag_name, country_id).ids

        domain = [('tax_tag_ids', 'in', wht_tag_ids)]
        query = report._get_report_query(options, 'strict_range', domain=domain)

        if current_groupby == 'l10n_th_income_tax_type':
            groupby_field_sql = SQL.identifier('wh_tax', 'l10n_th_income_tax_type')
        elif current_groupby:
            groupby_field_sql = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, query)
        else:
            groupby_field_sql = SQL()

        sql_query = SQL(
            """
                SELECT
                    %(select_from_groupby)s
                    MAX(partner.vat) AS tax_id,
                    MAX(account_move_line.date) AS payment_date,
                    -1 * SUM(account_move_line.tax_base_amount) AS withholding_base,
                    MAX(ABS(wh_tax.amount)) AS tax_rate,
                    -1 * SUM(account_move_line.balance) AS withholding_amount
                FROM %(table_references)s
                LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
                LEFT JOIN account_tax wh_tax ON account_move_line.tax_line_id = wh_tax.id
                WHERE %(search_condition)s
                %(groupby_clause)s
                %(orderby_clause)s
            """,
            select_from_groupby=SQL('%s AS grouping_key,', groupby_field_sql) if groupby_field_sql else SQL(),
            table_references=query.from_clause,
            search_condition=query.where_clause,
            groupby_clause=SQL('GROUP BY %s', groupby_field_sql) if groupby_field_sql else SQL(),
            orderby_clause=SQL('ORDER BY payment_date ASC'),
        )
        query_res_lines = self.env.execute_query_dict(sql_query)

        def build_result_dict(lines):
            if not lines:
                return {
                    'tax_id': None,
                    'payment_date': None,
                    'withholding_base': 0.0,
                    'tax_rate': 0.0,
                    'withholding_amount': 0.0,
                    'has_sublines': False,
                }
            if current_groupby == 'move_id':
                return {
                    'tax_id': lines[0]['tax_id'] or '',
                    'payment_date': lines[0]['payment_date'],
                    'withholding_base': sum(line['withholding_base'] or 0 for line in lines),
                    'tax_rate': None,
                    'withholding_amount': sum(line['withholding_amount'] or 0 for line in lines),
                    'has_sublines': True,
                }
            if current_groupby == 'l10n_th_income_tax_type':
                return {
                    'tax_id': None,
                    'payment_date': None,
                    'withholding_base': sum(line['withholding_base'] or 0 for line in lines),
                    'tax_rate': lines[0]['tax_rate'],
                    'withholding_amount': sum(line['withholding_amount'] or 0 for line in lines),
                    'has_sublines': False,
                }
            return {
                'tax_id': None,
                'payment_date': None,
                'withholding_base': sum(line['withholding_base'] or 0 for line in lines),
                'tax_rate': None,
                'withholding_amount': sum(line['withholding_amount'] or 0 for line in lines),
                'has_sublines': True,
            }

        expressions = next(iter(formulas_dict.values()))

        if not current_groupby:
            return {expressions: build_result_dict(query_res_lines)}

        all_res_per_grouping_key = {}
        for query_res in query_res_lines:
            grouping_key = query_res['grouping_key']
            all_res_per_grouping_key.setdefault(grouping_key, []).append(query_res)

        return {expressions: [
            (grouping_key, build_result_dict(lines))
            for grouping_key, lines in all_res_per_grouping_key.items()
        ]}

    def _headers(self):
        # Excel file headers
        return [_('No.'), _('Tax ID'), _('Title'), _('Contact Name'), _('Street'), _('Street2'), _('City'), _('State'), _('Zip'), _('Branch Number'), _('Payment Date'), _('Tax Rate'),
                _('Total Amount'), _('WHT Amount'), _('WHT Condition'), _('Tax Type')]

    def _rows(self, options, report, domain):
        query = report._get_report_query(options, 'strict_range', domain)

        dp = self.env.company.currency_id.decimal_places

        query = SQL(
            """
            SELECT
                ROW_NUMBER() OVER(ORDER BY account_move_line__move_id.date, partner.name, account_move_line__move_id.name, account_move_line.id) as rnum,
                COALESCE(partner.vat, '') as vat,
                CASE
                    WHEN partner.is_company THEN COALESCE(partner.l10n_th_company_type, '')
                    ELSE COALESCE(partner.l10n_th_title, 'khun')
                END AS title,
                COALESCE(partner.name, '') as name,
                COALESCE(partner.street, '') as street,
                COALESCE(partner.street2, '') as street2,
                COALESCE(partner.city, '') as city,
                COALESCE(state.name, '') as state_name,
                COALESCE(partner.zip, '') as zip,
                COALESCE(partner.additional_identifiers->>'TH_BRANCH_CODE', '') as branch_number,
                TO_CHAR(account_move_line__move_id.date, 'dd/mm/YYYY') as date,
                ROUND(ABS(tax.amount), %(decimal_precision)s)::text as tax_amount,
                ROUND(ABS(account_move_line.tax_base_amount), %(decimal_precision)s)::text as tax_base_amount,
                ROUND(ABS(account_move_line.balance), %(decimal_precision)s)::text as wht_amount,
                payment.l10n_th_wth_condition as wht_condition,
                CASE
                    WHEN tax.l10n_th_income_tax_type = 'others' THEN tax.l10n_th_income_tax_type_others
                    ELSE tax.l10n_th_income_tax_type
                END AS tax_type
            FROM %(table_references)s
                LEFT JOIN res_partner partner on partner.id = account_move_line__move_id.partner_id
                JOIN account_tax tax on tax.id = account_move_line.tax_line_id
                LEFT JOIN res_country_state state on partner.state_id = state.id
                LEFT JOIN account_payment payment on payment.id = account_move_line__move_id.origin_payment_id
            WHERE %(search_condition)s
         ORDER BY rnum
            """,
            decimal_precision=dp,
            table_references=query.from_clause,
            search_condition=query.where_clause,
        )

        self.env.cr.execute(query)
        res = self.env.cr.fetchall()

        return self._format_rows_for_csv(res)

    def _format_rows_for_csv(self, rows):
        """This method translates the internal values of the selection fields to the user-facing labels."""
        wht_condition_map = {
            'at_source': '1',
            'forever': '2',
            'one_time': '3',
        }
        tax_type_map = {
            'service': 'ค่าจ้างรับทำงานให้',
            'commission': 'ค่านายหน้า ส่วนแบ่งการขาย',
            'royalties': 'ค่าลิขสิทธิ์',
            'interest': 'ดอกเบี้ย',
            'dividend': 'เงินปันผล เงินส่วนแบ่งกำไร',
            'rentals': 'ค่าเช่า',
            'prof_fees': 'ค่าบริการวิชาชีพอิสระ',
            'contract': 'ค่ารับเหมา',
            'transportation': 'ค่าขนส่ง',
            'advertising': 'ค่าโฆษณา',
            'insurance': 'ค่าเบี้ยประกันภัย',
            'public_actor': 'ค่าจ้างนักแสดงสาธารณะ',
            'prize': 'เงินรางวัล',
            'hire_of_work': 'ค่าจ้างทำของ',
            'na': 'ไม่ระบุ',
        }

        def _format_row(row):
            row = list(row)
            row[0] = str(row[0])
            row[2] = TITLE_MAP_TH.get(row[2], '')
            row[14] = wht_condition_map.get(row[14], row[14])
            row[15] = tax_type_map.get(row[15], row[15])
            return tuple(row)

        return tuple(_format_row(row) for row in rows)

    def _export_to_csv(self, options, report_xml_id, wht_tag_name):
        report = self.env.ref(report_xml_id)
        domain = [('tax_tag_ids', '=', wht_tag_name)]
        data = self._rows(options, report, domain)

        output = _csv_row(*(self._headers()))
        for row in data:
            output += _csv_row(*row)

        return {
            "file_name": f"Tax Report {report.name}",
            "file_content": output.encode(),
            "file_type": "csv"
        }

    def export_pnd53_to_csv(self, options):
        return self._export_to_csv(options, 'l10n_th_reports.tax_report_pnd53', 'PND53')

    def export_pnd3_to_csv(self, options):
        return self._export_to_csv(options, 'l10n_th_reports.tax_report_pnd3', 'PND3')

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.setdefault('buttons', []).extend((
            {
                'name': self.env._('PND 3 - Export for RD Prep (CSV)'),
                'action': 'export_file',
                'action_param': 'export_pnd3_to_csv',
                'sequence': 80,
                'file_export_type': self.env._('CSV')
            },
            {
                'name': self.env._('PND 53 - Export for RD Prep (CSV)'),
                'action': 'export_file',
                'action_param': 'export_pnd53_to_csv',
                'sequence': 80,
                'file_export_type': self.env._('CSV')
            },
        ))


class L10n_ThPnd53ReportHandler(models.AbstractModel):
    _name = 'l10n_th.pnd53.report.handler'
    _inherit = ["l10n_th.pnd.report.handler"]
    _description = "Thai Tax Report (PND53) Custom Handler"

    def _report_engine_pnd53(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._report_engine_pnd(options, date_scope, formulas_dict, current_groupby, 'PND53', warnings=warnings)


class L10n_ThPnd3ReportHandler(models.AbstractModel):
    _name = 'l10n_th.pnd3.report.handler'
    _inherit = ["l10n_th.pnd.report.handler"]
    _description = "Thai Tax Report (PND3) Custom Handler"

    def _report_engine_pnd3(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return self._report_engine_pnd(options, date_scope, formulas_dict, current_groupby, 'PND3', warnings=warnings)
