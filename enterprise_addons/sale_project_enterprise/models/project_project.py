from odoo import models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def action_real_margin(self):
        action = super().action_real_margin()
        grid_view_id = self.env.ref('sale_project_enterprise.account_analytic_line_report_view_grid', raise_if_not_found=False).id
        action['views'] = [
            (grid_view_id if view_type == 'grid' else view_id, view_type)
            for view_id, view_type in action['views']
        ]
        return action
