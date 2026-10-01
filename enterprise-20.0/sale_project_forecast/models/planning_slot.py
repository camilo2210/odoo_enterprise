# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain

from odoo.addons.resource.models.utils import filter_map_domain


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    sale_line_id = fields.Many2one(compute='_compute_sale_line_id', store=True, readonly=False)
    allow_billable = fields.Boolean(compute='_compute_allow_billable', search='_search_allow_billable', compute_sudo=True, export_string_translation=False)

    @api.depends('sale_line_id.project_id', 'sale_line_id.task_id.project_id', 'sale_order_id.project_id')
    def _compute_project_id(self):
        slot_without_sol_project = self.env['planning.slot']
        for slot in self:
            project = slot.sale_line_id.task_id.project_id or slot.sale_line_id.project_id or slot.sale_order_id.project_id
            if not slot.project_id and project:
                slot.project_id = project
            else:
                slot_without_sol_project |= slot
        super(PlanningSlot, slot_without_sol_project)._compute_project_id()

    def _compute_sale_line_id(self):
        pass

    @api.depends('sale_line_id.task_id')
    def _compute_task_id(self):
        slot_without_sol_task = self.env['planning.slot']
        for slot in self:
            if not slot.task_id and slot.sale_line_id and slot.sale_line_id.task_id and slot.project_id:
                slot.task_id = slot.sale_line_id.task_id
            else:
                slot_without_sol_task |= slot
        super(PlanningSlot, slot_without_sol_task)._compute_task_id()

    @api.depends('task_id')
    def _compute_resource_ids(self):
        super(PlanningSlot, self.filtered('start_datetime'))._compute_resource_ids()

    @api.depends('project_id')
    def _compute_allow_billable(self):
        for slot in self:
            slot.allow_billable = slot.project_id.allow_billable

    def _search_allow_billable(self, operator, value):
        query = self.env['project.project'].sudo()._search([
            ('allow_billable', operator, value),
        ])
        return [('project_id', 'in', query)]

    @api.onchange('project_id', 'task_id')
    def _onchange_project_and_task(self):
        for slot in self:
            if not slot.sale_line_id and slot.project_id:
                slot.sale_line_id = slot.task_id.sale_line_id or slot.project_id.sale_line_id

    # -----------------------------------------------------------------
    # Business methods
    # -----------------------------------------------------------------

    def _get_shifts_to_plan_domain(self, view_domain=None):
        domain = super()._get_shifts_to_plan_domain(view_domain)

        def _map_condition(condition):
            if condition.field_expr == "project_id":
                return None
            return condition

        if self.env.context.get('default_project_id'):
            domain = Domain(filter_map_domain(domain, _map_condition))
            project = self.env['project.project'].browse(self.env.context.get('default_project_id'))
            sale_order_lines = project._fetch_sale_order_items({'project.task': [('is_closed', '=', False)]})
            domain &= Domain('sale_order_id', 'in', sale_order_lines.order_id.ids)
        return domain

    # -----------------------------------------------------------------
    # Assign sales order lines
    # -----------------------------------------------------------------

    @api.model
    def _get_employee_to_assign_priority_list(self):
        """
            This method will extend the possible priorities criteria.
            It makes sure any other priority is not skipped.
        """
        priority_list = super()._get_employee_to_assign_priority_list()

        def insert_after_or_append(preceding_priority, priority_to_insert):
            if preceding_priority in priority_list:
                priority_list.insert(priority_list.index(preceding_priority) + 1, priority_to_insert)
            else:
                priority_list.append(priority_to_insert)

        insert_after_or_append('previous_slot', 'task_assignee')
        return priority_list

    def _get_employee_per_priority(self, priority, employee_ids_to_exclude, cache):
        """
            This method returns the id of an employee filling the priority criterias and
            not present in the employee_ids_to_exclude.
        """
        employee_id = super()._get_employee_per_priority(priority, employee_ids_to_exclude, cache)
        if employee_id or priority in cache:
            return employee_id
        if priority == 'task_assignee' and self.task_id and len(self.task_id.user_ids) == 1:
            tmp_emp_id = self.task_id.user_ids.employee_id.id
            if tmp_emp_id not in employee_ids_to_exclude:
                cache[priority] = [tmp_emp_id]
        return cache[priority].pop(0) if cache.get(priority) else employee_id
