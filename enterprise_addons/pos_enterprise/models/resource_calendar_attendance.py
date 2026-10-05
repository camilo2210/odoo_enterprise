from odoo import api, models


class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        attendance_ids = data['pos.preset'].attendance_ids.ids
        return [('id', 'in', attendance_ids)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['id', 'hour_from', 'hour_to', 'dayofweek']
