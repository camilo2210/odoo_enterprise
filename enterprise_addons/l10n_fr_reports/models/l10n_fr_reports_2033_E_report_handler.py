from odoo import api, models

CODE_TO_EDI_ID = {
    'FR_2033_E_376': {
        'balance': {'zone': 'AA'},
    },
    'FR_2033_E_657': {
        'balance': {'zone': 'AB'},
    },
    'FR_2033_E_651': {
        'balance': {'zone': 'AC'},
    },
    'FR_2033_E_861': {
        'balance': {'zone': 'AD'},
    },
    'FR_2033_E_I': {
        'balance': {'zone': 'AF'},
    },
    'FR_2033_E_023': {
        'balance': {'zone': 'AH'},
    },
    'FR_2033_E_108': {
        'balance': {'zone': 'AJ'},
    },
    'FR_2033_E_111': {
        'balance': {'zone': 'AK'},
    },
    'FR_2033_E_121': {
        'balance': {'zone': 'AL'},
    },
    'FR_2033_E_145': {
        'balance': {'zone': 'AM'},
    },
    'FR_2033_E_II': {
        'balance': {'zone': 'AN'},
    },
    'FR_2033_E_III': {
        'balance': {'zone': 'AP'},
    },
    'FR_2033_E_026': {
        'balance': {'zone': 'AQ'},
    },
    'FR_2033_E_143': {
        'balance': {'zone': 'EE'},
    },
    'FR_2033_E_113': {
        'balance': {'zone': 'EF'},
    },
    'FR_2033_E_115': {
        'balance': {'zone': 'EL'},
    },
    'FR_2033_E_118': {
        'balance': {'zone': 'EN'},
    },
    'FR_2033_E_119': {
        'balance': {'zone': 'EP'},
    },
    'FR_2033_E_125': {
        'balance': {'zone': 'FE'},
    },
    'FR_2033_E_133': {
        'balance': {'zone': 'FH'},
    },
    'FR_2033_E_310': {
        'balance': {'zone': 'FJ'},
    },
    'FR_2033_E_148': {
        'balance': {'zone': 'FK'},
    },
    'FR_2033_E_150': {
        'balance': {'zone': 'FM'},
    },
    'FR_2033_E_135': {
        'balance': {'zone': 'FN'},
    },
    'FR_2033_E_calculation_added_value': {
        'balance': {'zone': 'GA'},
    },
    'FR_2033_E_V': {
        'balance': {'zone': 'GB'},
    },
    'FR_2033_E_128': {
        'balance': {'zone': 'GC'},
    },
    'FR_2033_E_153': {
        'balance': {'zone': 'GD'},
    },
    'FR_2033_E_020': {
        'balance': {'zone': 'KA', 'format': 'TBX'},
    },
    'FR_2033_E_024': {
        'balance': {'zone': 'KB', 'format': '102'},
    },
    'FR_2033_E_016': {
        'balance': {'zone': 'KC', 'format': '102'},
    },
    'FR_2033_E_022': {
        'balance': {'zone': 'KD'},
    },
    'FR_2033_E_termination_date': {
        'balance': {'zone': 'KG', 'format': '102'},
    },
}


class L10nFrReports2033EReportHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.2033.e.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = '2033 E Report Handler'

    @api.model
    def _get_code_to_edi_id(self):
        return CODE_TO_EDI_ID
