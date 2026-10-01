# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.depends('allow_timesheets', 'total_timesheet_time', 'total_forecast_time', 'timesheet_encode_uom_id')
    def _compute_timesheet_stat_values(self):
        uom_hour = self.env.ref('uom.product_uom_hour')
        for project in self:
            stat_timesheet_value = False
            stat_extra_time_value = False
            success_rate = False

            encode_uom = project.timesheet_encode_uom_id
            planned = uom_hour._compute_quantity(project.total_forecast_time, encode_uom)
            effective = project.total_timesheet_time
            if planned:
                success_rate = round(100 * effective / planned)
                stat_timesheet_value = self.env._(
                    '%(effective)s / %(planned)s %(uom_name)s',
                    effective=round(effective),
                    planned=round(planned),
                    uom_name=encode_uom.name,
                )
                if success_rate > 100:
                    stat_extra_time_value = self.env._(
                        '%(exceeding_hours)s %(uom_name)s (+%(exceeding_rate)s%%)',
                        exceeding_hours=round(effective - planned),
                        uom_name=encode_uom.name,
                        exceeding_rate=round(100 * (effective - planned) / planned),
                    )
            else:
                stat_timesheet_value = self.env._(
                    '%(effective)s %(uom_name)s',
                    effective=round(effective),
                    uom_name=encode_uom.name,
                )

            project.stat_timesheet_value = stat_timesheet_value
            project.stat_extra_time_value = stat_extra_time_value
            project.stat_success_rate = success_rate

    def action_project_forecast_from_project(self):
        action = super().action_project_forecast_from_project()
        pivot_view = self.env.ref('project_forecast.planning_action_schedule_by_project_pivot_inherit').id
        action['views'] = [
            (view_id, view_type) if view_type != 'pivot' else (pivot_view or view_id, view_type)
            for view_id, view_type in action['views']
        ]
        return action
