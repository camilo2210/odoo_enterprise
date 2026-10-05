import copy
import io
import xlsxwriter


from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import SQL


class AccountIntrastatGoodsReportHandler(models.AbstractModel):
    _inherit = 'account.intrastat.goods.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)

        if self.env.company.account_fiscal_country_id.code != 'SE':
            return

        # Override the generic xlsx export to instead export official xlsx documents
        xlsx_button_option = next(button_opt for button_opt in options['buttons'] if button_opt.get('action_param') == 'export_to_xlsx')
        xlsx_button_option['action_param'] = 'se_export_to_xlsx'
        xlsx_button_option['name'] = _('XLSX (IDEP.web)')

    def _get_exporting_query_data(self):
        res = super()._get_exporting_query_data()
        return SQL('%s account_move.name AS name,', res)

    def _get_exporting_dict_data(self, result_dict, query_res):
        super()._get_exporting_dict_data(result_dict, query_res)
        if self.env.company.partner_id.country_id.code == 'SE':
            result_dict['name'] = query_res['name']
        return result_dict

    def se_export_to_xlsx(self, options):
        """ Exports a xlsx document containing the required intrastat data, compliant with the official format.
        If filter intrastat_type is set to either 'Arrival' or 'Dispatch', then exports only the xlsx file.
        If both options are activated, then exports a zip file containing both arrivals and dispatches xlsx documents.
        """
        report = self.env['account.report'].browse(options['report_id'])
        options = report.get_options({**options, 'unfold_all': True, 'export_mode': 'file'})

        include_arrivals, include_dispatches = super()._determine_inclusion(options)

        xlsx_files = []
        if include_arrivals:
            options_arrivals = self._se_prepare_options(options, self._se_get_col_order('arrivals'), 'arrivals')
            xlsx_files.append((
                _("arrivals_%s", report.get_default_report_filename(options, 'xlsx')),
                self._se_generate_xlsx_report(report, options_arrivals),
            ))
        if include_dispatches:
            options_dispatches = self._se_prepare_options(options, self._se_get_col_order('dispatches'), 'dispatches')
            xlsx_files.append((
                _("dispatches_%s", report.get_default_report_filename(options, 'xlsx')),
                self._se_generate_xlsx_report(report, options_dispatches),
            ))
        # Should never happen, just to make sure returned values below are valid
        match xlsx_files:
            case []:
                raise UserError(_("Something went wrong when generating xlsx file, please make sure to include arrivals, or dispatches, or both"))
            case [(name, content)]:
                return {
                    'file_name': name,
                    'file_content': content,
                    'file_type': 'xlsx',
                }
            case files:
                return self._build_zip_response(report, options, files)

    @api.model
    def _se_prepare_options(self, options, col_order, intrastat_type):
        """ Returns a modified copy of the options that will be necessary to generate the
        documents in order for them to follow the proper format
        """
        assert intrastat_type in {'arrivals', 'dispatches'}

        options_copy = copy.deepcopy(options)  # Necessary in case we reorder/filter the columns for both arrivals and dispatches

        # Replace the 'country_name' column by the 'country_code' column because the xlsx files only need the code
        option_col_country = next(option_col for option_col in options_copy['columns'] if option_col['expression_label'] == 'country_name')
        option_col_country['expression_label'] = 'country_code'

        options_copy['columns'] = self._se_format_columns_options(col_order, options_copy)

        options_copy.setdefault('forced_domain', []).append(
            ('move_id.move_type', 'in', self._get_move_types_for_intrastat(intrastat_type))
        )

        return options_copy

    @api.model
    def _se_get_col_order(self, intrastat_type):
        """ Returns a list of columns that should be present in the official xlsx file.
        The provided order must be respected. Each value in the list corresponds to the
        expression_label of the column. The 'Reference' column is missing in these lists, and
        is added later because this data is the name of the lines and not a column in the options
        """
        assert intrastat_type in {'arrivals', 'dispatches'}
        return {
            'arrivals': ['commodity_code', 'transaction_code', 'country_code', 'weight', 'supplementary_units', 'value'],
            'dispatches': ['commodity_code', 'transaction_code', 'country_code', 'weight', 'supplementary_units', 'value', 'partner_vat', 'intrastat_product_origin_country_code']
        }[intrastat_type]

    @api.model
    def _se_generate_xlsx_report(self, report, options):
        """ Returns a xlsx file that follows the official format, which can be found at this address
        https://www.scb.se/en/data-collection/surveys/intrastat--swedish-foreign-trade-with-the-eu/information-about-idep.web
        """
        with io.BytesIO() as output:
            with xlsxwriter.Workbook(output, {
                'in_memory': True,
                'strings_to_formulas': False,
            }) as workbook:
                self._se_inject_report_into_xlsx_sheet(report, options, workbook, workbook.add_worksheet())

            return output.getvalue()

    @api.model
    def _se_format_columns_options(self, col_order, options):
        """ Reorder and filter the columns in the options based on the specified order provided in col_order.
        Also improves the name of the column titles such that it matches the official document.
        """
        columns_names = {
            'commodity_code': _("CN8 Commodity Code"),
            'country_code': _("Partner country"),
            'transaction_code': _("Nature of transaction"),
            'weight': _("Net Mass (KG)"),
            'supplementary_units': _("Suppl. Units"),
            'value': _("Invoice Value SEK"),
            'partner_vat': _("Partner ID/VAT number"),
            'intrastat_product_origin_country_code': _("Country of Origin"),
            'name': _("Reference"),
        }

        return [
            {**col, 'name': columns_names.get(col['expression_label'], col['name'])}
            for col in sorted(
                (col for col in options['columns'] if col['expression_label'] in col_order),
                key=lambda col: col_order.index(col['expression_label'])
            )
        ]

    @api.model
    def _se_intrastat_xlsx_get_data(self, report, options):
        """ Returns a list of lists, each containing one row used in the xlsx.
        The first row is the column titles
        """
        expressions = report.line_ids.expression_ids
        lines = self._report_engine_intrastat(options, expressions[0].date_scope, expressions.grouped('formula'), 'id', None)[expressions]
        for index, line_result in enumerate(lines):
            lines[index] = line_result[1]

        results = []
        column_titles = []
        column_labels = []

        # Add column row
        for column in options['columns']:
            column_titles.append(column.get('name', ''))
            column_labels.append(column.get('expression_label', ''))

        results.append(column_titles)

        # Add line rows
        for line in lines:
            res_line = []
            for column in column_labels:
                res_line.append(str(line[column] or ''))

            results.append(res_line)

        return results

    @api.model
    def _se_inject_report_into_xlsx_sheet(self, report, options, workbook, sheet):
        title_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'bottom': 2})
        line_style = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'font_color': '#666666'})

        sheet.set_column(0, len(options['columns']), 20)  # set a length of 20 for each column

        results = self._se_intrastat_xlsx_get_data(report, options)
        for line_offset, line in enumerate(results):
            for col_offset, value in enumerate(line):
                sheet.write(line_offset, col_offset, value, title_style if line_offset == 0 else line_style)
