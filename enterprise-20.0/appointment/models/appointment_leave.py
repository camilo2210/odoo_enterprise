from ast import literal_eval
from collections import defaultdict
from datetime import UTC, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.date_utils import localized
from odoo.tools.intervals import Intervals


class AppointmentLeave(models.Model):
    _name = 'appointment.leave'
    _description = 'Closing days for appointments and their users / resources'
    _order = 'date_from, id'

    def _default_datetime(self, dt):
        """ Converts given datetime from current user tz to UTC. """
        return dt.replace(tzinfo=self.env.tz).astimezone(UTC).replace(tzinfo=None)

    appointment_type_ids = fields.Many2many(
        'appointment.type', string='Appointments',
        compute='_compute_leave_type_related_fields', store=True, readonly=False)
    date_from = fields.Datetime(
        'Start Date', required=True,
        default=lambda self: self._default_datetime(fields.Datetime.today()))
    date_to = fields.Datetime(
        'End Date', required=True,
        default=lambda self: self._default_datetime(fields.Datetime.today() + timedelta(hours=23, minutes=59)))
    leave_type = fields.Selection(
        [('appointments', 'Appointments'),
         ('resources', 'Resources'),
         ('users', 'Users')],
        required=True, default='appointments')
    leave_reason = fields.Char('Reason')
    # Users / Resources
    resource_ids = fields.Many2many(
        'appointment.resource', string='Resources',
        compute='_compute_leave_type_related_fields', store=True, readonly=False)
    user_ids = fields.Many2many(
        'res.users', string='Users',
        compute='_compute_leave_type_related_fields', store=True, readonly=False)
    # Display
    appointment_type_domain = fields.Char(compute='_compute_appointment_type_domain')
    has_appointment_type_tz_mismatch = fields.Boolean(compute='_compute_has_appointment_type_tz_mismatch')
    resource_domain = fields.Char(compute='_compute_domains')
    user_domain = fields.Char(compute='_compute_domains')

    @api.depends('leave_type', 'resource_ids', 'user_ids')
    def _compute_appointment_type_domain(self):
        for leave in self:
            domain = []
            if leave.leave_type == 'resources':
                domain = [('schedule_based_on', '=', 'resources')]
            elif leave.leave_type == 'users':
                domain = [('schedule_based_on', '=', 'users')]
            leave.appointment_type_domain = domain

    @api.depends('leave_reason', 'leave_type')
    def _compute_display_name(self):
        for leave in self:
            leave.display_name = leave.leave_reason if leave.leave_reason else _("%s closing", leave.leave_type.capitalize())

    @api.depends('appointment_type_ids')
    def _compute_domains(self):
        for leave in self:
            domain = (
                # staff users / resources must be present in at least one of the specified appointment types
                [('appointment_type_ids', 'in', leave.appointment_type_ids.ids)] if leave.appointment_type_ids else
                [('appointment_type_ids', '!=', False)]
            )
            leave.resource_domain = domain
            leave.user_domain = domain

    @api.depends('appointment_type_ids')
    def _compute_has_appointment_type_tz_mismatch(self):
        user_tz = self.env.user.tz
        for leave in self:
            appointment_types = leave.appointment_type_ids or self.env['appointment.type'].search(literal_eval(leave.appointment_type_domain))
            leave.has_appointment_type_tz_mismatch = bool(set(appointment_types.mapped('appointment_tz')) - {user_tz})

    @api.depends('leave_type')
    def _compute_leave_type_related_fields(self):
        for leave in self:
            if leave.leave_type == 'resources':
                leave.appointment_type_ids = leave.appointment_type_ids.filtered(lambda apt: apt.schedule_based_on == 'resources')
                leave.user_ids = False
            elif leave.leave_type == 'users':
                leave.appointment_type_ids = leave.appointment_type_ids.filtered(lambda apt: apt.schedule_based_on == 'users')
                leave.resource_ids = False
            else:
                leave.resource_ids = False
                leave.user_ids = False

    @api.constrains('appointment_type_ids', 'leave_type', 'resource_ids', 'user_ids')
    def _check_leave_configuration(self):
        for leave in self:
            # Appointments
            if leave.leave_type == 'appointments' and (leave.resource_ids or leave.user_ids):
                raise ValidationError(_("You cannot set users or resources on a leave of type 'appointments'."))
            # Resources
            if leave.leave_type == 'resources':
                if not leave.resource_ids:
                    raise ValidationError(_("You must specify at least one resource on a leave of type 'resources'."))
                if leave.user_ids:
                    raise ValidationError(_("You cannot set users on a leave of type 'resources'."))
                if leave.appointment_type_ids and not (leave.appointment_type_ids <= leave.resource_ids.appointment_type_ids):
                    raise ValidationError(_(
                        "Each selected appointment type must include at least one of the specified resources."))
            # Users
            if leave.leave_type == 'users':
                if not leave.user_ids:
                    raise ValidationError(_("You must specify at least one user on a leave of type 'users'."))
                if leave.resource_ids:
                    raise ValidationError(_("You cannot set resources on a leave of type 'users'."))
                if leave.appointment_type_ids and not (leave.appointment_type_ids <= leave.user_ids.appointment_type_ids):
                    raise ValidationError(_(
                        "Each selected appointment type must include at least one of the specified users."))

    # --------------------------------------
    # Business Methods
    # --------------------------------------

    @api.model
    def _get_appointment_leave_intervals(self, date_from, date_to, staff_users=None, appointment_resources=None, appointment_types=None):
        """ Build leave intervals per given records.
        Only considering the given appointment types, if any.

        :param date_from: the start of the interval. Timezoned to UTC.
        :param date_to: the end of the interval. Timezoned to UTC.
        :param staff_users: optional staff users to get the leaves for
        :param appointment_resources: optional appointment resources to get the leaves for
        :param appointment_types: optional appointment types to get the leaves for, if none, only leaves applied on all apt types are considered
        :rtype: dict[<appointment.resource, 1>: Intervals object]
        """
        if not staff_users and not appointment_resources:
            return {}
        field = 'user_ids' if staff_users else 'resource_ids'
        records = staff_users or appointment_resources

        domain = Domain([
            ('date_from', '<', date_to.replace(tzinfo=None)),
            ('date_to', '>', date_from.replace(tzinfo=None)),
            '|', (field, 'in', records.ids), ('leave_type', '=', 'appointments'),
        ])
        appointment_type_domain = Domain('appointment_type_ids', '=', False)  # Consider leaves set on all appointment types
        if appointment_types:
            appointment_type_domain |= Domain('appointment_type_ids', 'in', appointment_types.ids)
        domain &= appointment_type_domain

        leaves = self.search(domain)
        intervals_by_record = defaultdict(Intervals)

        for leave in leaves:
            effective_apt_types = leave.appointment_type_ids & appointment_types if appointment_types else leave.appointment_type_ids
            impacted_records = records.filtered(lambda r: (
                # If restricted, only the staff users / resources specified on the leave
                (leave.leave_type == 'appointments' or r._origin in leave[field])
                # If restricted, only the staff users / resources impacted by the considered appointment types.
                and (not leave.appointment_type_ids or r._origin.appointment_type_ids & effective_apt_types)
            ))
            start = localized(leave.date_from)
            end = localized(leave.date_to)
            for record in impacted_records:
                intervals_by_record[record] |= Intervals([(start, end, record)])

        return intervals_by_record
