# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_payslip_done(self):
        # Override. A US payslip without payment date is computed on its closing date, keep that date as the payment one.
        for payslip in self.filtered(lambda p: p.country_code == 'US' and not p.paid_date):
            payslip.paid_date = payslip.date_to
        return super().action_payslip_done()

    @api.model
    def _issues_dependencies(self):
        # Override. The missing payment date warning has to follow the field.
        return super()._issues_dependencies() + ['paid_date']

    def _get_ytd_reference_date(self):
        # Override. US calculate payslips based on paid_date, falling back on the period closing date.
        self.ensure_one()
        if self.country_code == 'US' and self.paid_date:
            return self.paid_date
        return super()._get_ytd_reference_date()

    def _get_ytd_date_field(self):
        # Override.
        if self and all(payslip.country_code == 'US' for payslip in self):
            return 'paid_date'
        return super()._get_ytd_date_field()

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_us_hr_payroll', [
                'data/hr_salary_rule_category_data.xml',
                'data/hr_payroll_structure_type_data.xml',
                'data/hr_payroll_structure_data.xml',
                'data/hr_rule_parameters_data.xml',
                'data/res_partner_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]

    def _get_leaves_duration_between_two_dates(self, date_from, date_to):
        self.ensure_one()
        date_from += relativedelta(hour=0, minute=0, second=0)
        date_to += relativedelta(hour=23, minute=59, second=59)
        work_entries_vals = self.employee_id.version_ids.generate_work_entries(date_from.date(), date_to.date())

        entries_by_work_entry_type = defaultdict(list)
        for vals in work_entries_vals:
            if not vals.get('leave_ids'):
                continue
            leave = vals['leave_ids']
            entries_by_work_entry_type[leave.work_entry_type_id].append(vals)

        durations_by_work_entry_type = {}
        for work_entry_type, work_entries_vals in entries_by_work_entry_type.items():
            durations_by_work_entry_type[work_entry_type] = sum(vals['duration'] for vals in work_entries_vals)
        return durations_by_work_entry_type

    def _l10n_us_get_leave_lines(self):
        self.ensure_one()
        leaves_allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<', self.date_to),
            '|',
            ('date_to', '=', False),
            ('date_to', '>', self.date_from),
        ])
        if not leaves_allocations:
            return []

        day_before_period = self.date_from + relativedelta(days=-1)
        before_period_durations_by_work_entry_type = self._get_leaves_duration_between_two_dates(
            min(leaves_allocations.mapped('date_from')), day_before_period)
        period_durations_by_work_entry_type = self._get_leaves_duration_between_two_dates(
            self.date_from, self.date_to)

        # Only get the leave types associated to valid allocations
        work_entry_types = leaves_allocations.work_entry_type_id
        leave_lines = []
        for work_entry_type in work_entry_types.filtered(lambda h: h.l10n_us_show_on_payslip):
            related_allocations = leaves_allocations.filtered(lambda a: a.work_entry_type_id == work_entry_type)

            allocated_before = related_allocations._l10n_us_get_total_allocated(day_before_period)
            allocated_now = related_allocations._l10n_us_get_total_allocated(self.date_to)

            total_used_before = before_period_durations_by_work_entry_type.get(work_entry_type, 0.0)
            used = period_durations_by_work_entry_type.get(work_entry_type, 0.0)

            gain = allocated_now - allocated_before
            balance = allocated_now - total_used_before - used

            leave_lines.append({
                'type': work_entry_type.name,
                'used': used,
                'accrual': gain,
                'balance': balance,
            })
        return leave_lines
