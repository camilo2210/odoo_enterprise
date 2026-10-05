from odoo import fields, models, api
from .res_company import WA_PLANNING_TEMPLATES


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    planning_medium = fields.Selection(related="company_id.planning_medium", readonly=False)
    wa_template_schedule_published = fields.Many2one(related="company_id.wa_template_schedule_published", readonly=False)
    wa_template_open_shift_available = fields.Many2one(related="company_id.wa_template_open_shift_available", readonly=False)
    wa_template_assigned_shift = fields.Many2one(related="company_id.wa_template_assigned_shift", readonly=False)
    wa_template_shift_reassigned = fields.Many2one(related="company_id.wa_template_shift_reassigned", readonly=False)
    is_wa_template_planning_approved = fields.Boolean(compute="_compute_is_wa_template_planning_approved")

    @api.depends("wa_template_assigned_shift", "wa_template_open_shift_available", "wa_template_schedule_published", "wa_template_shift_reassigned", "planning_medium")
    def _compute_is_wa_template_planning_approved(self):
        for rec in self:
            if not rec.planning_medium:
                rec.is_wa_template_planning_approved = False
                continue
            rec.is_wa_template_planning_approved = True
            for template_name in WA_PLANNING_TEMPLATES:
                if not ((template := rec[template_name]._filtered_access('read')) and template.status == "approved"):
                    rec.is_wa_template_planning_approved = False
                    break
