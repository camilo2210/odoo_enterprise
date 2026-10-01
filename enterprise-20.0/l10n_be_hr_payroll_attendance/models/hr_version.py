# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models
from odoo.tools import float_round

from odoo.addons.resource.models.utils import HOURS_PER_DAY


class HrVersion(models.Model):
    _inherit = 'hr.version'

    def _get_work_hours_split_half(self, date_from, date_to, work_entries_vals):
        res = super()._get_work_hours_split_half(date_from, date_to, work_entries_vals)
        work_entry_type_overtime = self.env.ref('hr_work_entry.be_work_entry_type_overtime', False)
        if not work_entry_type_overtime:
            return res
        hours_per_day = self.resource_calendar_id.hours_per_day or self.reference_calendar_id.hours_per_day or HOURS_PER_DAY
        overtime_by_work_type_with_options = defaultdict(float)
        new_res = res.copy()
        for work_type_with_options in res:
            if work_type_with_options[0] == work_entry_type_overtime.id:
                _, hours = new_res.pop(work_type_with_options)
                work_type, options = work_type_with_options
                overtime_by_work_type_with_options[work_type, options] += hours

        for (work_type, options), overtime_hours in overtime_by_work_type_with_options.items():
            overtime_days = float_round(overtime_hours / hours_per_day, precision_rounding=1, rounding_method='UP')
            new_res[work_type, options] = [overtime_days, overtime_hours]
        return new_res
