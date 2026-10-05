from odoo import api, models
from odoo.tools import LazyTranslate
from odoo.addons.l10n_fr_reports.utils.fiscal_reports_utils import _add_section, _display_add_section_line, _remove_section, _set_custom_options, _update_aggregation_formulas

_lt = LazyTranslate(__name__)

CODE_TO_EDI_ID = {
    'FR_2033_D_1_I_A_1_S1': {
        'start': {'zone': 'AA'},
        'increase': {'zone': 'BA'},
        'decrease': {'zone': 'DA'},
        'end': {'zone': 'EA'},
    },
    'FR_2033_D_1_I_A_1_S3': {
        'start': {'zone': 'AB'},
        'increase': {'zone': 'BB'},
        'decrease': {'zone': 'CB'},
        'end': {'zone': 'DB'},
    },
    'FR_2033_D_1_I_A_2': {
        'start': {'zone': 'AC'},
        'increase': {'zone': 'BC'},
        'decrease': {'zone': 'CC'},
        'end': {'zone': 'DC'},
    },
    'FR_2033_D_1_I_A_3_S1': {
        'start': {'zone': 'AD'},
        'increase': {'zone': 'BD'},
        'decrease': {'zone': 'CD'},
        'end': {'zone': 'DD'},
    },
    'FR_2033_D_1_I_A_3_S2': {
        'start': {'zone': 'AE'},
        'increase': {'zone': 'BE'},
        'decrease': {'zone': 'CE'},
        'end': {'zone': 'DE'},
    },
    'FR_2033_D_1_I_A_3_S3': {
        'start': {'zone': 'AF'},
        'increase': {'zone': 'BF'},
        'decrease': {'zone': 'CF'},
        'end': {'zone': 'DF'},
    },
    'FR_2033_D_1_I_A_3_S4': {
        'start': {'zone': 'AG'},
        'increase': {'zone': 'BG'},
        'decrease': {'zone': 'CG'},
        'end': {'zone': 'DG'},
    },
    'FR_2033_D_1_I_A_4': {
        'start': {'zone': 'AH'},
        'increase': {'zone': 'BH'},
        'decrease': {'zone': 'CH'},
        'end': {'zone': 'DH'},
    },
    'FR_2033_D_1_I_A_1_S2': {
        'start': {'zone': 'AN'},
        'increase': {'zone': 'BN'},
        'decrease': {'zone': 'CN'},
        'end': {'zone': 'DN'},
    },
    'FR_2033_D_III_398': {
        'balance': {'zone': 'AJ'},
    },
    'FR_2033_D_III_397': {
        'balance': {'zone': 'AK'},
    },
    'FR_2033_D_II_982b': {
        'balance': {'zone': 'AL'},
    },
    'FR_2033_D_II_982t': {
        'balance': {'zone': 'AM'},
    },
    'FR_2033_D_III_381': {
        'balance': {'zone': 'AP'},
    },
    'FR_2033_D_III_374': {
        'balance': {'zone': 'AS'},
    },
    'FR_2033_D_III_378': {
        'balance': {'zone': 'AT'},
    },
    'FR_2033_D_III_399': {
        'balance': {'zone': 'AU'},
    },
    'FR_2033_D_III_381_325': {
        'balance': {'zone': 'AW'},
    },
    'FR_2033_D_III_381_327': {
        'balance': {'zone': 'AX'},
    },
    'FR_2033_D_I_B_1_681': {
        'balance': {'zone': 'AY'},
    },
    'FR_2033_D_I_B_1_683': {
        'balance': {'zone': 'AZ'},
    },
    'FR_2033_D_IV_690': {
    'balance': {'zone': 'DP'},
    },
    'FR_2033_D_IV_691': {
        'balance': {'zone': 'DQ'},
    },
    'FR_2033_D_IV_692': {
        'balance': {'zone': 'DR'},
    },
    'FR_2033_D_IV_693': {
        'balance': {'zone': 'DS'},
    },
    'FR_2033_D_I_B_2_700': {
        'balance': {'zone': 'EA'},
    },
    'FR_2033_D_I_B_3_710': {
        'balance': {'zone': 'EB'},
    },
    'FR_2033_D_I_B_4_720': {
        'balance': {'zone': 'EC'},
    },
    'FR_2033_D_I_B_5_730': {
        'balance': {'zone': 'ED'},
    },
    'FR_2033_D_I_B_6_740': {
        'balance': {'zone': 'EE'},
    },
    'FR_2033_D_I_B_7_750': {
        'balance': {'zone': 'EF'},
    },
    'FR_2033_D_I_B_8_760': {
        'balance': {'zone': 'EG'},
    },
    'FR_2033_D_I_B_9_770': {
        'balance': {'zone': 'EH'},
    },
    'FR_2033_D_I_B_2_705': {
        'balance': {'zone': 'FA'},
    },
    'FR_2033_D_I_B_3_715': {
        'balance': {'zone': 'FB'},
    },
    'FR_2033_D_I_B_4_725': {
        'balance': {'zone': 'FC'},
    },
    'FR_2033_D_I_B_5_735': {
        'balance': {'zone': 'FD'},
    },
    'FR_2033_D_I_B_6_745': {
        'balance': {'zone': 'FE'},
    },
    'FR_2033_D_I_B_7_755': {
        'balance': {'zone': 'FF'},
    },
    'FR_2033_D_I_B_8_765': {
        'balance': {'zone': 'FG'},
    },
    'FR_2033_D_I_B_9_775': {
        'balance': {'zone': 'FH'},
    },
    'FR_2033_D_I_C_compensation_amount': {
        'balance': {'zone': 'GJ', 'tag': 'ftx_1', 'repeatable': True},
    },
    'FR_2033_D_I_C_compensation_amount_static': {
        'balance': {'zone': 'HA'},
    },
    'FR_2033_D_I_C_780': {
        'balance': {'zone': 'HH'},
    },
    'FR_2033_D_I_C_compensation_label': {
        'balance': {'zone': 'HJ', 'repeatable': True},
    },
    'FR_2033_D_II_860': {
        'balance': {'zone': 'MG'},
    },
    'FR_2033_D_II_870': {
        'balance': {'zone': 'MH'},
    },
    'FR_2033_D_II_982': {
        'balance': {'zone': 'PG'},
    },
    'FR_2033_D_II_983': {
        'balance': {'zone': 'PH'},
    },
    'FR_2033_D_II_984': {
        'balance': {'zone': 'PJ'},
    },
}


