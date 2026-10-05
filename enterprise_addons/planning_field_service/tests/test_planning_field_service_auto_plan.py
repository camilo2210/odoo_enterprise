# Part of Odoo. See LICENSE file for full copyright and licensing details

import math
from datetime import timedelta
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import freeze_time

from odoo.addons.planning_field_service.models.planning_slot import (
    EARTH_RADIUS_KM,
    _distance_to_contour,
    _estimate_travel_time_with_isochrones,
    _point_in_contour,
    _project_coordinates,
    _project_isochrone,
)

from .common import TestPlanningFieldServiceCommon


class TestPlanningFieldServiceIsochroneMath(TestPlanningFieldServiceCommon):
    """Pure-math tests for the isochrone projection/interpolation helpers: no DB/HTTP involved."""

    def test_project_coordinates_x_is_linear_in_longitude(self):
        # The Mercator x-axis only depends on longitude, regardless of latitude.
        x0, _y0 = _project_coordinates(0.0, 0.0)
        x1, _y1 = _project_coordinates(0.0, 1.0)
        x1_at_60, _y1_at_60 = _project_coordinates(60.0, 1.0)
        self.assertEqual(x0, 0.0)
        self.assertAlmostEqual(x1, math.radians(1.0) * EARTH_RADIUS_KM)
        self.assertEqual(x1, x1_at_60)

    def test_project_coordinates_y_is_zero_at_equator(self):
        _x, y = _project_coordinates(0.0, 0.0)
        self.assertAlmostEqual(y, 0.0)

    def test_project_coordinates_y_grows_faster_away_from_equator(self):
        # Web Mercator inflates areas near the poles: the same 1° step in latitude covers
        # more projected distance the further away from the equator it is taken.
        _x, y_at_1 = _project_coordinates(1.0, 0.0)
        _x, y_at_60 = _project_coordinates(60.0, 0.0)
        _x, y_at_61 = _project_coordinates(61.0, 0.0)
        step_at_equator = y_at_1  # from 0° to 1°
        step_at_60 = y_at_61 - y_at_60  # from 60° to 61°
        self.assertGreater(step_at_60, step_at_equator)

    def test_point_in_contour_inside_and_outside(self):
        square_10 = [(-10, -10), (10, -10), (10, 10), (-10, 10)]
        self.assertTrue(_point_in_contour((0, 0), square_10))
        self.assertFalse(_point_in_contour((15, 0), square_10))

    def test_distance_to_contour(self):
        square_10 = [(-10, -10), (10, -10), (10, 10), (-10, 10)]
        self.assertAlmostEqual(_distance_to_contour((15, 0), square_10), 5.0)
        self.assertAlmostEqual(_distance_to_contour((0, 0), square_10), 10.0)

    def test_project_isochrone_projects_each_contour_point(self):
        raw_contour = [(0.0, 1.0), (1.0, 0.0)]  # (longitude, latitude) pairs, as MapBox returns them
        projected = _project_isochrone(raw_contour)
        self.assertEqual(projected, [
            _project_coordinates(1.0, 0.0),
            _project_coordinates(0.0, 1.0),
        ])

    def test_estimate_travel_time_inside_innermost_contour(self):
        square_10 = [(-10, -10), (10, -10), (10, 10), (-10, 10)]
        square_20 = [(-20, -20), (20, -20), (20, 20), (-20, 20)]
        isochrones = {10: square_10, 20: square_20}
        self.assertEqual(_estimate_travel_time_with_isochrones(isochrones, (0.0, 0.0), (5, 0)), 5)

    def test_estimate_travel_time_between_two_contours(self):
        square_10 = [(-10, -10), (10, -10), (10, 10), (-10, 10)]
        square_20 = [(-20, -20), (20, -20), (20, 20), (-20, 20)]
        isochrones = {10: square_10, 20: square_20}
        self.assertEqual(_estimate_travel_time_with_isochrones(isochrones, (0.0, 0.0), (15, 0)), 15)

    def test_estimate_travel_time_beyond_outermost_contour(self):
        square_10 = [(-10, -10), (10, -10), (10, 10), (-10, 10)]
        square_20 = [(-20, -20), (20, -20), (20, 20), (-20, 20)]
        isochrones = {10: square_10, 20: square_20}
        self.assertEqual(_estimate_travel_time_with_isochrones(isochrones, (0.0, 0.0), (30, 0)), 30)

    def test_estimate_travel_time_returns_none_with_a_single_contour(self):
        square_10 = [(-10, -10), (10, -10), (10, 10), (-10, 10)]
        isochrones = {10: square_10}
        self.assertIsNone(_estimate_travel_time_with_isochrones(isochrones, (0.0, 0.0), (30, 0)))

    def test_estimate_travel_time_returns_none_when_band_is_degenerate(self):
        square_10 = [(-10, -10), (10, -10), (10, 10), (-10, 10)]
        square_20 = [(-20, -20), (20, -20), (20, 20), (-20, 20)]
        # Contours mislabeled/out of order: the "20 minutes" ring is smaller than the "10 minutes"
        # one, so past both of them the band width comes out negative.
        isochrones = {10: square_20, 20: square_10}
        self.assertIsNone(_estimate_travel_time_with_isochrones(isochrones, (0.0, 0.0), (30, 0)))


