# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug.exceptions import Forbidden

from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request, route


class AppointmentCalendarView(http.Controller):

    # ------------------------------------------------------------
    # APPOINTMENT JSON ROUTES FOR BACKEND
    # ------------------------------------------------------------

    @route('/appointment/appointment_type/get_calendar_slot_editor_info', type='jsonrpc', auth='user')
    def appointment_get_calendar_slot_editor_info(self, appointment_type_id, **kwargs):
        """
        Get the information of the appointment invitation used to share the link
        of the appointment type selected.
        """
        appointment_type = request.env['appointment.type'].browse(int(appointment_type_id)).exists()
        if not appointment_type:
            raise ValidationError(_("An appointment type is needed to get the link."))
        return self._get_calendar_slot_editor_info(appointment_type, **kwargs)

    @route('/appointment/appointment_type/search_create_anytime', type='jsonrpc', auth='user')
    def appointment_type_search_create_anytime(self, **kwargs):
        return self._appointment_type_search_create_anytime(**kwargs)

    @classmethod
    def _appointment_type_search_create_anytime(cls, user=None, **kwargs):
        """Return the info (id, url, ...) of the anytime appointment type of the actual user.

        Search and return the anytime appointment type for the user.
        In case it doesn't exist yet, it creates an anytime appointment type.
        """
        user = user or request.env.user
        # Check if the user is a member of group_user to avoid portal user and the like to create appointment types
        if not user._is_internal():
            raise Forbidden()
        AppointmentType = request.env['appointment.type']
        appointment_type = AppointmentType.search([
            ('category', '=', 'anytime'),
            ('staff_user_ids', 'in', user.ids)])
        if not appointment_type:
            appt_type_vals = cls._prepare_appointment_type_anytime_values(user)
            appointment_type = AppointmentType.create(appt_type_vals)
        return cls._get_calendar_slot_editor_info(appointment_type, **kwargs)

    # Utility Methods
    # ----------------------------------------------------------

    @classmethod
    def _prepare_appointment_type_anytime_values(cls, user):
        return {
            'name': _("Meeting with %(name)s", name=user.name),
            'max_schedule_days': 15,
            'category': 'anytime',
            'staff_user_ids': [user.id],
        }

    @classmethod
    def _get_calendar_slot_editor_info(cls, appointment_type, user=None, **kwargs):
        """Return all the information needed to enter slot edition mode in the calendar view.

        This includes an invite url, which will be created if none exists.
        """
        user = user or request.env.user
        appointment_invitation_domain = cls._get_appointment_invite_domain(appointment_type, user, **kwargs)
        appointment_invitation = request.env['appointment.invite'].search(appointment_invitation_domain, limit=1)
        if not appointment_invitation:
            invitation_values = cls._get_appointment_invite_values(appointment_type, **kwargs)
            appointment_invitation = request.env['appointment.invite'].create(invitation_values)

        return {
            'appointment_type': appointment_type.read([
                'active',
                'appointment_duration',
                'appointment_tz',
                'category',
                'category_slot_scheduling',
                'end_datetime',
                'name',
                'slot_creation_interval',
                'start_datetime',
                'user_can_manage_slots'
            ])[0],
            'invite_url': appointment_invitation.book_url,
        }

    @classmethod
    def _get_appointment_invite_domain(cls, appointment_type, user, **kwargs):
        """ Returns the domain used to search for an existing invitation when copying a link
        to any 'punctual' or 'recurring' appointment type in the calendar view. When sharing an
        'anytime' appointment, we search for existing invitations (as the appointment may already
        exist). This prevents duplicating appointment.invite.
        The user can modify 'custom' appointments and share their link more than once. Indeed, the
        'configure' button allows them to change staff users. They can even remove themselves from
        the staff users. As a new 'custom' appointment is created on using the 'select dates' feature
        on the fly, we want to search for the invitation that has been created by the current user. """
        if appointment_type.category == 'custom' or appointment_type.schedule_based_on != 'users':
            return [
                ('appointment_type_ids', '=', appointment_type.id),
                ('create_uid', '=', user.id),
            ]
        return [
            ('appointment_type_ids', '=', appointment_type.id),
            ('staff_user_ids', '=', user.id),
        ]

    @classmethod
    def _get_appointment_invite_values(cls, appointment_type, **kwargs):
        invitation_values = {
            'appointment_type_ids': appointment_type.ids,
            'resources_choice': 'current_user',
            'short_code': request.env['appointment.invite']._get_unique_short_code(appointment_type=appointment_type),
        }
        if appointment_type.category == 'custom' or appointment_type.schedule_based_on != 'users':
            # Custom appointment users may be edited on the spot. 'all_assigned_resources'
            # allows the link copied to be correctly configured with latest users.
            # for resource appointments we similarly want to show all resources and don't care about staff users.
            invitation_values.update({
                'resources_choice': 'all_assigned_resources',
                'staff_user_ids': False,
            })
        return invitation_values
