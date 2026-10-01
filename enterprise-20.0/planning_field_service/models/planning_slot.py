import math
import random
import requests

from collections import defaultdict
from datetime import UTC, timedelta
from dateutil.relativedelta import relativedelta
from itertools import combinations, cycle, islice
from markupsafe import Markup
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from odoo import api, fields, models, modules
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import format_date, format_datetime, get_lang
from odoo.tools.intervals import Intervals

SLOT_PRIORITY = [
    ('0', 'Low'),
    ('1', 'Medium'),
    ('2', 'High'),
    ('3', 'Urgent'),
]

EARTH_RADIUS_KM = 6371
AVERAGE_SPEED_KMH = 60


def _project_coordinates(latitude, longitude):
    """Project a coordinate onto a plane in km, using the [Web Mercator projection](https://en.wikipedia.org/wiki/Web_Mercator_projection)."""
    return (
        EARTH_RADIUS_KM * math.radians(longitude),
        EARTH_RADIUS_KM * math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2)),
    )


def _project_isochrone(contour):
    """Project a single isochrone contour, once, as it does not depend on the destination."""
    return [_project_coordinates(latitude, longitude) for longitude, latitude in contour]


def _contour_segments(contour):
    """The contour's closed segments, without rebuilding a rotated copy of it: these run
    once per (source, destination) pair, so the copies add up to more than the maths."""
    return zip(contour, islice(cycle(contour), 1, len(contour) + 1))


def _point_in_contour(point, contour):
    """Even-odd rule algorithm (https://en.wikipedia.org/wiki/Even%E2%80%93odd_rule)."""
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in _contour_segments(contour):
        if (y < y1) != (y < y2):
            x_intersection = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_intersection:
                inside = not inside
    return inside


def _distance_to_contour(point, contour):
    """Shortest distance in km between a projected point and a contour."""
    x, y = point
    shortest = math.inf
    for (x1, y1), (x2, y2) in _contour_segments(contour):
        dx, dy = x2 - x1, y2 - y1
        length_squared = dx * dx + dy * dy
        # closest point of the segment, clamped to its ends
        position = ((x - x1) * dx + (y - y1) * dy) / length_squared if length_squared else 0.0
        position = min(max(position, 0.0), 1.0)
        shortest = min(shortest, math.hypot(x - (x1 + position * dx), y - (y1 + position * dy)))
    return shortest


def _estimate_travel_time_with_isochrones(isochrones, origin_point, point):
    """Estimate the driving time, in minutes, from an origin to a destination, by
    interpolating between the origin's isochrone contours.

    The contours are the level curves of the driving time around the origin, computed by
    road: the destination falls between two of them, and the time is interpolated on how
    close it is to each. Past the outermost contour, the width of the last band gives the
    pace to keep.

    Coordinates come in already projected in km, as a location is scored against every
    other one and projecting it once up front saves projecting it again for each of them.

    :param dict isochrones: contours of the origin projected in km, as {minutes: [(x, y), ...]}
    :param tuple origin_point: the projected origin the `isochrones` were computed around
    :param tuple point: the projected destination
    :return: the estimated driving time in minutes, None if it cannot be estimated
    """
    inner_minutes, inner_contour = 0, None
    for minutes, contour in isochrones.items():
        if _point_in_contour(point, contour):
            inner = (
                _distance_to_contour(point, inner_contour)
                if inner_contour
                # the origin itself is the inner bound of the first contour
                else math.dist(point, origin_point)
            )
            outer = _distance_to_contour(point, contour)
            return inner_minutes + (minutes - inner_minutes) * inner / (inner + outer)
        inner_minutes, inner_contour = minutes, contour

    # Beyond the outermost contour, no ring left to interpolate with: keep the last band's pace
    items = list(isochrones.items())
    if len(items) < 2:
        return None
    previous_minutes, previous_contour = items[-2]
    beyond = _distance_to_contour(point, inner_contour)
    band = _distance_to_contour(point, previous_contour) - beyond
    if band <= 0:
        return None
    estimated_travel_time = inner_minutes + (inner_minutes - previous_minutes) * beyond / band
    return math.ceil(estimated_travel_time)


def _haversine_distance(lat1, lon1, lat2, lon2):
    """Compute the straight-line distance in km between two coordinates using the [Haversine formula](https://en.wikipedia.org/wiki/Haversine_formula)."""
    dlat = math.radians(lat2 - lat1)
    dlong = math.radians(lon2 - lon1)
    arcsin = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(dlong / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(arcsin), math.sqrt(1 - arcsin))


