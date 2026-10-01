import json
from odoo import api, models
from odoo.tools import LazyTranslate
from odoo.addons.l10n_fr_reports.utils.fiscal_reports_utils import _add_section, _display_add_section_line, _remove_section, _set_custom_options

_lt = LazyTranslate(__name__)

CODE_TO_EDI_ID = {
    'l10n_fr_2069_parent_company': {
        'balance': {'zone': 'AD', 'format': 'TBX'},
    },
    'l10n_fr_2069_sme': {
        'balance': {'zone': 'AE', 'format': 'TBX'},
    },
    'l10n_fr_2069_sponsorship_amount': {
        'balance': {'zone': 'AH', 'repeatable': True},
    },
    'l10n_fr_2069_sponsorship_date': {
        'balance': {'zone': 'AL', 'repeatable': True, 'format': '102'},
    },
    'l10n_fr_2069_cice_remuneration_mayotte': {
        'balance': {'zone': 'AM'},
    },
    'l10n_fr_2069_cice_remuneration_topup': {
        'balance': {'zone': 'AN'},
    },
    'l10n_fr_2069_cice_partnership_share': {
        'balance': {'zone': 'AP'},
    },
    'l10n_fr_2069_sponsorship_beneficiary': {
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
            'repeatable': True,
        },
    },
    'l10n_fr_2069_clarification': {
        'balance': {'zone': 'AT', 'tag': 'ftx_1'},
    },
    'l10n_fr_2069_patronage_eu': {
        'balance': {'zone': 'AU'},
    },
    'l10n_fr_2069_cice_prefinanced': {
        'balance': {'zone': 'AV'},
    },
    'l10n_fr_2069_special_cases_first_case_label': {
        'balance': {'zone': 'AW', 'repeatable': True},
    },
    'l10n_fr_2069_special_cases_first_case_value': {
        'balance': {'zone': 'AX', 'repeatable': True},
    },
    'l10n_fr_2069_special_cases_second_case_label': {
        'balance': {'zone': 'AY', 'repeatable': True},
    },
    'l10n_fr_2069_special_cases_second_case_value': {
        'balance': {'zone': 'AZ', 'repeatable': True},
    },
    'l10n_fr_2069_cice': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'CIC'),
        },
    },
    'l10n_fr_2069_patronage': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'MEC'),
        },
    },
    'l10n_fr_2069_manager_training': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'AUT'),
        },
    },
    'l10n_fr_2069_employee_buyout': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'RAC'),
        },
    },
    'l10n_fr_2069_audiovisual_production': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'AUD'),
        },
    },
    'l10n_fr_2069_cinema_production': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'CIN'),
        },
    },
    'l10n_fr_2069_foreign_film': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'CCI'),
        },
    },
    'l10n_fr_2069_live_music': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'CSV'),
        },
    },
    'l10n_fr_2069_tertiary_renovation': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'REB'),
        },
    },
    'l10n_fr_2069_bicycles': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'VEL'),
        },
    },
    'l10n_fr_2069_press_company': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'AUT'),
        },
    },
    'l10n_fr_2069_theater': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'RTD'),
        },
    },
    'l10n_fr_2069_glyphosate_free': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'AUT'),
        },
    },
    'l10n_fr_2069_hve_certification': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'HVE'),
        },
    },
    'l10n_fr_2069_overseas_collectivises': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'COM'),
        },
    },
    'l10n_fr_2069_institutional_housing': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', '2LI'),
        },
    },
    'l10n_fr_2069_green_industry': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', '3IV'),
        },
    },
    'l10n_fr_2069_pam_tz': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'PAM'),
        },
    },
    'l10n_fr_2069_other_non_deferrable': {
        'balance': {
            'zone': 'BB',
            'repeatable': True,
            'pairs_with': ('BA', 'AUT'),
        },
    },
    'l10n_fr_2069_corsica_investment': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'COR'),
        },
    },
    'l10n_fr_2069_research_credit': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'CIR'),
        },
    },
    'l10n_fr_2069_family': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'FAM'),
        },
    },
    'l10n_fr_2069_organic_farming': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'BIO'),
        },
    },
    'l10n_fr_2069_phonographic': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'PHO'),
        },
    },
    'l10n_fr_2069_art_trades': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'ART'),
        },
    },
    'l10n_fr_2069_video_games': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'CJV'),
        },
    },
    'l10n_fr_2069_eco_ptz': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'CPE'),
        },
    },
    'l10n_fr_2069_ptz_plus': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'PTR'),
        },
    },
    'l10n_fr_2069_overseas_housing': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'COL'),
        },
    },
    'l10n_fr_2069_overseas_productive': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'CIO'),
        },
    },
    'l10n_fr_2069_agri_replacement': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'RTA'),
        },
    },
    'l10n_fr_2069_securities_credits': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'PVM'),
        },
    },
    'l10n_fr_2069_collab_research': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'CRC'),
        },
    },
    'l10n_fr_2069_music_publishers': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'EOM'),
        },
    },
    'l10n_fr_2069_zero_interest_loan_mobility': {
        'balance': {
            'zone': 'BD',
            'repeatable': True,
            'pairs_with': ('BC', 'TZM'),
        },
    },
    'l10n_fr_2069_decla_company': {
        'balance': {
            'zone': 'BE',
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
    'l10n_fr_2069_research_dom': {
        'balance': {'zone': 'BK'},
    },
    'l10n_fr_2069_sponsorship_intermediate': {
        'balance': {
            'zone': 'BL',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
            },
            'repeatable': True,
        },
    },
    'l10n_fr_2069_sponsorship_value': {
        'balance': {'zone': 'BN', 'repeatable': True},
    },
    'l10n_fr_2069_patronage_sme_finance': {
        'balance': {'zone': 'BP'},
    },
}

