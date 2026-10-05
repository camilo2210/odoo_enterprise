# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.tools import SQL


class ResCompany(models.Model):
    _inherit = "res.company"

    timesheet_show_rates = fields.Boolean(export_string_translation=False)
    timesheet_show_leaderboard = fields.Boolean(export_string_translation=False)

    def write(self, vals):
        if any(
            field in vals and any(company[field] != vals[field] for company in self)
            for field in ('timesheet_show_rates', 'timesheet_show_leaderboard')
        ):
            self.env.transaction.invalidate_ormcache()
        return super().write(vals)

    def _get_leaderboard_data(self, period_start, period_end):
        self.ensure_one()
        return self.env.execute_query_dict(SQL("""
            WITH A AS (
                   SELECT aal.employee_id AS id,
                          he.name, he.billable_time_target,
                          SUM(
                            CASE
                                WHEN aal.billable_type != '09_non_billable'
                                THEN aal.unit_amount
                                ELSE 0
                            END
                          ) AS billable_time,
                          SUM(aal.unit_amount) AS total_time
                     FROM account_analytic_line AS aal
                LEFT JOIN hr_employee AS he
                       ON aal.employee_id = he.id
                    WHERE aal.project_id IS NOT NULL
                      AND date BETWEEN %s AND %s
                      AND he.company_id = %s
                      AND billable_time_target > 0
                 GROUP BY aal.employee_id,
                          he.name,
                          he.billable_time_target
            )
            SELECT *,
                   A.billable_time / A.billable_time_target * 100 AS billing_rate
              FROM A
        """, period_start, period_end, self.id))

    @api.model
    def get_timesheet_ranking_data(self, period_start, period_end, fetch_tip=False):
        if not self.env.company.timesheet_show_leaderboard:
            return {}
        period_start = fields.Date.from_string(period_start)
        period_end = fields.Date.from_string(period_end)

        data = {
            "leaderboard": self.env.company._get_leaderboard_data(period_start, period_end),
            "employee_id": self.env.user.employee_id.id,
        }
        if fetch_tip:
            data["tip"] = self.env["hr.timesheet.tip"]._get_random_tip() or _("Make it a habit to record timesheets every day.")

        return data