@freeze_time('2026-01-06 08:00:00')
class TestPlanningFieldServiceAutoPlan(TestPlanningFieldServiceCommon):
    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_str('web_enterprise.token_map_box', 'fake-token')
        self._open_shift_ids = []

    def _create_open_shift(self, partner, **values):
        shift = self.env['planning.slot'].create({
            'name': 'Open shift',
            'partner_id': partner.id,
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
            'state': '2_published',
            **values,
        })
        self._open_shift_ids.append(shift.id)
        return shift

    def _auto_plan_context(self):
        return {
            'default_start_datetime': fields.Datetime.to_string(fields.Datetime.now()),
            'default_end_datetime': fields.Datetime.to_string(fields.Datetime.now() + relativedelta(hours=1)),
        }

    def _run_auto_plan(self):
        """Run the bulk auto-plan over every open shift created by this test (see
        `_open_shift_ids`), with every MapBox isochrone call mocked out so no real network
        call is made. Returns the mock, so tests can inspect which locations were queried."""
        with patch.object(
            self.env['planning.slot'].__class__,
            '_fetch_mapbox_isochrones',
            return_value=({}, None),
        ) as mock_isochrones:
            self.env['planning.slot'].with_context(**self._auto_plan_context()).auto_plan_ids([('id', 'in', self._open_shift_ids)])
        return mock_isochrones

    def _queried_locations(self, mock_isochrones):
        return {call.args[0] for call in mock_isochrones.call_args_list}

    def test_auto_plan_ids_falls_back_to_haversine_without_mapbox_token(self):
        self.env['ir.config_parameter'].sudo().set_str('web_enterprise.token_map_box', '')
        self.partner.write({'partner_latitude': 50.85, 'partner_longitude': 4.35})
        self._create_open_shift(self.partner)
        mock_isochrones = self._run_auto_plan()  # should not raise, and never touch MapBox
        mock_isochrones.assert_not_called()

    def test_auto_plan_ids_propagates_mapbox_error(self):
        self.partner.write({'partner_latitude': 50.85, 'partner_longitude': 4.35})
        self._create_open_shift(self.partner)
        with patch.object(
            self.env['planning.slot'].__class__, '_fetch_mapbox_isochrones', return_value=(None, 'Token invalid'),
        ):
            with self.assertRaises(UserError):
                self.env['planning.slot'].with_context(**self._auto_plan_context()).auto_plan_ids([('id', 'in', self._open_shift_ids)])

    def test_all_locations_includes_company_address(self):
        company_partner = self.intervention.company_id.partner_id
        company_partner.write({'partner_latitude': 50.8503, 'partner_longitude': 4.3517})
        self._create_open_shift(self.partner)  # role-less: sweeps every resource in as a candidate
        mock_isochrones = self._run_auto_plan()
        self.assertIn(company_partner, self._queried_locations(mock_isochrones))

    def test_all_locations_includes_resource_work_location(self):
        work_location = self.env['res.partner'].create({
            'name': "George's Depot",
            'partner_latitude': 50.4669,
            'partner_longitude': 4.8675,
        })
        self.george_employee.address_id = work_location.id
        self._create_open_shift(self.partner)  # role-less: sweeps George in via `_get_open_shifts_resources`
        mock_isochrones = self._run_auto_plan()
        self.assertIn(work_location, self._queried_locations(mock_isochrones))

    def test_all_locations_includes_other_intervention_today(self):
        other_customer = self.env['res.partner'].create({
            'name': 'Another Customer Today',
            'partner_latitude': 50.6326,
            'partner_longitude': 5.5797,
        })
        self.env['planning.slot'].create({
            'name': "George's other job today",
            'partner_id': other_customer.id,
            'resource_ids': self.george_employee.resource_id.ids,
            'start_datetime': fields.Datetime.now().replace(hour=13, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=16, minute=0, second=0),
            'state': '2_published',
        })
        self._create_open_shift(self.partner)  # sweeps George into `resources`
        mock_isochrones = self._run_auto_plan()
        self.assertIn(other_customer, self._queried_locations(mock_isochrones))

    def test_all_locations_includes_open_shift_customer(self):
        shift_customer = self.env['res.partner'].create({
            'name': 'Open Shift Customer',
            'partner_latitude': 50.4542,
            'partner_longitude': 3.9523,
        })
        self._create_open_shift(shift_customer)
        mock_isochrones = self._run_auto_plan()
        self.assertIn(shift_customer, self._queried_locations(mock_isochrones))


