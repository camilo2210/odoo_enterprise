from odoo import models, api, _
from odoo.fields import Domain


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ["project.task", "timesheet.grid.mixin"]

    def write(self, vals):
        result = super().write(vals)
        if 'company_id' in vals or 'project_id' in vals:
            # sudo: the private rules of the other users have to be cleaned up too
            self.env['aw.rule'].sudo().search([
                ('company_id', '!=', False),
                ('task_id', 'in', self.ids),
            ])._remove_records_from_other_companies()
        return result

    def _compute_allocated_hours(self):
        # Only change values when creating a new record from the gantt view
        # or the existing tasks that doesn't allow timesheets
        timesheeted_tasks = self.filtered(lambda task: task._origin and task.allow_timesheets)
        super(ProjectTask, self - timesheeted_tasks)._compute_allocated_hours()

    @api.onchange('project_id')
    def _onchange_project_id(self):
        super()._onchange_project_id()
        # If task has non-validated timesheets AND new project has not the timesheets feature enabled AND the task is not a template, raise a warning notification
        if not all(t.validated for t in self.timesheet_ids) and not self.project_id.allow_timesheets and not self.is_template:
            return {
                'warning': {
                    'title': _("Warning"),
                    'message': _("Moving this task to a project without timesheet support will retain timesheet drafts in the original project. "
                                 "Although they won't be visible here, you can still edit them using the Timesheets app."),
                    'type': "notification",
                },
            }

    def _set_allocated_hours_for_tasks(self):
        super(ProjectTask, self.filtered(lambda task: not task.allow_timesheets))._set_allocated_hours_for_tasks()

    def _gantt_progress_bar_project_id(self, res_ids):
        timesheet_read_group = self.env['account.analytic.line'].sudo()._read_group(
            [('project_id', 'in', res_ids)],
            ['project_id'],
            ['unit_amount:sum'],
        )
        return {
            project.id: {
                'value': unit_amount_sum,
                'max_value': project.sudo().allocated_hours,
            }
            for project, unit_amount_sum in timesheet_read_group
        }

    def _gantt_progress_bar(self, field, res_ids, start, stop):
        if field == 'project_id':
            return dict(
                self._gantt_progress_bar_project_id(res_ids),
                warning=_("This project isn't expected to have task during this period."),
            )
        return super()._gantt_progress_bar(field, res_ids, start, stop)

    def action_view_subtask_timesheet(self):
        action = super().action_view_subtask_timesheet()
        grid_view_id = self.env.ref('timesheet_grid.timesheet_view_grid_by_employee').id
        action['views'] = [
            [grid_view_id, view_mode] if view_mode == 'grid' else [view_id, view_mode]
            for view_id, view_mode in action['views']
        ]
        return action

    def get_allocated_hours_field(self):
        return 'allocated_hours'

    def get_worked_hours_fields(self):
        return ['effective_hours', 'subtask_effective_hours']

    def _get_hours_to_plan(self):
        return self.remaining_hours

    @api.model
    def get_additional_groups(self, domain, specification, limit):
        data = self.web_search_read(domain, specification, limit=limit, count_limit=1)
        if len(data['records']) > 0 or self.env['account.analytic.line'].search_count([('project_id', '!=', False), ('user_id', '=', self.env.uid)], limit=1):
            return data

        return self.web_search_read([('project_id', '!=', False)], specification, limit=limit, count_limit=1)

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        if name or not self.env.context.get('timesheet_timer_search') or not (employee := self.env.user.employee_id):
            return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

        task_domain = Domain.AND([
            domain or [],
            [('active', '=', True)],
        ])
        recent_tasks = self.env['account.analytic.line'].sudo()._get_recently_used_records(
            'task_id',
            domain=[('task_id', 'any', task_domain), ('employee_id', '=', employee.id), ('project_id', '!=', False)],
        )
        accessible_ids = self.browse(tid for tid, _name in recent_tasks)._filtered_access('read').ids
        recent_tasks = [(tid, name) for tid, name in recent_tasks if tid in accessible_ids]
        if not recent_tasks:
            return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

        if len(recent_tasks) >= limit:
            return recent_tasks

        recent_task_ids = [task_id for task_id, _display_name in recent_tasks]
        remaining_tasks = super().name_search(
            name=name,
            domain=Domain.AND([domain or [], [('id', 'not in', recent_task_ids)]]),
            operator=operator,
            limit=limit - len(recent_tasks)
        )
        return recent_tasks + remaining_tasks