class PlanningSlot(models.Model):
    _name = 'planning.slot'
    _order = 'start_datetime desc, priority desc, id desc'
    _inherit = [
        'planning.slot',
        'portal.mixin',
        'rating.mixin',
        'mail.thread',
        'mail.activity.mixin',
    ]

    start_datetime = fields.Datetime(tracking=2)
    end_datetime = fields.Datetime(tracking=3)
    allocated_hours = fields.Float(tracking=4)
    resource_ids = fields.Many2many(tracking=6)
    role_id = fields.Many2one(tracking=7)
    company_id = fields.Many2one(tracking=20)
    state = fields.Selection(selection_add=[
        ('3_in_progress', 'In Progress'),
        ('4_completed', 'Completed'),
    ], tracking=1)
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        tracking=11,
        check_company=True,
        store=True,  # to override the partner_id field definition in sale_planning module
        index='btree_not_null',
        related=False,
        readonly=False,
        group_expand='_group_expand_partner_id',
    )
    partner_phone = fields.Char(
        string="Phone",
        compute='_compute_partner_phone',
        inverse='_inverse_partner_phone',
        readonly=False,
        store=True,
        copy=False,
        tracking=12,
    )
    partner_name = fields.Char(related='partner_id.name')
    partner_city = fields.Char(related='partner_id.city')
    partner_zip = fields.Char(string='ZIP', related='partner_id.zip')
    partner_street = fields.Char(related='partner_id.street')
    partner_street2 = fields.Char(related='partner_id.street2')
    partner_country_id = fields.Many2one('res.country', related='partner_id.country_id')
    partner_state_id = fields.Many2one('res.country.state', string='Customer State', related='partner_id.state_id')
    partner_address = fields.Char(related='partner_id.address')
    sequence = fields.Integer(string='Sequence', default=10, export_string_translation=False)  # check if we move it in planning module
    worksheet_signature = fields.Binary('Signature', copy=False, attachment=True)
    worksheet_signed_by = fields.Char('Signed By', copy=False)
    break_time = fields.Float(string='Break Time', compute='_compute_break_time', readonly=False, store=True, tracking=5)
    show_customer_preview = fields.Boolean(compute='_compute_show_customer_preview', export_string_translation=False)
    show_sign_report = fields.Boolean(compute='_compute_show_sign_report', export_string_translation=False)
    priority = fields.Selection(SLOT_PRIORITY, string='Priority', default='0', tracking=8)
    travel_time_in = fields.Float(default=0.0, copy=False, help="Travel time from previous shift (or work location) to this shift.")
    travel_time_out = fields.Float(default=0.0, copy=False, help="Travel time from this shift to the next (or work location).")
    travel_distance_in = fields.Float(default=0.0, copy=False, help="Distance from previous shift (or work location) to this shift.")
    travel_distance_out = fields.Float(default=0.0, copy=False, help="Distance from this shift to the next (or work location).")
    travel_times_up_to_date = fields.Boolean(compute='_compute_travel_times_up_to_date', inverse='_inverse_travel_times_up_to_date', store=True, copy=False)

    @api.depends('partner_id.phone')
    def _compute_partner_phone(self):
        for slot in self:
            slot.partner_phone = slot.partner_id.phone or False

    def _inverse_partner_phone(self):
        for slot in self:
            if slot.partner_id and slot.partner_phone != slot.partner_id.phone:
                slot.partner_id.sudo().phone = slot.partner_phone

    def _compute_access_url(self):
        for slot in self:
            slot.access_url = f"/my/field-service/{slot.id}"

    @api.depends('resource_ids', 'start_datetime', 'end_datetime', 'allocated_hours')
    def _compute_break_time(self):
        for slot in self:
            break_time = 0.0
            if slot.start_datetime and slot.end_datetime and slot.allocation_type == 'planning':
                duration = (slot.end_datetime - slot.start_datetime).total_seconds() / 3600.0
                resource_factor = 1.0
                if slot.employee_public_ids:
                    resource_factor = len(slot.employee_public_ids)
                elif slot.resource_ids:
                    resource_factor = len(self.resource_ids)
                break_time = resource_factor * duration - slot.allocated_hours
            if break_time < 0:
                break_time = 0.0
            slot.break_time = break_time

    def _compute_allocated_percentage(self):
        interventions_assigned = self.filtered(
            lambda s: s.start_datetime and s.end_datetime and s.allocation_type == 'planning'
        )
        super(PlanningSlot, self - interventions_assigned)._compute_allocated_percentage()
        if interventions_assigned:
            in_schedule_break_time = interventions_assigned._get_in_schedule_break_time()
            for slot in interventions_assigned:
                in_schedule_time = slot.allocated_hours + in_schedule_break_time[slot.id]
                slot.allocated_percentage = slot.allocated_hours / in_schedule_time * 100 if in_schedule_time else 0

    @api.onchange('break_time')
    def _onchange_break_time(self):
        if not (self.start_datetime and self.end_datetime):
            return
        allocated_hours = self.allocated_hours / self.allocated_percentage * 100 if self.allocated_percentage else 0
        in_schedule_break_time = self._get_in_schedule_break_time()
        self.update({
            'allocated_hours': max(allocated_hours - in_schedule_break_time[self.id], 0),
            'break_time': max(self.break_time, 0),
        })

    def _get_in_schedule_break_time(self):
        working_hours_per_slot = self._get_working_hours()
        in_schedule_break_time = {}
        for slot in self:
            duration = (slot.end_datetime - slot.start_datetime).total_seconds() / 3600.0
            resource_factor = 1.0
            if slot.employee_public_ids:
                resource_factor = len(slot.employee_public_ids)
            elif slot.resource_ids:
                resource_factor = len(self.resource_ids)
            in_schedule_break_time[slot.id] = max(slot.break_time - (duration * resource_factor - working_hours_per_slot[slot.id]), 0)
        return in_schedule_break_time

    @api.depends('state')
    def _compute_show_sign_report(self):
        for slot in self:
            slot.show_sign_report = slot._can_show_sign_report_button()

    @api.depends('state')
    def _compute_show_customer_preview(self):
        for slot in self:
            slot.show_customer_preview = slot._can_sign_report()

    def _compute_planning_slot_company_id(self):
        super(PlanningSlot, self.filtered(lambda s: not s.company_id))._compute_planning_slot_company_id()

    @api.depends('user_ids')
    def _compute_can_edit(self):
        super()._compute_can_edit()
        if all(self.mapped('can_edit')):
            # then the current user is a planning manager
            return
        current_user = self.env.user
        if not current_user.has_group('planning.group_planning_user'):
            self.can_edit = False
            return
        for slot in self:
            slot.can_edit = current_user in slot.user_ids

    @api.depends('resource_ids', 'partner_id', 'start_datetime', 'end_datetime')
    def _compute_travel_times_up_to_date(self):
        for slot in self:
            slot.travel_times_up_to_date = not (slot.resource_ids and slot.partner_id and slot.start_datetime)

    def _inverse_travel_times_up_to_date(self):
        for slot in self:
            if self.env.context.get('reset_travel_times', True) or not slot.travel_times_up_to_date:
                slot.write({
                    'travel_time_in': 0,
                    'travel_time_out': 0,
                    'travel_distance_in': 0,
                    'travel_distance_out': 0,
                })

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self._origin and self.company_id and self._origin.company_id != self.company_id:
            self._reset_intervention_fields()

    def action_plan_shift(self):
        action = super().action_plan_shift()
        if self.partner_id:
            action["context"]["default_partner_id"] = self.partner_id.id
        action["context"]["default_priority"] = self.priority
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('start_datetime') is False and vals.get('end_datetime') is False and vals.get('state') in ['3_in_progress', '4_completed']:
                raise UserError(self.env._("You can't unschedule this shift because it's already in progress or completed."))
        slots = super(PlanningSlot, self.with_context(slot_create=True, mail_create_nosubscribe=True)).create(vals_list)
        slots._subscribe_assigned_resources()
        # drop `slot_create`, otherwise a later write on the returned slots would
        # subscribe the creator again, even after they unfollowed the shift
        return slots.with_env(self.env)

    def write(self, vals):
        if (
            vals.get('start_datetime') is False
            and vals.get('end_datetime') is False
            and vals.get('state') not in ['3_in_progress', '4_completed']
            and any(slot for slot in self if slot.state in ['3_in_progress', '4_completed'])
        ):
            raise UserError(self.env._("You can't unschedule this shift because it's already in progress or completed."))
        if vals.get('state') == '1_draft':
            if not self.env.user.has_groups('planning.group_planning_manager') and not self.env.su:
                raise UserError(self.env._("You cannot set a slot to draft."))
            if any(slot for slot in self if slot.state in ['3_in_progress', '4_completed']):
                raise UserError(self.env._("You can't move this shift to draft because it is already in progress or completed."))
        switch_employees_before = {slot.id: slot.switch_employee_ids for slot in self}

        res = super().write(vals)
        if 'switch_employee_ids' in vals:
            for slot in self:
                if switch_employee := slot.switch_employee_ids - switch_employees_before[slot.id]:
                    slot.message_post(
                        body=self.env._(
                            '%(employee)s requested a replacement for this shift.',
                            employee=switch_employee.name,
                        ),
                        subtype_xmlid="planning_field_service.mt_replacement_requested",
                    )
        if {'resource_ids', 'state'} & vals.keys():
            self._subscribe_assigned_resources()
        return res

    def split_pill(self, values):
        res_id = super(PlanningSlot, self.with_context(reset_travel_times=False)).split_pill(values)
        self.browse(res_id).write({
            'travel_time_out': self.travel_time_out,
            'travel_distance_out': self.travel_distance_out,
            'travel_times_up_to_date': True,
        })
        self.write({
            'travel_time_out': 0.0,
            'travel_distance_out': 0.0,
        })
        return res_id

    def gantt_undo_drag_drop(self, drag_action, data=None):
        return super(PlanningSlot, self.with_context(reset_travel_times=False)).gantt_undo_drag_drop(drag_action, data)

    def undo_split_shift(self, start_datetime, end_datetime, resource_ids):
        if len(self) != 2:
            raise ValueError(self.env._("This method must take two slots in argument."))
        initial_shift, copied_shift = self
        if not (initial_shift.exists() and copied_shift.exists()):
            return False
        initial_shift.travel_time_out = copied_shift.travel_time_out
        initial_shift.travel_distance_out = copied_shift.travel_distance_out
        initial_shift.travel_times_up_to_date = True
        return super(PlanningSlot, self.with_context(reset_travel_times=False)).undo_split_shift(start_datetime, end_datetime, resource_ids)

    def _group_expand_partner_id(self, partners, domain):
        domain = Domain(domain)
        dom_tuples = [(cond.field_expr, cond.operator) for cond in domain.iter_conditions()]
        if ('start_datetime', '<') in dom_tuples and ('end_datetime', '>') in dom_tuples:
            if ('partner_id', '=') in dom_tuples or ('partner_id', 'ilike') in dom_tuples:
                filter_domain = self._expand_domain_m2o_groupby(domain, 'partner_id')
                return self.env['res.partner'].search(filter_domain)
            filters = Domain.AND([[('partner_id.active', '=', True)], self._expand_domain_dates(domain)])
            return self.env['planning.slot'].search(filters).mapped('partner_id')
        return partners

    def _get_report_base_filename(self):
        if len(self) == 1:
            return self.env._("Field Service Report - %(date)s", date=format_date(self.env, self.start_datetime))
        return self.env._("Field Service Report")

    def _get_is_intervention_report_available_domain(self):
        return Domain.FALSE

    def _get_intervention_reports_domain(self, additional_domain=None):
        if not self.env['res.groups']._is_feature_enabled('planning.group_field_service_allow_customer_report'):
            return Domain.FALSE
        domain = Domain.AND([
            [('partner_id', '!=', False), ('state', '=', '4_completed')],
            self._get_is_intervention_report_available_domain(),
            additional_domain or [],
        ])
        if self.env.user.share:
            domain &= Domain('partner_id', 'child_of', self.env.user.commercial_partner_id.id)
        elif not self.env.user.has_group('planning.group_planning_user'):
            domain = Domain.FALSE
        return domain

    def _get_send_report_action(self):
        template_id = self.env.ref('planning_field_service.mail_template_data_intervention_report').id
        self.message_subscribe(partner_ids=self.partner_id.ids)
        return {
            'name': self.env._("Send Field Service Report"),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_composition_mode': 'mass_mail' if len(self.ids) > 1 else 'comment',
                'default_model': 'planning.slot',
                'default_res_ids': self.ids,
                'default_template_id': template_id,
            },
        }

    def _show_portal_field_service(self):
        """
        Determine if we show field service information in the portal. Meant to be overriden in website_planning_field_service.
        """
        return True

    def _is_intervention_report_available(self):
        return False

    def _can_sign_report(self):
        return (
            self.state == '4_completed'
            and self.env['res.groups']._is_feature_enabled('planning.group_field_service_allow_customer_report')
            and self._is_intervention_report_available()
        )

    def _track_log_get_default_subtype(self, track_init_values):
        if 'state' in track_init_values:
            return self.env.ref('planning_field_service.mt_intervention_status_changed', raise_if_not_found=False)
        if 'resource_ids' in track_init_values:
            old_resource = track_init_values.get('resource_ids')
            new_resource = self.resource_ids
            if self.state != "1_draft":
                assigned, unassigned = new_resource - old_resource, old_resource - new_resource
                if not old_resource and assigned:
                    return self.env.ref("planning_field_service.mt_shift_assigned", raise_if_not_found=False)
                elif assigned:
                    return self.env.ref("planning_field_service.mt_shift_reassigned", raise_if_not_found=False)
                elif unassigned:
                    return self.env.ref("planning_field_service.mt_shift_unassigned", raise_if_not_found=False)
        if ({"start_datetime", "end_datetime"} & track_init_values.keys() and self.state == "2_published"):
            return self.env.ref("planning_field_service.mt_shift_rescheduled", raise_if_not_found=False)
        return super()._track_log_get_default_subtype(track_init_values)

    def _mail_get_message_subtypes(self):
        subtypes = super()._mail_get_message_subtypes()
        if self.company_id.planning_employee_unavailabilities != 'switch':
            subtypes -= self.env.ref('planning_field_service.mt_replacement_requested')
        return subtypes

    def _notify_get_recipients_groups(self, message, model_description):
        groups = super()._notify_get_recipients_groups(message, model_description)
        for group_id, _dummy, group_vals in groups:
            if group_id in ['portal_customer', 'customer', 'user']:
                group_vals.setdefault('button_access', {})
                if group_id in ['portal_customer', 'customer']:
                    if self and self.state in ['3_in_progress', '4_completed']:
                        group_vals['button_access']['title'] = self.env._('View Report')
                    else:
                        group_vals['has_button_access'] = False
                elif group_id == 'user':
                    group_vals['button_access']['title'] = self.env._('View Intervention')
        return groups

    def _notify_by_email_prepare_rendering_context(self, message, model_description=False,
                                                    force_email_company=False, force_email_lang=False,
                                                    force_header=False, force_footer=False,
                                                    force_record_name=False):
        if not force_record_name and self.partner_id and self.state in ['3_in_progress', '4_completed']:
            force_record_name = self.env._(
                'Field Service Report - %s',
                format_datetime(
                    self.env,
                    self.start_datetime,
                    dt_format='MMM d, YYYY',
                    tz=self.partner_id.tz or self.env.user.tz or 'UTC',
                    lang_code=get_lang(self.env, force_email_lang).code
                ),
            )
        return super()._notify_by_email_prepare_rendering_context(
            message, model_description=model_description,
            force_email_company=force_email_company, force_email_lang=force_email_lang,
            force_header=force_header, force_footer=force_footer,
            force_record_name=force_record_name,
        )

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        res = super()._message_auto_subscribe_followers(updated_values, default_subtype_ids)
        if self.env.context.get('slot_create') and self.env.user.active and not self.env.user.share:
            subtype = self.env.ref(
                "planning_field_service.mt_replacement_requested"
                if self.company_id.planning_employee_unavailabilities == "switch"
                else "planning_field_service.mt_shift_unassigned"
            )
            res.append((self.env.user.partner_id.id, [*default_subtype_ids, subtype.id], False))
        return res

    def _subscribe_assigned_resources(self):
        """ Subscribe the resources assigned to a published shift to the subtypes
        notifying them about the changes made to that shift.

        Done per record: ``_message_auto_subscribe_followers`` returns partners for
        the whole recordset, which would subscribe every resource to every shift of
        a batch write such as publishing a planning.
        """
        subtype_ids = [
            self.env.ref("planning_field_service.mt_shift_reassigned").id,
            self.env.ref("planning_field_service.mt_shift_rescheduled").id,
            self.env.ref("planning_field_service.mt_shift_unassigned").id,
        ]
        for slot in self.filtered(lambda s: s.state == "2_published"):
            users = slot.resource_ids.user_id.filtered(lambda u: u.active and not u.share)
            # already subscribed resources are skipped, their own subtype selection prevails
            if partners := users.partner_id - slot.message_follower_ids.partner_id:
                slot.message_subscribe(partner_ids=partners.ids, subtype_ids=subtype_ids)

    def _get_unplanned_slot_values(self):
        return {
            **super()._get_unplanned_slot_values(),
            'partner_id': self.partner_id.id,
        }

    def _get_ics_description_data(self):
        return {
            **super()._get_ics_description_data(),
            'partner': self.partner_id.name,
            'partner_phone': self.partner_phone,
        }

    def _send_geolocation(self):
        self.ensure_one()
        geolocation_message = None
        if self.env['res.groups']._is_feature_enabled('planning.group_field_service_allow_geolocation') and (geolocation := self.env.context.get('geolocation')):
            success = geolocation.get("success")
            latitude = 0
            longitude = 0
            localisation_start = False

            if success:
                latitude = geolocation["latitude"]
                longitude = geolocation["longitude"]
                localisation_start = self.env["base.geocoder"]._get_localisation(latitude=latitude, longitude=longitude)

                geolocation_message = self.env._("GPS Coordinates: %(localisation_start)s (%(latitude)s, %(longitude)s)",
                    localisation_start=localisation_start,
                    latitude=latitude,
                    longitude=longitude,
                )
            else:
                geolocation_message = geolocation.get("message", self.env._("Location error"))
        if geolocation_message:
            body = geolocation_message
            if latitude and latitude:
                body += Markup(" <a href='https://maps.google.com?q={latitude},{longitude}' target='_blank'>{label}</a>").format(
                    latitude=latitude,
                    longitude=longitude,
                    label=self.env._("View on Map")
                )
            self.message_post(body=body)

    def _reset_intervention_fields(self):
        self.ensure_one()
        self.partner_id = False
        self.resource_ids = False

    def _get_field_display_name(self, fname):
        display_name = super()._get_field_display_name(fname)
        if fname == 'partner_id' and self.partner_city:
            display_name = self.env._(
                '%(display_name)s (%(partner_city)s)',
                display_name=display_name,
                partner_city=self.partner_city,
            )
        return display_name

    def _action_complete(self, from_status_bar=False):
        self.ensure_one()
        vals = {'state': '4_completed'}
        if from_status_bar:
            self.write(vals)
            return
        now_utc = fields.Datetime.context_timestamp(self, fields.Datetime.now()).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        if self.start_datetime and self.start_datetime < now_utc:
            vals.update({
                'end_datetime': now_utc,
                'break_time': self.break_time,  # to prevent break_time recomputation in case end_datetime is updated
            })
        self.write(vals)
        self._send_geolocation()
        if not self._can_sign_report():
            self._send_intervention_rating_mail()

    def action_sign_in(self):
        self.ensure_one()
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now()).astimezone(ZoneInfo('UTC'))
        vals = {
            'start_datetime': fields.Datetime.to_string(now),
            'state': '3_in_progress',
        }
        if not self.end_datetime or now > self.end_datetime.astimezone(ZoneInfo('UTC')):
            delta = self.allocated_hours / len(self.employee_ids) if self.employee_ids else self.allocated_hours
            delta += self.break_time
            allocated_hours = self.allocated_hours
            if not delta:
                # means no allocated_hours and break time set due to no end_datetime probably
                allocated_hours = delta = 1  # 1 hour by default
            vals.update({
                'end_datetime': fields.Datetime.to_string(now + relativedelta(hours=delta)),
                'allocated_hours': allocated_hours,  # to prevent allocated_hours recomputation in case end_datetime is updated
                'break_time': self.break_time,  # to prevent break_time recomputation in case end_datetime is updated
            })
        self.write(vals)
        if not self.employee_public_ids:
            self.action_self_assign()
        self._send_geolocation()
        return self._get_records_action()

    def action_complete(self, from_status_bar=False):
        self.ensure_one()
        self._action_complete(from_status_bar)
        if from_status_bar:
            if self.partner_id:
                self.action_send_report()
            return

    def action_preview_worksheet(self):
        self.ensure_one()
        if not self._can_sign_report():
            return {}
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': self.get_portal_url()
        }

    def _can_show_sign_report_button(self):
        return (
            self.state in ['3_in_progress', '4_completed']
            and self.env['res.groups']._is_feature_enabled('planning.group_field_service_allow_customer_report')
            and self._is_intervention_report_available()
        )

    def action_sign_report(self):
        if not self._can_show_sign_report_button():
            return {}
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': f'{self.get_portal_url()}&is_sign_report=true',
        }

    def action_send(self):
        self.ensure_one()
        if self.state == '4_completed':
            return self._get_notification_action('danger', self.env._('This shift is already completed.'))
        notification = super().action_send()
        if notification and notification.get('tag', '') == 'display_notification' and notification['params']['type'] == 'success' and self.partner_id:
            self._send_intervention_scheduled()
        return notification

    def action_send_report(self):
        slots_with_report = self.filtered(lambda slot: slot._can_sign_report())
        if not slots_with_report:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': self.env._("There are no reports to send."),
                    'sticky': False,
                    'type': 'danger',
                },
            }
        action = slots_with_report._get_send_report_action()
        if not self.env.context.get('discard_logo_check') and self.env.is_admin() and not self.env.company.external_report_layout_id:
            layout_action = self.env['ir.actions.report']._action_configure_external_report_layout(action)
            action.pop('close_on_report_download', None)
            return layout_action
        return action

    def _send_intervention_scheduled(self):
        for company, slots in self.grouped('company_id').items():
            if company.field_service_confirmation_email:
                slots.message_post_with_source(
                    company.field_service_confirmation_mail_template_id,
                    message_type="comment",
                    email_layout_xmlid="mail.mail_notification_layout",
                    subtype_xmlid='mail.mt_comment',
                )

    def action_planning_publish_and_send(self):
        notification = super().action_planning_publish_and_send()
        if notification and notification.get('tag', '') == 'display_notification' and notification['params']['type'] == 'success' and self.partner_id:
            self.filtered('partner_id')._send_intervention_scheduled()
        return notification

    def action_view_task(self):
        self.ensure_one()
        return self.task_id._get_records_action() if self.task_id else {}

    def action_open_map_navigation(self):
        self.ensure_one()
        if not self.partner_id.city or not self.partner_id.country_id:
            return
        encoded_address = quote_plus(self.partner_id.contact_address_complete)
        url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_address}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new'
        }

    def action_open_ratings(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('planning_field_service.rating_rating_action_planning_field_service')
        if self.rating_count == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.rating_ids[0].id,
                'views': [(view_id, view_type) for view_id, view_type in action['views'] if view_type == 'form'],
            })
        return action

    # ---------------------------------------------------
    # Rating business
    # ---------------------------------------------------

    def _send_intervention_rating_mail(self, force_send=False):
        if not self.env['res.groups']._is_feature_enabled('planning.group_field_service_allow_customer_ratings'):
            return

        rating_template_id = self.env['ir.config_parameter'].sudo().get_int('planning_field_service.rating_shift_request_mail_template_id')
        mail_template_id = self.env['mail.template'].browse(rating_template_id)
        for slot in self:
            partner = slot.partner_id
            if partner and partner != self.env.user.partner_id and slot.state == '4_completed':
                slot.rating_send_request(mail_template_id, lang=slot.partner_id.lang, force_send=force_send)

    def _rating_get_operator(self):
        """ Override since we have employee_ids instead of employee_id """
        self.ensure_one()
        return self.employee_ids[:1].work_contact_id or self.env['res.partner']

    # ---------------------------------------------------
    # Public methods
    # ---------------------------------------------------

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        gantt_data = super().get_gantt_data(domain, groupby, read_specification, limit=limit, offset=offset, unavailability_fields=unavailability_fields, progress_bar_fields=progress_bar_fields, start_date=start_date, stop_date=stop_date, scale=scale)
        if scale != "day" or not self.env.user.has_group('planning.group_planning_manager'):
            return gantt_data

        def get_resource_work_location(resource, located):
            work_location = resource._get_work_location()
            if not (work_location.partner_latitude and work_location.partner_longitude) and work_location.id not in located:
                work_location.geo_localize()
                located.add(work_location.id)

            return {
                "contact_address_complete": work_location.contact_address_complete,
                "partner_latitude": work_location.partner_latitude,
                "partner_longitude": work_location.partner_longitude,
            }

        resource_ids = set()
        for record in gantt_data.get('records', []):
            if (resources := record.get('resource_ids')) and record.get('partner_id'):
                resource_ids |= set(resources)

        located = set()
        resource_work_locations = {
            resource.id: get_resource_work_location(resource, located)
            for resource in self.env['resource.resource'].browse(resource_ids)
        }
        gantt_data['resource_work_locations'] = resource_work_locations

        return gantt_data

    @api.model
    def _handle_mapbox_error(self, status_code, response_json=None):
        """Return a user-facing error message for a Mapbox API failure."""
        match status_code:
            case 401:
                return self.env._("Token invalid")
            case 403:
                return self.env._("Unauthorized connection")
            case 422 | 429:
                message = (response_json or {}).get('message') or ''
                match message:
                    case 'Route exceeds maximum distance limitation':
                        return self.env._("Some routing points are too far apart")
                    case 'Too Many Requests':
                        return self.env._("Too many requests, try again in a few minutes")
                return message or self.env._("Mapbox could not compute the route.")
            case 500:
                return self.env._("MapBox servers unreachable")
            case _:
                return self.env._("Mapbox could not be reached.")

    @api.model
    def _fetch_mapbox_driving_route(self, partners):
        """Fetch a driving route from Mapbox."""
        if len(partners) != 2 or modules.module.current_test or not self.env.registry.ready:
            return None, None
        map_box_token = self.env['ir.config_parameter'].sudo().get_str('web_enterprise.token_map_box')
        if not map_box_token:
            return None, self._handle_mapbox_error(401)

        waypoints = ';'.join(
            f"{partner.partner_longitude},{partner.partner_latitude}"
            for partner in partners
        )
        try:
            response = requests.get(
                f'https://api.mapbox.com/directions/v5/mapbox/driving/{waypoints}',
                params={
                    'access_token': map_box_token,
                    'steps': 'false',
                    'overview': 'false',
                    'geometries': 'geojson',
                },
                timeout=10,
            )
            response_json = response.json()
        except requests.exceptions.RequestException:
            return None, None
        except ValueError:
            response_json = None

        if not response.ok or not (response_json and response_json.get('routes')):
            return None, self._handle_mapbox_error(
                response.status_code if not response.ok else 422,
                response_json,
            )
        return response_json['routes'][0], None

    @api.model
    def _fetch_mapbox_isochrones(self, location, session):
        """Fetch the isochrone contours around `location` from Mapbox."""
        if modules.module.current_test or not self.env.registry.ready:
            return None, None
        map_box_token = self.env['ir.config_parameter'].sudo().get_str('web_enterprise.token_map_box')
        if not map_box_token:
            return None, self._handle_mapbox_error(401)

        try:
            response = session.get(
                f'https://api.mapbox.com/isochrone/v1/mapbox/driving/{location.partner_longitude},{location.partner_latitude}',
                params={
                    'access_token': map_box_token,
                    'denoise': 1,
                    'generalize': 500,
                    "polygons": "false",
                    'contours_minutes': "10,20,30,40",
                },
                timeout=10,
            )
            response_json = response.json()
        except requests.exceptions.RequestException:
            return None, None
        except ValueError:
            response_json = None

        if not response.ok or not (response_json and response_json.get('features')):
            return None, self._handle_mapbox_error(
                response.status_code if not response.ok else 422,
                response_json,
            )

        isochrones = {
            f['properties']['contour']: f['geometry']['coordinates']
            for f in response_json['features']
        }
        return dict(sorted(isochrones.items())), None

    @api.model
    def _estimate_travel_times_without_mapbox(self, locations):
        coordinates = [(x.id, x.partner_latitude, x.partner_longitude) for x in locations]
        estimated_travel_times = {(x.id, x.id): 0.0 for x in locations}
        for (source_id, source_lat, source_lon), (dest_id, dest_lat, dest_lon) in combinations(coordinates, 2):
            travel_time = _haversine_distance(source_lat, source_lon, dest_lat, dest_lon) / AVERAGE_SPEED_KMH * 60
            estimated_travel_times[source_id, dest_id] = travel_time
            estimated_travel_times[dest_id, source_id] = travel_time

        return estimated_travel_times

    @api.model
    def _estimate_travel_times_with_mapbox(self, locations):
        point_per_location_id = {
            location.id: _project_coordinates(location.partner_latitude, location.partner_longitude)
            for location in locations
        }

        estimated_travel_times = {}
        with requests.Session() as session:
            for source in locations:
                contours, error = self._fetch_mapbox_isochrones(source, session)
                if error:
                    raise UserError(error)
                if contours is None:
                    continue  # could not reach MapBox for this location: no travel time to/from it

                isochrones = {
                    minutes: _project_isochrone(contour)
                    for minutes, contour in contours.items()
                }
                origin_point = point_per_location_id[source.id]
                for destination_id, destination_point in point_per_location_id.items():
                    estimated_travel_times[source.id, destination_id] = (
                        _estimate_travel_time_with_isochrones(isochrones, origin_point, destination_point)
                        if destination_id != source.id
                        else 0.0
                    )

        return estimated_travel_times

    @api.model
    def update_slot_travel_times(self, slots, reschedule=False):
        if not self.env.user.has_group('planning.group_planning_manager'):
            return False

        PlanningSlot = self.env['planning.slot']
        allowed_fields = {
            'travel_time_in',
            'travel_time_out',
            'travel_distance_in',
            'travel_distance_out',
        }
        slots_to_update = PlanningSlot.with_context(reset_travel_times=False)
        updated_ids = []
        for slot in slots:
            if 'id' not in slot:
                continue

            fields_to_write = slot.keys() & allowed_fields
            if fields_to_write:
                vals = {field: slot[field] for field in fields_to_write}
                vals['travel_times_up_to_date'] = True
                slots_to_update.browse(slot['id']).write(vals)

            updated_ids.append(slot['id'])

        updated_slots = PlanningSlot.browse(dict.fromkeys(updated_ids))
        if reschedule:
            updated_slots._reschedule_with_travel_times()

        return True

    def _reschedule_with_travel_times(self):
        """ Reschedules the daily (non-published) shifts of human resources using travel times. """
        resources = self.resource_ids.filtered(lambda r: r.resource_type == 'user')
        if not resources:
            return {}

        user_tz = ZoneInfo(self.env.user.tz or 'UTC')
        window_start_tz = min(self.mapped('start_datetime')).replace(tzinfo=UTC).astimezone(user_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        window_end_tz = max(self.mapped('end_datetime')).replace(tzinfo=UTC).astimezone(user_tz).replace(hour=0, minute=0, second=0, microsecond=0) + relativedelta(days=1)
        window_start = window_start_tz.astimezone(UTC).replace(tzinfo=None)
        window_end = window_end_tz.astimezone(UTC).replace(tzinfo=None)

        _flexible, schedule_intervals_per_resource_id, _hours_per_day, _hours_per_week = self._get_schedule_intervals_per_resource_id(resources, window_start_tz, window_end_tz)

        same_period_shifts = self.search([
            ('resource_ids', 'in', resources.ids),
            ('end_datetime', '>', window_start),
            ('start_datetime', '<', window_end),
        ], order="start_datetime")

        shifts_per_resource_id = defaultdict(list)
        for shift in same_period_shifts:
            for resource_id in shift.resource_ids.ids:
                shifts_per_resource_id[resource_id].append(shift)

        now_utc = fields.Datetime.now().replace(tzinfo=UTC)
        protected_fields = ['allocated_hours', 'allocated_percentage', 'break_time']
        for resource in resources:
            resource_schedule = schedule_intervals_per_resource_id.get(resource.id)
            previous_end = None
            for shift in shifts_per_resource_id[resource.id]:
                if shift not in self or shift.state != '1_draft':
                    previous_end = shift.end_datetime.replace(tzinfo=UTC)
                    continue

                if previous_end is not None:
                    anchor = previous_end
                elif resource_schedule:
                    moment = shift.start_datetime.replace(tzinfo=UTC)
                    work_from, _work_to = self._get_schedule_block_start_stop(resource_schedule, moment)
                    anchor = max(work_from.astimezone(UTC), now_utc)
                else:
                    anchor = max(shift.start_datetime.replace(tzinfo=UTC), now_utc)

                new_start = (anchor + timedelta(hours=shift.travel_time_in)).replace(tzinfo=None)
                new_end = new_start + timedelta(hours=shift.allocated_hours)

                with self.env.protecting([self._fields[fname] for fname in protected_fields], shift):
                    shift.with_context(reset_travel_times=False).write({
                        'start_datetime': new_start,
                        'end_datetime': new_end,
                    })
                previous_end = new_end.replace(tzinfo=UTC)

        return True

    @api.model
    def action_generate_live_map_demo_data(self):
        live_locations = [
            ('hr.employee_mit', relativedelta(), 'base.res_partner_address_1'),
            ('hr.employee_jth', relativedelta(hours=2), 'base.res_partner_address_3'),
            ('hr.employee_lur', relativedelta(minutes=10), 'base.res_partner_address_16'),
            ('hr.employee_niv', relativedelta(hours=1, minutes=20), 'base.res_partner_address_18'),
        ]
        now = fields.Datetime.now()
        for employee_xmlid, ago, partner_xmlid in live_locations:
            employee = self.env.ref(employee_xmlid, raise_if_not_found=False)
            if not (employee and employee.resource_id):
                continue
            resource = employee.resource_id
            # If the resource is already on a shift with a customer, use that one instead
            # of creating a demo intervention that would conflict with it.
            current_slot = self.search([
                ('resource_ids', 'in', resource.ids),
                ('partner_id', '!=', False),
                ('start_datetime', '<=', now),
                ('end_datetime', '>=', now),
            ], limit=1)
            if current_slot:
                partner = current_slot.partner_id
            else:
                partner = self.env.ref(partner_xmlid, raise_if_not_found=False)
                if not partner:
                    continue
                self.create({
                    'resource_ids': resource.ids,
                    'partner_id': partner.id,
                    'start_datetime': now - relativedelta(minutes=10),
                    'end_datetime': now + relativedelta(hours=1),
                })

            partner._ensure_geolocalized()
            resource.write({
                'live_latitude': partner.partner_latitude + random.uniform(-0.1, 0.1),
                'live_longitude': partner.partner_longitude + random.uniform(-0.1, 0.1),
                'live_location_last_update': now - ago,
            })

        return True

    # ---------------------------------------------------
    # Field Service Auto-plan
    # ---------------------------------------------------

    def auto_plan_id(self):
        self.ensure_one()
        if self.state == '3_in_progress':
            return self._get_notification_action('danger', self.env._('This shift is already in progress.'))
        if self.state == '4_completed':
            return self._get_notification_action('danger', self.env._('This shift is already completed.'))
        return super().auto_plan_id()

    @api.model
    def _auto_plan_estimate_travel_times(self, open_shifts, extra_partners, resource_work_locations):
        all_locations = (
            resource_work_locations
            | open_shifts.partner_id
            | extra_partners
        )
        all_geolocalized_locations = all_locations.filtered(lambda x: x._ensure_geolocalized())
        if self.env['ir.config_parameter'].sudo().get_str('web_enterprise.token_map_box'):
            return self._estimate_travel_times_with_mapbox(all_geolocalized_locations)

        return self._estimate_travel_times_without_mapbox(all_geolocalized_locations)

    @api.model
    def _auto_plan_result(self, assigned_shifts, auto_plan_data):
        return {
            **super()._auto_plan_result(assigned_shifts, auto_plan_data),
            'original_dates_per_shift_id': auto_plan_data['original_dates_per_shift_id'],
        }

    @api.model
    def action_rollback_auto_plan_ids(self, shifts_data):
        super().action_rollback_auto_plan_ids(shifts_data)

        shift_ids_per_dates = defaultdict(list)
        for shift_id, dates in (shifts_data.get('original_dates_per_shift_id') or {}).items():
            shift_ids_per_dates[tuple(dates)].append(int(shift_id))

        fields_to_protect = ['allocated_hours', 'allocated_percentage', 'break_time']
        for (start, end), shift_ids in shift_ids_per_dates.items():
            shifts = self.browse(shift_ids)
            with self.env.protecting([self._fields[fname] for fname in fields_to_protect], shifts):
                shifts.write({'start_datetime': start, 'end_datetime': end})

    @api.model
    def _auto_plan_search_open_shifts(self, view_domain):
        groups, open_shifts = super()._auto_plan_search_open_shifts(view_domain)
        if self._auto_plan_get_requested_period():
            open_shifts |= self.search(Domain.AND([
                Domain(view_domain).map_conditions(
                    lambda cond: Domain(cond.field_expr, '=', False)
                    if cond.field_expr in ('start_datetime', 'end_datetime')
                    else cond,
                ),
                [
                    ('resource_ids', '=', False),
                    ('partner_id', '!=', False),
                ],
            ]))
        return groups, open_shifts

    @api.model
    def _prepare_auto_plan_data(self, view_domain):
        auto_plan_data = super()._prepare_auto_plan_data(view_domain)
        auto_plan_data['original_dates_per_shift_id'] = {}
        auto_plan_data['open_shifts'] = auto_plan_data['open_shifts'].sorted(
            key=lambda shift: (shift.state == '1_draft', -int(shift.priority), -shift.allocated_hours),
        )

        open_shifts = auto_plan_data['open_shifts'].filtered(lambda s: s.partner_id)
        if not open_shifts:
            return auto_plan_data
        resources = auto_plan_data['resources']
        resources_and_materials = auto_plan_data['resources_and_materials']
        same_days_shifts = auto_plan_data['same_days_shifts']

        work_location_per_resource_id = {resource.id: resource._get_work_location() for resource in resources}
        auto_plan_data['work_location_per_resource_id'] = work_location_per_resource_id
        work_locations = self.env['res.partner'].union(work_location_per_resource_id.values())

        materials = resources.get_materials_assigned_to_human_resources()
        auto_plan_data['material_ids_per_resource_id'] = {
            resource_id: assigned.ids
            for resource_id, assigned in materials.grouped(lambda m: m.assigned_employee_id.resource_id.id).items()
        }

        intervals_per_resource_id = defaultdict(list)
        for other_shift in same_days_shifts:
            for resource_id in (other_shift.resource_ids & resources_and_materials).ids:
                intervals_per_resource_id[resource_id].append((other_shift.start_datetime, other_shift.end_datetime, other_shift))

        auto_plan_data['busy_intervals_per_resource_id'] = defaultdict(
            lambda: Intervals(keep_distinct=True),
            {
                resource_id: Intervals(intervals, keep_distinct=True)
                for resource_id, intervals in intervals_per_resource_id.items()
            },
        )

        auto_plan_data['travel_times'] = self._auto_plan_estimate_travel_times(open_shifts, same_days_shifts.partner_id, work_locations)

        return auto_plan_data

    def _auto_plan_assign_resource(self, shift, auto_plan_data):
        if not shift.partner_id:
            return super()._auto_plan_assign_resource(shift, auto_plan_data)
        if shift.state in ['3_in_progress', '4_completed'] or not shift.partner_id._is_geolocalized():
            return False  # we can't check travel feasibility without a location: skip the shift

        user_tz = auto_plan_data['user_tz']
        resources_dicts = auto_plan_data['resources_dicts']
        schedule_intervals_per_resource_id = auto_plan_data['schedule_intervals_per_resource_id']
        now_utc = fields.Datetime.now().replace(tzinfo=UTC)

        PlanningSlot = self.env['planning.slot']
        if not shift.start_datetime or not shift.end_datetime:
            period_start, period_end = auto_plan_data['requested_period']
            shift_intervals = Intervals([(
                max(period_start.replace(tzinfo=UTC), now_utc),
                period_end.replace(tzinfo=UTC),
                PlanningSlot,
            )])
        elif shift.state == '1_draft':
            day_start = shift.start_datetime.astimezone(user_tz).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            shift_intervals = Intervals([(max(day_start, now_utc.astimezone(user_tz)), day_end, PlanningSlot)])
        else:
            shift_intervals = Intervals([(
                shift.start_datetime.replace(tzinfo=UTC),
                shift.end_datetime.replace(tzinfo=UTC),
                PlanningSlot,
            )])

        needed_duration = timedelta(hours=shift.allocated_hours)
        for resources_dict in resources_dicts:
            resource_ids = shift._get_resources_dict_values(resources_dict)
            best_resource = best_start = best_end = best_travel_time = None

            for resource in self.env['resource.resource'].browse(resource_ids):
                split_shift_intervals = shift_intervals & schedule_intervals_per_resource_id[resource.id]
                if not split_shift_intervals:
                    continue  # the shift is out of the resource's working schedule

                if resource._is_flexible():
                    _rate, is_overloaded = self._auto_plan_get_flexible_resource_load(resource, shift, split_shift_intervals, auto_plan_data)
                    if is_overloaded:
                        continue

                busy_intervals = auto_plan_data['busy_intervals_per_resource_id'][resource.id]
                for material_id in auto_plan_data['material_ids_per_resource_id'].get(resource.id, []):
                    busy_intervals |= auto_plan_data['busy_intervals_per_resource_id'][material_id]
                if busy_intervals:
                    busy_intervals_aware = Intervals([
                        (busy_start.replace(tzinfo=UTC), busy_end.replace(tzinfo=UTC), busy_shifts)
                        for busy_start, busy_end, busy_shifts in busy_intervals
                    ])
                    free_intervals = split_shift_intervals - busy_intervals_aware
                else:
                    # nothing booked yet: the whole working schedule is free
                    free_intervals = split_shift_intervals

                for gap_start_tz, gap_stop_tz, _dummy in free_intervals:
                    placement = self._auto_plan_get_gap_placement(resource, shift, gap_start_tz, gap_stop_tz, needed_duration, auto_plan_data)
                    if placement and (best_travel_time is None or placement[2] < best_travel_time):
                        best_start, best_end, best_travel_time = placement
                        best_resource = resource

            if best_resource:
                self._auto_plan_confirm_assignment(shift, best_resource, best_start, best_end, auto_plan_data)
                return True

        return False

    def _auto_plan_get_neighbouring_shifts(self, resource, start, end, auto_plan_data):
        busy_intervals = auto_plan_data['busy_intervals_per_resource_id'][resource.id]

        previous_interventions = next_interventions = None
        for other_start, other_stop, other_shifts in busy_intervals:
            partners = other_shifts.partner_id
            if not partners:
                continue
            if other_stop <= start:
                previous_interventions = (partners, other_stop)
            elif other_start >= end:
                next_interventions = (partners, other_start)
                break
        return previous_interventions, next_interventions

    def _get_schedule_block_start_stop(self, resource_schedule, moment):
        """ Find the block the contains `moment` by scanning the `resource_schedule`. """
        for block_start, block_stop, _dummy in resource_schedule:
            if block_start <= moment < block_stop:
                return block_start, block_stop
        return None

    def _auto_plan_get_flexible_resource_load(self, resource, shift, split_shift_intervals, auto_plan_data):
        rate, is_overloaded = super()._auto_plan_get_flexible_resource_load(resource, shift, split_shift_intervals, auto_plan_data)
        return rate, is_overloaded or rate > 1

    def _auto_plan_get_gap_placement(self, resource, shift, gap_start_tz, gap_stop_tz, needed_duration, auto_plan_data):
        """ Where `shift` can start inside this free gap for `resource`, accounting for travel times.
            :return: (start, end, total travel time in minutes), or None if the shift cannot fit the gap.
        """
        if gap_stop_tz - gap_start_tz < needed_duration:
            return None
        gap_start = gap_start_tz.astimezone(UTC).replace(tzinfo=None)
        gap_stop = gap_stop_tz.astimezone(UTC).replace(tzinfo=None)

        partner = shift.partner_id
        travel_times = auto_plan_data['travel_times']
        work_location = auto_plan_data['work_location_per_resource_id'][resource.id]
        previous_interventions, next_interventions = self._auto_plan_get_neighbouring_shifts(resource, gap_start, gap_stop, auto_plan_data)
        block_start, block_stop = self._get_schedule_block_start_stop(auto_plan_data['schedule_intervals_per_resource_id'][resource.id], gap_start_tz)

        origins, previous_end = previous_interventions or (work_location, block_start.astimezone(UTC).replace(tzinfo=None))
        destinations, next_start = next_interventions or (work_location, block_stop.astimezone(UTC).replace(tzinfo=None))

        if not origins or not destinations:
            return None

        travel_in = max(travel_times.get((origin.id, partner.id)) for origin in origins)
        travel_out = max(travel_times.get((partner.id, destination.id)) for destination in destinations)
        if travel_in is None or travel_out is None:
            return None

        start = max(gap_start, previous_end + timedelta(minutes=travel_in))
        end = start + needed_duration
        if end > gap_stop or end + timedelta(minutes=travel_out) > next_start:
            return None

        return start, end, travel_in + travel_out

    def _auto_plan_confirm_assignment(self, shift, resource, start, end, auto_plan_data):
        auto_plan_data['original_dates_per_shift_id'][shift.id] = (
            fields.Datetime.to_string(shift.start_datetime),
            fields.Datetime.to_string(shift.end_datetime),
        )
        original_allocated_hours = shift.allocated_hours
        shift.write({'start_datetime': start, 'end_datetime': end})
        shift.resource_ids |= resource
        new_interval = Intervals([(start, end, shift)], keep_distinct=True)
        auto_plan_data['busy_intervals_per_resource_id'][resource.id] |= new_interval
        for material_id in auto_plan_data['material_ids_per_resource_id'].get(resource.id, []):
            auto_plan_data['busy_intervals_per_resource_id'][material_id] |= new_interval
        self._auto_plan_register_assignment(shift, resource, original_allocated_hours, auto_plan_data)
