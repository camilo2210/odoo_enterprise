# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_id_fixed_allowance = fields.Monetary(readonly=False, related="version_id.l10n_id_fixed_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_id_payroll_type = fields.Selection(readonly=False, related="version_id.l10n_id_payroll_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_id_bpjs_jkk = fields.Float(
        readonly=False,
        related="version_id.l10n_id_bpjs_jkk",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_id_kode_ptkp = fields.Selection(
        readonly=False,
        related="version_id.l10n_id_kode_ptkp",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )

    def l10n_id_action_view_historical_lines(self):
        """ As the historical payslip line values of 'GROSS', 'PPH21', 'JHT', and 'JP' is used to calculate
        for the end of year/contract payment, HR team likes to cross-check the values manually

        Show all payslip lines that are in validated/paid for code: 'GROSS', 'PPH21', 'JHT', or 'JP'"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Historical Payslip Lines"),
            'res_model': 'hr.payslip.line',
            'view_mode': 'list,form',
            'domain': [
                ('version_id', '=', self.version_id.id),
                ('slip_id.state', 'in', ['validated', 'paid']),
                ('code', 'in', ('GROSS', 'PPH21', 'JHT', 'JP')),
            ],
            'context': {'search_default_category_ids': 1},
            'search_view_id': [self.env.ref('hr_payroll.hr_payslip_line_view_search_report').id, 'search'],
            'views': [
                (self.env.ref('l10n_id_hr_payroll.hr_payslip_line_view_tree_id_history').id, 'list'),
                (False, 'form'),
            ],
        }
