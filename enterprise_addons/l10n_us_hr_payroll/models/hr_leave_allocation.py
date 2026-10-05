# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrLeaveAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    l10n_us_allocation_data = fields.Json(
        "Allocation data for accrual", export_string_translation=False,
    )

    def _track_execute(self, track_init_values, trackings, track_records=None):
        # override to store tracked changes on 'number_of_days' in a specific
        # JSON field to denormalize data and speedup access
        res = super()._track_execute(track_init_values, trackings, track_records=track_records)
        today_str = fields.Date.to_string(self.env.cr.now().date())
        for allocation in self:
            changes, _tracking_values = trackings.get(allocation.id, ([], None))
            if 'number_of_days' in changes:
                allocation_data = allocation.l10n_us_allocation_data or {}
                allocation_data[today_str] = allocation.number_of_hours
                allocation.l10n_us_allocation_data = allocation_data
        return res

    def _l10n_us_get_total_allocated(self, date):
        total_allocated_hours = 0
        for alloc in self.filtered(lambda a: (
            a.work_entry_type_id.l10n_us_show_on_payslip is True and
            a.date_from <= date
        )):
            allocation_data = alloc.l10n_us_allocation_data or {}
            past_dates = [fields.Date.from_string(track_date) for track_date in allocation_data if fields.Date.from_string(track_date) <= date]
            closest_key = fields.Date.to_string(max(past_dates)) if past_dates else False
            if closest_key is False:
                total_allocated_hours += alloc.number_of_hours
            else:
                total_allocated_hours += allocation_data[closest_key]

        return total_allocated_hours
