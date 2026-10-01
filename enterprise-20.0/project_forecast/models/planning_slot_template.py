# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PlanningSlotTemplate(models.Model):
    _inherit = 'planning.slot.template'

    project_id = fields.Many2one('project.project', string="Project", copy=True, domain="[('is_template', '=', False), '|', ('company_id', '=', False), ('company_id', '=?',  company_id)]", check_company=True)
    task_id = fields.Many2one('project.task', string="Task", copy=True, domain="[('is_template', '=', False), ('project_id', '=?', project_id)]", check_company=True)

    @api.depends('company_id')
    def _compute_company_id(self):
        super()._compute_company_id()

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.task_id.project_id != self.project_id:
            self.task_id = False

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id:
            self.project_id = self.task_id.project_id

    @api.onchange('company_id')
    def _onchange_company_id_check_project_task(self):
        if self.company_id:
            if self.project_id.company_id and self.company_id != self.project_id.company_id:
                self.project_id = False
                self.task_id = False
            elif self.task_id.company_id and self.company_id != self.task_id.company_id:
                self.task_id = False

    def _get_company(self):
        return self.project_id.company_id

    def _get_display_name_fields(self):
        return super()._get_display_name_fields() + ['project_id', 'task_id']

    def _get_extra_name_fields(self):
        fields = super()._get_extra_name_fields()
        if self.task_id:
            fields.insert(0, 'task_id')
        if self.project_id:
            fields.insert(0, 'project_id')
        return fields