SPECIAL_CASE_FIRST_SECTION = 'l10n_fr_2069_special_cases_first_case'
SPECIAL_CASE_SECOND_SECTION = 'l10n_fr_2069_special_cases_second_case'
SPONSORSHIP_SECTION = 'l10n_fr_2069_sponsorship'


SECTIONS = {
    SPECIAL_CASE_FIRST_SECTION: [
        {'title': _lt("Tax Credit"), 'figure_type': 'string', 'default_suffix': 'label', 'engine': 'external'},
        {'title': _lt("Tax Credit Value"), 'figure_type': 'monetary', 'default_suffix': 'value', 'engine': 'external'},
    ],
    SPECIAL_CASE_SECOND_SECTION: [
        {'title': _lt("Tax Credit"), 'figure_type': 'string', 'default_suffix': 'label', 'engine': 'external'},
        {'title': _lt("Tax Credit Value"), 'figure_type': 'monetary', 'default_suffix': 'value', 'engine': 'external'},
    ],
    SPONSORSHIP_SECTION: [
        {'title': _lt("Donation Amount"), 'figure_type': 'monetary', 'default_suffix': 'amount', 'engine': 'external'},
        {'title': _lt("Payment Date"), 'figure_type': 'date', 'default_suffix': 'date', 'engine': 'external'},
        {'title': _lt("Beneficiary Partner"), 'figure_type': 'many2one', 'default_suffix': 'beneficiary', 'engine': 'reference'},
        {'title': _lt("Intermediate Partner"), 'figure_type': 'many2one', 'default_suffix': 'intermediate', 'engine': 'reference'},
        {'title': _lt("Consideration Value"), 'figure_type': 'monetary', 'default_suffix': 'value', 'engine': 'external'},
    ],
}


class L10nFrReports2069RciReportHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.2069.rci.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = '2069 Rci Report Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        _set_custom_options(options=options, name='l10n_fr_reports.L10nFr2069RciReportLineName')

    def _custom_line_postprocessor(self, report, options, lines):
        selection_options = {
            "APR": self.env._("APR - Apprenticeship Tax Credit"),
            "PTZ": self.env._("PTZ - Tax Credit for First-Time Home Ownership (Standard Zero-Interest Loan)"),
            "BIO": self.env._("BIO - Organic Farming Tax Credit"),
            "ART": self.env._("ART - Artistic Crafts Tax Credit (Métiers d'Art)"),
            "MAI": self.env._("MAI - Master Restaurateur Tax Credit"),
            "PTR": self.env._("PTR - Enhanced Zero-Interest Loan Tax Credit (PTZ+)"),
            "CIR": self.env._("CIR - Research Tax Credit"),
            "CIC": self.env._("CIC - Competitiveness and Employment Tax Credit (CICE)"),
            "CPE": self.env._("CPE - Tax Credit on Repayable Advances for Energy Performance Improvement Works"),
            "HVE": self.env._("HVE - Tax Credit for Agricultural Businesses with High Environmental Value (HVE) Certification"),
            "COM": self.env._("COM - Tax Reduction for Productive Investments in Overseas Collectivities (and New Caledonia)"),
            "CRC": self.env._("CRC - Collaborative Research Tax Credit"),
            "EOM": self.env._("EOM - Tax Credit for Music Publishers"),
            "TZM": self.env._("TZM - Tax Reduction for the Zero-Interest Mobility Loan"),
            "2LI": self.env._("2LI - Tax Claim for Institutional Investors in Intermediate Rental Housing"),
        }

        for line in lines:
            if line.code and any(label in line.code for label in ('first_case_label', 'second_case_label')):
                balance_col_data = next(col_data for col_data in line.columns if col_data.expression_label == 'balance')

                balance_col_data.edit_popup_data = json.dumps({
                    **json.loads(balance_col_data.edit_popup_data or '{}'),
                    'selection_options': selection_options,
                })

        codes = {'l10n_fr_2069_special_cases_first_case', 'l10n_fr_2069_special_cases_second_case', 'l10n_fr_2069_sponsorship'}
        return _display_add_section_line(report=report, lines=lines, codes=codes, name=self.env._('Add new section'))

    def action_remove_section(self, options, params=None):
        _remove_section(handler=self, options=options, params=params)

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    def action_add_new_section(self, options, params=None):
        _add_section(handler=self, options=options, sections=SECTIONS, params=params)

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    @api.model
    def _get_code_to_edi_id(self):
        # Used in the fiscal declaration handler to have all the mapper
        return CODE_TO_EDI_ID
