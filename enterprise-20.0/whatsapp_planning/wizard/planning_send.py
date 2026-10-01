from odoo import api, fields, models


class PlanningSend(models.TransientModel):
    _inherit = 'planning.send'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, store=False, export_string_translation=False)
    sending_medium = fields.Selection(related="company_id.planning_medium")

    @api.depends('employee_ids', 'sending_medium')
    def _compute_employees_no_email(self):
        whatsapp = self.filtered(lambda p: p.sending_medium == 'whatsapp')
        super(PlanningSend, self - whatsapp)._compute_employees_no_email()
        for planning in whatsapp:
            planning.employees_no_email = planning.employee_ids.filtered(lambda employee: not employee.work_phone)

    def _inverse_employees_no_email(self):
        whatsapp = self.filtered(lambda p: p.sending_medium == 'whatsapp')
        super(PlanningSend, self - whatsapp)._inverse_employees_no_email()
        for planning in whatsapp:
            planning.employee_ids = planning.employees_no_email + planning.employee_ids.filtered('work_phone')

    def action_check_emails(self):
        if self.sending_medium != "whatsapp":
            return super().action_check_emails()

        if self.employees_no_email and self.employee_ids.has_access('write'):
            return {
                'name': self.env._('Some employees are missing a work phone number'),
                'view_mode': 'form',
                'res_model': 'planning.send',
                'views': [(self.env.ref('planning.employee_no_email_list_wizard').id, 'form')],
                'type': 'ir.actions.act_window',
                'res_id': self.id,
                'target': 'new',
            }
        return self.action_send()
