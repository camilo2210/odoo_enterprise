# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.tools import SQL
from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData

VAT_8_PURCHASE_BASE_TAGS = ['form_01_gtgt_report_C_I_1_amount_untaxed_8', 'form_01_gtgt_report_C_I_a_amount_untaxed_8']
VAT_8_PURCHASE_TAX_TAGS = ['form_01_gtgt_report_C_I_1_balance_8', 'form_01_gtgt_report_C_I_a_balance_8']
VAT_8_SALE_BASE_TAGS = ['form_01_gtgt_report_C_II_c_amount_untaxed_8']
VAT_8_SALE_TAX_TAGS = ['form_01_gtgt_report_C_II_c_balance_8']


class L10n_VnTaxReportHandler(models.AbstractModel):
    _name = 'l10n_vn_reports.appendix_142.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'Vietnamese Tax Report, TaxAppendix 142 Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['custom_display_config'].setdefault('pdf_export', {})['pdf_export_main'] = 'l10n_vn_reports.l10n_vn_appendix142_report_pdf_export'

    def _get_line_column(self, report, options, data, is_title=False, is_sales_line=False):
        line_columns = []
        columns = options['columns']
        for column in columns:
            col_value = data.get(column['column_group_index'], {}).get(column['expression_label'])
            line_columns.append(report._build_column_data(
                col_value=col_value or '',
                options_col_desc=column,
                options=options,
            ))
        if self.env.context.get('l10n_vn_appendix142_xlsx_export'):
            # xlsx export returns 2 extra columns, with fixed values
            extra_cols = ['8 %', '10 %'] if is_sales_line else ['', '']
            if is_title and is_sales_line:
                extra_cols = [_('VAT rate after deduction'), _('Original VAT rate')]
            for extra_val in extra_cols:
                line_columns.insert(1, report._build_column_data(extra_val, None))
        return line_columns

    def _create_total_line(self, report, line, total_base, total_vat, options, is_sales_line=False):
        new_line = report._generate_total_below_section_line(line)
        base_amount_index = next((index for (index, col) in enumerate(options['columns']) if col["expression_label"] == "base_amount"), None)
        vat_amount_index = next((index for (index, col) in enumerate(options['columns']) if col["expression_label"] == "vat_amount"), None)
        if self.env.context.get('l10n_vn_appendix142_xlsx_export'):
            # 2 columns are added between the base and vat columns, in the XLSX export
            vat_amount_index += 2
            new_line.columns[vat_amount_index - 1].no_format = ''
            new_line.columns[vat_amount_index - 2].no_format = ''
        new_line.name = _('Total')
        new_line.columns[base_amount_index].no_format = total_base
        new_line.columns[vat_amount_index].no_format = total_vat
        return new_line

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        if warnings is None:
            warnings = {}

        purchases_data, total_base_purchases, total_vat_purchases = self._get_month_data(report, options, VAT_8_PURCHASE_BASE_TAGS, VAT_8_PURCHASE_TAX_TAGS, False)
        sales_data, total_base_sales, total_vat_sales = self._get_month_data(report, options, VAT_8_SALE_BASE_TAGS, VAT_8_SALE_TAX_TAGS, True)
        report_lines = []
        if not purchases_data and not sales_data:
            warnings['l10n_vn_reports.no_data_warning'] = {
                'alert_type': 'warning',
            }
        elif not sales_data:
            warnings['l10n_vn_reports.no_sales_warning'] = {
                'alert_type': 'warning',
            }
        else:
            report_lines = self._create_section_line(report, options, 1, {
                'name': _('I. Purchased Goods and Services in the period with 8% VAT rate'),
                'base_amount': _('Untaxed amount'),
                'vat_amount': _('VAT amount'),
            })
            report_lines += self._create_report_lines(report, options, purchases_data)
            purchase_total_line = self._create_total_line(report, report_lines[0], total_base_purchases, total_vat_purchases, options)
            report_lines.append(purchase_total_line)
            sales_report_lines = self._create_section_line(report, options, 2, {
                'name': _('II. Sold Goods and Services in the period'),
                'base_amount': _('Untaxed amount'),
                'vat_amount': _('Deducted amount of VAT'),
                }, is_sales_line=True)
            report_lines += sales_report_lines
            report_lines += self._create_report_lines(report, options, sales_data, is_sales_line=True)
            sales_total_line = self._create_total_line(report, sales_report_lines[0], total_base_sales, total_vat_sales, options, is_sales_line=True)
            report_lines.append(sales_total_line)
            report_lines += self._create_grand_total_line(report, options, total_vat_sales - total_vat_purchases)

        # Inject sequences on the dynamic lines
        return [(0, line) for line in report_lines]

    def _create_section_line(self, report, options, section_number, columns, is_sales_line=False):
        ddict = {}
        for column_group_index, col_group_options in report._split_options_per_column_group(options).items():
            ddict[column_group_index] = {col_opt['expression_label']: columns.get(col_opt['expression_label'], '') for col_opt in col_group_options['columns']}
        line_id = 'appendix_section' + str(section_number)
        return [AccountReportLineData(
            id=report._get_generic_line_id('', '', markup=line_id),
            name=columns['name'],
            unfoldable=False,
            unfolded=False,
            columns=self._get_line_column(report, options, ddict, is_title=True, is_sales_line=is_sales_line),
            level=0,
        )]

    def _create_report_lines(self, report, options, data, is_sales_line=False):
        return [AccountReportLineData(
                id=report._get_generic_line_id('account.move.line', res['id']),
                name=res['name'],
                unfoldable=False,
                unfolded=False,
                columns=self._get_line_column(report, options, res['columns'], is_title=False, is_sales_line=is_sales_line),
                level=3,
        ) for res in data]

    def _post_process_query(self, rows):
        lines_dict = {}
        total_base = 0
        total_vat = 0

        # sum the base/vat amounts to display in the 'total' lines, grouping the lines per product name
        # or journal items label, as per the legal requirements
        for res in rows:
            line_key = res['report_line_name']
            line_dict = lines_dict.setdefault(line_key, {
                'id': res['id'],
                'name': line_key,
                'columns': {}
            })
            total_base += res['base_amount']
            total_vat += res['tax_amount']
            line_dict['columns'][res['column_group_index']] = {
                'vat_amount': res['tax_amount'],
                'base_amount': res['base_amount'],
            }
        streamlined_res = [lines_dict[x] for x in lines_dict]
        return streamlined_res, total_base, total_vat

    def _get_month_data(self, report, options, base_tags_refs, tax_tags_refs, is_sale):
        # tags_ref = list of xml-ids referencing account.report.expression
        queries = []
        base_grids = self.env['account.report.expression']
        for tag_ref in base_tags_refs:
            base_grids |= self.env.ref('l10n_vn.' + tag_ref)
        base_tags = base_grids._get_matching_tags()

        tax_grids = self.env['account.report.expression']
        for tag_ref in tax_tags_refs:
            tax_grids |= self.env.ref('l10n_vn.' + tag_ref)
        tax_tags = tax_grids._get_matching_tags()

        for column_group_index, column_group_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(column_group_options, date_scope="strict_range", domain=[('tax_tag_ids', 'in', base_tags.ids)])
            tax_details_base_query = report._get_report_query(column_group_options, date_scope="strict_range", domain=[('tax_tag_ids', 'in', (base_tags | tax_tags).ids)])
            tax_details_query = self.env['account.move.line']._get_query_tax_details(tax_details_base_query)

            user_lang = self.env.user.lang or 'en_US'
            select = SQL("""
                  SELECT MIN(account_move_line.id) AS id,  -- using MIN() to ensure a unique ID since we're using an aggregate function
                         prod_templ.id AS product_tmpl_id,
                         COALESCE(prod_templ.name->>%(user_lang)s, account_move_line.name) AS report_line_name,
                         %(column_group_index)s AS column_group_index,
                """,
                column_group_index=column_group_index,
                user_lang=user_lang,
            )
            if is_sale:
                amount_columns = SQL("""
                         -SUM(tdr.base_amount) AS base_amount,
                         -SUM(tdr.base_amount) * 0.02 AS tax_amount
                """)
            else:
                amount_columns = SQL("""
                         SUM(tdr.base_amount) AS base_amount,
                         SUM(tdr.tax_amount) AS tax_amount
                """)
            queries.append(
                SQL("""%(select)s
                    %(amount_columns)s
                    FROM %(table_references)s
                    JOIN (%(tax_details_query)s) AS tdr ON (tdr.base_line_id = account_move_line.id)
               LEFT JOIN product_product prod ON account_move_line.product_id = prod.id
               LEFT JOIN product_template prod_templ ON prod.product_tmpl_id = prod_templ.id

                   WHERE %(search_condition)s

                GROUP BY prod_templ.id, COALESCE(prod_templ.name->>%(user_lang)s, account_move_line.name)
                """,
                select=select,
                amount_columns=amount_columns,
                table_references=query.from_clause,
                search_condition=query.where_clause,
                tax_details_query=tax_details_query,
                user_lang=user_lang,
            ))

        self.env.cr.execute(SQL(" UNION ALL ").join(queries))
        return self._post_process_query(self.env.cr.dictfetchall())

    def _create_grand_total_line(self, report, options, total):
        return self._create_section_line(report, options, 3, {
            'name': _("III. Difference of VAT amount between Purchased and Sold Goods and Services in the period which applies the 8% VAT rate:"),
            'base_amount': '',
            'vat_amount': total,
            })

    ##############
    # PDF EXPORT #
    ##############
    def _get_pdf_sections(self, report, options, lines):
        """Split lines into purchase, sales, and grand total sections for the PDF export.

        The report is structured as:
          - Section 1 (appendix_section1): Purchased Goods header + purchase data lines + total
          - Section 2 (appendix_section2): Sold Goods header + sales data lines + total
          - Section 3 (appendix_section3): Grand total line (difference of VAT)

        Returns a dict with 'purchase_lines', 'sales_lines', and 'section_3_total'.
        """
        if not lines:
            return {
                'purchase_lines': [],
                'sales_lines': [],
                'section_3_total': 0,
            }

        vat_amount_index = next(
            (index for (index, col) in enumerate(options['columns']) if col["expression_label"] == "vat_amount"), None
        )

        sale_section_index = 0
        for line in lines:
            if report._get_markup(line.id) == 'appendix_section2':
                break
            sale_section_index += 1
        purchase_lines = lines[0:sale_section_index]
        sales_lines = lines[sale_section_index:-1]

        for line in purchase_lines + sales_lines:
            markup = report._get_markup(line.id)
            if markup in ('appendix_section1', 'appendix_section2'):
                line.name = _('Goods and Services')

        section_3_total = 0
        if lines and vat_amount_index is not None and vat_amount_index < len(lines[-1].columns):
            section_3_total = lines[-1].columns[vat_amount_index].no_format

        return {
            'purchase_lines': purchase_lines,
            'sales_lines': sales_lines,
            'section_3_total': section_3_total,
        }

    def _get_pdf_export_html(self, options, lines=None, additional_context=None, template=None, report=None):
        """
        Override the default _get_pdf_export_html to handle the different 3 parts of the report, each having a distinct table in the template
        """
        report = report or self.env['account.report'].browse(options['report_id'])
        lines = lines or []

        if additional_context is None:
            additional_context = {}

        additional_context.update(self._get_pdf_sections(report, options, lines))
        return report._get_pdf_export_html(options, lines=lines, additional_context=additional_context, template=template)

    ###############
    # XLSX EXPORT #
    ###############
    def _inject_report_into_xlsx_sheet(self, options, workbook):
        # add the context key l10n_vn_appendix142_xlsx_export to allow the xlsx export to have 4 columns
        report = self.env['account.report'].browse(options['report_id'])
        sheet = workbook.add_worksheet(report.name)
        report.with_context(l10n_vn_appendix142_xlsx_export=True)._inject_report_into_xlsx_sheet(options, workbook, sheet)
