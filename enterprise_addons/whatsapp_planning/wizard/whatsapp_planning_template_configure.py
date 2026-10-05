from odoo import api, fields, models
from ..models.res_company import WA_PLANNING_TEMPLATES


class TemplateConfigure(models.TransientModel):
    _name = 'whatsapp.planning.template.configure'
    _description = 'Whatsapp Planning Wizard'

    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, store=False)
    wa_template_schedule_published = fields.Many2one(related="company_id.wa_template_schedule_published", readonly=False)
    wa_template_open_shift_available = fields.Many2one(related="company_id.wa_template_open_shift_available", readonly=False)
    wa_template_assigned_shift = fields.Many2one(related="company_id.wa_template_assigned_shift", readonly=False)
    wa_template_shift_reassigned = fields.Many2one(related="company_id.wa_template_shift_reassigned", readonly=False)

    wa_template_schedule_published_account = fields.Many2one(string="Publish Schedule Account", related="company_id.wa_template_schedule_published.wa_account_id", readonly=False)
    wa_template_open_shift_available_account = fields.Many2one(string="Open Shift Account", related="company_id.wa_template_open_shift_available.wa_account_id", readonly=False)
    wa_template_assigned_shift_account = fields.Many2one(string="Assigned Shift Account", related="company_id.wa_template_assigned_shift.wa_account_id", readonly=False)
    wa_template_shift_reassigned_account = fields.Many2one(string="Reassigned Shift Account", related="company_id.wa_template_shift_reassigned.wa_account_id", readonly=False)

    wa_template_schedule_published_status = fields.Selection(string="Publish Schedule Status", related="company_id.wa_template_schedule_published.status", readonly=True)
    wa_template_open_shift_available_status = fields.Selection(string="Open Shift Status", related="company_id.wa_template_open_shift_available.status", readonly=True)
    wa_template_assigned_shift_status = fields.Selection(string="Assigned Shift Status", related="company_id.wa_template_assigned_shift.status", readonly=True)
    wa_template_shift_reassigned_status = fields.Selection(string="Reassigned Shift Status", related="company_id.wa_template_shift_reassigned.status", readonly=True)

    def action_approve(self):
        for template_name in WA_PLANNING_TEMPLATES:
            template = self.env.company[template_name]
            if template and template.status == 'draft':
                template.button_submit_template()

    @api.onchange('wa_template_schedule_published', 'wa_template_open_shift_available', 'wa_template_assigned_shift', 'wa_template_shift_reassigned')
    def _on_change_template(self):
        for template_name in WA_PLANNING_TEMPLATES:
            if not self[template_name]._filtered_access('read'):
                continue
            self[template_name + '_account'] = self[template_name].wa_account_id
            self[template_name + '_status'] = self[template_name].status
