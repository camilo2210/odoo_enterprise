# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class DigestDigest(models.Model):
    _inherit = 'digest.digest'

    kpi_account_bank_cash = fields.Boolean('Bank & Cash Moves')
    kpi_account_bank_cash_value = fields.Monetary(compute='_compute_kpi_account_total_bank_cash_value')

    def _compute_kpi_account_total_bank_cash_value(self):
        self._raise_if_not_member_of('account.group_account_user')

        start, end, companies = self._get_kpi_compute_parameters()
        data = self.env['account.move']._read_group([
            ('date', '>=', start),
            ('date', '<', end),
            ('journal_id.type', 'in', ('cash', 'bank')),
            ('company_id', 'in', companies.ids),
        ], ['company_id'], ['amount_total:sum'])
        data = dict(data)

        for record in self:
            company = record.company_id or self.env.company
            record.kpi_account_bank_cash_value = data.get(company)

    def _get_kpi_custom_settings(self, company, user):
        res = super()._get_kpi_custom_settings(company, user)
        menu_id = self.env.ref('account.menu_finance').id
        res['kpi_action']['kpi_account_bank_cash'] = f'account.open_account_journal_dashboard_kanban?menu_id={menu_id}'
        res['kpi_sequence']['kpi_account_bank_cash'] = 5550
        return res