@freeze_time('2026-01-06 08:00:00')
class TestPlanningFieldServiceAutoPlanAssignment(TestPlanningFieldServiceCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.tz = 'UTC'
        cls.env['ir.config_parameter'].sudo().set_str('web_enterprise.token_map_box', '')
        cls.role = cls.env['planning.role'].create({'name': 'Role'})
        cls.customer = cls.env['res.partner'].create({
            'name': 'Customer',
            'partner_latitude': 50.85,
            'partner_longitude': 4.35,
        })

    def setUp(self):
        super().setUp()
        self._open_shift_ids = []

    def _create_resource(self, name, attendances, work_location_coords=(50.85, 4.35), role=None):
        employee = self.env['hr.employee'].create({
            'name': name,
            'tz': 'UTC',
            'resource_calendar_id': self.env['resource.calendar'].create({
                'name': f'{name} calendar',
                'attendance_ids': [
                    Command.create({'dayofweek': '1', 'hour_from': hour_from, 'hour_to': hour_to})
                    for hour_from, hour_to in attendances
                ],
            }).id,
            'address_id': self.env['res.partner'].create({
                'name': f'{name} work location',
                'partner_latitude': work_location_coords[0],
                'partner_longitude': work_location_coords[1],
            }).id,
        })
        employee.resource_id.role_ids = [Command.link((role or self.role).id)]
        return employee.resource_id

    def _create_decoy(self):
        """A second role, resource and shift - unrelated to whatever scenario a test is
        actually exercising - present alongside it to prove the auto-plan tells them apart,
        rather than only getting the right answer because there's nothing else in the
        database. The shift has no customer, so this also exercises the base (non
        field-service) assignment path within the very same `auto_plan_ids` call."""
        decoy_role = self.env['planning.role'].create({'name': 'Decoy Role'})
        decoy_resource = self._create_resource('Sophie', [(8, 17)], role=decoy_role)
        decoy_shift = self.env['planning.slot'].create({
            'name': 'Decoy shift',
            'role_id': decoy_role.id,
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=9, minute=0, second=0),
            'allocated_hours': 1,
            'state': '2_published',
        })
        self._open_shift_ids.append(decoy_shift.id)
        return decoy_resource, decoy_shift

    def _create_open_shift(self, start_hour, end_hour, allocated_hours, priority=None, state='2_published'):
        now = fields.Datetime.now()
        values = {
            'name': 'Open shift',
            'partner_id': self.customer.id,
            'role_id': self.role.id,
            'start_datetime': now.replace(hour=start_hour, minute=0, second=0),
            'end_datetime': now.replace(hour=end_hour, minute=0, second=0),
            'allocated_hours': allocated_hours,
            'state': state,
        }
        if priority is not None:
            values['priority'] = priority
        shift = self.env['planning.slot'].create(values)
        self._open_shift_ids.append(shift.id)
        return shift

    def _create_dateless_shift(self, priority=None, allocated_hours=2):
        values = {
            'name': 'Open shift',
            'partner_id': self.customer.id,
            'role_id': self.role.id,
            'allocated_hours': allocated_hours,
            'state': '1_draft',
        }
        if priority is not None:
            values['priority'] = priority
        shift = self.env['planning.slot'].with_context(planning_keep_default_datetime=True).create(values)
        self.assertFalse(shift.start_datetime, "sanity check: this shift must start out with no dates at all")
        self._open_shift_ids.append(shift.id)
        return shift

    def _run_auto_plan(self, period=relativedelta(hours=1)):
        context = {
            'default_start_datetime': fields.Datetime.to_string(fields.Datetime.now()),
            'default_end_datetime': fields.Datetime.to_string(fields.Datetime.now() + period),
            'add_materials_assigned_to_employees': True,
        }
        with patch.object(self.env['planning.slot'].__class__, '_fetch_mapbox_isochrones') as mock_isochrones:
            result = self.env['planning.slot'].with_context(**context).auto_plan_ids([('id', 'in', self._open_shift_ids)])
            mock_isochrones.assert_not_called()
        return result

    def test_auto_plan_narrows_shift_to_the_gap_around_a_break(self):
        #   Time (UTC) ->      8h        9h        10h       11h       12h       13h       14h
        #                      |---------|---------|---------|---------|---------|---------|
        #   customer window:   [===========================================================]
        #   George's calendar: [               free (4h)               |  lunch  |free (1h)]
        #                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^          ^^^^^^^^^^
        #                      gap A: 8h-12h (4h)                                gap B: 13h-14h (1h)
        #
        #   allocated_hours = 3h: gap A (4h) is big enough on its own, gap B (1h) isn't.
        #   George's work location is a realistic 10 real-world minutes away from the customer
        #   (haversine, no MapBox token) - a technician always has to drive there first, so
        #   sitting right on top of the customer (like most other tests in this class do, to
        #   isolate the gap logic from travel-time arithmetic) would be unrealistic here.
        #   → shift is narrowed to gap A, starting as early as it can be reached: 8h10-11h10.
        #   (Sophie, from `_create_decoy`, has a different role and no customer on her shift -
        #   she's here to prove none of that gets mixed up with George's.)
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource(
            'George', [(8, 12), (13, 14)],
            work_location_coords=(50.85 + math.degrees(10 / EARTH_RADIUS_KM), 4.35),  # 10 real-world minutes away
        )
        shift = self._create_open_shift(start_hour=8, end_hour=14, allocated_hours=3)

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (shift | decoy_shift).ids)
        self.assertEqual(shift.resource_ids, george)
        self.assertAlmostEqual(shift.start_datetime, fields.Datetime.now().replace(hour=8, minute=10), delta=timedelta(seconds=1))
        self.assertAlmostEqual(shift.end_datetime, fields.Datetime.now().replace(hour=11, minute=10), delta=timedelta(seconds=1))
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_rollback_restores_a_published_shift_to_its_original_wide_window(self):
        #   A *published* shift isn't spared either: `allocated_hours = 3h` inside an 8h-14h
        #   window (`allocated_percentage` well under 100%) still gets narrowed down to
        #   whichever gap actually fits (same setup as
        #   `test_auto_plan_narrows_shift_to_the_gap_around_a_break`, 8h-14h narrowed to
        #   8h10-11h10) - undoing it must restore the original 8h-14h window, not leave it
        #   parked at the narrowed one with just the resource unassigned again.
        george = self._create_resource(
            'George', [(8, 12), (13, 14)],
            work_location_coords=(50.85 + math.degrees(10 / EARTH_RADIUS_KM), 4.35),  # 10 real-world minutes away
        )
        shift = self._create_open_shift(start_hour=8, end_hour=14, allocated_hours=3)

        result = self._run_auto_plan()
        self.assertEqual(shift.resource_ids, george)
        self.assertAlmostEqual(shift.start_datetime, fields.Datetime.now().replace(hour=8, minute=10), delta=timedelta(seconds=1))

        self.env['planning.slot'].action_rollback_auto_plan_ids(result)

        shift.invalidate_recordset()
        self.assertFalse(shift.resource_ids)
        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=8))
        self.assertEqual(shift.end_datetime, fields.Datetime.now().replace(hour=14))

    def test_auto_plan_skips_a_gap_too_short_for_a_later_one_that_fits(self):
        #   Time (UTC) ->      8h        9h        10h       11h       12h       13h       14h
        #                      |---------|---------|---------|---------|---------|---------|
        #   customer window:   [===========================================================]
        #   George's calendar: [  free   |  busy   |               free (4h)               ]
        #                      ^^^^^^^^^^          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        #                      gap A: 8h-9h (1h)   gap B: 10h-14h (4h)
        #
        #   allocated_hours = 3h: gap A (1h) is too short and is skipped, gap B (4h) fits.
        #   → shift is narrowed to gap B, starting as early as possible within it: 10h-13h.
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(8, 9), (10, 14)])
        shift = self._create_open_shift(start_hour=8, end_hour=14, allocated_hours=3)

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (shift | decoy_shift).ids)
        self.assertEqual(shift.resource_ids, george)
        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=10))
        self.assertEqual(shift.end_datetime, fields.Datetime.now().replace(hour=13))
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_leaves_shift_open_when_no_single_gap_is_long_enough(self):
        #   Time (UTC) ->      8h        9h        10h       11h       12h       13h       14h
        #                      |---------|---------|---------|---------|---------|---------|
        #   customer window:   [===========================================================]
        #   George's calendar: [               free (4h)               |  lunch  |free (1h)]
        #                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^          ^^^^^^^^^^
        #                      gap A: 8h-12h (4h)                                gap B: 13h-14h (1h)
        #
        #   allocated_hours = 5h: gap A + gap B add up to 5h of free time, but the job can't
        #   be split around the lunch break, and neither gap alone reaches 5h.
        #   → no candidate fits: the shift is left unassigned. Sophie's own (unrelated) shift
        #   is still expected to succeed, proving the rest of the batch keeps working normally.
        decoy_resource, decoy_shift = self._create_decoy()
        self._create_resource('George', [(8, 12), (13, 14)])
        shift = self._create_open_shift(start_hour=8, end_hour=14, allocated_hours=5)

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], decoy_shift.ids)
        self.assertFalse(shift.resource_ids)
        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=8))
        self.assertEqual(shift.end_datetime, fields.Datetime.now().replace(hour=14))
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_picks_the_resource_with_the_shortest_travel_time(self):
        #   George, Marcel and Henri are all free all day and can all do the 8h-11h job on
        #   their own: the tie is broken by travel time (Q3: "the one with less distance") -
        #   and it's a genuine ranking among 3 candidates, not just a binary choice.
        #
        #                     customer          George's depot    Henri's depot    Marcel's depot
        #   coordinates:      (50.85, 4.35)     (50.85, 4.35)     (51.30, 4.35)    (48.85, 2.35)
        #                     |                 |                 |                |
        #                     '-- 0 km away --' '-- ~50 km away --'--- ~250 km away ---'
        #
        #   → George (right next door) is picked over both Henri (nearby) and Marcel (far away).
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(8, 17)])
        self._create_resource('Henri', [(8, 17)], work_location_coords=(51.30, 4.35))
        self._create_resource('Marcel', [(8, 17)], work_location_coords=(48.85, 2.35))
        shift = self._create_open_shift(start_hour=8, end_hour=11, allocated_hours=3)

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (shift | decoy_shift).ids)
        self.assertEqual(shift.resource_ids, george)
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_finds_the_gap_after_an_already_assigned_shift(self):
        #   Time (UTC) ->      8h        9h        10h       11h       12h
        #                      |---------|---------|---------|---------|
        #   customer window:   [=======================================]
        #   George's calendar: [             free all day              ]
        #   already assigned:  [ Cust A2 ]
        #                      ^^^^^^^^^^
        #                      not a calendar break: an already-booked shift for a *different*
        #                      customer, exactly 5 real-world minutes away by road (haversine,
        #                      no MapBox token), sitting right in the middle of an otherwise
        #                      single free block.
        #
        #   allocated_hours = 2h: the calendar alone offers one big 8h-12h block, but 8h-9h of
        #   it is already taken. The search must not just try the earliest 2h of the calendar
        #   block (8h-10h, which overlaps the existing job) and give up - it must find the
        #   remaining free time right after it, pushed back another 5 minutes for the drive
        #   over from Cust A2's site: 9h05-11h05.
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(8, 12)])
        other_customer = self.env['res.partner'].create({
            'name': 'Cust A2',
            'partner_latitude': 50.85 + math.degrees(5 / EARTH_RADIUS_KM),  # exactly 5 km north
            'partner_longitude': 4.35,
        })
        self.env['planning.slot'].create({
            'name': 'Already booked',
            'partner_id': other_customer.id,
            'resource_ids': george.ids,
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=9, minute=0, second=0),
            'allocated_hours': 1,
            'state': '2_published',
        })
        shift = self._create_open_shift(start_hour=8, end_hour=12, allocated_hours=2)

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (shift | decoy_shift).ids)
        self.assertEqual(shift.resource_ids, george)
        self.assertAlmostEqual(shift.start_datetime, fields.Datetime.now().replace(hour=9, minute=5), delta=timedelta(seconds=1))
        self.assertAlmostEqual(shift.end_datetime, fields.Datetime.now().replace(hour=11, minute=5), delta=timedelta(seconds=1))
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_skips_a_resource_whose_linked_material_is_already_busy(self):
        #   George's own calendar is wide open all day - but he's linked to a van (assigning
        #   George to a shift automatically drags the van along with him, see
        #   `_inverse_resource_ids`), and that van is already booked 8h-9h on some other shift
        #   that doesn't even involve George. A resource's own calendar being free isn't
        #   enough - its linked material must be free too, or the van itself would end up
        #   double-booked on two shifts at once.
        #
        #   → Marcel (no linked material) gets the shift instead of George.
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(8, 17)])
        marcel = self._create_resource('Marcel', [(8, 17)])
        van = self.env['resource.resource'].create({
            'name': 'Van',
            'resource_type': 'material',
            'assigned_employee_id': george.employee_id.id,
        })
        self.env['planning.slot'].create({
            'name': 'Van already booked',
            'resource_ids': van.ids,
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=9, minute=0, second=0),
            'allocated_hours': 1,
            'state': '2_published',
        })
        shift = self._create_open_shift(start_hour=8, end_hour=9, allocated_hours=1)

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (shift | decoy_shift).ids)
        self.assertEqual(shift.resource_ids, marcel)
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_rollback_also_clears_a_resources_linked_material(self):
        #   Assigning George also drags his van along onto the shift (`_inverse_resource_ids`,
        #   same as `test_auto_plan_skips_a_resource_whose_linked_material_is_already_busy`) -
        #   rollback must clear the van too, not just George, or it would stay stuck looking
        #   busy on this shift forever.
        george = self._create_resource('George', [(8, 17)])
        van = self.env['resource.resource'].create({
            'name': 'Van',
            'resource_type': 'material',
            'assigned_employee_id': george.employee_id.id,
        })
        shift = self._create_open_shift(start_hour=8, end_hour=9, allocated_hours=1)

        result = self._run_auto_plan()
        self.assertEqual(shift.resource_ids, george | van, "the van should have tagged along with George")

        self.env['planning.slot'].action_rollback_auto_plan_ids(result)

        shift.invalidate_recordset()
        self.assertFalse(shift.resource_ids, "both George and his van should be cleared")

    def test_auto_plan_delays_start_until_travel_time_from_a_previous_job_elapses(self):
        #   Time (UTC) ->      8h        9h        10h       11h       12h
        #                      |---------|---------|---------|---------|
        #   George's calendar: [             free (8h-12h)             ]
        #   earlier job:       [ Cust B  ]
        #                      ^^^^^^^^^^
        #                      Cust B is a *different* customer than this shift's, exactly 15
        #                      real-world minutes away by road (haversine, no MapBox token).
        #
        #   allocated_hours = 2h, free gap after subtracting the earlier job = 9h-12h (3h): the
        #   earliest moment of that gap (9h) isn't actually reachable - George is only free to
        #   leave Cust B's site at 9h, and still needs those 15 minutes to get here. So the
        #   placement is pushed back to 9h15-11h15, not 9h-11h.
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(8, 12)])
        other_customer = self.env['res.partner'].create({
            'name': 'Cust B',
            'partner_latitude': 50.85 + math.degrees(15 / EARTH_RADIUS_KM),  # exactly 15 km north
            'partner_longitude': 4.35,
        })
        self.env['planning.slot'].create({
            'name': 'Earlier job',
            'partner_id': other_customer.id,
            'resource_ids': george.ids,
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=9, minute=0, second=0),
            'allocated_hours': 1,
            'state': '2_published',
        })
        shift = self._create_open_shift(start_hour=9, end_hour=12, allocated_hours=2)

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (shift | decoy_shift).ids)
        self.assertEqual(shift.resource_ids, george)
        # the haversine-derived 15 minutes isn't exactly 15:00.000000 (floating-point), hence the tolerance
        self.assertAlmostEqual(shift.start_datetime, fields.Datetime.now().replace(hour=9, minute=15), delta=timedelta(seconds=1))
        self.assertAlmostEqual(shift.end_datetime, fields.Datetime.now().replace(hour=11, minute=15), delta=timedelta(seconds=1))
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_places_shift_between_two_existing_jobs(self):
        #   Time (UTC) ->      8h        9h        10h       11h       12h
        #                      |---------|---------|---------|---------|
        #   George's calendar: [             free all day              ]
        #   previous job:      [ Cust P  ]
        #   next job:                                        [ Cust N  ]
        #                      ^^^^^^^^^^                    ^^^^^^^^^^
        #                      10 min away                    5 min away
        #
        #   The new job (for `self.customer`, sitting right on top of George's own work
        #   location, so 0 travel time to/from there in isolation) is sandwiched between two
        #   real jobs on both sides: George can only leave Cust P's site at 9h, plus the 10
        #   real-world minutes (haversine, no MapBox token) it takes to get here, and he must
        #   still have enough time (5 minutes) left to reach Cust N's site by 11h.
        #   allocated_hours = 1h fits comfortably either way: 9h10-10h10.
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(8, 17)])
        cust_p = self.env['res.partner'].create({
            'name': 'Cust P',
            'partner_latitude': 50.85 + math.degrees(10 / EARTH_RADIUS_KM),  # exactly 10 km north
            'partner_longitude': 4.35,
        })
        cust_n = self.env['res.partner'].create({
            'name': 'Cust N',
            'partner_latitude': 50.85 - math.degrees(5 / EARTH_RADIUS_KM),  # exactly 5 km south
            'partner_longitude': 4.35,
        })
        self.env['planning.slot'].create([
            {
                'name': 'Previous job',
                'partner_id': cust_p.id,
                'resource_ids': george.ids,
                'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
                'end_datetime': fields.Datetime.now().replace(hour=9, minute=0, second=0),
                'allocated_hours': 1,
                'state': '2_published',
            },
            {
                'name': 'Next job',
                'partner_id': cust_n.id,
                'resource_ids': george.ids,
                'start_datetime': fields.Datetime.now().replace(hour=11, minute=0, second=0),
                'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
                'allocated_hours': 1,
                'state': '2_published',
            },
        ])
        # windowed to only overlap the middle gap, so it can't wander off into the (also free)
        # 12h-17h at the end of the day instead
        shift = self._create_open_shift(start_hour=9, end_hour=11, allocated_hours=1)

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (shift | decoy_shift).ids)
        self.assertEqual(shift.resource_ids, george)
        self.assertAlmostEqual(shift.start_datetime, fields.Datetime.now().replace(hour=9, minute=10), delta=timedelta(seconds=1))
        self.assertAlmostEqual(shift.end_datetime, fields.Datetime.now().replace(hour=10, minute=10), delta=timedelta(seconds=1))
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_prefers_published_shifts_over_draft_regardless_of_priority(self):
        #   George's only free time that day is a single 1h slot (8h-9h). Two shifts compete
        #   for it: a HIGH-priority draft one, and a LOW-priority published one. Priority alone
        #   would favor the draft shift, but a published shift is already a real commitment to
        #   a customer, while a draft one is still just a placeholder - published shifts always
        #   get first crack at a resource's time, regardless of relative priority. Draft shifts
        #   are only considered once every published shift has had its chance.
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(8, 9)])
        published_shift = self._create_open_shift(start_hour=8, end_hour=9, allocated_hours=1, priority='0')
        draft_shift = self._create_open_shift(start_hour=8, end_hour=9, allocated_hours=1, priority='2', state='1_draft')

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (published_shift | decoy_shift).ids)
        self.assertEqual(published_shift.resource_ids, george)
        self.assertFalse(draft_shift.resource_ids)
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_schedules_longest_job_first_to_avoid_fragmentation(self):
        #   Time (UTC) ->      8h        9h        10h       11h       12h       13h       14h
        #                      |---------|---------|---------|---------|---------|---------|
        #   George's calendar: [               free (4h)               |  lunch  |free (1h)]
        #
        #   Two same-priority, same-published shifts, both free to land anywhere that day
        #   (8h-14h): a 4h one (exactly gap A's size) and a 1h one (fits either gap). If the 1h
        #   one were scheduled first, it would grab the earliest slot (8h-9h, out of gap A),
        #   leaving only 3h in gap A + 1h in gap B - neither enough for the 4h job on its own,
        #   so it would fail even though there's 4h of free time in total. Scheduling the
        #   longest job first avoids that: it takes gap A whole, and the 1h job still fits
        #   afterwards, in gap B.
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(8, 12), (13, 14)])
        long_shift = self._create_open_shift(start_hour=8, end_hour=14, allocated_hours=4)
        short_shift = self._create_open_shift(start_hour=8, end_hour=14, allocated_hours=1)

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (long_shift | short_shift | decoy_shift).ids)
        self.assertEqual(long_shift.resource_ids, george)
        self.assertEqual(short_shift.resource_ids, george)
        self.assertEqual(long_shift.start_datetime, fields.Datetime.now().replace(hour=8))
        self.assertEqual(long_shift.end_datetime, fields.Datetime.now().replace(hour=12))
        self.assertEqual(short_shift.start_datetime, fields.Datetime.now().replace(hour=13))
        self.assertEqual(short_shift.end_datetime, fields.Datetime.now().replace(hour=14))
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_prioritizes_higher_priority_shifts_when_capacity_runs_out(self):
        #   Time (UTC) ->      8h        9h        10h       11h       12h       13h       14h
        #                      |---------|---------|---------|---------|---------|---------|
        #   George's calendar: [               free (4h)               |  lunch  |free (1h)]
        #
        #   6 shifts compete for George's day (all for the same customer, so travel time
        #   between them is a flat 0 here - this test is about priority ordering, not travel
        #   time; see `test_auto_plan_picks_the_resource_with_the_shortest_travel_time` and
        #   `test_auto_plan_delays_start_until_travel_time_from_a_previous_job_elapses` for
        #   that):
        #     - 3 HIGH-priority shifts (2h + 1h + 1h, windowed to only overlap gap A) that
        #       together exactly fill it.
        #     - 1 HIGH-priority shift (1h, windowed to only overlap gap B) that exactly fills
        #       it too.
        #     - 2 LOW-priority shifts (1h each, free to land anywhere in the day) created
        #       *first* - a naive creation-order assignment would grab a gap before the
        #       higher-priority shifts even get a chance at it. They must lose out instead,
        #       since by the time their (lower) priority is due, every minute of George's day
        #       is already spoken for by the higher-priority ones.
        #
        #   Each high-priority shift's own window is restricted to a single gap on purpose: our
        #   auto-plan groups same-day/same-priority shifts together without guaranteeing which
        #   one of an equal-priority tier is attempted before another, so a shift able to land
        #   in *either* gap could make this test's outcome depend on that unspecified order.
        #   Restricting each one to a single gap removes that ambiguity - this test is about
        #   priority ordering *between* tiers, not about resolving ties *within* one.
        #
        #   Henri shares George's role but is already booked solid all day (a third, unrelated
        #   customer): the low-priority shifts must fail because the *team* is out of capacity,
        #   not merely because George specifically is busy.
        decoy_resource, decoy_shift = self._create_decoy()
        low_priority_1 = self._create_open_shift(start_hour=8, end_hour=14, allocated_hours=1, priority='0')
        low_priority_2 = self._create_open_shift(start_hour=8, end_hour=14, allocated_hours=1, priority='0')
        self._create_resource('George', [(8, 12), (13, 14)])
        henri = self._create_resource('Henri', [(8, 17)])
        self.env['planning.slot'].create({
            'name': "Henri's other job",
            'partner_id': self.env['res.partner'].create({
                'name': 'Cust C', 'partner_latitude': 52.0, 'partner_longitude': 4.0,
            }).id,
            'resource_ids': henri.ids,
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=17, minute=0, second=0),
            'allocated_hours': 9,
            'state': '2_published',
        })
        gap_a_shift_1 = self._create_open_shift(start_hour=8, end_hour=12, allocated_hours=2, priority='2')
        gap_a_shift_2 = self._create_open_shift(start_hour=8, end_hour=12, allocated_hours=1, priority='2')
        gap_a_shift_3 = self._create_open_shift(start_hour=8, end_hour=12, allocated_hours=1, priority='2')
        gap_b_shift = self._create_open_shift(start_hour=13, end_hour=14, allocated_hours=1, priority='2')

        result = self._run_auto_plan()

        assigned = self.env['planning.slot'].browse(result['open_shift_assigned'])
        self.assertEqual(assigned, gap_a_shift_1 | gap_a_shift_2 | gap_a_shift_3 | gap_b_shift | decoy_shift)
        self.assertFalse(low_priority_1.resource_ids)
        self.assertFalse(low_priority_2.resource_ids)
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

        # gap A's 3 shifts must tile it exactly (8h-12h), whichever of them landed where
        gap_a_shifts = gap_a_shift_1 + gap_a_shift_2 + gap_a_shift_3
        expected_start = fields.Datetime.now().replace(hour=8)
        for shift in gap_a_shifts.sorted('start_datetime'):
            self.assertEqual(shift.start_datetime, expected_start)
            expected_start = shift.end_datetime
        self.assertEqual(expected_start, fields.Datetime.now().replace(hour=12))

        self.assertEqual(gap_b_shift.start_datetime, fields.Datetime.now().replace(hour=13))
        self.assertEqual(gap_b_shift.end_datetime, fields.Datetime.now().replace(hour=14))

    def test_auto_plan_schedules_a_draft_shift_at_any_time_of_day(self):
        #   Time (UTC) ->       8h        9h        10h       11h       12h       13h       14h       15h       16h       17h
        #                      |---------|---------|---------|---------|---------|---------|---------|---------|---------|
        #   George's calendar:                                                             [       free (14h-17h)        ]
        #   draft shift window:[  8h-9h  ]
        #
        #   The shift's own 8h-9h window is both too narrow (1h) for its allocated_hours (2h)
        #   and outside George's only free time that day (14h-17h) - it would never get
        #   assigned as a published shift (see `_create_open_shift`'s default state). But it's
        #   still in draft: that window is just a placeholder, not a real commitment to the
        #   customer yet, so it's widened to the whole day and the search finds 14h-16h.
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(14, 17)])
        shift = self._create_open_shift(start_hour=8, end_hour=9, allocated_hours=2, state='1_draft')

        result = self._run_auto_plan()

        self.assertCountEqual(result['open_shift_assigned'], (shift | decoy_shift).ids)
        self.assertEqual(shift.resource_ids, george)
        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=14))
        self.assertEqual(shift.end_datetime, fields.Datetime.now().replace(hour=16))
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_rollback_restores_a_draft_shift_to_its_original_placeholder_window(self):
        #   Unlike the base module (which never touches dates, only `resource_ids`), our own
        #   auto-plan widens/narrows a shift's own start/end datetime - here, the draft
        #   shift's placeholder window (8h-9h) gets widened to George's afternoon (14h-16h),
        #   same as `test_auto_plan_schedules_a_draft_shift_at_any_time_of_day`. Undoing that
        #   must restore the *original* 8h-9h placeholder, not leave it parked at 14h-16h with
        #   just the resource unassigned again.
        george = self._create_resource('George', [(14, 17)])
        shift = self._create_open_shift(start_hour=8, end_hour=9, allocated_hours=2, state='1_draft')

        result = self._run_auto_plan()
        self.assertEqual(shift.resource_ids, george)
        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=14))

        self.env['planning.slot'].action_rollback_auto_plan_ids(result)

        shift.invalidate_recordset()
        self.assertFalse(shift.resource_ids)
        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=8))
        self.assertEqual(shift.end_datetime, fields.Datetime.now().replace(hour=9))

    def test_auto_plan_rollback_restores_a_dateless_shift_to_having_no_dates_at_all(self):
        #   The dateless shift started with no dates whatsoever, got placed at 14h-16h by
        #   auto-plan (`test_auto_plan_schedules_a_dateless_shift_at_any_gap_any_day`) -
        #   undoing it must clear the dates back to False/False, not just unassign George and
        #   leave it pinned at 14h-16h as if that had always been its placeholder.
        george = self._create_resource('George', [(14, 17)])
        shift = self._create_dateless_shift()

        result = self._run_auto_plan(period=relativedelta(hours=10))
        self.assertEqual(shift.resource_ids, george)
        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=14))

        self.env['planning.slot'].action_rollback_auto_plan_ids(result)

        shift.invalidate_recordset()
        self.assertFalse(shift.resource_ids)
        self.assertFalse(shift.start_datetime)
        self.assertFalse(shift.end_datetime)

    def test_auto_plan_schedules_a_dateless_shift_at_any_gap_any_day(self):
        #   George's calendar: free only 14h-17h that day. Unlike a draft shift (which at
        #   least has a placeholder date to widen to its own day), this shift has *no* date at
        #   all - there's no "own day" to widen from, so it searches any gap, any day, across
        #   the whole auto-plan period (the one the user picked when launching auto-plan) and
        #   finds 14h-16h.
        decoy_resource, decoy_shift = self._create_decoy()
        george = self._create_resource('George', [(14, 17)])
        shift = self._create_dateless_shift()

        result = self._run_auto_plan(period=relativedelta(hours=10))

        self.assertCountEqual(result['open_shift_assigned'], (shift | decoy_shift).ids)
        self.assertEqual(shift.resource_ids, george)
        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=14))
        self.assertEqual(shift.end_datetime, fields.Datetime.now().replace(hour=16))
        self.assertEqual(decoy_shift.resource_ids, decoy_resource)

    def test_auto_plan_does_not_schedule_a_dateless_shift_before_the_viewed_day(self):
        self.env.user.tz = 'Europe/Brussels'
        calendar = self.env['resource.calendar'].create({
            'name': 'George calendar',
            'attendance_ids': [
                Command.create({'dayofweek': dayofweek, 'hour_from': 8, 'hour_to': 16})
                for dayofweek in ('0', '1')  # Monday, Tuesday
            ],
        })
        george = self.env['hr.employee'].create({
            'name': 'George',
            'resource_calendar_id': calendar.id,
            'address_id': self.customer.id,
        }).resource_id
        george.role_ids = [Command.link(self.role.id)]
        shift = self._create_dateless_shift()

        context = {
            'default_start_datetime': '2026-01-05 23:00:00',
            'default_end_datetime': '2026-01-06 23:00:00',
            'add_materials_assigned_to_employees': True,
        }
        with patch.object(self.env['planning.slot'].__class__, '_fetch_mapbox_isochrones') as mock_isochrones:
            self.env['planning.slot'].with_context(**context).auto_plan_ids([('id', 'in', self._open_shift_ids)])
            mock_isochrones.assert_not_called()

        self.assertEqual(shift.resource_ids, george)
        self.assertGreaterEqual(
            shift.start_datetime, fields.Datetime.from_string('2026-01-06'),
            "the shift must not be scheduled before the day the user was actually viewing",
        )

    def test_auto_plan_does_not_schedule_a_dateless_shift_before_now(self):
        # Resource is available from 6 am but the auto-plan should not schedule in the past; schedule as early as 'now'
        george = self._create_resource('George', [(6, 17)])
        shift = self._create_dateless_shift()

        context = {
            'default_start_datetime': fields.Datetime.to_string(fields.Datetime.now().replace(hour=0, minute=0, second=0)),
            'default_end_datetime': fields.Datetime.to_string(fields.Datetime.now().replace(hour=0, minute=0, second=0) + relativedelta(days=1)),
            'add_materials_assigned_to_employees': True,
        }
        with patch.object(self.env['planning.slot'].__class__, '_fetch_mapbox_isochrones') as mock_isochrones:
            self.env['planning.slot'].with_context(**context).auto_plan_ids([('id', 'in', self._open_shift_ids)])
            mock_isochrones.assert_not_called()

        self.assertEqual(shift.resource_ids, george)
        self.assertEqual(shift.start_datetime, fields.Datetime.now())


