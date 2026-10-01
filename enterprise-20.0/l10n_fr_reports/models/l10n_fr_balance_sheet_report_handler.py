from odoo import models


class L10nFrBalanceSheetReportHandler(models.AbstractModel):
    _name = 'l10n_fr.balance.sheet.report.handler'
    _inherit = 'account.balance.sheet.report.handler'
    _description = 'French Balance Sheet Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        """
        Keep all balance sheet columns for the current period, but only Net
        for comparison periods, and adjust the corresponding header colspans.
        """
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        comparison_dates = options.get('comparison', {}).get('periods', [])
        if not comparison_dates:
            return

        def get_column_date(column):
            column_group = options['column_groups'][column['column_group_index']]
            return column_group['forced_options'].get('date')

        options['columns'] = [
            column
            for column in options['columns']
            if column['expression_label'] == 'net'
            or get_column_date(column) not in comparison_dates
        ]
        for header in options['column_headers'][0]:
            header_date = header['forced_options']['date']
            header['colspan'] = sum(
                get_column_date(column) == header_date
                for column in options['columns']
            )
