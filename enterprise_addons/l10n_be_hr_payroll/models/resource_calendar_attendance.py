from odoo import api, fields, models


class ResourceCalendarAttendance(models.Model):
    _inherit = "resource.calendar.attendance"

    l10n_be_is_time_credit = fields.Boolean(related="work_entry_type_id.l10n_be_is_time_credit", store=True)
    # color of the reorganisation measure computed per attendance (a calendar can mix several measures, each with its own color)
    l10n_be_reorganisation_measure_color = fields.Integer(compute='_compute_l10n_be_reorganisation_measure_color')

    @api.depends('work_entry_type_id.code', 'calendar_id.l10n_be_reorganisation_measure_ids.color')
    def _compute_l10n_be_reorganisation_measure_color(self):
        Measure = self.env['l10n.be.reorganisation.measure']
        career_break_measures = (
            (self.env.ref('l10n_be_hr_payroll.l10n_be_reorganisation_measure_009_3', raise_if_not_found=False) or Measure)
            | (self.env.ref('l10n_be_hr_payroll.l10n_be_reorganisation_measure_009_4', raise_if_not_found=False) or Measure)
        )
        adapted_work_measure = self.env.ref('l10n_be_hr_payroll.l10n_be_reorganisation_measure_005_5', raise_if_not_found=False) or Measure
        for attendance in self:
            code = attendance.work_entry_type_id.code
            linked_measures = attendance.calendar_id.l10n_be_reorganisation_measure_ids
            if code in ('147.00', '147.05', '147.07', '147.04', '147.08'):
                measure = linked_measures & career_break_measures
            elif code == '122.04':
                measure = linked_measures & adapted_work_measure
            else:
                measure = Measure
            attendance.l10n_be_reorganisation_measure_color = measure[:1].color
