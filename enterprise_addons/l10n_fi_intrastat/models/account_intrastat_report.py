import copy

from odoo import api, models
from odoo.exceptions import RedirectWarning


class AccountIntrastatGoodsReportHandler(models.AbstractModel):
    _inherit = 'account.intrastat.goods.report.handler'

    def _show_region_code(self):
        # The region code is irrelevant for the Finland and will always be an empty column, with
        # this function we can conditionally exclude it from the report.
        if self.env.company.account_fiscal_country_id.code == 'FI':
            return False
        return super()._show_region_code()

    def fi_intrastat_export_to_csv(self, options):
        """ Exports csv documents in zip containing the required intrastat data, compliant with the official format. """
        options['export_mode'] = 'file'
        report = self.env['account.report'].browse(options['report_id'])
        csv_files = []

        # Generate both arrivals and dispatches files
        for intrastat_type in ('arrivals', 'dispatches'):
            export_options = self._fi_prepare_options_for_export(options, intrastat_type)
            results = self._fi_get_report_results_for_file_export(export_options)
            content = self._fi_intrastat_get_csv_file_content(results, export_options, intrastat_type)
            filename = self.env._("%(type)s_%(filename)s", type=intrastat_type, filename=report.get_default_report_filename(options, 'csv'))
            csv_files.append((filename, content))

        return self._build_zip_response(report, options, csv_files)

    @api.model
    def _fi_get_report_results_for_file_export(self, options):
        """ Retrieve Intrastat report data for export. """
        report = self.env['account.report'].browse(options['report_id'])
        expressions = report.line_ids.expression_ids
        return self._report_engine_intrastat(options, expressions[0].date_scope, expressions.grouped('formula'), 'id')[expressions]

    @api.model
    def _fi_prepare_options_for_export(self, options, intrastat_type):
        """ Return a modified copy of the options for export grouping by intrastat type. """
        assert intrastat_type in {'arrivals', 'dispatches'}

        options_copy = copy.deepcopy(options)
        options_copy['intrastat_type'] = intrastat_type
        options_copy.setdefault('forced_domain', []).append(
            ('move_id.move_type', 'in', self._get_move_types_for_intrastat(intrastat_type))
        )

        return options_copy

    @api.model
    def _fi_intrastat_get_csv_file_content(self, results, options, direction_type):
        """ Generate Finnish-compliant CSV content for specific direction. """
        company = self.env.company
        company_vat = company.vat

        if not company_vat:
            raise RedirectWarning(
                self.env._("The company VAT number is required to export Intrastat data."),
                self.env['ir.actions.act_window']._for_xml_id('base.action_res_company_form'),
                self.env._("Configure Company"),
            )

        period = options['date']['date_from'][:7].replace('-', '')  # Convert YYYY-MM to YYYYMM
        is_arrivals = direction_type == 'arrivals'
        direction_code = '1' if is_arrivals else '2'

        agent_vat = company.account_representative_id.vat if is_arrivals and company.account_representative_id else ''

        columns = [
            'Data provider',
            'Period',
            'Direction',
            'Agent' if is_arrivals else 'Trading partner',
            'CN8 code',
            'Nature of transaction',
            'Country of consignment' if is_arrivals else 'Country of destination',
            'Country of origin',
            'Mode of transport',
            'Net mass',
            'Quantity in supplementary units',
            'Invoice value in euros',
            'Statistical value in euros',
            'Row reference',
        ]

        csv_rows = [';'.join(columns)]

        for index, result in enumerate(results):
            result_data = result[1]
            summary_row = index == 0

            # For Column D
            if is_arrivals:
                partner_vat = agent_vat if summary_row else ''  # For arrivals use agent VAT (only on second row if applicable)
            else:
                partner_vat = result_data.get('partner_vat') or ''  # For dispatches use trading partner VAT (on every row)

            net_mass = int(float(result_data['weight'])) if result_data.get('weight') is not None else ''
            supplementary_units = max(1, int(float(result_data['supplementary_units']))) if result_data.get('supplementary_units') is not None else ''
            invoice_value = max(1, int(result_data['value'])) if result_data.get('value') else 1

            row_data = [
                company_vat if summary_row else '',                               # A. Data provider (only on second row)
                period if summary_row else '',                                    # B. Period (only on second row)
                direction_code if summary_row else '',                            # C. Direction (only on second row)
                partner_vat,                                                      # D. Agent/Trading partner
                result_data.get('commodity_code') or '',                          # E. CN8 code
                result_data.get('transaction_code') or '',                        # F. Nature of transaction
                result_data.get('country_code') or '',                            # G. Country of consignment/destination
                result_data.get('intrastat_product_origin_country_code') or '',   # H. Country of origin
                result_data.get('transport_code') or '',                          # I. Mode of transport
                net_mass,                                                         # J. Net mass in kg
                supplementary_units,                                              # K. Quantity in supplementary units
                invoice_value,                                                    # L. Invoice value in euros
                '',                                                               # M. Statistical value (optional)
                ''                                                                # N. Row reference (optional)
            ]

            csv_rows.append(';'.join(str(field) for field in row_data))

        return '\n'.join(csv_rows).encode('utf-8')
