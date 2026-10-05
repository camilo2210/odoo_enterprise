# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.appointment.controllers.calendar_view import AppointmentCalendarView
from odoo.fields import Domain


class AppointmentCrmCalendarView(AppointmentCalendarView):

    @classmethod
    def _get_appointment_invite_domain(cls, appointment_type, user, opportunity_id=None, **kwargs):
        domain = super()._get_appointment_invite_domain(appointment_type, user, **kwargs)
        if opportunity_id:
            domain = Domain.AND([domain, [('opportunity_id', '=', opportunity_id)]])
        return domain

    @classmethod
    def _get_appointment_invite_values(cls, appointment_type, opportunity_id=None, **kwargs):
        invitation_values = super()._get_appointment_invite_values(appointment_type, **kwargs)
        if opportunity_id:
            invitation_values['opportunity_id'] = opportunity_id
        return invitation_values
