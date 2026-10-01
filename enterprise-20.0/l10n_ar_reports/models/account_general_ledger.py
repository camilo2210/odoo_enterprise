# Part of Odoo. See LICENSE file for full copyright and licensing details.
import calendar
import io
from collections import defaultdict
from datetime import date

from odoo import api, models
from odoo.exceptions import UserError


class AccountGeneralLedgerReportHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)

        if self.env.company.account_fiscal_country_id.code != 'AR':
            return

        if previous_options.get('is_opening_report') and not previous_options.get('not_reset_journals_filter'):
            if previous_options.get('journals'):
                restore_options = {**previous_options, 'is_opening_report': False}
                report._init_options_journals(options, restore_options)
                select_all = not any(journal['selected'] for journal in options.get('journals', []))
            else:
                select_all = True
            # Select every ledger by default
            if select_all:
                for journal in options.get('journals', []):
                    journal['selected'] = True
                for group in options.get('journal_groups', []):
                    group['selected'] = True
            report._init_options_journals_names(options, previous_options)

        options['buttons'].append({
            'name': self.env._("Daily Book XLSX (AR)"),
            'sequence': 60,
            'action': 'export_file',
            'action_param': 'l10n_ar_reports_export_daily_book',
            'file_export_type': 'XLSX',
            'branch_allowed': True,
        })

    @api.model
    def _l10n_ar_reports_check_daily_book_export(self, options):
        """ Check if it's valid to export daily book; otherwise, raise."""
        company_ids = [company['id'] for company in options['companies']]
        companies = self.env['res.company'].browse(company_ids)
        if any(company.account_fiscal_country_id.code != 'AR' for company in companies):
            raise UserError(self.env._(
                "The Daily Book export is only available for Argentina. "
                "Please unselect the companies from a different country."
            ))

        distinct_cuits = {cuit for cuit in companies.mapped('partner_id.l10n_ar_formatted_vat') if cuit}
        if not distinct_cuits:
            raise UserError(self.env._(
                "The selected branch has no CUIT. "
                "Please select its parent company, or set a CUIT on the branch."
            ))
        if len(distinct_cuits) > 1:
            raise UserError(self.env._(
                "Companies with different CUIT cannot be exported together. "
                "Please unselect the companies with a different CUIT."
            ))

    @api.model
    def _l10n_ar_reports_categorize_daily_book_data(self, move_lines):
        """ Return the entry types dict data to be sorted.
        Entry Types:
        - Summary Entries: Journals that belong to a ledger group are aggregated,
        per group and per month
        - Detailed Entries: Journals without a group are exported as
        one entry per account move keeping its own lines
        """
        summary_entries = {}  # {'group', 'date', 'accounts': {account: [debit, credit]}}
        detail_entries = {}   # {'date', 'description', 'lines': [(account, debit, credit)]}
        for line in move_lines:
            group = line.journal_id.journal_group_id
            if group:
                key = (group.id, line.date.year, line.date.month)
                entry = summary_entries.get(key)
                if not entry:
                    last_day = calendar.monthrange(line.date.year, line.date.month)[1]
                    entry = summary_entries[key] = {
                        'group': group,
                        'date': date(line.date.year, line.date.month, last_day),
                        'accounts': defaultdict(lambda: [0.0, 0.0]),
                    }
                balance = entry['accounts'][line.account_id]
                balance[0] += line.debit
                balance[1] += line.credit
            else:
                move = line.move_id
                entry = detail_entries.get(move.id)
                if not entry:
                    entry = detail_entries[move.id] = {'date': move.date, 'move': move, 'lines': []}
                entry['lines'].append((line.account_id, line.debit, line.credit))
        return summary_entries, detail_entries

    @api.model
    def _l10n_ar_reports_process_daily_book_data(self, company, summary_entries, detail_entries):
        """ Return the sorted list of entries ordered by date and alphabetically."""
        entries = []
        for entry in summary_entries.values():
            group = entry['group']
            description = group.name
            lines = [
                {
                    'account_code': account.with_company(company).code,
                    'account_name': account.name,
                    'debit': debit,
                    'credit': credit,
                }
                for account, (debit, credit) in sorted(entry['accounts'].items(), key=lambda item: item[0].with_company(company).code or '')
            ]
            entries.append({'date': entry['date'], 'sort_key': group.name or '', 'description': description, 'lines': lines})

        for entry in detail_entries.values():
            move = entry['move']
            description = f"{move.name} - {move.partner_id.name}" if move.partner_id else move.name
            lines = [
                {
                    'account_code': account.with_company(company).code,
                    'account_name': account.name,
                    'debit': debit,
                    'credit': credit,
                }
                for account, debit, credit in entry['lines']
            ]
            entries.append({'date': entry['date'], 'sort_key': description or '', 'description': description, 'lines': lines})

        entries.sort(key=lambda entry: (entry['date'], entry['sort_key']))
        return entries

    @api.model
    def _l10n_ar_reports_get_daily_book_entries(self, company, domain, start_entry_number):
        """ Return the daily book entries to be exported.

        All entries are sorted by date and numbered with an unbroken sequence starting from the
        entry number set on the company.
        """
        move_lines = self.env['account.move.line'].search(domain)
        summary_entries, detail_entries = self._l10n_ar_reports_categorize_daily_book_data(move_lines)
        entries = self._l10n_ar_reports_process_daily_book_data(company, summary_entries, detail_entries)
        for sequence, entry in enumerate(entries, start=start_entry_number):
            entry['sequence'] = sequence
        return entries

    @api.model
    def _l10n_ar_reports_write_daily_book_entries(self, workbook, sheet, company, entries, period):
        """ Write the daily book data into the XLSX file with
        each entry having bold header row (number, date and description spanning the
        "Account Code / Name" columns followed by its account detail rows (code, name, amounts).
        """
        # Common style attributes
        font_name = 'Arial'
        title_font_size = 14
        line_font_size = 10
        border_thickness = 7

        # Report header block
        title_style = workbook.add_format({'font_name': font_name, 'font_size': title_font_size, 'align': 'center'})
        company_style = workbook.add_format({'font_name': font_name, 'bold': True, 'align': 'center'})
        period_style = workbook.add_format({'font_name': font_name, 'align': 'center'})

        sheet.merge_range(0, 0, 0, 5, self.env._("Daily Book"), title_style)
        sheet.merge_range(1, 0, 1, 5, self.env._(
            "%(company)s - CUIT: %(cuit)s",
            company=company.name,
            cuit=company.partner_id.vat,
        ), company_style)
        sheet.merge_range(2, 0, 2, 5, self.env._(
            "Period: %(date_from)s - %(date_to)s",
            date_from=period[0],
            date_to=period[1],
        ), period_style)

        # Column headers
        header_row = 4
        header_left_style = workbook.add_format({'font_name': font_name, 'bold': True, 'font_size': line_font_size, 'align': 'left'})
        header_center_style = workbook.add_format({'font_name': font_name, 'bold': True, 'font_size': line_font_size, 'align': 'center'})

        sheet.set_column(0, 0, 12)    # Entry Number
        sheet.set_column(1, 1, 11.5)  # Date
        sheet.set_column(2, 2, 13.5)  # Account code
        sheet.set_column(3, 3, 37)    # Account name
        sheet.set_column(4, 5, 12)    # Debit / Credit
        sheet.write(header_row, 0, self.env._("Entry Number"), header_center_style)
        sheet.write(header_row, 1, self.env._("Date"), header_center_style)
        sheet.merge_range(header_row, 2, header_row, 3, self.env._("Account Code / Name"), header_left_style)
        sheet.write(header_row, 4, self.env._("Debit"), header_center_style)
        sheet.write(header_row, 5, self.env._("Credit"), header_center_style)

        # Entries: a bold header row followed by its account detail rows.
        entry_number_style = workbook.add_format({'font_name': font_name, 'bold': True, 'font_size': line_font_size, 'align': 'left', 'bottom': border_thickness})
        entry_date_style = workbook.add_format({'font_name': font_name, 'bold': True, 'font_size': line_font_size, 'align': 'center', 'bottom': border_thickness})
        entry_description_style = workbook.add_format({'font_name': font_name, 'bold': True, 'font_size': line_font_size, 'align': 'left', 'bottom': border_thickness})
        entry_blank_style = workbook.add_format({'bottom': border_thickness})
        account_code_style = workbook.add_format({'font_name': font_name, 'font_size': line_font_size})
        account_name_style = workbook.add_format({'font_name': font_name, 'font_size': line_font_size})
        amount_style = workbook.add_format({'font_name': font_name, 'font_size': line_font_size, 'num_format': '#,##0.00', 'align': 'center'})

        row = header_row + 1
        for entry in entries:
            sheet.write_number(row, 0, entry['sequence'], entry_number_style)
            sheet.write(row, 1, entry['date'].strftime("%d/%m/%Y"), entry_date_style)
            sheet.merge_range(row, 2, row, 3, entry['description'] or "", entry_description_style)
            sheet.write_blank(row, 4, None, entry_blank_style)
            sheet.write_blank(row, 5, None, entry_blank_style)
            row += 1
            for line in entry['lines']:
                sheet.write(row, 2, line['account_code'] or "", account_code_style)
                sheet.write(row, 3, line['account_name'] or "", account_name_style)
                sheet.write_number(row, 4, line['debit'], amount_style)
                sheet.write_number(row, 5, line['credit'], amount_style)
                row += 1

    @api.model
    def l10n_ar_reports_export_daily_book(self, options):
        """ Export a XLSX file containing the Daily Book (Libro Diario) data. """
        # Check if valid to export
        self._l10n_ar_reports_check_daily_book_export(options)

        report = self.env['account.report'].browse(options['report_id'])
        company = report._get_sender_company_for_export(options)._l10n_ar_reports_get_daily_book_company()
        period = (options['date']['date_from'], options['date']['date_to'])
        domain = report._get_options_domain(options, 'strict_range')
        entries = self._l10n_ar_reports_get_daily_book_entries(company, domain, company.l10n_ar_daily_book_start_entry_number)
        if entries:
            company.sudo().l10n_ar_daily_book_start_entry_number = entries[-1]['sequence'] + 1

        import xlsxwriter  # noqa: PLC0415
        with io.BytesIO() as output:
            with xlsxwriter.Workbook(output, {
                'in_memory': True,
                'strings_to_formulas': False,
            }) as workbook:
                self._l10n_ar_reports_write_daily_book_entries(workbook, workbook.add_worksheet(), company, entries, period)
            return {
                'file_name': f"{company.name} {period[0]} - {period[1]} {self.env._('Daily Book')}.xlsx",
                'file_content': output.getvalue(),
                'file_type': 'xlsx',
            }
