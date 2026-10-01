# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from dateutil.relativedelta import relativedelta, MO, SU
from odoo.tools import float_round


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    l10n_be_has_time_credit = fields.Boolean(compute='_compute_l10n_be_has_time_credit')
    l10n_be_reorganisation_measure_ids = fields.Many2many(
        'l10n.be.reorganisation.measure',
        string="Working Time Reorganisation",
        compute='_compute_l10n_be_reorganisation_measure_ids',
        store=True,
        groups="hr_payroll.group_hr_payroll_user",
        readonly=False)
    l10n_be_time_reorganisation_amount = fields.Float(
        string="Time Reorganisation Amount",
        groups="hr_payroll.group_hr_payroll_user",
        help="Amount of hours per week dedicated to credit-time / working time reorganisation.",
    )
    l10n_be_show_time_reorganisation_amount = fields.Boolean(
        compute='_compute_l10n_be_show_time_reorganisation_amount',
    )

    def _work_intervals_batch(self, start_dt, end_dt, resources_per_tz=None, domain=None, compute_leaves=True):
        work_intervals = super()._work_intervals_batch(start_dt, end_dt, resources_per_tz=resources_per_tz, domain=domain, compute_leaves=compute_leaves)
        if self.sudo().company_id.country_id.code != 'BE' or not compute_leaves:
            return work_intervals

        all_resources = set()
        if not resources_per_tz or self:
            all_resources.add(self.env['resource.resource'])
        if resources_per_tz:
            for _, resources in resources_per_tz.items():
                all_resources |= set(resources)

        credit_time_attendance_intervals = self.sudo()._attendance_intervals_batch(
            start_dt, end_dt, resources_per_tz=resources_per_tz, domain=[('work_entry_type_id.l10n_be_is_time_credit', '=', True)])
        return {
            r.id: (work_intervals[r.id] - credit_time_attendance_intervals[r.id]) if r and not r._is_flexible() else (work_intervals[r.id])
            for r in all_resources
        }

    @api.depends('attendance_ids.work_entry_type_id.l10n_be_is_time_credit')
    def _compute_l10n_be_has_time_credit(self):
        for calendar in self:
            calendar.l10n_be_has_time_credit = any(a.work_entry_type_id.l10n_be_is_time_credit for a in calendar.attendance_ids)

    @api.depends('attendance_ids.work_entry_type_id.l10n_be_is_time_credit')
    def _compute_l10n_be_reorganisation_measure_ids(self):
        for calendar in self:
            calendar.l10n_be_reorganisation_measure_ids = [(5, 0, 0)]
            if not calendar.attendance_ids:
                continue
            if all(a.work_entry_type_id.code in ['147.00', '147.05', '147.07', '147.04', '147.08'] for a in calendar.attendance_ids):
                mrt = self.env.ref('l10n_be_hr_payroll.l10n_be_reorganisation_measure_009_3', raise_if_not_found=False)
                if mrt:
                    calendar.l10n_be_reorganisation_measure_ids = [(4, mrt.id)]
                continue
            if any(a.work_entry_type_id.code in ['147.00', '147.05', '147.07', '147.04', '147.08'] for a in calendar.attendance_ids):
                mrt = self.env.ref('l10n_be_hr_payroll.l10n_be_reorganisation_measure_009_4', raise_if_not_found=False)
                if mrt:
                    calendar.l10n_be_reorganisation_measure_ids = [(4, mrt.id)]
            if any(a.work_entry_type_id.code == '122.04' for a in calendar.attendance_ids):
                mrt = self.env.ref('l10n_be_hr_payroll.l10n_be_reorganisation_measure_005_5', raise_if_not_found=False)
                if mrt:
                    calendar.l10n_be_reorganisation_measure_ids = [(4, mrt.id)]

    @api.depends('l10n_be_reorganisation_measure_ids')
    def _compute_l10n_be_show_time_reorganisation_amount(self):
        for calendar in self:
            calendar.l10n_be_show_time_reorganisation_amount = any(
                code in ('3', '4')
                for code in calendar.l10n_be_reorganisation_measure_ids.mapped('dmfa_code')
            )

    @api.onchange('l10n_be_reorganisation_measure_ids', 'hours_per_week')
    def _onchange_l10n_be_reorganisation_measure_ids(self):
        selected_codes = self.l10n_be_reorganisation_measure_ids.mapped('dmfa_code')

        if '3' in selected_codes:
            self.l10n_be_time_reorganisation_amount = self.hours_per_week
        elif '4' in selected_codes:
            self.l10n_be_time_reorganisation_amount = 0.0
        else:
            self.l10n_be_time_reorganisation_amount = 0.0

    def _get_days_per_week_for_period(self, start_dt, end_dt, half_day_hours_threshold):
        self.ensure_one()
        days = 0
        attendances_by_date = self._get_attendances_by_date(start_dt, end_dt)
        for attendances in attendances_by_date.values():
            for att in attendances.filtered(lambda a: a._is_work_period()):
                if att.day_period == 'full_day':
                    days += 1
                else:
                    days += 0.5 if att.duration_hours <= half_day_hours_threshold else 1
        return days / ((end_dt - start_dt).days + 1) * 7

    def _l10n_be_get_hours_per_week_for_period(self, start_dt, end_dt):
        """Average worked hours per week over [start_dt, end_dt].

        Correct for both fixed and variable calendars: variable calendars store 0
        in ``hours_per_week``, so the value is reconstructed from the actual
        attendances of the period instead.
        """
        self.ensure_one()
        attendances_by_date = self._get_attendances_by_date(start_dt, end_dt)
        total_hours = sum(
            sum(attendances.filtered(lambda a: a._is_work_period()).mapped('duration_hours'))
            for attendances in attendances_by_date.values()
        )
        weeks = ((end_dt - start_dt).days + 1) / 7
        return total_hours / weeks if weeks else 0

    def _l10n_be_get_work_time_rate_med_included(self, date_from, date_to, ref_calendar):
        self.ensure_one()

        period_start, period_end = date_from + relativedelta(weekday=MO(-1)), date_to + relativedelta(weekday=SU(1))
        days = (period_end - period_start).days + 1

        attendances_by_date = self._get_attendances_by_date(period_start, period_end)
        total_hours = sum(
            sum(attendances.filtered(lambda a: a._is_work_period() or a.work_entry_type_id.code == '122.04').mapped('duration_hours'))
            for attendances in attendances_by_date.values()
        )

        hours_per_week = total_hours / (days / 7) if days else 0

        return hours_per_week / ref_calendar.hours_per_week if ref_calendar.hours_per_week else 1

    def _l10n_be_get_work_time_rate_time_credit_included(self, date_from, date_to, ref_calendar):
        self.ensure_one()

        period_start, period_end = date_from + relativedelta(weekday=MO(-1)), date_to + relativedelta(weekday=SU(1))
        days = (period_end - period_start).days + 1

        attendances_by_date = self._get_attendances_by_date(period_start, period_end)
        total_hours = sum(
            sum(attendances.filtered(lambda a: a._is_work_period() or a.work_entry_type_id.l10n_be_is_time_credit).mapped('duration_hours'))
            for attendances in attendances_by_date.values()
        )

        hours_per_week = total_hours / (days / 7) if days else 0
        return float_round(hours_per_week / ref_calendar.hours_per_week, precision_digits=2) if ref_calendar.hours_per_week else 1

    def _l10n_be_get_time_credit_proration(self, date_from, date_to):
        """
        Returns the ratio of actual working hours to total calendar hours
        , where it doesn't include time_credit entry on actual working hours
        Ex1: Employee contract calendar is 5 days a week, 4 days actual working days & 1 day is time credit
            the proration factor will be 4/5 = 0.8

        Ex2: Employee contract calendar is 4 days a week, 3 days actual working days & 1 day is time credit
            the proration factor will be 3/4 = 0.75
        """
        self.ensure_one()

        if self.calendar_type == 'fixed':
            period_start = date_from + relativedelta(weekday=MO(-1))
            period_end = date_to + relativedelta(weekday=SU(1))
        else:
            period_start = date_from
            period_end = date_to

        attendances_by_date = self._get_attendances_by_date(period_start, period_end)

        actual_working_hours = sum(
            sum(attendances.filtered(lambda a: a._is_work_period()).mapped('duration_hours'))
            for attendances in attendances_by_date.values()
        )
        total_calendar_hours = sum(
            sum(attendances.mapped('duration_hours'))
            for attendances in attendances_by_date.values()
        )

        if not total_calendar_hours:
            return 0.0

        return actual_working_hours / total_calendar_hours

    def _l10n_be_get_short_attendance_resource_calendar(self):
        self.ensure_one()
        attendances_by_day = self.attendance_ids.grouped('dayofweek')
        return any(sum(attendance.mapped('duration_hours')) < 2 for attendance in attendances_by_day.values())
