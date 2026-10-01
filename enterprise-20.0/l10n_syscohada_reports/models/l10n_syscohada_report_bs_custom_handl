from odoo import models


class L10nSyscohadaReportBsCustomHandler(models.AbstractModel):
    _name = 'l10n_syscohada.report.bs.custom.handler'
    _inherit = 'account.report.custom.handler'
    _description = "SYSCOHADA Balance Sheet Custom Handler"

    def _report_engine_get_note(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        if current_groupby:
            return {next(iter(formulas_dict.values())): []}
        return {next(iter(formulas_dict.values())):  {
            'AD': '3',
            'AI': '3',
            'AP': '3',
            'AQ': '4',
            'BA': '5',
            'BB': '6',
            'BH': '17',
            'BI': '7',
            'BJ': '8',
            'BQ': '9',
            'BR': '10',
            'BS': '11',
            'BU': '12',
            'CA': '13',
            'CB': '13',
            'CD': '14',
            'CE': '3E',
            'CF': '14',
            'CG': '14',
            'CH': '14',
            'CL': '15',
            'CM': '15',
            'DA': '16',
            'DB': '16',
            'DC': '16',
            'DH': '5',
            'DI': '7',
            'DJ': '17',
            'DK': '18',
            'DM': '19',
            'DN': '19',
            'DQ': '20',
            'DR': '20',
            'has_sublines': False,
        }}

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)

        for line in lines:
            columns = line.columns
            note_column = next((column for column in columns if column.expression_label == 'note'), None)
            balance_column = next((column for column in columns if column.expression_label == 'balance'), None)
            if note_column and balance_column and balance_column.is_zero:
                note_column.name = ''
                note_column.no_format = ''
                note_column.is_zero = True

        return lines
