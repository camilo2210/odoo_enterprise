from odoo import api, models
from odoo.tools import LazyTranslate
from odoo.addons.l10n_fr_reports.utils.fiscal_reports_utils import _add_section, _display_add_section_line, _remove_section, _set_custom_options

_lt = LazyTranslate(__name__)

CODE_TO_EDI_ID = {
    'FR_2033_F_capital_held_individuals_info': {
        'balance': {
            'zone': 'BA',
            'structure': {
                'city': 'city',
                'country_code': 'country_code',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
                'designation': 'name',
            },
            'repeatable': True,
        },
    },
    'FR_2033_F_capital_held_individuals_shares': {
        'balance': {'zone': 'BD', 'repeatable': True},
    },
    'FR_2033_F_capital_held_individuals_birth_date': {
        'balance': {'zone': 'BE', 'format': '102', 'repeatable': True},
    },
    'FR_2033_F_capital_held_individuals_birth': {
        'balance': {
            'zone': 'BG',
            'depends': {
                'FR_2033_F_capital_held_individuals_birth_city': ['address', 'city'],
                'FR_2033_F_capital_held_individuals_birth_country': ['address', 'country_code'],
                'FR_2033_F_capital_held_individuals_birth_dep': ['address', 'postal_code'],
            },
            'repeatable': True,
        },
    },
    'FR_2033_F_capital_held_individuals_percentage': {
        'balance': {'zone': 'BR', 'repeatable': True},
    },
    'FR_2033_F_capital_held_legal_entities_info': {
        'balance': {
            'zone': 'GA',
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
    'FR_2033_F_capital_held_legal_entities_shares': {
        'balance': {'zone': 'GD', 'repeatable': True},
    },
    'FR_2033_F_capital_held_legal_entities_percentage': {
        'balance': {'zone': 'GR', 'repeatable': True},
    },
    'FR_2033_F_901': {
        'balance': {'zone': 'GT'},
    },
    'FR_2033_F_902': {
        'balance': {'zone': 'GU'},
    },
    'FR_2033_F_903': {
        'balance': {'zone': 'GV'},
    },
    'FR_2033_F_904': {
        'balance': {'zone': 'GW'},
    },
    'FR_2033_F_905': {
        'balance': {'zone': 'GX'},
    },
    'FR_2033_F_906': {
        'balance': {'zone': 'GY'},
    },
}

LEGAL_ENTITIES_FIELDS = 'FR_2033_F_capital_held_legal_entities'
INDIVIDUAL_FIELDS = 'FR_2033_F_capital_held_individuals'

SECTIONS = {
    LEGAL_ENTITIES_FIELDS: [
        {'title': _lt("Company Information"), 'figure_type': 'many2one', 'default_suffix': 'info', 'engine': 'reference'},
        {'title': _lt("Ownership Percentage"), 'figure_type': 'percentage', 'default_suffix': 'percentage', 'engine': 'external'},
        {'title': _lt("Number of Shares"), 'figure_type': 'integer', 'default_suffix': 'shares', 'engine': 'external'},
    ],
    INDIVIDUAL_FIELDS: [
        {'title': _lt("Individual infos"), 'figure_type': 'many2one', 'default_suffix': 'info', 'engine': 'reference'},
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
        {'title': _lt("Ownership Percentage"), 'figure_type': 'percentage', 'default_suffix': 'percentage', 'engine': 'external'},
        {'title': _lt("Number of Shares"), 'figure_type': 'integer', 'default_suffix': 'shares', 'engine': 'external'},
    ],
}


class L10nFrReports2033FReportHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.2033.f.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = '2033 F Report Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        _set_custom_options(options=options, name='l10n_fr_reports.2033FLineName')

    def _custom_line_postprocessor(self, report, options, lines):
        codes = {'FR_2033_F_capital_held_legal_entities', 'FR_2033_F_capital_held_individuals'}
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
