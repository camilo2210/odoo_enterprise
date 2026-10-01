# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_compare


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    l10n_be_follow_pay_period = fields.Boolean(
        string="Follow Pay Period",
        compute='_compute_l10n_be_follow_pay_period', store=True, readonly=False,
        help="Define if this amount must be fiscally attached to the fiscal period of this payslip "
             "or to the pay period. Example: benefit in kind must be attached to the pay period.")

    @api.depends('salary_rule_id', 'total', 'slip_id.origin_payslip_id')
    def _compute_l10n_be_follow_pay_period(self):
        """Resolve the attachment its salary rule gives the amount.

        The delta is what the amount adds to what was already declared for it. Outside of a
        correction there is nothing declared yet, so the delta is the amount itself.
        """
        delta_lines = self.filtered(
            lambda line: line.salary_rule_id.l10n_be_follow_pay_period in ['positive', 'negative'])
        corrections = delta_lines.slip_id.filtered('is_correction_payslip')
        declared = {}
        if corrections and delta_lines.mapped('code'):
            declared = corrections.origin_payslip_id._get_line_values(delta_lines.mapped('code'))
        for line in self:
            policy = line.salary_rule_id.l10n_be_follow_pay_period
            if policy in ['always', 'never']:
                line.l10n_be_follow_pay_period = policy == 'always'
                continue
            origin = line.slip_id.origin_payslip_id if line.slip_id.is_correction_payslip else False
            already_declared = declared[line.code][origin.id]['total'] if origin and declared else 0.0
            delta = float_compare(line.total - already_declared, 0, 2)
            line.l10n_be_follow_pay_period = delta > 0 if policy == 'positive' else delta < 0
