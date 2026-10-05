# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from werkzeug.exceptions import BadRequest, Forbidden
from werkzeug.urls import url_encode

from odoo import fields
from odoo.http import request, route
from odoo.tools import consteq

from odoo.addons.base.models.ir_qweb import keep_query
from odoo.addons.calendar.controllers.main import CalendarController


class AppointmentCalendarController(CalendarController):

    # ------------------------------------------------------------
    # CALENDAR EVENT VIEW
    # ------------------------------------------------------------

    @route()
    def view_meeting(self, token, id):
        """Redirect the internal logged in user to the form view of calendar.event, and redirect
           regular attendees to the website page of the calendar.event for appointments"""
        super(AppointmentCalendarController, self).view_meeting(token, id)
        attendee = request.env['calendar.attendee'].sudo().search([
            ('access_token', '=', token),
            ('event_id', '=', int(id))])
        if not attendee:
            return request.render("appointment.appointment_invalid", {})

        # If user is internal and logged, redirect to form view of event
        if request.env.user._is_internal():
            return request.redirect(f'/odoo/{attendee.event_id._name}/{id}?db={request.env.cr.dbname}')

        request.session['timezone'] = attendee.partner_id.tz
        access_token = attendee.event_id._calendar_event_ensure_token()
        return request.redirect(
            f'/calendar/view/{access_token}?partner_id={attendee.partner_id.id}&attendee_token={token}'
        )

    @route(['/calendar/view/<string:access_token>'], type='http', auth="public", website=True)
    def appointment_view(self, access_token, partner_id=False, state=False, attendee_token=None, **kwargs):
        """
        Render the validation of an appointment and display a summary of it

        :param access_token: the access_token of the event linked to the appointment
        :param partner_id: id of the partner who booked the appointment
        :param state: allow to display an info message, possible values:
            - 'new': Info message displayed when the appointment has been correctly created
            - 'no_reschedule': Warning message displayed when the appointment type is not accessible
            - other values: see _get_prevent_cancel_status
        """
        partner_id = int(partner_id) if partner_id else False
        event = request.env['calendar.event'].with_context(active_test=False).sudo().search([('access_token', '=', access_token)], limit=1)
        if not event:
            return request.not_found()
        timezone = request.session.get('timezone') or event.appointment_type_id.appointment_tz
        request.session['timezone'] = timezone
        tz_session = ZoneInfo(timezone)

        if not event.allday:
            datetime_start = fields.Datetime.from_string(event.start).replace(tzinfo=UTC).astimezone(tz_session)
            display_duration = event.duration
        else:
            date_start = fields.Date.from_string(event.start_date)
            display_duration = (fields.Date.from_string(event.stop_date) - date_start).days + 1
            datetime_start = fields.Datetime.from_string(event.start_date)

        attendee = event.attendee_ids.filtered(lambda attendee: attendee.partner_id.id == int(partner_id))
        attendee = attendee_token and consteq(attendee.access_token or '', attendee_token) and attendee

        return request.render("appointment.appointment_validated", {
            'cancel_responsible': event.user_id if event.user_id.active and event.user_id._is_internal() else False,
            'event': event,
            'event_attendee': attendee,
            'datetime_start': datetime_start,
            'display_duration': display_duration,
            'state': state,
            'partner_id': partner_id,
            'attendee_status': event.attendee_ids.filtered(lambda a: a.partner_id.id == partner_id).state if partner_id else False,
            'can_access_appointment_type': event.appointment_type_id and self._can_access_appointment_type(event.appointment_type_id),
            'is_cancelled': not event.active,
        }, headers={'Cache-Control': 'no-store'})

    @route(['/calendar/<string:access_token>/add_attendees_from_emails'], type="jsonrpc", auth="public", website=True)
    def appointment_add_attendee(self, access_token, emails_str):
        """
        Add the attendee at the time of the validation of an appointment page

        :param access_token: access_token of the event linked to the appointment
        :param emails_str: guest emails in the block of text
        """
        event_sudo = request.env['calendar.event']
        event_sudo = event_sudo.sudo().search([('access_token', '=', access_token)], limit=1)
        if not event_sudo:
            return request.not_found()
        if not event_sudo.appointment_type_id.allow_guests:
            raise BadRequest()
        if not emails_str:
            return []
        guests = event_sudo.sudo()._find_or_create_partners(emails_str)
        if guests:
            event_sudo.write({
                'partner_ids': [(4, pid.id, False) for pid in guests]
            })

    @route(['/calendar/cancel/<string:access_token>',
            '/calendar/<string:access_token>/cancel',
           ], type='http', auth="public", website=True, methods=['POST'])
    def appointment_cancel(self, access_token, partner_id=False, **kwargs):
        """
            Route to cancel an appointment event, this route is linked to a button in the validation page
        """
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        appointment_type = event.appointment_type_id
        appointment_invite = event.appointment_invite_id
        if not event:
            return request.not_found()
        if cancel_status := self._get_prevent_cancel_status(event):
            return request.redirect(f'/calendar/view/{access_token}?state={cancel_status}&partner_id={partner_id}')
        event.sudo().action_cancel_meeting([int(partner_id)] if partner_id else [])
        if appointment_invite:
            redirect_url = appointment_invite.redirect_url + '&state=cancel'
        elif not self._can_access_appointment_type(appointment_type):
            redirect_url = f'/calendar/view/{access_token}?partner_id={partner_id or ""}'
        else:
            reset_params = {'state': 'cancel'}
            if appointment_type.schedule_based_on == 'resources':
                reset_params.update({
                    'resource_selected_id': '',
                    'available_resource_ids': '',
                })
            redirect_url = f'/appointment/{request.env['ir.http']._slug(appointment_type)}?{keep_query("*", **reset_params)}'
        return request.redirect(redirect_url)

    @route('/calendar/<string:access_token>/reschedule', type='http', auth='public', website=True, methods=['POST'])
    def appointment_reschedule(self, access_token, partner_id=False, **kwargs):
        """
        Route to reschedule an appointment event, the existing event is NOT cancelled
        here, it is only cancelled after the user successfully books a new slot.
        """
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not event:
            return request.not_found()
        if cancel_status := self._get_prevent_cancel_status(event):
            return request.redirect(f'/calendar/view/{access_token}?state={cancel_status}&partner_id={partner_id}')
        appointment_type = event.appointment_type_id
        if not appointment_type:
            return request.not_found()
        if not event.appointment_invite_id and not self._can_access_appointment_type(appointment_type):
            return request.redirect(f'/calendar/view/{access_token}?state=no_reschedule&partner_id={partner_id or ""}')
        params = {
            'state': 'reschedule',
            'access_token': access_token,
        }
        if partner_id:
            params['partner_id'] = partner_id
        if appointment_invite := event.appointment_invite_id:
            redirect_url = f"{appointment_invite.redirect_url}&{url_encode(params)}"
        else:
            redirect_url = f'/appointment/{request.env["ir.http"]._slug(appointment_type)}?{url_encode(params)}'
        return request.redirect(redirect_url)

    def _can_access_appointment_type(self, appointment_type):
        """Check the attendee read access rights on the appointment type."""
        return appointment_type.sudo(False).has_access('read')

    def _get_prevent_cancel_status(self, event):
        """
            This method returns status corresponding to any reason preventing event cancelling.
            It can be overriden to add other cancelling condition checks and return their status value.
        """
        if (fields.Datetime.from_string(event.allday and event.start_date or event.start)
            < datetime.now() + timedelta(hours=event.appointment_type_id.min_cancellation_hours)):
            return 'no_time_left'
        return False

    @route('/calendar/videocall/<string:access_token>', type='http', auth='public')
    def calendar_videocall(self, access_token):
        if not access_token:
            raise Forbidden()
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not event or not event.videocall_location:
            return request.not_found()

        if event.videocall_source == 'discuss':
            return self.calendar_join_videocall(access_token)
        # custom / google_meet
        return request.redirect(event.videocall_location, local=False)
