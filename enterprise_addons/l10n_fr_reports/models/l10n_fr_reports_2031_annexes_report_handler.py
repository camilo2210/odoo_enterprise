from odoo import api, models
from odoo.tools import LazyTranslate
from odoo.addons.l10n_fr_reports.utils.fiscal_reports_utils import _add_section, _display_add_section_line, _remove_section, _set_custom_options

_lt = LazyTranslate(__name__)

CODE_TO_EDI_ID = {
    'l10n_fr_2031_annexes_partner_legal_partner': {
        'balance': {
            'zone': 'AA',
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
    'l10n_fr_2031_annexes_i_lease_management_profit': {
        'balance': {'zone': 'AB'},
    },
    'l10n_fr_2031_annexes_i_lease_management_loss': {
        'balance': {'zone': 'AC'},
    },
    'l10n_fr_2031_annexes_i_other_furnished_profit': {
        'balance': {'zone': 'AD'},
    },
    'l10n_fr_2031_annexes_i_furnished_social_profit': {
        'balance': {'zone': 'AE'},
    },
    'l10n_fr_2031_annexes_i_furnished_social_loss': {
        'balance': {'zone': 'AF'},
    },
    'l10n_fr_2031_annexes_partner_legal_share_pl': {
        'balance': {'zone': 'AH', 'repeatable': True},
    },
    'l10n_fr_2031_annexes_partner_legal_share_gains': {
        'balance': {'zone': 'AJ', 'repeatable': True},
    },
    'l10n_fr_2031_annexes_i_other_furnished_loss': {
        'balance': {'zone': 'AL'},
    },
    'l10n_fr_2031_annexes_partner_natural_share_pl_pro': {
        'balance': {'zone': 'AP', 'repeatable': True},
    },
    'l10n_fr_2031_annexes_partner_natural_share_pl_non_pro': {
        'balance': {'zone': 'AQ', 'repeatable': True},
    },
    'l10n_fr_2031_annexes_partner_natural_gains': {
        'balance': {'zone': 'AR', 'repeatable': True},
    },
    'l10n_fr_2031_annexes_partner_natural_birth_date': {
        'balance': {
            'zone': 'AU',
            'repeatable': True,
            'format': '102',
        },
    },
    'l10n_fr_2031_annexes_partner_natural_birth': {
        'balance': {
            'zone': 'AV',
            'depends': {
                'l10n_fr_2031_annexes_partner_natural_birth_city': ['address', 'city'],
                'l10n_fr_2031_annexes_partner_natural_birth_country': ['address', 'country_code'],
                'l10n_fr_2031_annexes_partner_natural_birth_dep': ['address', 'postal_code'],
            },
            'repeatable': True,
        },
    },
    'l10n_fr_2031_annexes_partner_natural_partner': {
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
            'repeatable': True,
        },
    },
    'l10n_fr_2031_annexes_partner_natural_manager': {
        'balance': {
            'zone': 'AX',
            'format': 'TBX',
            'repeatable': True,
        },
    },
    'l10n_fr_2031_annexes_overhead_costs_gifts': {
        'balance': {'zone': 'BF'},
    },
    'l10n_fr_2031_annexes_overhead_costs_reception': {
        'balance': {'zone': 'BG'},
    },
    'l10n_fr_2031_annexes_scs_distributed_profits': {
        'balance': {'zone': 'EC'},
    },
    'l10n_fr_2031_annexes_other_establishments_addresses_establishment': {
        'balance': {
            'zone': 'FA',
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
    'l10n_fr_2031_annexes_fund_owner_info': {
        'balance': {
            'zone': 'GA',
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
    'l10n_fr_2031_annexes_h_gross_wages': {
        'balance': {'zone': 'HA'},
    },
    'l10n_fr_2031_annexes_h_fees_reversals': {
        'balance': {'zone': 'HB'},
    },
    'l10n_fr_2031_annexes_h_personal_drawings': {
        'balance': {'zone': 'HC'},
    },
    'l10n_fr_2031_annexes_h_capital_contributions': {
        'balance': {'zone': 'HD'},
    },
    'l10n_fr_2031_annexes_h_tax_free_capital_gains_nature': {
        'balance': {'zone': 'KA', 'tag': 'ftx_1'},
    },
    'l10n_fr_2031_annexes_h_tax_free_capital_gains_reevalued': {
        'balance': {'zone': 'KB', 'repeatable': True},
    },
    'l10n_fr_2031_annexes_h_tax_free_capital_gains_acquisition': {
        'balance': {'zone': 'KC', 'repeatable': True},
    },
    'l10n_fr_2031_annexes_h_tax_free_capital_gains_gain': {
        'balance': {'zone': 'KD', 'repeatable': True},
    },
    'l10n_fr_2031_annexes_i_racehorse_profit': {
        'balance': {'zone': 'SA'},
    },
    'l10n_fr_2031_annexes_i_other_non_prof_profit': {
        'balance': {'zone': 'SB'},
    },
    'l10n_fr_2031_annexes_i_total_profit_to_7a': {
        'balance': {'zone': 'SC'},
    },
    'l10n_fr_2031_annexes_i_racehorse_loss': {
        'balance': {'zone': 'TA'},
    },
    'l10n_fr_2031_annexes_i_other_non_prof_loss': {
        'balance': {'zone': 'TB'},
    },
    'l10n_fr_2031_annexes_i_total_loss_to_7b': {
        'balance': {'zone': 'TC'},
    },
}

SECTION_E_NATURAL = 'l10n_fr_2031_annexes_partner_natural'
SECTION_E_LEGAL = 'l10n_fr_2031_annexes_partner_legal'
SECTION_G = 'l10n_fr_2031_annexes_other_establishments_addresses'
SECTION_H = 'l10n_fr_2031_annexes_h_tax_free_capital_gains'

SECTIONS = {
    SECTION_E_NATURAL: [
        {'title': _lt("Partner"), 'figure_type': 'many2one', 'default_suffix': 'partner', 'engine': 'reference'},
        {
            'title': _lt("Birth address"),
            'figure_type': 'parent',
            'default_suffix': 'birth',
            'children': [
                {"title": _lt("Birth Postal Code"), 'figure_type': 'string', 'default_suffix': 'birth_dep', 'engine': 'external'},
                {"title": _lt("Birth City"), 'figure_type': 'string', 'default_suffix': 'birth_city', 'engine': 'external'},
                {"title": _lt("Birth Country"), 'figure_type': 'many2one', 'default_suffix': 'birth_country', 'engine': 'reference', 'formula': 'res.country'},
            ],
        },
        {'title': _lt("Birth Date"), 'figure_type': 'date', 'default_suffix': 'birth_date', 'engine': 'external'},
        {'title': _lt("Manager Status"), 'figure_type': 'boolean', 'default_suffix': 'manager', 'engine': 'external'},
        {'title': _lt("Share Professional Profit/Loss"), 'figure_type': 'monetary', 'default_suffix': 'share_pl_pro', 'engine': 'external'},
        {'title': _lt("Share Non-Professional Profit/Loss"), 'figure_type': 'monetary', 'default_suffix': 'share_pl_non_pro', 'engine': 'external'},
        {'title': _lt("Share Capital Gains"), 'figure_type': 'monetary', 'default_suffix': 'share_gains', 'engine': 'external'},
    ],
    SECTION_E_LEGAL: [
        {'title': _lt("Partner"), 'figure_type': 'many2one', 'default_suffix': 'partner', 'engine': 'reference'},
        {'title': _lt("Share Profit/Loss"), 'figure_type': 'monetary', 'default_suffix': 'share_pl', 'engine': 'external'},
        {'title': _lt("Share Capital Gains"), 'figure_type': 'monetary', 'default_suffix': 'share_gains', 'engine': 'external'},
    ],
    SECTION_G: [
        {'title': _lt("Establishment"), 'figure_type': 'many2one', 'default_suffix': 'establishment', 'engine': 'reference'},
    ],
    SECTION_H: [
        {'title': _lt("Asset Nature"), 'figure_type': 'string', 'default_suffix': 'nature', 'engine': 'external'},
        {'title': _lt("Revalued Value"), 'figure_type': 'monetary', 'default_suffix': 'reevalued', 'engine': 'external'},
        {'title': _lt("Acquisition Price"), 'figure_type': 'monetary', 'default_suffix': 'acquisition', 'engine': 'external'},
        {'title': _lt("Capital Gain"), 'figure_type': 'monetary', 'default_suffix': 'gain', 'engine': 'external'},
    ],
}


class L10nFrReports2031AnnexesReportHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.2031.annexes.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = '2031 Report Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        _set_custom_options(options=options, name='l10n_fr_reports.2031LineName')

    def _custom_line_postprocessor(self, report, options, lines):
        codes = {'l10n_fr_2031_annexes_partner_natural', 'l10n_fr_2031_annexes_partner_legal', 'l10n_fr_2031_annexes_h_tax_free_capital_gains', 'l10n_fr_2031_annexes_other_establishments_addresses'}
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
