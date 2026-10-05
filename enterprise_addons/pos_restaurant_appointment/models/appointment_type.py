# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AppointmentType(models.Model):
    _name = 'appointment.type'
    _inherit = ['appointment.type', 'pos.load.mixin']

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['resource_total_capacity']

    @api.model
    def _load_pos_data_domain(self, data):
        return [('id', '=', data['pos.config'].appointment_type_id.id)]

    def get_available_appointment_resources(self):
        self.ensure_one()
        start_date = self.env.context.get('start_date')
        resources = self.resource_ids
        return resources.filtered(
            lambda r: not r.is_used or
            not start_date or
            fields.Datetime.from_string(r.is_used.get('event_start')) > start_date or
            fields.Datetime.from_string(r.is_used.get('event_stop')) < start_date
        )
