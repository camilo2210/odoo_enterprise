from odoo import api, fields, models
from odoo.fields import Domain


class Rating(models.Model):
    _inherit = 'rating.rating'

    appointment_schedule_based_on = fields.Selection(
        [('users', 'Users'), ('resources', 'Resources')],
        string="Schedule Based On",
        compute='_compute_appointment_fields',
        search='_search_appointment_schedule_based_on',
    )
    appointment_resource_ids = fields.Many2many(
        'appointment.resource',
        string="Appointment Resources",
        compute='_compute_appointment_fields',
        search='_search_appointment_resource_ids',
    )

    @api.depends('resource_ref')
    def _compute_appointment_fields(self):
        for rating in self:
            if rating.res_model == 'calendar.event' and rating.resource_ref:
                rating.appointment_schedule_based_on = rating.resource_ref.appointment_type_id.schedule_based_on
                rating.appointment_resource_ids = rating.resource_ref.appointment_resource_ids
            else:
                rating.appointment_schedule_based_on = False
                rating.appointment_resource_ids = False

    def _search_appointment_schedule_based_on(self, operator, value):
        events = self.env['calendar.event'].with_context(active_test=False)._search([
            ('appointment_type_id.schedule_based_on', operator, value)
        ])
        return Domain('res_model', '=', 'calendar.event') & Domain('res_id', 'in', events)

    def _search_appointment_resource_ids(self, operator, value):
        events = self.env['calendar.event'].with_context(active_test=False)._search([
            ('appointment_resource_ids', operator, value)
        ])
        return Domain('res_model', '=', 'calendar.event') & Domain('res_id', 'in', events)
