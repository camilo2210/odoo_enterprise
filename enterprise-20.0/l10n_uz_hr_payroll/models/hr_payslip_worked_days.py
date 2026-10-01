# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    def _compute_amount(self):
        """
        All work entries except the annual labor leave are computed as normal, using the scheduled working days.
        The rate for the annual labor leaves is based on the average daily wage computed from the last 12 months.
        """

        annual_leave_lines = self.env['hr.payslip.worked_days']
        regular_lines = self.env['hr.payslip.worked_days']

        for wd in self:
            company = wd.payslip_id.company_id
            if company.country_id.code == 'UZ' and wd.work_entry_type_id == company.l10n_uz_annual_leave_work_entry_type_id:
                annual_leave_lines |= wd
            else:
                regular_lines |= wd

        super(HrPayslipWorkedDays, regular_lines)._compute_amount()

        for wd in annual_leave_lines:
            if wd.payslip_id.edited or wd.payslip_id.state != 'draft':
                continue
            if not wd.is_paid:
                wd.amount = 0.0
                continue
            wd.amount = wd.payslip_id.l10n_uz_average_daily_wage * wd.number_of_days
