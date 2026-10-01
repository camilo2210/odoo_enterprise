from odoo import api, models
from odoo.tools import LazyTranslate
from odoo.addons.l10n_fr_reports.utils.fiscal_reports_utils import _add_section, _display_add_section_line, _remove_section, _set_custom_options

_lt = LazyTranslate(__name__)

CODE_TO_EDI_ID = {
    'FR2033G_905_info': {
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
    'FR2033G_905_info_percentage': {
        'balance': {'zone': 'GR', 'repeatable': True},
    },
    'FR2033G_905': {
        'balance': {'zone': 'GT'},
    },
}

SUBSIDIARY = 'FR2033G_905'
SECTIONS = {
    SUBSIDIARY: [
        {'title': _lt("Company Information"), 'figure_type': 'many2one', 'default_suffix': 'info', 'engine': 'reference'},
        {'title': _lt("Ownership Percentage"), 'figure_type': 'percentage', 'default_suffix': 'percentage', 'engine': 'external'},
    ]
}


class L10nFrReport2033GReportHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.2033.g.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = "2033G Subsidiaries and Investments Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        _set_custom_options(options=options, name='l10n_fr_reports.2033GLineName')

    def _custom_line_postprocessor(self, report, options, lines):
        codes = {'FR2033G_905'}
        return _display_add_section_line(report=report, lines=lines, codes=codes, name=self.env._('Add subsidiary'))

    def action_remove_section(self, options, params):
        parent_line = _remove_section(handler=self, options=options, params=params)

        if count_expression := parent_line.expression_ids.filtered(lambda expr: expr.label == 'balance'):
            count_expression.formula = self._count_subsidiaries(parent_line)

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    def action_add_new_section(self, options, params=None):
        parent_line = _add_section(handler=self, options=options, sections=SECTIONS, params=params)

        if count_expression := parent_line.expression_ids.filtered(lambda expr: expr.label == 'balance'):
            count_expression.formula = self._count_subsidiaries(parent_line)

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    @api.model
    def _count_subsidiaries(self, line):
        return len(line.children_ids)

    @api.model
    def _get_code_to_edi_id(self):
        # Used in the fiscal declaration handler to have all the mapper
        return CODE_TO_EDI_ID
