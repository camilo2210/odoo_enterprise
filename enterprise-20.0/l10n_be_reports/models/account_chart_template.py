# -*- coding: utf-8 -*-
from odoo.addons.account.models.chart_template import template
from odoo import _, models
from odoo.fields import Command


def _account_ref(chart_template, xmlid, code):
    if chart_template.ref(xmlid, raise_if_not_found=False):
        return xmlid
    account_model = chart_template.env['account.account'].sudo().with_company(chart_template.env.company)
    account = account_model.search([
        *account_model._check_company_domain(chart_template.env.company),
        ('code', '=like', f'{code}%'),
    ], limit=1, order='id')
    return account.id or xmlid


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('be_asso', 'res.company')
    def _get_be_asso_reports_res_company(self):
        return self._get_be_reports_res_company()

    @template('be_comp', 'res.company')
    def _get_be_comp_reports_res_company(self):
        return self._get_be_reports_res_company()

    @template('be', 'res.company')
    def _get_be_reports_res_company(self):
        return {
            self.env.company.id: {
                'deferred_expense_account_id': 'a490',
                'deferred_revenue_account_id': 'a493',
            }
        }

    @template('be_asso', 'res.partner')
    def _get_be_asso_reports_res_partner(self):
        return self._get_be_reports_res_partner()

    @template('be_comp', 'res.partner')
    def _get_be_comp_reports_res_partner(self):
        return self._get_be_reports_res_partner()

    @template('be', model='res.partner')
    def _get_be_reports_res_partner(self):
        account_4121 = _account_ref(self, 'a4121', '4121')
        account_4521 = _account_ref(self, 'a4521', '4521')

        return {
            'l10n_be_reports.partner_fps_belgium': {
                'property_account_receivable_id': 'a4112',
                'property_account_payable_id': 'a4512',
            },
            'l10n_be_reports.partner_centre_de_perception_belgium': {
                'property_account_receivable_id': account_4121,
                'property_account_payable_id': account_4521,
            },
        }

    @template(model='account.reconcile.model')
    def _get_be_account_reconcile_model(self, template_code):
        be_recon_models = {}
        if template_code in ['be', 'be_comp', 'be_asso']:
            account_4121 = _account_ref(self, 'a4121', '4121')

            prepayment_communication = self.env['qr.code.payment.wizard']._be_company_vat_communication(self.env.company).replace('+++', '')
            prepayment_collection_partner = self.env.ref('l10n_be_reports.partner_centre_de_perception_belgium', raise_if_not_found=False)
            be_recon_models = {
                'advanced_tax_payment_reco': {
                    'name': _('Advanced Tax Payment'),
                    'trigger': 'auto_reconcile' if prepayment_communication else 'manual',
                    'match_partner_ids': [prepayment_collection_partner.id] if prepayment_collection_partner else [],
                    'match_amount': 'lower',
                    'match_amount_max': 0.0,
                    **({
                        'match_label': 'contains',
                        'match_label_param': prepayment_communication,
                    } if prepayment_communication else {}),
                    'line_ids': [
                        Command.create({
                            'partner_id': prepayment_collection_partner.id if prepayment_collection_partner else False,
                            'account_id': account_4121,
                            'amount_type': 'percentage',
                            'amount_string': '100',
                        }),
                    ],
                },
            }
        return be_recon_models

    @template('be', 'account.return.type')
    def _get_be_account_return_type(self):
        return {
            'l10n_be_reports.be_vat_return_type': {
                'tax_payable_account_id': 'a4512',
                'tax_receivable_account_id': 'a4112',
            },
        }
