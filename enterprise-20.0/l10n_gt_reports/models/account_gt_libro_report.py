# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io

from odoo import models
from odoo.tools import SQL, format_date, formatLang

from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData

DOC_TYPE_DISPLAY = {
    'FESP': 'FE',
    'NABN': 'NA',
    'NCRE': 'NC',
    'NDEB': 'ND',
}

# The SAT sigla of every specific (non-IVA) tax, i.e. l10n_gt_edi's NOMBRE_CORTO_KEYS minus IVA.
# Also the definition of "specific tax" for the book queries.
SPECIFIC_TAX_SIGLA = {
    'PETROLEO': 'IDP',
    'TURISMO HOSPEDAJE': 'ITH',
    'TURISMO PASAJES': 'ITP',
    'TIMBRE DE PRENSA': 'TDP',
    'BOMBEROS': 'IFB',
    'TASA MUNICIPAL': 'MUN',
    'BEBIDAS ALCOHOLICAS': 'IDB',
    'TABACO': 'TAB',
    'CEMENTO': 'CEM',
    'BEBIDAS NO ALCOHOLICAS': 'IBN',
    'TARIFA PORTUARIA': 'TAP',
}

NUMBER_LABELS = (
    'taxed_goods', 'taxed_services', 'exempt_goods', 'exempt_services',
    'specific_tax_subtotal', 'specific_tax_amount', 'vat_amount', 'amount_total',
)

BOOK_MOVE_TYPES = {
    'sale': ('out_invoice', 'out_refund', 'out_receipt'),
    'purchase': ('in_invoice', 'in_refund', 'in_receipt'),
}

SMALL_TAXPAYER_DOC_TYPES = ('FPEQ', 'FCAP')

SUMMARY_AMOUNT_KEYS = ('exempt', 'taxable', 'specific', 'vat', 'total')


