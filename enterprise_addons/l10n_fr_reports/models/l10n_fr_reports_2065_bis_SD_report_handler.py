from odoo import api, models
from odoo.tools import LazyTranslate
from odoo.addons.l10n_fr_reports.utils.fiscal_reports_utils import _add_section, _display_add_section_line, _remove_section, _set_custom_options

_lt = LazyTranslate(__name__)

CODE_TO_EDI_ID = {
    'FR_2065_SD_G_1_A': {
        'balance': {'zone': 'AA'},
    },
    'FR_2065_SD_G_1_B': {
        'balance': {'zone': 'AB'},
    },
    'FR_2065_SD_G_C': {
        'balance': {'zone': 'AC'},
    },
    'FR_2065_SD_G_D': {
        'balance': {'zone': 'AD'},
    },
    'FR_2065_SD_G_2_E_VALUE': {
        'balance': {'zone': 'AE', 'repeatable': True},
    },
    'FR_2065_SD_G_2_F_VALUE': {
        'balance': {'zone': 'AE', 'repeatable': True},
    },
    'FR_2065_SD_G_2_G_VALUE': {
        'balance': {'zone': 'AE', 'repeatable': True},
    },
    'FR_2065_SD_G_2_H_VALUE': {
        'balance': {'zone': 'AE', 'repeatable': True},
    },
    'FR_2065_SD_K_F1': {
        'balance': {'zone': 'AF'},
    },
    'FR_2065_SD_K_F2': {
        'balance': {'zone': 'AG'},
    },
    'FR_2065_SD_J_2_1_F1': {
        'balance': {'zone': 'AH'},
    },
    'FR_2065_SD_G_2_TOTAL': {
        'balance': {'zone': 'AJ'},
    },
    'FR_2065_SD_G_2_I_VALUE': {
        'balance': {'zone': 'AK'},
    },
    'FR_2065_SD_G_2_J_VALUE': {
        'balance': {'zone': 'AL'},
    },
    'FR_2065_SD_J_2_2_F1': {
        'balance': {'zone': 'AM'},
    },
    'FR_2065_SD_J_2_3_F1': {
        'balance': {'zone': 'AN'},
    },
    'FR_2065_SD_J_2_4_F1': {
        'balance': {'zone': 'AP'},
    },
    'FR_2065_SD_J_2_1_F3': {
        'balance': {'zone': 'AQ'},
    },
    'FR_2065_SD_J_2_2_F3': {
        'balance': {'zone': 'AR'},
    },
    'FR_2065_SD_J_2_3_F3': {
        'balance': {'zone': 'AS'},
    },
    'FR_2065_SD_J_2_4_F3': {
        'balance': {'zone': 'AT'},
    },
    'FR_2065_SD_G_2_E_LABEL': {
        'balance': {'zone': 'BE', 'tag': 'ftx_1', 'repeatable': True}
    },
    'FR_2065_SD_G_2_F_LABEL': {
        'balance': {'zone': 'BE', 'tag': 'ftx_1', 'repeatable': True},
    },
    'FR_2065_SD_G_2_G_LABEL': {
        'balance': {'zone': 'BE', 'tag': 'ftx_1', 'repeatable': True},
    },
    'FR_2065_SD_G_2_H_LABEL': {
        'balance': {'zone': 'BE', 'tag': 'ftx_1', 'repeatable': True},
    },
    'FR_2065_SD_H_info_name': {
        'balance': {
            'zone': 'CA',
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
            'repeatable': True,
        },
    },
    'FR_2065_SD_H_sarl_shares': {
        'balance': {'zone': 'CG', 'repeatable': True},
    },
    'FR_2065_SD_H_paid_year': {
        'balance': {'zone': 'CH', 'repeatable': True, 'format': '602'},
    },
    'FR_2065_SD_H_paid_amount_sal': {
        'balance': {'zone': 'CJ', 'repeatable': True},
    },
    'FR_2065_SD_H_paid_amount_repr_lump': {
        'balance': {'zone': 'CK', 'repeatable': True},
    },
    'FR_2065_SD_H_paid_amount_repr_refund': {
        'balance': {'zone': 'CL', 'repeatable': True},
    },
    'FR_2065_SD_H_paid_amount_other_lump': {
        'balance': {'zone': 'CM', 'repeatable': True},
    },
    'FR_2065_SD_H_paid_amount_other_refund': {
        'balance': {'zone': 'CN', 'repeatable': True},
    },
    'FR_2065_SD_I_1': {
        'balance': {
            'zone': 'CV',
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
    'FR_2065_SD_I_2_establishment': {
        'balance': {
            'zone': 'CW',
            'structure': {
                'city': 'city',
                'postal_code': 'zip',
                'street': 'street',
                'complement': 'street2',
            },
            'repeatable': True,
        },
    },
    'FR_2065_SD_J_1_F1': {
        'balance': {'zone': 'CX'},
    },
    'FR_2065_SD_J_1_F2': {
        'balance': {'zone': 'CY'},
    },
    'FR_2065_SD_J_2_1_F2': {
        'balance': {'zone': 'CZ'},
    },
    'FR_2065_SD_J_2_2_F2': {
        'balance': {'zone': 'DA'},
    },
    'FR_2065_SD_J_2_3_F2': {
        'balance': {'zone': 'DB'},
    },
    'FR_2065_SD_J_2_4_F2': {
        'balance': {'zone': 'DC'},
    },
}

REMUNERATION_SECTION = 'FR_2065_SD_H'
ESTABLISHMENT_SECTION = 'FR_2065_SD_I_2'

SECTIONS = {
    REMUNERATION_SECTION: [
        {'title': _lt("Partner"), 'figure_type': 'many2one', 'default_suffix': 'info_name', 'engine': 'reference'},
        {
            'title': _lt("For SARLs"),
            'figure_type': 'parent',
            'default_suffix': 'sarl',
            'children': [
                {'title': _lt("Number of Shares"), 'figure_type': 'integer', 'default_suffix': 'sarl_shares', 'engine': 'external'},
            ],
        },
        {
            'title': _lt("Remuneration paid to each partner during the tax period"),
            'figure_type': 'parent',
            'default_suffix': 'paid',
            'children': [
                {'title': _lt("Remuneration year"), 'figure_type': 'datetime_year', 'default_suffix': 'paid_year', 'engine': 'external'},
                {
                    'title': _lt("Amount of sums paid"),
                    'figure_type': 'parent',
                    'default_suffix': 'paid_amount',
                    'children': [
                        {'title': _lt("As salaries, emoluments and allowances properly speaking"), 'figure_type': 'monetary', 'default_suffix': 'paid_amount_sal', 'engine': 'external'},
                        {
                            'title': _lt("As representation, mission and travel expenses"),
                            'figure_type': 'parent',
                            'default_suffix': 'paid_amount_repr',
                            'children': [
                                {'title': _lt("Lump-sum compensation"), 'figure_type': 'monetary', 'default_suffix': 'paid_amount_repr_lump', 'engine': 'external'},
                                {'title': _lt("Refunds"), 'figure_type': 'monetary', 'default_suffix': 'paid_amount_repr_refund', 'engine': 'external'},
                            ],
                        },
                        {
                            'title': _lt("As other fees"),
                            'figure_type': 'parent',
                            'default_suffix': 'paid_amount_other',
                            'children': [
                                {'title': _lt("Lump-sum compensation"), 'figure_type': 'monetary', 'default_suffix': 'paid_amount_other_lump', 'engine': 'external'},
                                {'title': _lt("Refunds"), 'figure_type': 'monetary', 'default_suffix': 'paid_amount_other_refund', 'engine': 'external'},
                            ],
                        },
                    ],
                }
            ]
        },
    ],
    ESTABLISHMENT_SECTION: [
        {'title': _lt("Establishment"), 'figure_type': 'many2one', 'default_suffix': 'establishment', 'engine': 'reference'},
    ],
}


class L10nFr2065BisSDReport(models.AbstractModel):
    _name = 'l10n_fr_reports.2065_sd.bis.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = "Handler of the 2065-bis-SD report"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        _set_custom_options(options=options, name='l10n_fr_reports.2065SDLineName')

    def _custom_line_postprocessor(self, report, options, lines):
        codes = {REMUNERATION_SECTION, ESTABLISHMENT_SECTION}
        return _display_add_section_line(report=report, lines=lines, codes=codes, name=self.env._('Add section'))

    def action_remove_section(self, options, params):
        _remove_section(handler=self, options=options, params=params)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_add_new_section(self, options, params=None):
        _add_section(handler=self, options=options, sections=SECTIONS, params=params)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def _get_code_to_edi_id(self):
        # Used in the fiscal declaration handler to have all the mapper
        return CODE_TO_EDI_ID