@freeze_time('2026-01-06 08:00:00')
class TestPlanningFieldServiceRescheduleWithTravelTimes(TestPlanningFieldServiceCommon):
    """ `update_slot_travel_times(slots, reschedule=True)` is what runs right after
    auto-plan recomputes real (rather than estimated) travel times for the resources it
    just assigned: it reschedules the shifts that were just planned and are still
    draft - moving them earlier or later, whichever the real travel time calls for -
    while leaving published shifts (and resources untouched by this run) alone. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.tz = 'UTC'
        cls.role = cls.env['planning.role'].create({'name': 'Role'})
        cls.customer = cls.env['res.partner'].create({
            'name': 'Customer',
            'partner_latitude': 50.85,
            'partner_longitude': 4.35,
        })

    def _create_resource(self, name, attendances):
        employee = self.env['hr.employee'].create({
            'name': name,
            'tz': 'UTC',
            'resource_calendar_id': self.env['resource.calendar'].create({
                'name': f'{name} calendar',
                'attendance_ids': [
                    Command.create({'dayofweek': '1', 'hour_from': hour_from, 'hour_to': hour_to})
                    for hour_from, hour_to in attendances
                ],
            }).id,
        })
        employee.resource_id.role_ids = [Command.link(self.role.id)]
        return employee.resource_id

    def _create_shift(self, resource, start_hour, start_minute, end_hour, end_minute, allocated_hours, state='1_draft'):
        now = fields.Datetime.now()
        return self.env['planning.slot'].create({
            'name': 'Shift',
            'partner_id': self.customer.id,
            'role_id': self.role.id,
            'resource_ids': resource.ids,
            'start_datetime': now.replace(hour=start_hour, minute=start_minute, second=0),
            'end_datetime': now.replace(hour=end_hour, minute=end_minute, second=0),
            'allocated_hours': allocated_hours,
            'state': state,
        })

    def test_reschedule_moves_start_earlier_when_real_travel_time_is_shorter_than_estimated(self):
        #   George's only (first) shift of the day was placed using an estimated 1h
        #   travel time (9h-10h). The real travel time turns out to be only 15 minutes:
        #   anchored on the start of George's working day (8h) + 15 min, the shift moves
        #   to 8h15 - earlier than where it was, not later.
        george = self._create_resource('George', [(8, 17)])
        shift = self._create_shift(george, 9, 0, 10, 0, allocated_hours=1)

        self.env['planning.slot'].update_slot_travel_times([{'id': shift.id, 'travel_time_in': 0.25, 'travel_time_out': 0}], reschedule=True)

        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=8, minute=15))
        self.assertEqual(shift.end_datetime, fields.Datetime.now().replace(hour=9, minute=15))

    def test_reschedule_moves_start_later_when_real_travel_time_is_longer_than_estimated(self):
        #   Same setup, but the real travel time turns out to be 2h instead of the 1h
        #   assumed when the shift was placed (9h-10h): it moves to 10h - later, not
        #   earlier.
        george = self._create_resource('George', [(8, 17)])
        shift = self._create_shift(george, 9, 0, 10, 0, allocated_hours=1)

        self.env['planning.slot'].update_slot_travel_times(
            [{'id': shift.id, 'travel_time_in': 2, 'travel_time_out': 0}], reschedule=True)

        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=10))
        self.assertEqual(shift.end_datetime, fields.Datetime.now().replace(hour=11))

    def test_reschedule_anchors_on_previous_shifts_real_end_not_its_own_old_start(self):
        #   George has an earlier, published job ending at 9h, then a draft one placed
        #   using an estimated 30-minute travel time from it (9h30-10h30). The real
        #   travel time is 45 minutes: the draft shift is pushed to 9h45, anchored on
        #   the previous job's actual end (9h), not on its own old (estimated) start.
        george = self._create_resource('George', [(8, 17)])
        earlier_job = self._create_shift(george, 8, 0, 9, 0, allocated_hours=1, state='2_published')
        shift = self._create_shift(george, 9, 30, 10, 30, allocated_hours=1)

        self.env['planning.slot'].update_slot_travel_times(
            [{'id': shift.id, 'travel_time_in': 0.75, 'travel_time_out': 0}], reschedule=True)

        self.assertEqual(earlier_job.start_datetime, fields.Datetime.now().replace(hour=8))
        self.assertEqual(earlier_job.end_datetime, fields.Datetime.now().replace(hour=9))
        self.assertEqual(shift.start_datetime, fields.Datetime.now().replace(hour=9, minute=45))
        self.assertEqual(shift.end_datetime, fields.Datetime.now().replace(hour=10, minute=45))

    def test_published_shifts_are_never_rescheduled_even_if_included_in_the_batch(self):
        #   A published shift is included in the same update_slot_travel_times batch as
        #   the draft one (its travel times get refreshed too, like any other shift on
        #   an affected resource) - but it must never be rescheduled itself, only used
        #   as an anchor for what comes after it. A large travel_time_in is given for it
        #   on purpose: if it were (wrongly) rescheduled, it would move a lot.
        george = self._create_resource('George', [(8, 17)])
        published_shift = self._create_shift(george, 8, 0, 9, 0, allocated_hours=1, state='2_published')
        draft_shift = self._create_shift(george, 9, 30, 10, 30, allocated_hours=1)

        self.env['planning.slot'].update_slot_travel_times([
            {'id': published_shift.id, 'travel_time_in': 5, 'travel_time_out': 0},
            {'id': draft_shift.id, 'travel_time_in': 0.25, 'travel_time_out': 0},
        ], reschedule=True)

        self.assertEqual(published_shift.start_datetime, fields.Datetime.now().replace(hour=8))
        self.assertEqual(published_shift.end_datetime, fields.Datetime.now().replace(hour=9))
        self.assertEqual(draft_shift.start_datetime, fields.Datetime.now().replace(hour=9, minute=15))
        self.assertEqual(draft_shift.end_datetime, fields.Datetime.now().replace(hour=10, minute=15))

    def test_resource_not_in_the_batch_is_left_untouched(self):
        #   Henri didn't get anything new from this auto-plan run: his shift isn't part
        #   of the update_slot_travel_times batch at all, and must come out exactly as
        #   it went in - only George's (who is in the batch) gets rescheduled.
        george = self._create_resource('George', [(8, 17)])
        henri = self._create_resource('Henri', [(8, 17)])
        george_shift = self._create_shift(george, 9, 0, 10, 0, allocated_hours=1)
        henri_shift = self._create_shift(henri, 9, 0, 10, 0, allocated_hours=1)

        self.env['planning.slot'].update_slot_travel_times(
            [{'id': george_shift.id, 'travel_time_in': 0.25, 'travel_time_out': 0}], reschedule=True)

        self.assertEqual(george_shift.start_datetime, fields.Datetime.now().replace(hour=8, minute=15))
        self.assertEqual(henri_shift.start_datetime, fields.Datetime.now().replace(hour=9))
        self.assertEqual(henri_shift.end_datetime, fields.Datetime.now().replace(hour=10))

    def test_allocated_hours_percentage_and_break_time_are_never_changed(self):
        #   Rescheduling must never touch allocated_hours/allocated_percentage/
        #   break_time - only start_datetime/end_datetime move.
        george = self._create_resource('George', [(8, 17)])
        shift = self._create_shift(george, 9, 0, 11, 0, allocated_hours=1)  # 2h window, 1h allocated: 50%
        shift.break_time = 0.25

        self.env['planning.slot'].update_slot_travel_times([{'id': shift.id, 'travel_time_in': 0.5, 'travel_time_out': 0}], reschedule=True)

        self.assertEqual(shift.allocated_hours, 1)
        self.assertEqual(shift.allocated_percentage, 100.0)
        self.assertEqual(shift.break_time, 0.25)
