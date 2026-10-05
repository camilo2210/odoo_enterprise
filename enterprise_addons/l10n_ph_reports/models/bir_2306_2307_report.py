# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io
import json
import zipfile
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.fields import Date, Domain
from odoo.models import TableSQL
from odoo.tools import html2plaintext, pdf
from odoo.tools.date_utils import get_month, get_quarter
from odoo.tools.sql import SQL


class L10n_Ph2306_2307ReportHandler(models.AbstractModel):
    _name = 'l10n_ph.2306_2307.report.handler'
    _inherit = ['l10n_ph.generic.report.handler']
    _description = 'Philippine BIR 2306 and 2307 Report Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        pdf_button_option = next(button_opt for button_opt in options['buttons'] if button_opt.get('action_param') == 'export_to_pdf')
        pdf_button_option['action'] = 'action_export_2306_2307_certificates'
        pdf_button_option['action_param'] = None
        options.update({
            'journal_type': 'purchase',
            'custom_display_config': {
                'pdf_export': {'pdf_export_main': 'l10n_ph_reports.pdf_export_main'},
            }
        })
        if certificate_move_id := (previous_options or {}).get('l10n_ph_certificate_move_id'):
            options['l10n_ph_certificate_move_id'] = certificate_move_id

    def _l10n_ph_2306_2307_add_warnings(self, query_result, warnings):
        row = query_result[0] if query_result else {}
        if partner_ids := row.get('partners_without_entity_type'):
            warnings['l10n_ph_reports.warning_partner_without_entity_type'] = {
                'alert_type': 'warning',
                'ids': partner_ids,
                'name': _('Contacts missing entity type'),
            }
        if partners_without_vat := row.get('partners_without_vat'):
            warnings['l10n_ph_reports.warning_partner_without_vat'] = {
                'partners_without_vat': partners_without_vat,
            }

    def _custom_line_postprocessor(self, report, options, lines):
        if self.env.context.get('l10n_ph_is_certificate_generation', False) and report == self.env.ref('l10n_ph_reports.2307_report'):

            # We need the ATC lines to be displayed, but not the move lines.
            # To avoid unfolding all and losing performances during exports, we will manually expand up to the ATC lines when printing the PDF.
            expanded_lines = []
            for line in lines:
                expanded_lines.append(line)
                if line.unfoldable and line.groupby == "tax_line_id,move_id" and not line.unfolded:
                    line.unfolded = True
                    expanded_lines.extend(report._expand_unfoldable_line(
                        line.expand_function, line.id, line.groupby, options,
                        line.horizontal_split_side, ignore_load_more=True,
                    ))
            lines = expanded_lines

            # Query month-wise data
            month_wise_data, month_wise_total_data = self._get_month_wise_base_amounts(options['partner_ids'] and options['partner_ids'][0] or self._get_partners(options).ids[0], options)
            atc_lines = list(filter(lambda l: l.unfoldable and l.groupby == "move_id", lines))
            total_line = next((l for l in lines if l.unfoldable and l.groupby == "tax_line_id,move_id"), None)
            if not month_wise_data:
                raise UserError(self.env._('No record found for the selected date range and partners.'))
            for line in atc_lines:
                custom = line.get_custom()
                custom.update(month_wise_data[line.name])
            total_line.get_custom().update(month_wise_total_data)

        return lines

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        return []

    def _get_custom_groupby_map(self):
        res = super()._get_custom_groupby_map()
        res['tax_line_id'] = {
            'model': None,
            'domain_builder': self._l10n_ph_tax_domain_builder,
        }
        return res

    def _l10n_ph_tax_domain_builder(self, grouping_key):
        tax_ids = self._get_l10n_ph_tax_ids(grouping_key)
        return ['|', ('tax_line_id', 'in', tax_ids), ('tax_ids', 'in', tax_ids)]

    def _custom_groupby_line_completer(self, report, options, line_data, current_groupby):
        if current_groupby == 'tax_line_id':
            line_id_parts = report._parse_line_id(line_data.id)
            grouping_key = line_id_parts[-1][2]
            tax_ids = self._get_l10n_ph_tax_ids(grouping_key)
            tax = self.env['account.tax'].browse(tax_ids[0])
            line_data.update_values(
                atc=tax.l10n_ph_atc,
                tax_description=html2plaintext(tax.description) if tax.description else ''
            )

    def _get_l10n_ph_tax_ids(self, grouping_key):
        atc = grouping_key
        desc_to_match = ""
        if ' - ' in grouping_key:
            parts = grouping_key.split(' - ', 1)
            atc = parts[0]
            desc_to_match = grouping_key.replace(atc + ' - ', '', 1)

        taxes = self.env['account.tax'].search([
            ('l10n_ph_atc', '=', atc),
            ('company_id', '=', self.env.company.id),
        ])
        return taxes.filtered(lambda t: html2plaintext(t.description or '') == desc_to_match).ids

    ####################################################
    # RETURN RESULT FUNCTION
    ####################################################

    def build_result_dict(self, query_res_lines, current_groupby):
        tax_base_amount = sum(row.get('tax_base_amount', 0) for row in query_res_lines if row.get('tax_base_amount') is not None)
        balance = sum(row.get('balance', 0) for row in query_res_lines)

        res = {
            'tax_base_amount': tax_base_amount,
            'balance': balance,
            'has_sublines': current_groupby != 'move_id',
        }

        return res

    ####################################################
    # CUSTOM ENGINES
    ####################################################

    def _report_engine_l10n_ph_2306(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return {next(iter(formulas_dict.values())): self._report_engine_l10n_ph_2306_2307(options, current_groupby, self.env['account.report'].browse(options['report_id']), ('1601/1604FA', '1601/1604FB'), warnings)}

    def _report_engine_l10n_ph_2307(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        return {next(iter(formulas_dict.values())): self._report_engine_l10n_ph_2306_2307(options, current_groupby, self.env['account.report'].browse(options['report_id']), ('1601/1604A', '1601/1604B'), warnings)}

    def _report_engine_l10n_ph_2306_2307(self, options, current_groupby, report, allowed_tags, warnings=None):
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        query = self._build_ph_query(report, options, current_groupby, allowed_tags)
        query_result = self.env.execute_query_dict(query)

        if warnings is not None and not current_groupby:
            self._l10n_ph_2306_2307_add_warnings(query_result, warnings)

        if not current_groupby:
            return self.build_result_dict(query_result, current_groupby)

        return [
            (row['grouping_key'], self.build_result_dict([row], current_groupby))
            for row in query_result
        ]

    def _get_certificate_move_domain(self, certificate_move_id):
        """Domain matching the lines of a given bill, including those on any payment reconciled
        against it: withhold-at-payment taxes book their tax line on the payment's own move,
        not on the bill's."""
        certificate_move = self.env['account.move'].browse(certificate_move_id)
        move_ids = (certificate_move | certificate_move.reconciled_payment_ids.move_id).ids
        return Domain('move_id', 'in', move_ids)

    def _build_ph_query(self, report, options, current_groupby, allowed_tags):
        """Build query based on current groupby level."""
        move_id = options.get('l10n_ph_certificate_move_id')
        bir_certificate_extra_domain = self._get_certificate_move_domain(move_id) if move_id else None

        query = self._get_report_query(report, options, extra_domain=bir_certificate_extra_domain)

        account_tax = TableSQL('account_tax', self.env['account.tax'], query)
        account_tag = TableSQL('account_tag', self.env['account.account.tag'], query)

        if current_groupby == 'partner_id':
            # Level 1: Partner grouping
            select_groupby = SQL("partner.id AS grouping_key,")

        elif current_groupby == 'tax_line_id':
            # Level 2: ATC grouping
            tax_desc_sql = SQL(
                "REGEXP_REPLACE(COALESCE(%(tax_description)s, ''), '(<([^>]+)>)', '', 'g')",
                tax_description=account_tax.description
            )
            select_groupby = SQL("""
                account_tax.l10n_ph_atc ||
                CASE WHEN %(tax_desc)s != '' THEN ' - ' || %(tax_desc)s ELSE '' END AS grouping_key,
            """, tax_desc=tax_desc_sql)

        elif current_groupby == 'move_id':
            # Level 3: Move grouping
            select_groupby = SQL("account_move_line__move_id.id AS grouping_key,")

        else:
            select_groupby = SQL("NULL AS grouping_key,") if not current_groupby else SQL("%(field)s AS grouping_key,", field=self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, query))

        warning_select = SQL("")
        if not current_groupby:
            warning_select = SQL("""
                , ARRAY_AGG(DISTINCT partner.id) FILTER (WHERE partner.l10n_ph_entity_type IS NULL)                                                         AS partners_without_entity_type
                , JSONB_AGG(DISTINCT JSONB_BUILD_OBJECT('id', partner.id, 'name', partner.name)) FILTER (WHERE partner.vat IS NULL OR partner.vat = '')     AS partners_without_vat
            """)

        query = SQL("""
            SELECT
                %(select_groupby)s
                SUM(ABS(%(base_amount)s) * SIGN(%(tax_amount)s) * -1) AS tax_base_amount,
                SUM(CASE WHEN account_move_line.tax_line_id IS NOT NULL THEN -(%(tax_amount)s) ELSE 0 END) AS balance
                %(warning_select)s
            FROM %(tables)s
            JOIN res_partner partner ON partner.id = account_move_line__move_id.commercial_partner_id
            WHERE %(where_clause)s
                AND account_tax.l10n_ph_atc IS NOT NULL
                AND %(account_tag_name)s IN %(allowed_tags)s
            GROUP BY grouping_key
            HAVING
                ROUND(SUM(
                    CASE
                        WHEN account_move_line.tax_line_id IS NOT NULL
                            THEN -(%(tax_amount)s)
                        ELSE 0
                        END
                ), %(currency_precision)s) != 0
            ORDER BY grouping_key
        """,
            select_groupby=select_groupby,
            warning_select=warning_select,
            base_amount=SQL("account_move_line.tax_base_amount * %s", query.table.consolidation_rate),
            tax_amount=query.table.consolidation_balance,
            tables=query.from_clause,
            where_clause=query.where_clause,
            account_tag_name=account_tag.name,
            allowed_tags=allowed_tags,
            currency_precision=self.env.company.currency_id.decimal_places,
        )

        return query

    ####################################################
    # HELPER FUNCTIONS
    ####################################################

    def _get_partners(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        allowed_tags_2307 = (self.env.ref('l10n_ph.l10n_ph_2550Q_2550q_1601_1604a_balance').label, self.env.ref('l10n_ph.l10n_ph_2550Q_2550q_1601_1604b_balance').label)
        allowed_tags_2306 = (self.env.ref('l10n_ph.l10n_ph_2550Q_2550q_1601_1604FA_balance').label, self.env.ref('l10n_ph.l10n_ph_2550Q_2550q_1601_1604FB_balance').label)

        allowed_tags = allowed_tags_2307 if report.name == "2307" else allowed_tags_2306

        query = self._get_report_query(report, options)

        query = SQL("""
            SELECT DISTINCT partner.id
            FROM %(tables)s
            JOIN res_partner partner ON partner.id = account_move_line__move_id.commercial_partner_id
            WHERE %(where_clause)s
                AND account_tax.l10n_ph_atc IS NOT NULL
                AND %(account_tag_name)s IN %(allowed_tags)s
        """,
            tables=query.from_clause,
            where_clause=query.where_clause,
            account_tag_name=TableSQL('account_tag', self.env['account.account.tag'], query).name,
            allowed_tags=allowed_tags,
        )

        self.env.cr.execute(query)
        partner_ids = [row['id'] for row in self.env.cr.dictfetchall()]
        return self.env['res.partner'].browse(partner_ids)

    def _get_month_wise_base_amounts(self, partner_id, options):
        """Query month-wise tax base amounts for a specific partner (used in certificates)."""

        def get_month_boundary(boundary_type, month_index):
            if quarter_months[month_index]:
                return quarter_months[month_index][boundary_type]
            return (date_to + relativedelta(days=1)) if boundary_type == 'start' else (date_from - relativedelta(days=1))

        def get_quarter_month_ranges():
            """Compute the 3-month period of a quarter with proper start and end dates."""
            q_start, _q_end = get_quarter(date_from)
            months = [{}, {}, {}]

            for i in range(3):
                m_start = q_start + relativedelta(months=i)
                m_first, m_last = get_month(m_start)
                if m_first <= date_to and m_last >= date_from:
                    months[i] = {
                        'start': max(m_first, date_from),
                        'end': min(m_last, date_to),
                    }

            return months

        report = self.env['account.report'].browse(options['report_id'])
        date_from = fields.Date.to_date(options['date']['date_from'])
        date_to = fields.Date.to_date(options['date']['date_to'])

        # Calculate month boundaries
        quarter_months = get_quarter_month_ranges()

        allowed_tags = ("1601/1604A", "1601/1604B") if report.name == "2307" else ("1601/1604FA", "1601/1604FB")

        extra_domain = Domain('move_id.commercial_partner_id.id', '=', partner_id)
        if certificate_move_id := options.get('l10n_ph_certificate_move_id'):
            extra_domain &= self._get_certificate_move_domain(certificate_move_id)

        query = self._get_report_query(report, options, extra_domain=extra_domain)
        account_tax = TableSQL('account_tax', self.env['account.tax'], query)
        account_tag = TableSQL('account_tag', self.env['account.account.tag'], query)

        tax_desc_sql = SQL(
            "REGEXP_REPLACE(COALESCE(%(tax_description)s, ''), '(<([^>]+)>)', '', 'g')",
            tax_description=account_tax.description
        )
        query = SQL(
            """
              WITH aml_filtered AS (
                  SELECT
                    %(base_select)s                                                                                              AS tax_base_amount,
                    %(tax_balance_select)s                                                                                       AS tax_balance,
                    account_move_line.date,
                    account_tax.l10n_ph_atc ||
                    CASE WHEN %(tax_desc)s != '' THEN ' - ' || %(tax_desc)s ELSE '' END                                          AS atc_grouping_key,
                    CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END                                                              AS negate_factor
                    FROM %(tables)s
                    JOIN res_partner partner ON partner.id = account_move_line__move_id.commercial_partner_id
                    WHERE %(where_clause)s
                    AND account_tax.l10n_ph_atc IS NOT NULL
                    /*
                    * Filter by the specific set of tax tags relevant to the selected report (2306 or 2307).
                    * This is crucial to separate the data sources and prevent lines from the 2306 report
                    * (tags 1601/1604FA, FB) from appearing on the 2307 report (tags 1601/1604A, B), and vice-versa.
                    */
                    AND %(account_tag_name)s IN %(allowed_tags)s
              )
              SELECT
                     atc_grouping_key,

                     -- Month 1: Tax base amount only
                     COALESCE(SUM(
                         ABS(tax_base_amount) * SIGN(tax_balance) * negate_factor
                     ) FILTER (
                         WHERE date >= %(month1_start)s AND date <= %(month1_end)s
                     ), 0)                                                                                                       AS first_month_base,

                     -- Month 2: Tax base amount only
                     COALESCE(SUM(
                         ABS(tax_base_amount) * SIGN(tax_balance) * negate_factor
                     ) FILTER (
                         WHERE date >= %(month2_start)s AND date <= %(month2_end)s
                     ), 0)                                                                                                       AS second_month_base,

                     -- Month 3: Tax base amount only
                     COALESCE(SUM(
                         ABS(tax_base_amount) * SIGN(tax_balance) * negate_factor
                     ) FILTER (
                         WHERE date >= %(month3_start)s AND date <= %(month3_end)s
                     ), 0)                                                                                                       AS third_month_base
                FROM aml_filtered
            GROUP BY atc_grouping_key
        """,
            base_select=SQL("account_move_line.tax_base_amount * %s", query.table.consolidation_rate),
            tax_balance_select=query.table.consolidation_balance,
            tax_desc=tax_desc_sql,
            balance_negate=account_tag.balance_negate,
            tables=query.from_clause,
            where_clause=query.where_clause,
            account_tag_name=account_tag.name,
            allowed_tags=allowed_tags,
            month1_start=get_month_boundary('start', 0),
            month1_end=get_month_boundary('end', 0),
            month2_start=get_month_boundary('start', 1),
            month2_end=get_month_boundary('end', 1),
            month3_start=get_month_boundary('start', 2),
            month3_end=get_month_boundary('end', 2),
        )

        self.env.cr.execute(query)

        tax_lines_data = {}
        total_line_data = {'first_month_base_total': 0, 'second_month_base_total': 0, 'third_month_base_total': 0}
        for row in self.env.cr.dictfetchall():
            tax_lines_data[row['atc_grouping_key']] = {
                'first_month_base': row['first_month_base'],
                'second_month_base': row['second_month_base'],
                'third_month_base': row['third_month_base'],
            }
            total_line_data['first_month_base_total'] += row['first_month_base']
            total_line_data['second_month_base_total'] += row['second_month_base']
            total_line_data['third_month_base_total'] += row['third_month_base']
        return tax_lines_data, total_line_data

    ####################################################
    # EXPORT AND PRINTING HELPERS
    ####################################################

    def _l10n_ph_certificate_filename(self, partner_name, form_names, options):
        """Certificate PDF filename.

        - From the bill action (options has l10n_ph_certificate_move_id): BillRef_PartnerName_Form_2306_2307.pdf
        - From the report view (no specific move): DDMMYY_PartnerName_Form_2306.pdf
        """
        def slug(value):
            return ''.join(char if char.isalnum() else '_' for char in (value or '')).strip('_')

        if move_id := options.get('l10n_ph_certificate_move_id'):
            move = self.env['account.move'].browse(move_id)
            prefix = slug(move.name)
        else:
            prefix = Date.to_date(options['date']['date_to']).strftime('%d%m%y')

        return f"{prefix}_{slug(partner_name)}_Form_{'_'.join(form_names)}.pdf"

    def action_export_2306_2307_certificates(self, options):
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'options': json.dumps(options),
                'file_generator': 'export_2306_2307_certificates',
                'next_action': None,
            }
        }

    def _action_export_bir_certificates(self, options):
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'options': json.dumps(options),
                'file_generator': 'export_bir_certificates',
                'next_action': None,
            }
        }

    def export_bir_certificates(self, options):
        """Generate one BIR certificate PDF per selected vendor bill (both forms of a bill are merged
        into a single PDF). A single bill downloads as one PDF; several bills are bundled in one zip."""
        if not options.get('l10n_ph_certificate_move_ids'):
            raise UserError(self.env._('There is no withheld amount to certify for the selected bills.'))
        moves = self.env['account.move'].browse(options['l10n_ph_certificate_move_ids'])

        attachments = []
        for move in moves:
            attachment = self._l10n_ph_generate_bill_certificate(move, options)
            if attachment:
                attachments.append(attachment)

        if not attachments:
            raise UserError(self.env._('There is no withheld amount to certify for the selected bills.'))

        if len(attachments) == 1:
            return {'file_name': attachments[0][0], 'file_content': attachments[0][1], 'file_type': 'pdf'}

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
            for filename, content in attachments:
                zipfile_obj.writestr(filename, content)
        return {'file_name': 'BIR_2306_2307_Certificates.zip', 'file_content': buffer.getvalue(), 'file_type': 'zip'}

    def _l10n_ph_generate_bill_certificate(self, move, base_options):
        """Build the certificate PDF for a single vendor bill, merging the 2306 and 2307 pages when
        both apply. Returns ``(file_name, pdf_bytes)`` or ``None`` when the bill has nothing to certify."""
        q_start, q_end = get_quarter(move.invoice_date or move.date)
        per_move_options = {
            **base_options,
            'date': {
                'mode': 'range',
                'filter': 'custom',
                'date_from': fields.Date.to_string(q_start),
                'date_to': fields.Date.to_string(q_end),
            },
            'partner_ids': [move.commercial_partner_id.id],
            'l10n_ph_certificate_move_id': move.id,
            'unfold_all': True,
        }

        form_pdfs = []
        generated_forms = []
        for form_name in sorted(move._l10n_ph_certificate_forms()):
            section = self.env.ref('l10n_ph_reports.2307_report' if form_name == '2307' else 'l10n_ph_reports.2306_report')
            section_options = {**per_move_options, 'report_id': section.id, 'selected_section_id': section.id}
            form_pdfs.append(self.export_2306_2307_certificates(section_options)['file_content'])
            generated_forms.append(form_name)

        if not form_pdfs:
            return None

        content = form_pdfs[0] if len(form_pdfs) == 1 else pdf.merge_pdf(form_pdfs)
        file_name = self._l10n_ph_certificate_filename(move.commercial_partner_id.name, generated_forms, per_move_options)
        return file_name, content

    def export_2306_2307_certificates(self, options):
        report = self.env['account.report'].browse(options['selected_section_id'])
        is_2307_section = report == self.env.ref('l10n_ph_reports.2307_report')
        same_quarter = get_quarter(Date.to_date(options['date']['date_from'])) == get_quarter(Date.to_date(options['date']['date_to']))
        if is_2307_section and not same_quarter:
            raise ValidationError(self.env._('The date range must fall within the same quarter.'))

        report_options = report.get_options(previous_options={**options, 'export_mode': 'print'})
        partner_ids = self.env['res.partner'].browse(options['partner_ids']) or self._get_partners(report_options)

        file_type, file_name, file_content = self._generate_ph_certificate_content(report_options, partner_ids, report)
        return {
            'file_name': file_name,
            'file_content': file_content,
            'file_type': file_type
        }

    def _generate_ph_certificate_content(self, options, partner_ids, report):
        attachments = []
        for partner in partner_ids:
            # Create partner-specific options
            partner_options = report.get_options(previous_options={**options, 'partner_ids': [partner.id]})
            if not report._get_lines(partner_options):
                continue

            file = report.with_context(exclude_page_footer=True, l10n_ph_is_certificate_generation=True).export_to_pdf(partner_options)
            attachments.append((self._l10n_ph_certificate_filename(partner.name, [report.name], partner_options), file['file_content']))
        if not attachments:
            raise ValidationError(self.env._('No record found for the selected date range and partners.'))

        if len(attachments) > 1:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
                for filename, content in attachments:
                    zipfile_obj.writestr(filename, content)
            return 'zip', report.name + '.zip', buffer.getvalue()

        return 'pdf', attachments[0][0], attachments[0][1]

    def _get_pdf_export_html(self, options, lines, additional_context=None, template=None):
        def _build_payee_payor_name(partner):
            if partner.commercial_partner_id.l10n_ph_last_name:  # individual
                name = partner.commercial_partner_id.l10n_ph_last_name
                if partner.commercial_partner_id.l10n_ph_first_name:
                    name += f", {partner.commercial_partner_id.l10n_ph_first_name}"
                if partner.commercial_partner_id.l10n_ph_middle_name:
                    name += f" {partner.commercial_partner_id.l10n_ph_middle_name}"
                return name

            return partner.complete_name

        payee = self.env['res.partner'].browse(options['partner_ids'])
        payee_address = payee.address_inline if not payee.zip else payee.address_inline.replace('  ' + payee.zip, '')
        payee_name = _build_payee_payor_name(payee)
        payor = self.env.company.partner_id
        payor_address = payor.address_inline if not payor.zip else payor.address_inline.replace('  ' + payor.zip, '')
        payor_name = _build_payee_payor_name(payor)

        payee_payor_info = {
            'payee_info': {
                'name': payee_name,
                'tin': payee.vat.replace('-', '') if payee.vat else '',
                'registered_address': payee_address if self.env.ref('base.ph') == payee.country_id else '',
                'foreign_address': payee_address if self.env.ref('base.ph') != payee.country_id else '',
                'zip': payee.zip if self.env.ref('base.ph') == payee.country_id and payee.zip else '',
            },
            'payor_info': {
                'name': payor_name,
                'tin': payor.vat.replace('-', '') if payor.vat else '',
                'registered_address': payor_address,
                'zip': payor.zip or '',
            },
            'date_from': datetime.strptime(options['date']['date_from'], '%Y-%m-%d').strftime('%m%d%Y'),
            'date_to': datetime.strptime(options['date']['date_to'], '%Y-%m-%d').strftime('%m%d%Y'),
        }

        additional_context.update(payee_payor_info)

        return self.env['account.report'].browse(options['report_id'])._get_pdf_export_html(options, lines, additional_context, template)
