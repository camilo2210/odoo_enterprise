# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    l10n_sa_wps_file_reference = fields.Char(string="WPS File Reference", copy=False)
    l10n_sa_total_net_cost = fields.Monetary(compute='_compute_l10n_sa_totals')
    l10n_sa_total_gosi_contribution = fields.Monetary(compute='_compute_l10n_sa_totals')

    _l10n_sa_wps_unique_reference = models.Constraint(
        'UNIQUE(l10n_sa_wps_file_reference)',
        "WPS File reference must be unique",
    )

    @api.depends("slip_ids", "slip_ids.state")
    def _compute_l10n_sa_totals(self):
        sa_payslip_runs = self.filtered(lambda r: r.country_code == "SA")
        (self - sa_payslip_runs).update({
            'l10n_sa_total_net_cost': 0,
            'l10n_sa_total_gosi_contribution': 0,
        })
        sa_payslips = sa_payslip_runs.slip_ids
        line_values = sa_payslips._get_line_values(['NETCOST', 'GOSI_EMP', 'GOSI_COMP'])
        for payslip_run, payslips in sa_payslips.grouped('payslip_run_id').items():
            net_cost, gosi = 0, 0
            for payslip in payslips:
                if payslip.state == 'cancel':
                    continue
                net_cost += line_values['NETCOST'][payslip.id]['total']
                gosi += abs(line_values['GOSI_EMP'][payslip.id]['total']) + abs(line_values['GOSI_COMP'][payslip.id]['total'])
            payslip_run.update({
                'l10n_sa_total_net_cost': net_cost,
                'l10n_sa_total_gosi_contribution': gosi,
            })

    def _l10n_sa_wps_generate_file_reference(self):
        self.ensure_one()
        if not self.l10n_sa_wps_file_reference:
            # Required unique 16 character reference
            self.l10n_sa_wps_file_reference = self.env['ir.sequence'].next_by_code("l10n_sa.wps")
            self.slip_ids.l10n_sa_wps_file_reference = self.l10n_sa_wps_file_reference
        return self.l10n_sa_wps_file_reference

    def action_payment_report(self, export_format='l10n_sa_wps'):
        action = super().action_payment_report()
        if self.company_id.country_code != 'SA':
            return action
        action.update({
            'context': {
                **action['context'],
                'default_export_format': export_format,
            },
        })
        return action
