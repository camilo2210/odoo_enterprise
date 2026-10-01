# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    def _compute_amount(self):
        id_ot_entries = self.filtered(
            lambda wd: wd.payslip_id.struct_id.country_id.code == 'ID'
            and wd.code in {'OVERTIMEID1', 'OVERTIMEID2'}
        )
        for worked_days in id_ot_entries:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state != 'draft':
                continue
            if not worked_days.version_id or not worked_days.is_paid:
                worked_days.amount = 0
                continue
            if worked_days.version_id.wage_type == 'hourly':
                ot_hourly_rate = worked_days.version_id._get_contract_wage()
            else:
                # Indonesian Labor Law (PP No. 35/2021) requires the hourly overtime rate
                # to be calculated using a fixed monthly divisor (statutory 173 hours)
                # rather than the actual working hours of the specific month.
                monthly_working_hours = worked_days.payslip_id._rule_parameter('l10n_id_statutory_working_hours')
                ot_hourly_rate = worked_days.version_id._get_contract_wage() / monthly_working_hours
            worked_days.amount = ot_hourly_rate * worked_days.number_of_hours * worked_days.work_entry_type_id.amount_rate

        return super(HrPayslipWorkedDays, self - id_ot_entries)._compute_amount()
