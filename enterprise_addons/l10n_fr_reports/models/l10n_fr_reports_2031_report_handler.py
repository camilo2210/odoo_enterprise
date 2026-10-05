from odoo import api, models
from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__)

CODE_TO_EDI_ID = {
    'l10n_fr_2031_super_simplified': {
        'balance': {
            'zone': 'AA',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_activities_performed': {
        'balance': {
            'zone': 'AB',
            'tag': 'ftx_1',
        },
    },
    'l10n_fr_2031_assessment_tempory': {
        'balance': {'zone': 'AC'},
    },
    'l10n_fr_2031_vat': {
        'balance': {
            'zone': 'AD',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_share_of_equipment': {
        'balance': {'zone': 'AE'},
    },
    'l10n_fr_2031_short_term_capital_losses': {
        'balance': {'zone': 'AF'},
    },
    'l10n_fr_2031_exemption_bud': {
        'balance': {
            'zone': 'AG',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_non_prof_st_gains_subsidies': {
        'balance': {'zone': 'AL'},
    },
    'l10n_fr_2031_non_prof_st_losses': {
        'balance': {'zone': 'AM'},
    },
    'l10n_fr_2031_pv_ct_short_term_capital_gains': {
        'balance': {'zone': 'AP'},
    },
    'l10n_fr_2031_net_income': {
        'balance': {'zone': 'AQ'},
    },
    'l10n_fr_2031_exemption_priority_dev_zone': {
        'balance': {
            'zone': 'AR',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_tax_compliance_examination': {
        'balance': {
            'zone': 'AT',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_non_prof_deduction_applied': {
        'balance': {'zone': 'AU'},
    },
    'l10n_fr_2031_non_prof_lt_gains_128': {
        'balance': {'zone': 'AV'},
    },
    'l10n_fr_2031_service_provider': {
        'balance': {
            'zone': 'AW',
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
    'l10n_fr_2031_exemption_frr': {
        'balance': {
            'zone': 'AY',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_declarant_capacity_name': {
        'balance': {
            'zone': 'BG',
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
    'l10n_fr_2031_declarant_old_address': {
        'balance': {
            'zone': 'BM',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
            },
        },
    },
    'l10n_fr_2031_person_registered': {
        'balance': {
            'zone': 'BT',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_profit': {
        'balance': {'zone': 'CA'},
    },
    'l10n_fr_2031_loss': {
        'balance': {'zone': 'CB'},
    },
    'l10n_fr_2031_income_exempt': {
        'balance': {'zone': 'CC'},
    },
    'l10n_fr_2031_deducted': {
        'balance': {'zone': 'CD'},
    },
    'l10n_fr_2031_net_exempt_income': {
        'balance': {'zone': 'CE'},
    },
    'l10n_fr_2031_income_subject_tax': {
        'balance': {'zone': 'CF'},
    },
    'l10n_fr_2031_c_plus_d': {
        'balance': {'zone': 'CH'},
    },
    'l10n_fr_2031_total_col_1': {
        'balance': {'zone': 'CJ'},
    },
    'l10n_fr_2031_total_col_2': {
        'balance': {'zone': 'CK'},
    },
    'l10n_fr_2031_taxable_income': {
        'balance': {'zone': 'CL'},
    },
    'l10n_fr_2031_deductible_loss': {
        'balance': {'zone': 'CM'},
    },
    'l10n_fr_2031_pv_lt_128': {
        'balance': {'zone': 'CN'},
    },
    'l10n_fr_2031_pv_part': {
        'balance': {'zone': 'CP'},
    },
    'l10n_fr_2031_deduction_applied_cap_gains_128': {
        'balance': {'zone': 'CQ'},
    },
    'l10n_fr_2031_deduction_applied_professional_profit': {
        'balance': {'zone': 'CR'},
    },
    'l10n_fr_2031_pv_lt_deferred': {
        'balance': {'zone': 'CV'},
    },
    'l10n_fr_2031_non_professional_profit': {
        'balance': {'zone': 'CW'},
    },
    'l10n_fr_2031_non_professional_loss': {
        'balance': {'zone': 'CX'},
    },
    'l10n_fr_2031_accountant_empl': {
        'balance': {'zone': 'DA', 'format': 'TST'},
    },
    'l10n_fr_2031_accountant': {
        'balance': {
            'zone': 'DC',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
                'designation': 'name',
                'designation_1': 'l10n_fr_profession_id.name',
                'mandatory': {'profession'},
            },
        },
    },
    'l10n_fr_2031_council_empl': {
        'balance': {'zone': 'FA', 'format': 'TST'},
    },
    'l10n_fr_2031_council': {
        'balance': {
            'zone': 'FC',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
                'designation': 'name',
                'designation_1': 'l10n_fr_profession_id.name',
                'mandatory': {'profession'},
            },
        },
    },
    'l10n_fr_2031_exemption_new_business': {
        'balance': {
            'zone': 'JA',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_exemption_zfu': {
        'balance': {
            'zone': 'JB',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_partnership_tax_regime': {
        'balance': {'zone': 'JK'},
    },
    'l10n_fr_2031_exemption_other_devices': {
        'balance': {
            'zone': 'JL',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_pv_ct_lt_exo': {
        'balance': {'zone': 'KG'},
    },
    'l10n_fr_2031_exemption_jei': {
        'balance': {
            'zone': 'KK',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_pv_lt_long_term_capital_gains': {
        'balance': {'zone': 'KM'},
    },
    'l10n_fr_2031_exemption_zfa_new_gen': {
        'balance': {
            'zone': 'KQ',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_exemption_defense_restructuring': {
        'balance': {
            'zone': 'KR',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_exemption_zrr': {
        'balance': {
            'zone': 'KX',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_tonnage': {
        'balance': {
            'zone': 'KY',
            'format': 'TBX',
        },
    },
    'l10n_fr_2031_option_overseas_tax_credit': {
        'balance': {
            'zone': 'KZ',
            'format': 'TBX',
        },
    },
}


class L10nFrReports2031ReportHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.2031.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = '2031 Report Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        options['ignore_totals_below_sections'] = True

    @api.model
    def _get_code_to_edi_id(self):
        # Used in the fiscal declaration handler to have all the mapper
        return CODE_TO_EDI_ID
