
from odoo import http
from odoo.http import request
from odoo.addons.base.models.ir_qweb import keep_query

class AppointmentLegacy(http.Controller):
    """
        Retro compatibility layer for legacy endpoint
    """

    @http.route(['/calendar/<model("appointment.type"):appointment_type>/appointment'],
                type='http', auth='public', website=True, sitemap=False)
    def calendar_appointment(self, appointment_type, filter_staff_user_ids=None, timezone=None, failed=False, **kwargs):
        return request.redirect('/calendar/%s?%s' % (request.env['ir.http']._slug(appointment_type), keep_query('*')))

    @http.route(['/calendar/ics/<string:access_token>.ics'], type='http', auth="public", website=True)
    def appointment_get_ics_file(self, access_token, **kwargs):
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not event:
            return request.not_found()
        return request.redirect(f'/calendar/ics/{event.id}/{access_token}')
