from odoo import models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def web_gantt_write(self, data):
        # If it's schedule context (One of the projects doesn't have date)
        # we need to remove m2o field like user_id from data if they are empty to keep the old values
        if not self[0].date:
            for field in [
                f_name for f_name, value in data.items()
                if (
                    not value
                    and f_name in self._fields
                    and self._fields[f_name].type == 'many2one'
                )
            ]:
                del data[field]

        return self.write(data)

    def action_view_tasks(self):
        action = super().action_view_tasks()
        if not self.allow_milestones:
            action['views'] = [
                (view_id if view_type != 'map' else self.env.ref('project_enterprise.project_task_map_view_no_title_no_milestone').id, view_type)
                for view_id, view_type in action['views']
            ]
        if self._get_hide_partner() or self.is_template:
            action['views'] = [(view_id, view_type) for view_id, view_type in action['views'] if view_type != 'map']
        return action
