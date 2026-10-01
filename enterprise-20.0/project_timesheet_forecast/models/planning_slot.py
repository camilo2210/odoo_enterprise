# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime

from odoo import _, api, fields, models
from odoo.fields import Domain


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    allow_timesheets = fields.Boolean(
        "Allow timesheets",
        compute='_compute_allow_timesheets',
        search='_search_allow_timesheets',
        compute_sudo=True,
        help="Timesheets can be logged on this slot."
    )
    effective_hours = fields.Float("Effective Time", compute='_compute_effective_hours', compute_sudo=True, store=True,
        help="Number of time recorded on the employee's Timesheets for this task (and its sub-tasks) during the timeframe of the shift.")
    timesheet_ids = fields.Many2many('account.analytic.line', compute='_compute_timesheet_ids', compute_sudo=True, export_string_translation=False)
    percentage_hours = fields.Float("Progress", compute='_compute_percentage_hours', compute_sudo=True, store=True)

    @api.depends('project_id')
    def _compute_allow_timesheets(self):
        for slot in self:
            slot.allow_timesheets = slot.project_id.allow_timesheets

    def _search_allow_timesheets(self, operator, value):
        query = self.env['project.project'].sudo()._search([
            ('allow_timesheets', operator, value),
        ])
        return [('project_id', 'in', query)]

    @api.depends('allocated_hours', 'effective_hours')
    def _compute_percentage_hours(self):
        for forecast in self:
            if forecast.allocated_hours:
                forecast.percentage_hours = forecast.effective_hours / forecast.allocated_hours * 100
            else:
                forecast.percentage_hours = 0

    def _get_timesheet_domain(self):
        '''
        Returns the domain used to fetch the timesheets, None is returned in case there would be no match
        '''
        self.ensure_one()
        if not self.project_id:
            return None
        domain = Domain([
            ('employee_id', 'in', self.employee_ids.ids),
            ('date', '>=', self.start_datetime.date()),
            ('date', '<=', self.end_datetime.date())
        ])
        if self.task_id:
            all_task = self.task_id + self.task_id.with_context(active_test=False)._get_all_subtasks()
            domain &= Domain('task_id', 'in', all_task.ids)
        if self.project_id:
            domain = Domain('project_id', '=', self.project_id.id) & domain
        return domain

    @api.depends('project_id', 'task_id', 'start_datetime', 'end_datetime', 'resource_ids')
    def _compute_effective_hours(self):
        for forecast in self:
            forecast.effective_hours = sum(
                timesheet.unit_amount
                for timesheet in forecast.timesheet_ids
            )

    @api.depends('resource_ids', 'start_datetime', 'end_datetime')
    def _compute_timesheet_ids(self):
        self.timesheet_ids = False
        Timesheet = self.env['account.analytic.line']
        for forecast in self:
            if forecast.project_id and forecast.start_datetime and forecast.end_datetime:
                domain = forecast._get_timesheet_domain()
                if domain:
                    forecast.timesheet_ids = Timesheet.search(domain)

    def _read_group_fields_nullify(self):
        return super()._read_group_fields_nullify() + ['effective_hours:sum', 'effective_hours_cost:sum', 'percentage_hours:sum']

    def _gantt_progress_bar_project_id(self, res_ids, start, stop):
        planning_read_group = self.env['planning.slot']._read_group(
            [
                ('project_id', 'in', res_ids),
                ('start_datetime', '<=', stop.replace(tzinfo=None)),
                ('end_datetime', '>=', start.replace(tzinfo=None)),
            ],
            ['project_id'],
            ['allocated_hours:sum'],
        )
        dict_values_per_project = {
            project.id: {
                'value': allocated_hours_sum,
                'max_value': project.sudo().allocated_hours
            }
            for project, allocated_hours_sum in planning_read_group
        }
        project_dict = {
            project.id: project.allocated_hours
            for project in self.env['project.project'].sudo().search([('id', 'in', res_ids)])
        }
        for project_id, allocated_hours in project_dict.items():
            if project_id not in dict_values_per_project:
                dict_values_per_project[project_id] = {
                    'value': 0.0,
                    'max_value': allocated_hours,
                }
        return dict_values_per_project

    def _gantt_progress_bar(self, field, res_ids, start, stop):
        if field == 'project_id':
            return self._gantt_progress_bar_project_id(res_ids, start.replace(tzinfo=datetime.UTC), stop.replace(tzinfo=datetime.UTC))
        return super()._gantt_progress_bar(field, res_ids, start, stop)

    def action_open_timesheets(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_timesheet.timesheet_action_all')
        # Remove all references to the original action, to avoid studio and be able to change the action name
        action.pop('id', None)
        action.pop('xml_id', None)
        action.pop('display_name', None)
        action.update({
            'name': _('Timesheets'),
            'domain': self._get_timesheet_domain(),
            'view_mode': 'list,grid,kanban,pivot,graph,form',
            'mobile_view_mode': 'grid',
            'views': [
                [self.env.ref('hr_timesheet.timesheet_view_tree_user').id, 'list'],
                [self.env.ref('timesheet_grid.timesheet_view_grid_by_employee').id, 'grid'],
                [self.env.ref('hr_timesheet.view_kanban_account_analytic_line').id, 'kanban'],
                [self.env.ref('hr_timesheet.view_hr_timesheet_line_pivot').id, 'pivot'],
                [self.env.ref('hr_timesheet.view_hr_timesheet_line_graph_all').id, 'graph'],
                [self.env.ref('hr_timesheet.hr_timesheet_line_form').id, 'form'],
            ],
        })
        action['context'] = {
            'default_date': self.start_datetime.date()\
                if self.start_datetime < fields.Datetime.now() else fields.Date.context_today(self),
            'default_employee_id': self.employee_ids[0].id if self.employee_ids else False,
            'default_project_id': self.project_id.id,
            'default_task_id': self.task_id.id,
            'grid_anchor': self.start_datetime.date(),
        }
        if self.duration < 24:
            action['context']['default_unit_amount'] = self.allocated_hours
        return action
