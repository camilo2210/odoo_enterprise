from odoo import fields, models

WA_PLANNING_TEMPLATES = [
    "wa_template_schedule_published",
    "wa_template_open_shift_available",
    "wa_template_assigned_shift",
    "wa_template_shift_reassigned",
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _default_wa_planning_template(self, xmlid):
        # a new company is on no account yet, so it can only read a template without one
        template = self.env.ref(xmlid, raise_if_not_found=False)
        return template if template and not template.sudo().wa_account_id else False

    planning_medium = fields.Selection([('mail', 'Email'), ('whatsapp', 'WhatsApp')], string="Send Planning", default='mail')
    wa_template_schedule_published = fields.Many2one('whatsapp.template', string="Schedule Publishing Template", default=lambda self: self._default_wa_planning_template('whatsapp_planning.whatsapp_template_planning_schedule_published'))
    wa_template_open_shift_available = fields.Many2one('whatsapp.template', string="Open Shift Template", default=lambda self: self._default_wa_planning_template('whatsapp_planning.whatsapp_template_planning_open_shift_available'))
    wa_template_assigned_shift = fields.Many2one('whatsapp.template', string="Assigned Shift Template", default=lambda self: self._default_wa_planning_template('whatsapp_planning.whatsapp_template_planning_assigned_shift'))
    wa_template_shift_reassigned = fields.Many2one('whatsapp.template', string="Shift Reassigned Template", default=lambda self: self._default_wa_planning_template('whatsapp_planning.whatsapp_template_planning_shift_reassigned'))
