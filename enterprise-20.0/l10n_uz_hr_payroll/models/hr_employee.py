# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_uz_annual_leave_eligibility = fields.Float(related="version_id.l10n_uz_annual_leave_eligibility", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_uz_initial_average_monthly_wage = fields.Monetary(
        related="version_id.l10n_uz_initial_average_monthly_wage",
        string="Initial Average Monthly Wage",
        currency_field="currency_id",
        readonly=True,
        tracking=True,
    )

    def action_open_initial_wage_update_wizard(self):
        self.ensure_one()

        today = fields.Date.context_today(self)
        twelve_months_ago = today - relativedelta(months=12, day=1)

        has_validated_payslips = bool(self.env['hr.payslip'].search_count([
            ('employee_id', '=', self.id),
            ('state', 'in', ('validated', 'paid')),
            ('date_from', '>=', twelve_months_ago),
        ], limit=1))

        if has_validated_payslips:
            raise UserError(self.env._(
                "You cannot adjust the Initial Average Monthly Wage for %s because validated payslips exist within the last 12 months.\n\n"
                "Changing this figure retroactively would alter historical average wage calculations for previously approved payrolls.",
                self.name,
            ))
        return {
            'name': self.env._('Adjust Initial Average Wage'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.uz.average.monthly.wage.update.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_version_id': self.version_id.id,
                'default_new_wage': self.l10n_uz_initial_average_monthly_wage,
            },
        }
