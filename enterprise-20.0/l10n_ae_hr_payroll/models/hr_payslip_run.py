# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    l10n_ae_total_net_cost = fields.Monetary(compute="_compute_payrun_cost")
    l10n_ae_total_static_allowance = fields.Monetary(compute="_compute_payrun_cost")
    l10n_ae_total_variable_allowance = fields.Monetary(compute="_compute_payrun_cost")

    def _compute_payrun_cost(self):
        for payslip_run in self:
            payslip_run.l10n_ae_total_net_cost = sum(payslip_run.slip_ids.filtered(lambda p: p.state != 'cancel').line_ids.filtered(lambda l: l.code == 'NETCOST').mapped('total'))
            payslip_run.l10n_ae_total_static_allowance = sum(payslip_run.slip_ids.filtered(lambda p: p.state != 'cancel').line_ids.filtered(lambda l: 'STATICALW' in l.category_ids.mapped('code') or 'BASIC' in l.category_ids.mapped('code')).mapped('total'))
            payslip_run.l10n_ae_total_variable_allowance = sum(payslip_run.slip_ids.filtered(lambda p: p.state != 'cancel').line_ids.filtered(lambda l: 'VARIABLEALW' in l.category_ids.mapped('code')).mapped('total'))

    def action_payment_report(self, export_format='l10n_ae_wps'):
        action = super().action_payment_report()
        if self.company_id.country_code != 'AE':
            return action
        action.update({
            'context': {
                **action['context'],
                'default_export_format': export_format,
            },
        })
        return action
