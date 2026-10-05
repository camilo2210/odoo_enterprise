# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    l10n_au_total_super_contributions = fields.Float(compute="_compute_l10n_au_totals", string="Super Contributions")
    l10n_au_total_withholding_tax = fields.Float(compute="_compute_l10n_au_totals", string="Tax Withholding")

    @api.depends('slip_ids', 'slip_ids.state')
    def _compute_l10n_au_totals(self):
        au_payruns = self.filtered(lambda r: r.country_code == 'AU')
        (self - au_payruns).update({'l10n_au_total_super_contributions': 0.0, 'l10n_au_total_withholding_tax': 0.0})
        for payrun in au_payruns:
            not_cancelled_slips = payrun.slip_ids.filtered(lambda p: p.state != 'cancel')
            payrun.l10n_au_total_super_contributions = sum(not_cancelled_slips.mapped('l10n_au_super_contributions'))
            payrun.l10n_au_total_withholding_tax = sum(not_cancelled_slips.mapped('l10n_au_withholding_tax'))