SECTION_C = 'FR_2033_D_I_C'
SECTIONS = {
    SECTION_C: [
        {'title': _lt("Label"), 'figure_type': 'string', 'default_suffix': 'compensation_label', 'engine': 'external'},
        {'title': _lt("Amount"), 'figure_type': 'monetary', 'default_suffix': 'compensation_amount', 'engine': 'external'},
    ],
}

TOTAL_LINE_CODE = 'FR_2033_D_I_C_780'


class L10nFr2033DReport(models.AbstractModel):
    _name = 'l10n_fr_reports.2033.d.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = "Handler of the 2033 D report"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        _set_custom_options(options=options, name='l10n_fr_reports.2033DLineName')

    def _custom_line_postprocessor(self, report, options, lines):
        codes = {'FR_2033_D_I_C'}
        return _display_add_section_line(report=report, lines=lines, codes=codes, name=self.env._('Add compensation'))

    def action_remove_section(self, options, params):
        parent_line = _remove_section(handler=self, options=options, params=params, exclude_code=[TOTAL_LINE_CODE])

        if total_line := parent_line.children_ids.filtered(lambda child: child.code == TOTAL_LINE_CODE):
            _update_aggregation_formulas(
                parent_line=parent_line,
                total_line=total_line,
                labels=['balance'],
                default_code='_compensation_amount'
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    def action_add_new_section(self, options, params):
        parent_line = _add_section(handler=self, options=options, sections=SECTIONS, params=params, exclude_code=[TOTAL_LINE_CODE])

        if total_line := parent_line.children_ids.filtered(lambda child: child.code == TOTAL_LINE_CODE):
            _update_aggregation_formulas(
                parent_line=parent_line,
                total_line=total_line,
                labels=['balance'],
                default_code='_compensation_amount'
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    @api.model
    def _get_code_to_edi_id(self):
        # Used in the fiscal declaration handler to have all the mapper
        return CODE_TO_EDI_ID
