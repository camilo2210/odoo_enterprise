# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.sql import drop_view_if_exists, SQL


class ProjectTimesheetForecastReportAnalysis(models.Model):
    _name = 'project.timesheet.forecast.report.analysis'

    _description = "Planning & Timesheets Analysis"
    _auto = False
    _rec_name = 'entry_date'
    _order = 'entry_date desc'

    entry_date = fields.Date('Date', readonly=True)
    employee_id = fields.Many2one('hr.employee', 'Employee', readonly=True)
    company_id = fields.Many2one('res.company', string="Company", readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", string="Currency", readonly=True)
    project_id = fields.Many2one('project.project', string='Project', readonly=True)
    task_id = fields.Many2one('project.task', string='Task', readonly=True)
    line_type = fields.Selection([('forecast', 'Planning'), ('timesheet', 'Timesheet')], string='Type', readonly=True)
    effective_hours = fields.Float('Actual Time', readonly=True)
    planned_hours = fields.Float('Planned Time', readonly=True)
    difference = fields.Float('Time Variance(Planned - Actual)', readonly=True)
    is_published = fields.Boolean(readonly=True)
    effective_costs = fields.Monetary('Actual Costs', readonly=True)
    planned_costs = fields.Monetary('Planned Costs', readonly=True)

    def _number_of_days_without_weekend(self):
        # this method should return working days based on resource calendar
        # TODO: naming should be changed on master
        return SQL("""
            WITH no_weekend_days AS (
                SELECT
                    slot_res_counts.forecast_id,
                    SUM(slot_res_counts.res_working_days) AS total_resource_working_days
                 FROM (
                    SELECT
                        F.id AS forecast_id,
                        rel.resource_resource_id AS resource_id,
                        GREATEST(COUNT(DISTINCT g::date), 1) AS res_working_days
                     FROM
                        planning_slot F
                        JOIN planning_slot_resource_resource_rel rel ON F.id = rel.planning_slot_id
                        JOIN resource_resource R ON rel.resource_resource_id = R.id
                        LEFT JOIN resource_calendar_attendance A ON A.calendar_id = R.calendar_id
                        CROSS JOIN LATERAL generate_series(F.start_datetime::date, F.end_datetime::date, '1 day') g
                     WHERE
                        (EXTRACT(ISODOW FROM g) = (A.dayofweek::integer + 1) OR A.dayofweek IS NULL)
                        AND R.resource_type = 'user'
                  GROUP BY
                        F.id, rel.resource_resource_id
                 ) AS slot_res_counts
                GROUP BY
                    slot_res_counts.forecast_id
            )
        """)

    @api.model
    def _select(self):
        nb_days_with_clause = self._number_of_days_without_weekend()
        return SQL("""
            %s
            SELECT
                d.date::date AS entry_date,
                E.id AS employee_id,
                F.company_id AS company_id,
                F.project_id AS project_id,
                F.task_id AS task_id,
                0.0 AS effective_hours,
                0.0 As effective_costs,
                F.allocated_hours / COALESCE(W.total_resource_working_days, 1) AS planned_hours,
                (F.allocated_hours / COALESCE(W.total_resource_working_days, 1)) * E.hourly_cost AS planned_costs,
                F.allocated_hours / COALESCE(W.total_resource_working_days, 1) AS difference,
                'forecast' AS line_type,
                F.id AS id,
                CASE WHEN F.state = '2_published' THEN TRUE ELSE FALSE END AS is_published
        """, nb_days_with_clause)

    @api.model
    def _from(self):
        return SQL("""
            FROM planning_slot F
            JOIN planning_slot_resource_resource_rel RF ON F.id = RF.planning_slot_id
            JOIN resource_resource R ON RF.resource_resource_id = R.id
            JOIN hr_employee E ON R.id = E.resource_id
            LEFT JOIN no_weekend_days W ON F.id = W.forecast_id
            CROSS JOIN LATERAL (
                SELECT g.day::date AS date
                FROM generate_series(
                    (start_datetime)::date,
                    (end_datetime)::date,
                    '1 day'::interval
                ) AS g(day)
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM resource_calendar_leaves RL
                    WHERE (RL.calendar_id = R.calendar_id OR RL.calendar_id IS NULL)
                      AND (RL.resource_id = R.id OR RL.resource_id IS NULL)
                      AND (RL.company_id = F.company_id OR RL.company_id IS NULL)
                      AND NOT (F.end_datetime::date < RL.date_from::date OR F.start_datetime::date > RL.date_to::date)
                      AND g.day::date BETWEEN
                      (RL.date_from AT TIME ZONE 'UTC' AT TIME ZONE COALESCE(R.tz, 'UTC'))::date AND
                      (RL.date_to AT TIME ZONE 'UTC' AT TIME ZONE COALESCE(R.tz, 'UTC'))::date
                )
            ) AS d
        """)

    @api.model
    def _select_union(self):
        return SQL("""
            SELECT
                A.date AS entry_date,
                E.id AS employee_id,
                A.company_id AS company_id,
                A.project_id AS project_id,
                A.task_id AS task_id,
                A.unit_amount / UOM.factor * HOUR_UOM.factor AS effective_hours,
                (A.unit_amount / UOM.factor * HOUR_UOM.factor) * E.hourly_cost AS effective_costs,
                0.0 AS planned_hours,
                0.0 AS planned_costs,
                -A.unit_amount / UOM.factor * HOUR_UOM.factor AS difference,
                'timesheet' AS line_type,
                -A.id AS id,
                TRUE AS is_published
        """)

    @api.model
    def _from_union(self):
        return SQL("""
            FROM account_analytic_line A
                LEFT JOIN hr_employee E ON A.employee_id = E.id
                LEFT JOIN project_project P ON A.project_id = P.id
        """)

    @api.model
    def _from_union_timesheet_uom(self):
        return SQL("""
            LEFT JOIN uom_uom UOM ON A.product_uom_id = UOM.id,
            (
                SELECT U.factor
                  FROM uom_uom U
                 WHERE U.id = %s
            ) HOUR_UOM
        """, self.env.ref('uom.product_uom_hour').id)

    @api.model
    def _where_union(self):
        return SQL("""
            WHERE A.project_id IS NOT NULL
              AND A.date <= CURRENT_DATE
        """)

    @api.model
    def _where(self):
        return SQL("""
                WHERE EXISTS (
                    SELECT 1
                    FROM resource_calendar_attendance A
                    WHERE A.calendar_id = R.calendar_id
                    AND (
                        (
                            -- Attendance is duration-based (No specific hour boundaries)
                            A.duration_based = TRUE
                            AND d.date::date BETWEEN F.start_datetime::date AND F.end_datetime::date
                        )
                        OR
                        (
                            -- Attendance is NOT duration-based
                            COALESCE(A.duration_based, FALSE) = FALSE
                            AND A.dayofweek::int + 1 = EXTRACT(ISODOW FROM d.date)
                            AND F.start_datetime < (d.date::date + (A.hour_to || ' hour')::interval)
                            AND F.end_datetime > (d.date::date + (A.hour_from || ' hour')::interval)
                        )
                    )
                ) OR R.calendar_id IS NULL
        """)

    def init(self):
        query = SQL(
            "(%s %s %s) UNION ALL (%s %s %s %s)",
            self._select(),
            self._from(),
            self._where(),
            self._select_union(),
            self._from_union(),
            self._from_union_timesheet_uom(),
            self._where_union()
        )

        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("""CREATE or REPLACE VIEW %s as (%s)""", SQL.identifier(self._table), query))

    @api.model
    def formatted_read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[dict]:
        if not order:  # For pivot and graph view
            order = ", ".join([
                (f"{group} DESC" if group.startswith('entry_date') else group) for group in groupby
            ])
        return super().formatted_read_group(domain, groupby, aggregates, having, offset, limit, order)
