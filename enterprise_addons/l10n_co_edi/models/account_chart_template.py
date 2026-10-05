# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('co', 'account.tax')
    def _get_co_edi_account_tax(self):
        return self._parse_csv('co', 'account.tax', module='l10n_co_edi')

    @template('co', 'account.tax.group')
    def _get_co_edi_account_tax_group(self):
        return self._parse_csv('co', 'account.tax.group', module='l10n_co_edi')

    @template(template='co', model='account.journal', demo=True)
    def _get_co_demo_data_journal(self):
        return {
            'invoice_journal': {
                'name': "DIAN Sales",
                'code': "SETP",
                'type': 'sale',
                'sequence': 1,
                'default_account_id': 'co_puc_420500',
                'l10n_co_edi_dian_authorization_number': "18760000001",
                'l10n_co_edi_dian_authorization_date': fields.Date.to_date("2019-01-19"),
                'l10n_co_edi_dian_authorization_end_date': fields.Date.to_date("2030-01-19"),
                'l10n_co_edi_min_range_number': 990000000,
                'l10n_co_edi_max_range_number': 995000000,
                'l10n_co_edi_technical_key': 'fc8eac422eba16e22ffd8c6f94b3f40a6e38162c',
            },
            'debit_note_journal': {
                'name': "DIAN Debit Notes",
                'code': "ND",
                'type': 'sale',
                'sequence': 2,
                'l10n_co_edi_debit_note': True,
                'default_account_id': 'co_puc_420500',
                'l10n_co_edi_dian_authorization_number': "18760000001",
                'l10n_co_edi_dian_authorization_date': fields.Date.to_date("2019-01-19"),
                'l10n_co_edi_dian_authorization_end_date': fields.Date.to_date("2030-01-19"),
                'l10n_co_edi_min_range_number': 990000000,
                'l10n_co_edi_max_range_number': 995000000,
                'l10n_co_edi_technical_key': 'fc8eac422eba16e22ffd8c6f94b3f40a6e38162c',
            },
            'support_document_journal': {
                'name': "DIAN Support Documents",
                'code': "SEDS",
                'type': 'purchase',
                'sequence': 3,
                'l10n_co_edi_is_support_document': True,
                'default_account_id': 'co_puc_520500',
                'l10n_co_edi_dian_authorization_number': "18760000001",
                'l10n_co_edi_dian_authorization_date': fields.Date.to_date("2019-01-19"),
                'l10n_co_edi_dian_authorization_end_date': fields.Date.to_date("2030-01-19"),
                'l10n_co_edi_min_range_number': 990000000,
                'l10n_co_edi_max_range_number': 995000000,
                'l10n_co_edi_technical_key': 'fc8eac422eba16e22ffd8c6f94b3f40a6e38162c',
            },
        }
