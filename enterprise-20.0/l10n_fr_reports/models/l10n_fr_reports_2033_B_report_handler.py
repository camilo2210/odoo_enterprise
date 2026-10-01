from odoo import api, models

CODE_TO_EDI_ID = {
    'FR_2033_B_c209': {
        'balance': {'zone': 'AA'},
    },
    'FR_2033_B_c215': {
        'balance': {'zone': 'AB'},
    },
    'FR_2033_B_c217': {
        'balance': {'zone': 'AC'},
    },
    'FR_2033_B_c249': {
        'balance': {'zone': 'AD'},
    },
    'FR_2033_B_c251': {
        'balance': {'zone': 'AE'},
    },
    'FR_2033_B_c998': {
        'balance': {'zone': 'AF'},
    },
    'FR_2033_B_c997': {
        'balance': {'zone': 'AG'},
    },
    'FR_2033_B_c655': {
        'balance': {'zone': 'AH'},
    },
    'FR_2033_B_c999': {
        'balance': {'zone': 'AJ'},
    },
    'FR_2033_B_c347': {
        'balance': {'zone': 'AK'},
    },
    'FR_2033_B_c348': {
        'balance': {'zone': 'AL'},
    },
    'FR_2033_B_re_lease': {
        'balance': {'zone': 'AN'},
    },
    'FR_2033_B_c243': {
        'balance': {'zone': 'AP'},
    },
    'FR_2033_B_c991': {
        'balance': {'zone': 'AQ'},
    },
    'FR_2033_B_c992': {
        'balance': {'zone': 'AR'},
    },
    'FR_2033_B_c643': {
        'balance': {'zone': 'AS'},
    },
    'FR_2033_B_c990': {
        'balance': {'zone': 'AT'},
    },
    'FR_2033_B_c259': {
        'balance': {'zone': 'AU'},
    },
    'FR_2033_B_c260': {
        'balance': {'zone': 'AV'},
    },
    'FR_2033_B_c645': {
        'balance': {'zone': 'AX'},
    },
    'FR_2033_B_c993': {
        'balance': {'zone': 'AY'},
    },
    'FR_2033_B_c649': {
        'balance': {'zone': 'AZ'},
    },
    'FR_2033_B_c210': {
        'balance': {'zone': 'BA'},
    },
    'FR_2033_B_c214': {
        'balance': {'zone': 'BB'},
    },
    'FR_2033_B_c218': {
        'balance': {'zone': 'BC'},
    },
    'FR_2033_B_c222': {
        'balance': {'zone': 'BD'},
    },
    'FR_2033_B_c224': {
        'balance': {'zone': 'BE'},
    },
    'FR_2033_B_c226': {
        'balance': {'zone': 'BF'},
    },
    'FR_2033_B_c230': {
        'balance': {'zone': 'BG'},
    },
    'FR_2033_B_c232': {
        'balance': {'zone': 'BH'},
    },
    'FR_2033_B_c234': {
        'balance': {'zone': 'BJ'},
    },
    'FR_2033_B_c236': {
        'balance': {'zone': 'BK'},
    },
    'FR_2033_B_c238': {
        'balance': {'zone': 'BL'},
    },
    'FR_2033_B_c240': {
        'balance': {'zone': 'BM'},
    },
    'FR_2033_B_c242': {
        'balance': {'zone': 'BN'},
    },
    'FR_2033_B_c244': {
        'balance': {'zone': 'BP'},
    },
    'FR_2033_B_c250': {
        'balance': {'zone': 'BQ'},
    },
    'FR_2033_B_c252': {
        'balance': {'zone': 'BR'},
    },
    'FR_2033_B_c254': {
        'balance': {'zone': 'BS'},
    },
    'FR_2033_B_c256': {
        'balance': {'zone': 'BT'},
    },
    'FR_2033_B_c262': {
        'balance': {'zone': 'BU'},
    },
    'FR_2033_B_c264': {
        'balance': {'zone': 'BV'},
    },
    'FR_2033_B_c270': {
        'balance': {'zone': 'BW'},
    },
    'FR_2033_B_c280': {
        'balance': {'zone': 'BX'},
    },
    'FR_2033_B_c290': {
        'balance': {'zone': 'BY'},
    },
    'FR_2033_B_c294': {
        'balance': {'zone': 'BZ'},
    },
    'FR_2033_B_c300': {
        'balance': {'zone': 'CA'},
    },
    'FR_2033_B_c306': {
        'balance': {'zone': 'CB'},
    },
    'FR_2033_B_c310': {
        'balance': {'zone': 'CC'},
    },
    'FR_2033_B_c312': {
        'balance': {'zone': 'CD'},
    },
    'FR_2033_B_c316': {
        'balance': {'zone': 'CE'},
    },
    'FR_2033_B_c318': {
        'balance': {'zone': 'CF'},
    },
    'FR_2033_B_c322': {
        'balance': {'zone': 'CG'},
    },
    'FR_2033_B_c324': {
        'balance': {'zone': 'CH'},
    },
    'FR_2033_B_c330': {
        'balance': {'zone': 'CJ'},
    },
    'FR_2033_B_c255': {
        'balance': {'zone': 'CK'},
    },
    'FR_2033_B_c352': {
        'balance': {'zone': 'CM'},
    },
    'FR_2033_B_c356': {
        'balance': {'zone': 'CN'},
    },
    'FR_2033_B_c370': {
        'balance': {'zone': 'CR'},
    },
    'FR_2033_B_c647': {
        'balance': {'zone': 'CX'},
    },
    'FR_2033_B_c648': {
        'balance': {'zone': 'CY'},
    },
    'FR_2033_B_c641': {
        'balance': {'zone': 'CZ'},
    },
    'FR_2033_B_c314': {
        'balance': {'zone': 'ED'},
    },
    'FR_2033_B_c380': {
        'balance': {'zone': 'EE'},
    },
    'FR_2033_B_c342': {
        'balance': {'zone': 'EK'},
    },
    'FR_2033_B_c350': {
        'balance': {'zone': 'EL'},
    },
    'FR_2033_B_c354': {
        'balance': {'zone': 'EM'},
    },
    'FR_2033_B_c360': {
        'balance': {'zone': 'EP'},
    },
    'FR_2033_B_c372': {
        'balance': {'zone': 'ER'},
    },
    'FR_2033_B_c181': {
        'balance': {'zone': 'EU'},
    },
    'FR_2033_B_c127': {
        'balance': {'zone': 'FA'},
    },
    'FR_2033_B_c138': {
        'balance': {'zone': 'FB'},
    },
    'FR_2033_B_c248': {
        'balance': {'zone': 'FJ'},
    },
    'FR_2033_B_c247': {
        'balance': {'zone': 'FK'},
    },
    'FR_2033_B_c346': {
        'balance': {'zone': 'FL'},
    },
    'FR_2033_B_eq_lease': {
        'balance': {'zone': 'GN'},
    },
    'FR_2033_B_c344': {
        'balance': {'zone': 'HL'},
    },
    'FR_2033_B_c986': {
        'balance': {'zone': 'MC'},
    },
    'FR_2033_B_c987': {
        'balance': {'zone': 'MD'},
    },
    'FR_2033_B_c989': {
        'balance': {'zone': 'MF'},
    },
    'FR_2033_B_c345': {
        'balance': {'zone': 'MH'},
    },
}


class L10nFrReports2033BReportHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.2033.b.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = '2033 B Report Handler'

    @api.model
    def _get_code_to_edi_id(self):
        # Used in the fiscal declaration handler to have all the mapper
        return CODE_TO_EDI_ID
