from odoo import api, fields, models


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    project_id = fields.Many2one(tracking=9)
    task_id = fields.Many2one(tracking=10)

    @api.depends('project_id', 'task_id')
    def _compute_partner_id(self):
        super()._compute_partner_id()
        for slot in self:
            if not slot.partner_id:
                if base_partner := (slot.task_id.partner_id or slot.project_id.partner_id):
                    slot.partner_id = base_partner.address_get(['delivery']).get('delivery') or base_partner

    @api.depends('project_id')
    def _compute_allow_timesheets(self):
        for slot in self:
            slot.allow_timesheets = slot.project_id.allow_timesheets

    def _search_allow_timesheets(self, operator, value):
        query = self.env['project.project'].sudo()._search([
            ('allow_timesheets', operator, value),
        ])
        return [('project_id', 'in', query)]

    @api.depends('project_id')
    def _compute_allow_billable(self):
        for slot in self:
            slot.allow_billable = slot.project_id.allow_billable

    def _search_allow_billable(self, operator, value):
        query = self.env['project.project'].sudo()._search([
            ('allow_billable', operator, value),
        ])
        return [('project_id', 'in', query)]

    def _get_field_service_field_list(self, field_list):
        slot_field_list = []
        if not self.partner_id and self.project_id and 'project_id' in field_list:
            slot_field_list.append('project_id')
        return slot_field_list + super()._get_field_service_field_list(field_list)

    def _get_timesheetable_project(self):
        self.ensure_one()
        return self.project_id

    def _get_timesheet_vals(self, additional_vals=None):
        self.ensure_one()
        return {
            'task_id': self.task_id.id,
            **super()._get_timesheet_vals(additional_vals),
        }

    def _reset_intervention_fields(self):
        self.task_id = False
        self.project_id = False
        super()._reset_intervention_fields()
