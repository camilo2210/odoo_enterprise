from odoo import api, models
from odoo.tools import LazyTranslate
from odoo.addons.l10n_fr_reports.utils.fiscal_reports_utils import _add_section, _display_add_section_line, _remove_section, _set_custom_options, _update_aggregation_formulas

_lt = LazyTranslate(__name__)

CODE_TO_EDI_ID = {
    'l10n_fr_2033_c_i_fonds_commerc': {
        'begin': {'zone': 'AA'},
        'increase': {'zone': 'BA'},
        'decrease': {'zone': 'CA'},
        'end': {'zone': 'DA'},
        'origin': {'zone': 'EA'},
    },
    'l10n_fr_2033_c_i_other_intang': {
        'begin': {'zone': 'AB'},
        'increase': {'zone': 'BB'},
        'decrease': {'zone': 'CB'},
        'end': {'zone': 'DB'},
        'origin': {'zone': 'EB'},
    },
    'l10n_fr_2033_c_i_terrains': {
        'begin': {'zone': 'AC'},
        'increase': {'zone': 'BC'},
        'decrease': {'zone': 'CC'},
        'end': {'zone': 'DC'},
        'origin': {'zone': 'EC'},
    },
    'l10n_fr_2033_c_i_constru': {
        'begin': {'zone': 'AD'},
        'increase': {'zone': 'CD'},
        'decrease': {'zone': 'BD'},
        'end': {'zone': 'DD'},
        'origin': {'zone': 'ED'},
    },
    'l10n_fr_2033_c_i_tmo': {
        'begin': {'zone': 'AE'},
        'increase': {'zone': 'BE'},
        'decrease': {'zone': 'CE'},
        'end': {'zone': 'DE'},
        'origin': {'zone': 'EE'},
    },
    'l10n_fr_2033_c_i_gaa': {
        'begin': {'zone': 'AF'},
        'increase': {'zone': 'BF'},
        'decrease': {'zone': 'CF'},
        'end': {'zone': 'DF'},
        'origin': {'zone': 'EF'},
    },
    'l10n_fr_2033_c_i_transport': {
        'begin': {'zone': 'AG'},
        'increase': {'zone': 'BG'},
        'decrease': {'zone': 'CG'},
        'end': {'zone': 'DG'},
        'origin': {'zone': 'EG'},
    },
    'l10n_fr_2033_c_i_other_tang': {
        'begin': {'zone': 'AH'},
        'increase': {'zone': 'BH'},
        'decrease': {'zone': 'CH'},
        'end': {'zone': 'DH'},
        'origin': {'zone': 'EH'},
    },
    'l10n_fr_2033_c_i_immo_fin': {
        'begin': {'zone': 'AJ'},
        'increase': {'zone': 'BJ'},
        'decrease': {'zone': 'CJ'},
        'end': {'zone': 'DJ'},
        'origin': {'zone': 'EJ'},
    },
    'l10n_fr_2033_c_i_total': {
        'begin': {'zone': 'AK'},
        'increase': {'zone': 'BK'},
        'decrease': {'zone': 'CK'},
        'end': {'zone': 'DK'},
        'origin': {'zone': 'EK'},
    },
    'l10n_fr_2033_c_ii_fonds_commerc': {
        'begin': {'zone': 'AL'},
        'increase': {'zone': 'AM'},
        'decrease': {'zone': 'AN'},
        'end': {'zone': 'AP'},
    },
    'l10n_fr_2033_c_ii_other_intang': {
        'begin': {'zone': 'FA'},
        'increase': {'zone': 'GA'},
        'decrease': {'zone': 'HA'},
        'end': {'zone': 'JA'},
    },
    'l10n_fr_2033_c_ii_terrains': {
        'begin': {'zone': 'FB'},
        'increase': {'zone': 'GB'},
        'decrease': {'zone': 'HB'},
        'end': {'zone': 'JB'},
    },
    'l10n_fr_2033_c_ii_constru': {
        'begin': {'zone': 'FC'},
        'increase': {'zone': 'GC'},
        'decrease': {'zone': 'HC'},
        'end': {'zone': 'JC'},
    },
    'l10n_fr_2033_c_ii_tmo': {
        'begin': {'zone': 'FD'},
        'increase': {'zone': 'GD'},
        'decrease': {'zone': 'HD'},
        'end': {'zone': 'JD'},
    },
    'l10n_fr_2033_c_ii_gaa': {
        'begin': {'zone': 'FE'},
        'increase': {'zone': 'GE'},
        'decrease': {'zone': 'HE'},
        'end': {'zone': 'JE'},
    },
    'l10n_fr_2033_c_ii_transport': {
        'begin': {'zone': 'FF'},
        'increase': {'zone': 'GF'},
        'decrease': {'zone': 'HF'},
        'end': {'zone': 'JF'},
    },
    'l10n_fr_2033_c_ii_other_tang': {
        'begin': {'zone': 'FG'},
        'increase': {'zone': 'GG'},
        'decrease': {'zone': 'HG'},
        'end': {'zone': 'JG'},
    },
    'l10n_fr_2033_c_ii_total': {
        'begin': {'zone': 'FH'},
        'increase': {'zone': 'GH'},
        'decrease': {'zone': 'HH'},
        'end': {'zone': 'JH'},
    },
    'l10n_fr_2033_c_iii_immo_parent_section_line': {
        'nature': {'zone': 'KA', 'tag': 'ftx_1', 'repeatable': True},
        'asset_val': {'zone': 'LA', 'repeatable': True},
        'depreciation': {'zone': 'MA', 'repeatable': True},
        'res_val': {'zone': 'NA', 'repeatable': True},
        'disp_price': {'zone': 'PA', 'repeatable': True},
        'short_term': {'zone': 'QA', 'repeatable': True},
        'lt_19': {'zone': 'SA', 'repeatable': True},
        'lt_15_or_12_8': {'zone': 'UA', 'repeatable': True},
        'lt_0': {'zone': 'TA', 'repeatable': True},
    },
    'l10n_fr_2033_c_iii_total': {
        'asset_val': {'zone': 'LL'},
        'depreciation': {'zone': 'ML'},
        'res_val': {'zone': 'NL'},
        'disp_price': {'zone': 'PL'},
        'short_term': {'zone': 'QL'},
        'lt_19': {'zone': 'SL'},
        'lt_15_or_12_8': {'zone': 'UL'},
        'lt_0': {'zone': 'TL'},
    },
    'l10n_fr_2033_c_iii_579': {
        'res_val': {'zone': 'QP'},
    },
    'l10n_fr_2033_c_iii_regul': {
        'short_term': {'zone': 'QM'},
        'lt_19': {'zone': 'SM'},
        'lt_15_or_12_8': {'zone': 'UM'},
        'lt_0': {'zone': 'TM'},
    },
    'l10n_fr_2033_c_iii_total_apres_regul': {
        'short_term': {'zone': 'QN'},
        'lt_19': {'zone': 'SN'},
        'lt_15_or_12_8': {'zone': 'UN'},
        'lt_0': {'zone': 'TN'},
    },
}


