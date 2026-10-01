from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('br', 'account.return.type')
    def _get_br_account_return_type(self):
        return {
            'l10n_br_reports.br_icms_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011003',
                'tax_receivable_account_id': 'account_template_102010802',
            },
            'l10n_br_reports.br_icms_st_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011049',
                'tax_receivable_account_id': 'account_template_102010852',
            },
            'l10n_br_reports.br_irpj_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011066',
                'tax_receivable_account_id': 'account_template_102010870',
            },
            'l10n_br_reports.br_iss_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011064',
                'tax_receivable_account_id': 'account_template_102010868',
            },
            'l10n_br_reports.br_csll_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011062',
                'tax_receivable_account_id': 'account_template_102010866',
            },
            'l10n_br_reports.br_cofins_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011005',
                'tax_receivable_account_id': 'account_template_102010805',
            },
            'l10n_br_reports.br_pis_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011004',
                'tax_receivable_account_id': 'account_template_102010803',
            },
            'l10n_br_reports.br_ipi_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011002',
                'tax_receivable_account_id': 'account_template_102010801',
            },
            'l10n_br_reports.br_ii_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011089',
                'tax_receivable_account_id': 'account_template_102010890',
            },
            'l10n_br_reports.br_inss_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011090',
                'tax_receivable_account_id': 'account_template_102010891',
            },
            'l10n_br_reports.br_is_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011012',
                'tax_receivable_account_id': 'account_template_102010808',
            },
            'l10n_br_reports.br_cbs_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011014',
                'tax_receivable_account_id': 'account_template_102010810',
            },
            'l10n_br_reports.br_ibs_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011015',
                'tax_receivable_account_id': 'account_template_102010811',
            },
            'l10n_br_reports.br_icms_fcp_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011045',
                'tax_receivable_account_id': 'account_template_102010848',
            },
            'l10n_br_reports.br_icms_difal_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011043',
                'tax_receivable_account_id': 'account_template_102010846',
            },
            'l10n_br_reports.br_cprb_tax_return_type': {
                'tax_payable_account_id': 'account_template_202011067',
                'tax_receivable_account_id': 'account_template_102010872',
            },
        }
