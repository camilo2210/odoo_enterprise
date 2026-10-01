from datetime import UTC
from odoo import fields, models
from odoo.fields import Domain


class ProjectTask(models.Model):
    _inherit = 'project.task'

    scheduled_datetime = fields.Datetime('Scheduled Date', compute='_compute_scheduled_datetime', groups='planning.group_planning_user')

    def _compute_scheduled_datetime(self):
        domain = Domain([('start_datetime', '!=', False)])
        tasks = self.filtered('project_id')
        subtask_ids_per_task_id = tasks._get_subtask_ids_per_task_id()
        all_tasks = tasks | self.browse(set.union(set(), *subtask_ids_per_task_id.values()))
        today = fields.Datetime.context_timestamp(self, fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).astimezone(UTC).replace(tzinfo=None)
        scheduled_datetime_per_task = dict(
            self.env['planning.slot']._read_group(
                domain & Domain([('end_datetime', '>=', today), ('task_id', 'in', all_tasks.ids)]),
                ['task_id'],
                ['start_datetime:min'],
            )
        )
        remaining_tasks = all_tasks.filtered(lambda t: t not in scheduled_datetime_per_task)
        if remaining_tasks:
            scheduled_datetime_per_task.update(dict(
                self.env['planning.slot']._read_group(
                    domain & Domain('task_id', 'in', remaining_tasks.ids),
                    ['task_id'],
                    ['start_datetime:max'],
                )
            ))

        for task in self:
            subtask_ids = subtask_ids_per_task_id.get(task.id)
            scheduled_datetime = scheduled_datetime_per_task.get(task, False)
            if subtask_ids and (scheduled_datetime_list := [scheduled_datetime for t, scheduled_datetime in scheduled_datetime_per_task.items() if t == task or t.id in subtask_ids]):
                scheduled_datetime = min(scheduled_datetime_list)
                if scheduled_datetime < today and len(scheduled_datetime_list) > 1:
                    for start_datetime in scheduled_datetime_list:
                        if start_datetime >= today and (scheduled_datetime < today or scheduled_datetime > start_datetime):
                            scheduled_datetime = start_datetime

            task.scheduled_datetime = scheduled_datetime

    def action_get_project_forecast_by_user(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("project_forecast.project_forecast_action_schedule_by_employee")
        allowed_tasks = self
        first_slot = self.env['planning.slot']
        if self.scheduled_datetime:
            allowed_tasks |= self._get_all_subtasks()
            first_slot = self.env['planning.slot'].search(
                [
                    ('start_datetime', '>=', fields.Datetime.now()),
                    ('task_id', 'in', allowed_tasks.ids)
                ],
                limit=1,
                order="start_datetime"
            )
            action['domain'] = [('task_id', 'in', allowed_tasks.ids)]
        action_context = {}
        if first_slot:
            action_context.update({'initialDate': first_slot.start_datetime})
        else:
            planned_tasks = allowed_tasks.filtered('planned_date_begin')
            min_date = min(planned_tasks.mapped('planned_date_begin')) if planned_tasks else False
            if min_date and min_date > fields.Datetime.now():
                action_context.update({'initialDate': min_date})
        action['context'] = action_context
        return action