class L10n_GtLibroReportHandler(models.AbstractModel):
    """ Handler for the Guatemala VAT book (an ``account.generic_tax_report`` variant).

    One report serves both legal books (Sales / Purchases); the ``l10n_gt_libro_book`` option
    selects which, and the move types, amount sign, foreign transaction code and FEL number all
    follow from it. The detail amounts are aggregated from ``account_move_line`` with TableSQL in
    separate queries (base buckets, tax amounts, move fields, FEL number) merged per move; joining
    them in one query would multiply each other's rows.
    """
    _name = 'l10n_gt.libro.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = "Guatemala VAT Book Report Handler"

    # -- Options / Book filter --------------------------------------------------------------

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['l10n_gt_libro_book'] = previous_options.get('l10n_gt_libro_book') or 'sale'
        # Legal book title shown in the framework report header (and the PDF file name).
        options['report_title'] = (
            self.env._("Sales Book") if options['l10n_gt_libro_book'] == 'sale'
            else self.env._("Purchases and Received Services Book")
        )
        options['l10n_gt_libro_period'] = self.env._(
            "%(date_from)s to %(date_to)s",
            date_from=format_date(self.env, options['date'].get('date_from')),
            date_to=format_date(self.env, options['date'].get('date_to')),
        )
        options['custom_display_config'] = {
            'templates': {
                'AccountReportFilters': 'l10n_gt_reports.L10nGtLibroReportFiltersCustomizable',
            },
            'components': {
                'AccountReportFilters': 'L10nGtLibroReportFilters',
            },
            'pdf_export': {
                'pdf_export_main': 'l10n_gt_reports.l10n_gt_libro_pdf_export_main',
            },
        }
        if options.get('export_mode') == 'print':
            options['custom_display_config']['css_custom_class'] = 'o_l10n_gt_libro_pdf'
        # Drop the generic XLSX export; the CSV covers data exports.
        options['buttons'] = [
            button for button in options.get('buttons', [])
            if button.get('action_param') != 'export_to_xlsx'
        ]
        options['buttons'].append({
            'name': self.env._("CSV"),
            'sequence': 50,
            'action': 'export_file',
            'action_param': 'l10n_gt_libro_export_to_csv',
            'file_export_type': self.env._("CSV"),
        })

    def _l10n_gt_is_sales(self, options):
        return options.get('l10n_gt_libro_book', 'sale') == 'sale'

    # -- Report lines -----------------------------------------------------------------------

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        move_info = {}          # move_id -> {column_group_index: {label: value}}
        line_names = {}         # move_id -> displayed line label
        sort_keys = {}          # move_id -> (date, name) used to order the rows
        totals = {}             # column_group_index -> {label: running total}

        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            totals.setdefault(column_group_index, dict.fromkeys(NUMBER_LABELS, 0.0))
            for move_id, vals in self._l10n_gt_get_book_lines(report, column_group_options).items():
                line_names[move_id] = vals['move_name']
                sort_keys.setdefault(move_id, (str(vals.get('invoice_date') or ''), vals.get('move_name') or ''))
                move_info.setdefault(move_id, {})[column_group_index] = vals
                for label in NUMBER_LABELS:
                    totals[column_group_index][label] += vals.get(label) or 0.0

        lines = [
            (0, self._l10n_gt_create_line(report, options, move_info[move_id], move_id, line_names[move_id]))
            for move_id in sorted(move_info, key=lambda move_id: sort_keys[move_id])
        ]
        if move_info:
            lines.append((0, self._l10n_gt_create_total_line(report, options, totals)))
        return lines

    def _l10n_gt_label_transaction_type(self, options, columns):
        """ E/L/I are opaque on screen and in the PDF: show the full word there (which reads .name)
        while the CSV export and the raw book keep the single-letter code (it reads .no_format). """
        labels = {'E': self.env._("Export"), 'L': self.env._("Local"), 'I': self.env._("Import")}
        for column_data, column in zip(columns, options['columns']):
            if column['expression_label'] == 'transaction_type' and column_data.no_format:
                column_data.name = labels.get(column_data.no_format, column_data.no_format)
        return columns

    def format_column_values_from_client(self, options, client_lines):
        """ The rounding-unit filter rebuilds every cell name from no_format without re-running the
        lines generator, which would revert the transaction type to its single-letter code. """
        report = self.env['account.report'].browse(options['report_id'])
        lines = report.format_column_values_from_client(options, client_lines)
        for line in lines:
            self._l10n_gt_label_transaction_type(options, line.columns)
        return lines

    def _l10n_gt_columns(self, report, options, values_by_group):
        """ Build the column cells of one report line from a {column_group_index: {label: value}}
        map; a group the document has no figures for yields blank cells. """
        return self._l10n_gt_label_transaction_type(options, [
            report._build_column_data(
                values_by_group.get(column['column_group_index'], {}).get(column['expression_label']),
                column,
                options=options,
            )
            for column in options['columns']
        ])

    def _l10n_gt_create_line(self, report, options, move_vals, move_id, line_name):
        return AccountReportLineData(
            id=report._get_generic_line_id('account.move', move_id),
            caret_options='account.move',
            name=line_name,
            columns=self._l10n_gt_columns(report, options, move_vals),
            level=2,
        )

    def _l10n_gt_create_total_line(self, report, options, totals):
        return AccountReportLineData(
            id=report._get_generic_line_id(None, None, markup='total'),
            name=self.env._("Total"),
            css_class='total',
            level=1,
            columns=self._l10n_gt_columns(report, options, totals),
        )

    # -- Data (TableSQL) --------------------------------------------------------------------

    def _l10n_gt_base_domain(self, options):
        book = options.get('l10n_gt_libro_book', 'sale')
        # Every sale/purchase document (the framework already restricts to posted moves). Don't
        # filter on l10n_gt_edi_doc_type: it can be empty, which would silently drop documents.
        return [('move_id.move_type', 'in', BOOK_MOVE_TYPES[book])]

    def _l10n_gt_get_book_lines(self, report, options):
        base = self._l10n_gt_base_buckets(report, options)
        tax = self._l10n_gt_tax_amounts(report, options)
        move_ids = list(set(base) | set(tax))
        if not move_ids:
            return {}
        fields_by_move = self._l10n_gt_move_fields(move_ids)
        fel_by_move = self._l10n_gt_fel_numbers(options, fields_by_move)
        specific_base = self._l10n_gt_specific_tax_base(report, options)

        sales = self._l10n_gt_is_sales(options)
        sign = -1.0 if sales else 1.0
        foreign_code = 'E' if sales else 'I'
        currency = self.env.company.currency_id

        def amount(source, key):
            return currency.round(sign * (source.get(key) or 0.0))

        result = {}
        for move_id in move_ids:
            buckets, taxes = base.get(move_id, {}), tax.get(move_id, {})
            move, fel = fields_by_move.get(move_id, {}), fel_by_move.get(move_id, {})

            taxed_goods = amount(buckets, 'taxed_goods')
            taxed_services = amount(buckets, 'taxed_services')
            exempt_goods = amount(buckets, 'exempt_goods')
            exempt_services = amount(buckets, 'exempt_services')
            specific_tax_subtotal = amount(specific_base, move_id)
            vat_amount = amount(taxes, 'vat_amount')
            specific_tax_amount = amount(taxes, 'specific_tax_amount')

            fel_series, fel_number = fel.get('fel_series') or '', fel.get('fel_number') or ''
            country_code = move.get('country_code')
            doc_type = move.get('doc_type')

            result[move_id] = {
                'invoice_date': move.get('invoice_date'),
                'move_name': move.get('move_name') or '',
                'fel_series': fel_series,
                'fel_number': fel_number,
                'doc_type': DOC_TYPE_DISPLAY.get(doc_type, doc_type or ''),
                'transaction_type': foreign_code if country_code and country_code != 'GT' else 'L',
                'id_type': self._l10n_gt_id_type(move),
                'partner_vat': move.get('partner_vat') or '',
                'partner_name': move.get('partner_name') or '',
                'taxed_goods': taxed_goods,
                'taxed_services': taxed_services,
                'exempt_goods': exempt_goods,
                'exempt_services': exempt_services,
                'specific_tax_type': ', '.join(SPECIFIC_TAX_SIGLA.get(short, short) for short in (taxes.get('specific_types') or [])),
                'specific_tax_subtotal': specific_tax_subtotal,
                'specific_tax_amount': specific_tax_amount,
                'vat_amount': vat_amount,
                # Use the move's own total rather than re-summing buckets (which would miss any base
                # without an IVA tax); -sign normalises amount_total_signed to the book's convention.
                'amount_total': currency.round(-sign * (move.get('amount_total_signed') or 0.0)),
            }
        return result

    def _l10n_gt_base_buckets(self, report, options):
        """ Per move, split the product-line base into goods/services x taxable/exempt by the IVA
        tax rate. Filtering the ``tax_ids`` join to IVA keeps each line counted once when a
        specific tax also applies. """
        query = report._get_report_query(options, 'strict_range', domain=[*self._l10n_gt_base_domain(options), ('display_type', '=', 'product')])
        aml = query.table
        move_id = aml.move_id
        short = aml._join('tax_ids').l10n_gt_edi_short_name
        rate = aml._join('tax_ids').amount
        product_type = aml.product_id.product_tmpl_id.type
        balance = aml.balance
        query.groupby = move_id
        rows = self.env.execute_query_dict(query.select(
            SQL('%s AS move_id', move_id),
            SQL("SUM(%s) FILTER (WHERE %s = 'IVA' AND %s > 0 AND %s = 'consu') AS taxed_goods", balance, short, rate, product_type),
            SQL("SUM(%s) FILTER (WHERE %s = 'IVA' AND %s > 0 AND %s IS DISTINCT FROM 'consu') AS taxed_services", balance, short, rate, product_type),
            SQL("SUM(%s) FILTER (WHERE %s = 'IVA' AND %s = 0 AND %s = 'consu') AS exempt_goods", balance, short, rate, product_type),
            SQL("SUM(%s) FILTER (WHERE %s = 'IVA' AND %s = 0 AND %s IS DISTINCT FROM 'consu') AS exempt_services", balance, short, rate, product_type),
        ))
        return {row.pop('move_id'): row for row in rows}

    def _l10n_gt_specific_tax_base(self, report, options):
        """ Per move, the base of product lines carrying a specific (non-IVA) tax. ``tax_ids`` is a
        Many2many, so aggregating over a tax join would multiply a line's base by its number of
        specific taxes; keeping the tax condition in the domain makes the ORM express it as a
        subquery instead, so each base line is counted once. """
        query = report._get_report_query(options, 'strict_range', domain=[
            *self._l10n_gt_base_domain(options),
            ('display_type', '=', 'product'),
            ('tax_ids.l10n_gt_edi_short_name', 'in', list(SPECIFIC_TAX_SIGLA)),
        ])
        aml = query.table
        move_id = aml.move_id
        query.groupby = move_id
        rows = self.env.execute_query_dict(query.select(
            SQL('%s AS move_id', move_id),
            SQL("SUM(%s) AS specific_tax_base", aml.balance),
        ))
        return {row['move_id']: row['specific_tax_base'] for row in rows}

    def _l10n_gt_tax_amounts(self, report, options):
        """ Per move, sum the IVA tax and (combined) specific taxes off the tax lines, and
        collect the distinct specific-tax codes. Taxes without a short name (e.g. withholding)
        are ignored. """
        query = report._get_report_query(options, 'strict_range', domain=[*self._l10n_gt_base_domain(options), ('tax_line_id', '!=', False)])
        aml = query.table
        move_id = aml.move_id
        short = aml.tax_line_id.l10n_gt_edi_short_name
        balance = aml.balance
        query.groupby = move_id
        rows = self.env.execute_query_dict(query.select(
            SQL('%s AS move_id', move_id),
            SQL("SUM(%s) FILTER (WHERE %s = 'IVA') AS vat_amount", balance, short),
            SQL("SUM(%s) FILTER (WHERE %s IS NOT NULL AND %s <> 'IVA') AS specific_tax_amount", balance, short, short),
            SQL("ARRAY_AGG(DISTINCT %s) FILTER (WHERE %s IS NOT NULL AND %s <> 'IVA') AS specific_types", short, short, short),
        ))
        return {row.pop('move_id'): row for row in rows}

    def _l10n_gt_id_type(self, move):
        """ The NIT is held in the partner's VAT; a customer identified by their CUI carries it
        among the additional identifiers instead. Foreign customers have neither. """
        if move.get('country_code') != 'GT':
            return ''
        if move.get('partner_vat'):
            return 'NIT'
        return 'CUI' if (move.get('partner_identifiers') or {}).get('GT_CUI') else ''

    def _l10n_gt_move_fields(self, move_ids):
        query = self.env['account.move']._search([('id', 'in', move_ids)])
        move = query.table
        partner = move.commercial_partner_id
        rows = self.env.execute_query_dict(query.select(
            SQL('%s AS move_id', move.id),
            SQL('%s AS invoice_date', move.invoice_date),
            SQL('%s AS move_name', move.name),
            SQL('%s AS ref', move.ref),
            SQL('%s AS doc_type', move.l10n_gt_edi_doc_type),
            SQL('%s AS partner_name', partner.name),
            SQL('%s AS partner_vat', partner.vat),
            SQL('%s AS country_code', partner.country_id.code),
            SQL('%s AS partner_identifiers', partner.additional_identifiers),
            SQL('%s AS amount_total_signed', move.amount_total_signed),
        ))
        return {row.pop('move_id'): row for row in rows}

    def _l10n_gt_fel_numbers(self, options, fields_by_move):
        if self._l10n_gt_is_sales(options):
            return self._l10n_gt_sales_fel_numbers(list(fields_by_move))
        return self._l10n_gt_purchase_fel_numbers(fields_by_move)

    def _l10n_gt_sales_fel_numbers(self, move_ids):
        """ Sales: the FEL series/serial of the document we issued. Pin to ``invoice_sent`` (a
        blank sending_failed/cancel_failed sibling would otherwise win) and order by id so the
        per-move collapse below is deterministic. """
        query = self.env['l10n_gt_edi.document']._search(
            [('invoice_id', 'in', move_ids), ('state', '=', 'invoice_sent')],
            order='id',
        )
        doc = query.table
        rows = self.env.execute_query_dict(query.select(
            SQL('%s AS move_id', doc.invoice_id),
            SQL('%s AS fel_series', doc.series),
            SQL('%s AS fel_number', doc.serial_number),
        ))
        return {row['move_id']: row for row in rows}

    def _l10n_gt_purchase_fel_numbers(self, fields_by_move):
        """ Purchases: the vendor's FEL number lives in the bill ``ref`` (series before the first
        '-', number after), except special invoices (FE) and abono notes (NA) we issue, which keep
        the issued FEL document. A bill with no ``ref`` is left blank. """
        issued = self._l10n_gt_sales_fel_numbers(list(fields_by_move))
        result = {}
        for move_id, move in fields_by_move.items():
            if move['doc_type'] in ('FESP', 'NABN') and move_id in issued:
                result[move_id] = issued[move_id]
                continue
            series, separator, number = (move['ref'] or '').partition('-')
            result[move_id] = {
                'fel_series': series if separator else '',
                'fel_number': number if separator else (move['ref'] or ''),
            }
        return result

    # -- Book documents / summary -----------------------------------------------------------

    def _l10n_gt_book_documents(self, options, lines):
        """ The detail rows of the book as {expression_label: value} dicts, read back off the
        rendered lines. The exports (PDF, CSV) already hold every document, so the closing figures
        and the summary are built from them rather than by running the whole book query twice. """
        report = self.env['account.report'].browse(options['report_id'])
        labels = [column['expression_label'] for column in options['columns']]
        return [
            dict(zip(labels, (column.no_format for column in line.columns)))
            for line in lines
            if not report._get_markup(line.id)  # skip the Total (and placeholder) rows
        ]

    def _l10n_gt_total_vat(self, book):
        return self.env.company.currency_id.round(sum(vals['vat_amount'] for vals in book))

    def _l10n_gt_format_amount(self, amount):
        return formatLang(self.env, amount, digits=2)

    # -- PDF (legal SAT layout) -------------------------------------------------------------

    def _get_pdf_export_html(self, options, lines, additional_context=None, template=None):
        """ Add the legal extras the framework body layout doesn't carry: document count, total
        VAT (débito on sales / crédito on purchases) and the summary table. """
        report = self.env['account.report'].browse(options['report_id'])

        book = self._l10n_gt_book_documents(options, lines)
        summary_rows, summary_total = self._l10n_gt_summary_rows(options, lines)
        has_specific_tax = any(
            vals['specific_tax_type'] or vals['specific_tax_subtotal'] or vals['specific_tax_amount']
            for vals in book
        )
        if not has_specific_tax:
            options, lines = self._l10n_gt_drop_specific_tax_columns(options, lines)

        context = {
            'l10n_gt_doc_count': len(book),
            'l10n_gt_total_vat': self._l10n_gt_format_amount(self._l10n_gt_total_vat(book)),
            'l10n_gt_summary_rows': summary_rows,
            'l10n_gt_summary_total': summary_total,
            'l10n_gt_has_specific_tax': has_specific_tax,
            **(additional_context or {}),
        }
        return report._get_pdf_export_html(options, lines, additional_context=context, template=template)

    def _l10n_gt_drop_specific_tax_columns(self, options, lines):
        """ Few companies deal with specific taxes, so when no document in the book carries one,
        drop the three specific-tax columns from the printed detail grid to free width. Only for
        the PDF: data exports (CSV) always keep every column. """
        keep = [
            index for index, column in enumerate(options['columns'])
            if not column['expression_label'].startswith('specific_tax_')
        ]
        for line in lines:
            line.columns = [line.columns[index] for index in keep]
        return {**options, 'columns': [options['columns'][index] for index in keep]}, lines

    def _l10n_gt_summary_row_labels(self):
        """ The summary rows, in printed order, with their translatable labels. """
        return {
            'goods_local': self.env._("Goods Local"),
            'goods_foreign': self.env._("Goods Foreign"),
            'services_local': self.env._("Services Local"),
            'services_foreign': self.env._("Services Foreign"),
            'small': self.env._("Small Taxpayer (FPEQ/FCAP)"),
        }

    def _l10n_gt_summary_data(self, options, lines):
        """ Build the summary: goods/services x local/foreign plus a small-taxpayer row, each with
        exempt base, taxable base, specific tax, VAT and total. A small-taxpayer document (FPEQ/FCAP)
        lands wholly in its own row; otherwise the base splits goods/services by line, the VAT splits
        proportionally to the taxable base and the specific taxes go to Goods. All-zero rows are
        hidden. """
        currency = self.env.company.currency_id
        labels = self._l10n_gt_summary_row_labels()
        totals = {key: dict.fromkeys(('docs', *SUMMARY_AMOUNT_KEYS), 0.0) for key in labels}

        def add(key, *, exempt=0.0, taxable=0.0, specific=0.0, vat=0.0):
            bucket = totals[key]
            bucket['docs'] += 1
            bucket['exempt'] += exempt
            bucket['taxable'] += taxable
            bucket['specific'] += specific
            bucket['vat'] += vat

        for vals in self._l10n_gt_book_documents(options, lines):
            taxed_goods, taxed_services = vals['taxed_goods'], vals['taxed_services']
            exempt_goods, exempt_services = vals['exempt_goods'], vals['exempt_services']
            vat, specific = vals['vat_amount'], vals['specific_tax_amount']
            if vals['doc_type'] in SMALL_TAXPAYER_DOC_TYPES:
                add('small', exempt=exempt_goods + exempt_services, taxable=taxed_goods + taxed_services,
                    specific=specific, vat=vat)
                continue
            local = vals['transaction_type'] == 'L'
            taxable_base = taxed_goods + taxed_services
            if taxed_goods or exempt_goods or specific:
                add('goods_local' if local else 'goods_foreign', exempt=exempt_goods, taxable=taxed_goods,
                    specific=specific, vat=vat * taxed_goods / taxable_base if taxable_base else 0.0)
            if taxed_services or exempt_services:
                add('services_local' if local else 'services_foreign', exempt=exempt_services,
                    taxable=taxed_services, vat=vat * taxed_services / taxable_base if taxable_base else 0.0)

        def finalize(label, bucket):
            bucket['total'] = bucket['exempt'] + bucket['taxable'] + bucket['specific'] + bucket['vat']
            return {'label': label, 'docs': int(bucket['docs']),
                    **{col: currency.round(bucket[col]) for col in SUMMARY_AMOUNT_KEYS}}

        rows, grand = [], dict.fromkeys(('docs', *SUMMARY_AMOUNT_KEYS), 0.0)
        for key in labels:
            bucket = totals[key]
            if not bucket['docs']:  # hide all-zero rows
                continue
            row = finalize(labels[key], bucket)
            rows.append(row)
            # Total from the already-rounded rows so the columns foot exactly (no cent drift).
            grand['docs'] += row['docs']
            for col in SUMMARY_AMOUNT_KEYS:
                grand[col] += row[col]
        total_row = {'label': self.env._("Total"), 'docs': int(grand['docs']),
                     **{col: currency.round(grand[col]) for col in SUMMARY_AMOUNT_KEYS}}
        return rows, total_row

    def _l10n_gt_summary_rows(self, options, lines):
        """ The summary formatted for the PDF template: grouped 2-decimal strings. """
        rows, total = self._l10n_gt_summary_data(options, lines)

        def fmt(row):
            return {'label': row['label'], **{col: self._l10n_gt_format_amount(row[col]) for col in SUMMARY_AMOUNT_KEYS}}

        return [fmt(row) for row in rows], fmt(total)

    # -- CSV export -------------------------------------------------------------------------

    def l10n_gt_libro_export_to_csv(self, options):
        """ CSV of the book: legal header, the detail grid (header, one row per document, totals)
        then the summary. Numbers are written raw (no thousands separators) so Excel reads them as
        numbers. """
        report = self.env['account.report'].browse(options['report_id'])
        lines = report._get_lines(options)
        output = io.StringIO()
        writer = csv.writer(output)
        self._l10n_gt_write_header_csv(writer, options)
        writer.writerow(['', *(column['name'] for column in options['columns'])])
        for line in lines:
            writer.writerow([line.name, *(column.no_format for column in line.columns)])

        if lines:
            self._l10n_gt_write_summary_csv(writer, options, lines)

        return {
            'file_name': report.get_default_report_filename(options, 'csv'),
            'file_content': output.getvalue().encode('utf-8-sig'),
            'file_type': 'csv',
        }

    def _l10n_gt_write_header_csv(self, writer, options):
        """ Legal header above the detail grid (book title, company tax identification, trade name,
        fiscal address and reporting period), mirroring the PDF. """
        company = self.env.company
        # Same address rendering as the PDF header's contact widget (country address format).
        address = company.partner_id._display_address(without_name=True, separator=', ')
        writer.writerow([options.get('report_title') or ''])
        writer.writerow(["Quetzales (Q)"])
        writer.writerow([])
        writer.writerow([self.env._("Tax ID Number"), company.vat or '', '', self.env._("Fiscal Address"), address])
        writer.writerow([self.env._("Trade Name"), company.name, '', self.env._("Registry period"), options.get('l10n_gt_libro_period') or ''])
        writer.writerow([])

    def _l10n_gt_write_summary_csv(self, writer, options, lines):
        """ Append the summary under the detail rows: document count, total VAT, then the
        goods/services x local/foreign table. """
        book = self._l10n_gt_book_documents(options, lines)
        rows, total = self._l10n_gt_summary_data(options, lines)
        vat_label = self.env._("Total tax debit:") if self._l10n_gt_is_sales(options) else self.env._("Total tax credit:")

        writer.writerow([])
        writer.writerow([self.env._("Summary")])
        writer.writerow([self.env._("Number of documents:"), len(book)])
        writer.writerow([vat_label, self._l10n_gt_total_vat(book)])
        writer.writerow([])
        writer.writerow(['', self.env._("Exempt"), self.env._("Taxable"),
                         self.env._("Specific Tax Amount"), self.env._("VAT Amount"), self.env._("Total")])
        for row in (*rows, total):
            writer.writerow([row['label'], *(row[key] for key in SUMMARY_AMOUNT_KEYS)])
