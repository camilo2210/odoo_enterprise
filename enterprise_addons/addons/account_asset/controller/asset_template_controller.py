import io
import xlsxwriter
from odoo import http, _
from odoo.http import request


class AssetTemplateController(http.Controller):

    @http.route('/web/binary/download_asset_template/<int:company_id>', type='http', auth='user')
    def download_template(self, company_id):
        """
        Handles the HTTP request and serves the generated Excel file for download.
        """
        content = self._generate_asset_import_template(company_id)

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="asset_import_template.xlsx"'),
            ]
        )

    def _get_technical_headers(self):
        """ Defines and returns the common functional and technical headers. """
        return [item[0] for item in self._get_instructions_data()]

    def _get_localized_example_data(self, current_company_id, env):
        """
        Dynamically fetches localized example values for accounts
        based on the current company and generates multiple example rows.
        """
        current_company = env['res.company'].browse(current_company_id)

        def get_account_by_type(account_types):
            for acc_type in account_types:
                if account := env['account.account'].with_company(current_company).search([
                    *env['account.account']._check_company_domain(current_company),
                    ('account_type', '=', acc_type),
                    ('depreciation_model_id', '!=', None),
                ], limit=1):
                    return account

            return None

        asset_account = get_account_by_type(['asset_fixed', 'asset_non_current'])
        if asset_account:
            asset_account_example = asset_account.display_name
            depreciation_model_example = asset_account.depreciation_model_id.display_name
        else:
            asset_account_example = ''
            depreciation_model_example = ''

        all_example_rows = [
            [
                'Computer 1', '800.00', '01-01-2025', '', depreciation_model_example, 'No Prorata', '01-01-2025',
                '200.00', '0.00', current_company.name,
                asset_account_example,
            ],
            [
                'Computer 2', '25000.00', '03-15-2025', '', depreciation_model_example, 'Based on days per period', '03-15-2025',
                '0.00', '2000.00', current_company.name,
                asset_account_example,
            ],
            [
                'Machine A', '15000.00', '09-01-2024', '', depreciation_model_example, 'Constant Periods', '09-01-2024',
                '1500.00', '500.00', current_company.name,
                asset_account_example,
            ],
            [
                'Machine B', '100000.00', '06-20-2025', '', depreciation_model_example, 'Constant Periods', '06-20-2025',
                '10000.00', '10000.00', current_company.name,
                asset_account_example,
            ]
        ]

        return all_example_rows

    def _get_instructions_data(self):
        """Defines and returns the data for the 'Instructions' sheet."""
        return [
            ('name', _('Asset Name'), True, _('Mandatory column. This is the name of the asset.')),
            ('original_value', _('Original Value'), True, _('The amount will be considered in company currency.')),
            ('acquisition_date', _('Acquisition Date'), True, _('e.g. 01-27-2025 (format: MM-DD-YYYY)')),
            ('asset_group_id', _('Asset Group'), False, _('Optional. The name or external ID of the asset group. Must exist in Odoo (e.g., Office Equipment, Vehicles, Machinery).')),
            ('model_id', _('Depreciation Model'), True, _('Name of depreciation model to be used with the asset, e.g. 5 year linear. Must exist in Odoo before importing.')),
            ('prorata_computation_type', _('Computation'), True, _('e.g. No Prorata, Constant Periods, Based on days per period. This determines how the first depreciation entry is calculated.')),
            ('prorata_date', _('Prorata Date'), True, _('Start date of the depreciation period. Should be in MM-DD-YYYY format. If left blank, it defaults to the acquisition date.')),
            ('already_depreciated_amount_import', _('Depreciated Amount'), False, _('The total amount of depreciation already recorded for the asset before import. This amount will be considered in company currency.')),
            ('salvage_value', _('Not Depreciable Value'), False, _('The estimated residual value of the asset at the end of its useful life. This amount will not be depreciated. Considered in company currency.')),
            ('company_id', _('Company'), True, _("Must match the selected company during import. Use the company's display name.")),
            ('account_asset_id', _('Fixed Asset Account'), True, _('The balance sheet account for the asset itself (e.g., "151000 Fixed Asset"). Must exist in Odoo and be of "Fixed Asset" or "Non-current Assets" type with depreciation model, accumulated depreciation, and depreciation expense account set.')),
            ('account_depreciation_id', _('Accumulated Depreciation Account'), False, _('The accumulated depreciation account (contra-asset account). Must exist in Odoo and be of "Fixed Asset" or "Non-current Assets" type.')),
            ('account_depreciation_expense_id', _('Depreciation Expense Account'), False, _('The expense account for posting periodic depreciation entries (e.g., "630000 Depreciation Expenses"). Must exist in Odoo and be of "Depreciation" or "Expense" type.')),
        ]

    def _write_asset_sheet(self, workbook, company_id):
        """
        Creates and populates the 'Assets' sheet with headers, multiple example data rows, and comments.
        """
        headers = self._get_technical_headers()
        all_example_rows = self._get_localized_example_data(company_id, request.env)
        self._create_sheet(workbook, 'Assets', headers, all_example_rows)

    def _write_instructions_sheet(self, workbook):
        """
        Creates and populates the 'Instructions' sheet with column details and notes.
        """
        instructions_data = self._get_instructions_data()
        headers = ['Column Name', 'Column Functional Name', 'Comments / Notes']
        values = [
            [field, f"{label}*" if mandatory else label, help_text]
            for field, label, mandatory, help_text in instructions_data
        ]
        self._create_sheet(workbook, 'Instructions', headers, values)

    def _write_depreciation_model_sheet(self, workbook):
        """
        Creates and populates the 'Assets' sheet with headers, multiple example data rows, and comments.
        """
        headers = ['method', 'method_mode', 'method_number', 'method_period', 'method_rate', 'method_progress_factor', 'journal_id', 'company_id']
        examples = [
            ['Straight Line', 'Duration', 2, 'Year'],
            ['Straight Line', 'Rate', '', 'Year', 0.20],
            ['Declining', '', 36, 'Month', '', 0.30],
            ['Declining then Straight Line', '', 36, 'Month', '', 0.35],
        ]
        self._create_sheet(workbook, 'Depreciation Model', headers, examples)

    def _create_sheet(self, workbook, name, headers, values):
        worksheet = workbook.add_worksheet(name)
        header_format = workbook.add_format({'bold': True})

        for col_idx, header_text in enumerate(headers):
            worksheet.write(0, col_idx, header_text, header_format)

        for row_idx, example_row in enumerate(values, start=1):
            for col, example_value in enumerate(example_row):
                worksheet.write(row_idx, col, example_value)

        for col, header in enumerate(headers):
            max_len = len(str(header))
            for example_row in values:
                if col < len(example_row):
                    max_len = max(max_len, len(str(example_row[col])))
            worksheet.set_column(col, col, max_len + 4)

    def _generate_asset_import_template(self, company_id):
        """
        Generates an Excel file with:
        - Sheet 1: Asset import template (headers, example, comments)
        - Sheet 2: Instructions (column details, notes)
        - Sheet 3: Depreciation Model import template
        """
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        self._write_asset_sheet(workbook, company_id)
        self._write_instructions_sheet(workbook)
        self._write_depreciation_model_sheet(workbook)

        workbook.close()
        return output.getvalue()