TOTAL_EXPRESSION_LABELS = ['asset_val', 'depreciation', 'res_val', 'disp_price', 'short_term', 'lt_19', 'lt_15_or_12_8', 'lt_0']
TOTAL_LINE_CODE = 'l10n_fr_2033_c_iii_total'

EXPRESSIONS = [
    {'label': 'nature', 'engine': 'external', 'formula': 'most_recent', 'date_scope': 'from_beginning', 'figure_type': 'string', 'subformula': 'editable;rounding=0'},
    {'label': 'asset_val', 'engine': 'external', 'formula': 'most_recent', 'date_scope': 'from_beginning', 'figure_type': 'monetary', 'subformula': 'editable;rounding=0'},
    {'label': 'depreciation', 'engine': 'external', 'formula': 'most_recent', 'date_scope': 'from_beginning', 'figure_type': 'monetary', 'subformula': 'editable;rounding=0'},
    {'label': 'res_val', 'engine': 'aggregation', 'formula': '{default_code}{code_suffix}_dynadded.asset_val - {default_code}{code_suffix}_dynadded.depreciation', 'date_scope': 'from_beginning', 'figure_type': 'monetary'},
    {'label': 'disp_price', 'engine': 'external', 'formula': 'most_recent', 'date_scope': 'from_beginning', 'figure_type': 'monetary', 'subformula': 'editable;rounding=0'},
    {'label': 'short_term', 'engine': 'external', 'formula': 'most_recent', 'date_scope': 'from_beginning', 'figure_type': 'monetary', 'subformula': 'editable;rounding=0'},
    {'label': 'lt_19', 'engine': 'external', 'formula': 'most_recent', 'date_scope': 'from_beginning', 'figure_type': 'monetary', 'subformula': 'editable;rounding=0'},
    {'label': 'lt_15_or_12_8', 'engine': 'external', 'formula': 'most_recent', 'date_scope': 'from_beginning', 'figure_type': 'monetary', 'subformula': 'editable;rounding=0'},
    {'label': 'lt_0', 'engine': 'external', 'formula': 'most_recent', 'date_scope': 'from_beginning', 'figure_type': 'monetary', 'subformula': 'editable;rounding=0'},
]


class L10nFrReport2033CReportHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.2033.c.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = '2033-C Fixed Assets – Depreciation – Capital Gains – Capital Losses'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        _set_custom_options(options=options, name='l10n_fr_reports.2033CLineName')

    def _custom_line_postprocessor(self, report, options, lines):
        codes = {'l10n_fr_2033_c_iii_immo'}
        return _display_add_section_line(report=report, lines=lines, codes=codes, name=self.env._('Add asset'))

    def action_remove_section(self, options, params=None):
        parent_line = _remove_section(handler=self, options=options, params=params, exclude_code=[TOTAL_LINE_CODE])

        if total_line := parent_line.children_ids.filtered(lambda child: child.code == TOTAL_LINE_CODE):
            _update_aggregation_formulas(
                parent_line=parent_line,
                total_line=total_line,
                labels=TOTAL_EXPRESSION_LABELS,
                default_code='l10n_fr_2033_c_iii_immo_parent_section_line_'
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    def action_add_new_section(self, options, params=None):
        parent_line = _add_section(handler=self, options=options, expressions=EXPRESSIONS, params=params, exclude_code=[TOTAL_LINE_CODE])

        if total_line := parent_line.children_ids.filtered(lambda child: child.code == TOTAL_LINE_CODE):
            _update_aggregation_formulas(
                parent_line=parent_line,
                total_line=total_line,
                labels=TOTAL_EXPRESSION_LABELS,
                default_code='l10n_fr_2033_c_iii_immo_parent_section_line_'
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    @api.model
    def _get_code_to_edi_id(self):
        # Used in the fiscal declaration handler to have all the mapper
        return CODE_TO_EDI_ID
