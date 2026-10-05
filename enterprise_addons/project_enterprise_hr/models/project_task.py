from odoo import api, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        result = super(ProjectTask, self.with_context(scale=scale)).get_gantt_data(domain, groupby, read_specification, limit=limit, offset=offset, unavailability_fields=unavailability_fields, progress_bar_fields=progress_bar_fields, start_date=start_date, stop_date=stop_date, scale=scale)
        if "user_ids" in groupby:
            user_ids = [group["user_ids"][0] for group in result["groups"] if group["user_ids"]]
            employees = self.env["hr.employee"].sudo().with_context(active_test=False).search([('user_id', 'in', user_ids)])
            result["working_periods"] = employees._get_working_periods_by_field(start_date, stop_date, 'user_id')
        return result
