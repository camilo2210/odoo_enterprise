# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from functools import partial

from odoo import api, fields, models
from odoo.tools import SQL
from odoo.tools.date_utils import localized, to_timezone
from odoo.tools.intervals import Intervals


class MrpWorkcenter(models.Model):
    _name = 'mrp.workcenter'
    _inherit = ["mrp.workcenter", 'maintenance.mixin', 'mail.thread', 'mail.activity.mixin']

    equipment_ids = fields.One2many(
        'maintenance.equipment', 'workcenter_id', string="Maintenance Equipment",
        check_company=True)
    maintenance_ids = fields.One2many('maintenance.request', 'workcenter_id', domain=[('maintenance_for', '=', 'workcenter')])
    # maintenance.mixin override
    technician_user_id = fields.Many2one(tracking=True)

    def _get_workorders_intervals(self, start_datetime, end_datetime):
        """
            Get the workorder intervals on specific workcenters

            :param start_datetime: start of the search range
            :param end_datetime: end of the search range
            :return: {workcenter_id: [(start, end, set()), ...]}
            :rtype: Dict[List[Intervals]] with the datetime returned in UTC, as its stored
        """
        if not self:
            return {}

        rows = self.env.execute_query(SQL(
            """
            SELECT workcenter_id, ARRAY_AGG(ARRAY[date_start, date_finished]) as date_intervals
            FROM mrp_workorder
            WHERE workcenter_id IN %(workcenter_ids)s
                AND leave_id IS NOT NULL
                AND (date_start, date_finished) OVERLAPS (%(start_datetime)s, %(end_datetime)s)
            GROUP BY workcenter_id
            """,
            workcenter_ids=tuple(self.ids),
            start_datetime=fields.Datetime.to_string(start_datetime),
            end_datetime=fields.Datetime.to_string(end_datetime),
        ))  # [(wc_id, [[start1, end1], ...]), ...]
        # TODO check without flush is okay
        return {
            wc_id: [(start, end, set()) for start, end in (date_intervals or [])]
            for wc_id, date_intervals in rows
        }

    def _get_maintenances_intervals(self, start_datetime, end_datetime):
        """
            Get the maintenances intervals for the workcenter

            :param start_datetime: start of the search range
            :param end_datetime: end of the search range
            :return: {workcenter_id: [(start, end, set()), ...]}
            :rtype: Dict[List[Intervals]] with the datetime returned in UTC, as its stored
        """
        if not self:
            return {}

        rows = self.env.execute_query(SQL(
            """
            SELECT workcenter_id, ARRAY_AGG(ARRAY[schedule_date, schedule_end]) as date_intervals
            FROM maintenance_request
            WHERE workcenter_id IN %(workcenter_ids)s
                AND schedule_date IS NOT NULL
                AND schedule_end IS NOT NULL
                AND (schedule_date, schedule_end) OVERLAPS (%(start_datetime)s, %(end_datetime)s)
            GROUP BY workcenter_id
            """,
            workcenter_ids=tuple(self.ids),
            start_datetime=fields.Datetime.to_string(start_datetime),
            end_datetime=fields.Datetime.to_string(end_datetime),
        ))  # [(wc_id, [[start1, end1], ...]), ...]
        return {
            wc_id: [(start, end, set()) for start, end in (date_intervals or [])]
            for wc_id, date_intervals in rows
        }

    @api.model
    def _get_gantt_unavailability(self, res_ids, start, stop, from_model=None):
        """
            Helper to return the unavailability of a workcenter to display in a Gantt view.

            :param res_ids: List of WC ids to compute unavailabilities for
            :param start, stop: Beginning and end of the period to compute availabilities
            :param from_model: adds unavailabilites from other models to the base schedule unavailabilities
            :return: combined unavalaibilities in format expected by _gantt_unavailability
            :rtype Dict[List[Dict]]: { wc_id: [{ start: ..., stop: ... }, ... ], ...}
        """

        workcenters = self.browse(res_ids)
        leaves_by_wc = workcenters._get_unavailability_intervals(start, stop)

        maintenances_intervals = {}
        if from_model and from_model != "maintenance.request":
            maintenances_intervals = workcenters._get_maintenances_intervals(start, stop)
        wo_intervals = {}
        if from_model and from_model != "mrp.workorder":
            wo_intervals = workcenters._get_workorders_intervals(start, stop)

        res = {}
        for wc in workcenters:
            leave_intervals = [
                (to_timezone(None)(start), to_timezone(None)(end), set())  # Naive UTC
                for start, end, _ in leaves_by_wc.get(wc.id, [])
            ]  # Add empty recordset, as in wo_intervals, ..., to use Intervals merging
            merged = Intervals(leave_intervals + maintenances_intervals.get(wc.id, []) + wo_intervals.get(wc.id, []))
            res[wc.id] = [{"start": start_dt, "stop": end_dt} for start_dt, end_dt, _ in merged]

        return res

    def _get_first_flexible_available_slot(self, start_datetime, duration) -> tuple[datetime | None, datetime | None]:
        """
        Get the first available interval for the workcenter, ignoring working schedule (flexible).

        Returns the first available interval within 700 days of the requested start date, or (None, None) if none is found.

        :param start_datetime: datetime to start searching from
        :param duration: required duration of the slot (in hours)
        :return: tuple containing (start datetime, end datetime) or (None, None)
        """
        self.ensure_one()
        resource = self.resource_id
        revert = to_timezone(start_datetime.tzinfo)
        start_datetime = localized(start_datetime)
        get_workorder_intervals = partial(
            self.resource_calendar_id._leave_intervals_batch,
            domain=[('count_as', '=', 'working_time')],  # workorder leaves only
            resources_per_tz=resource._get_resources_per_tz(),
        )

        date_start = start_datetime
        duration = relativedelta(hours=duration)
        result = None, None
        date_limit = start_datetime + relativedelta(days=700)  # Limit search to 700 days to ensure performance.
        while date_start <= date_limit:
            date_end = date_start + duration

            if not (workorder_intervals := get_workorder_intervals(date_start, date_end)[resource.id]):
                result = revert(date_start), revert(date_end)  # if no overlapping intervals found
                break
            # Set next start to the original end date of the last leave interval (not the clipped overlap)
            date_start = localized(max(list(workorder_intervals)[-1][2].mapped('date_to')))
        return result
