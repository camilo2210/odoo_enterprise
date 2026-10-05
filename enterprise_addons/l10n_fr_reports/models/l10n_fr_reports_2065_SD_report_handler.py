from odoo import api, models


CODE_TO_EDI_ID = {
    'FR_2065_SD_A_F3': {
        'balance': {
            'zone': 'AC',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
            },
        },
    },
    'FR_2065_SD_C_3_F6': {
        'balance': {
            'zone': 'AF',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_A_F4': {
        'balance': {
            'zone': 'AK',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
            },
        },
    },
    'FR_2065_SD_C_1_F5': {
        'balance': {'zone': 'AL'},
    },
    'FR_2065_SD_C_3_F10': {
        'balance': {
            'zone': 'AM',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_B_F2': {
        'balance': {
            'zone': 'AP',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_B_F1': {
        'balance': {'zone': 'AQ', 'tag': 'ftx_1'},
    },
    'FR_2065_SD_F_F1': {
        'balance': {'zone': 'AR', 'format': 'TBX'},
    },
    'FR_2065_SD_A_F1': {
        'balance': {
            'zone': 'AS',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
                'designation': 'name',
                'identifier': {
                    'number': 'l10n_fr_siret',
                    'is_siren': True,
                },
                'mandatory': {'identifier'},
            },
        },
    },
    'FR_2065_SD_C_1_F2': {
        'balance': {'zone': 'AT'},
    },
    'FR_2065_SD_C_2_F3': {
        'balance': {'zone': 'AU'},
    },
    'FR_2065_SD_C_3_F8': {
        'balance': {
            'zone': 'AW',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_C_3_F1': {
        'balance': {
            'zone': 'AX',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_C_3_F11': {
        'balance': {
            'zone': 'BA',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_C_3_F13': {
        'balance': {'zone': 'BB'},
    },
    'FR_2065_SD_D_F1': {
        'balance': {'zone': 'BE'},
    },
    'FR_2065_SD_D_F2': {
        'balance': {'zone': 'BF'},
    },
    'FR_2065_SD_F_F2_1': {
        'balance': {'zone': 'BN', 'format': 'TST'},
    },
    'FR_2065_SD_F_F3_1': {
        'balance': {'zone': 'BQ', 'format': 'TST'},
    },
    'FR_2065_SD_C_3_F4': {
        'balance': {
            'zone': 'BY',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_F_F2': {
        'balance': {
            'zone': 'CA',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
                'designation': 'name',
            },
        },
    },
    'FR_2065_SD_F_F3': {
        'balance': {
            'zone': 'EA',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
                'designation': 'name',
            },
        },
    },
    'FR_2065_SD_C_1_F1': {
        'balance': {'zone': 'HA'},
    },
    'FR_2065_SD_C_3_F7': {
        'balance': {
            'zone': 'HD',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_C_3_F12': {
        'balance': {
            'zone': 'HJ',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_E_F1': {
        'balance': {'zone': 'JA'},
    },
    'FR_2065_SD_C_1_F3': {
        'balance': {'zone': 'LC'},
    },
    'FR_2065_SD_C_3_F9': {
        'balance': {
            'zone': 'LL',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_C_2_F2': {
        'balance': {'zone': 'LN'},
    },
    'FR_2065_SD_C_3_F2': {
        'balance': {
            'zone': 'LQ',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_C_2_F1': {
        'balance': {'zone': 'LT'},
    },
    'FR_2065_SD_C_3_F14': {
        'balance': {'zone': 'LV'},
    },
    'FR_2065_SD_C_2_F4': {
        'balance': {'zone': 'LW'},
    },
    'FR_2065_SD_C_2_F5': {
        'balance': {'zone': 'LX'},
    },
    'FR_2065_SD_C_3_F5': {
        'balance': {
            'zone': 'LY',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_C_3_F3': {
        'balance': {
            'zone': 'MA',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_A_1_F1': {
        'balance': {'zone': 'PA', 'format': '102'},
    },
    'FR_2065_SD_A_1_1': {
        'balance': {
            'zone': 'PD',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
                'designation': 'name',
                'designation_2': 'name',
                'identifier': {'number': 'l10n_fr_siret'},
                'mandatory': {'identifier'},
            },
        },
    },
    'FR_2065_SD_F5': {
        'balance': {
            'zone': 'PE',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_C_4_F1': {
        'balance': {
            'zone': 'PF',
            'format': 'TBX',
        },
    },
    'FR_2065_SD_F4': {
        'balance': {
            'zone': 'PH',
            'format': 'TBX',
        },
    },
}


class L10nFr2065SDReport(models.AbstractModel):
    _name = 'l10n_fr_reports.2065_sd.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = "Handler of the 2065-SD report"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        options['ignore_totals_below_sections'] = True

    @api.model
    def _get_code_to_edi_id(self):
        # Used in the fiscal declaration handler to have all the mapper
        return CODE_TO_EDI_ID
