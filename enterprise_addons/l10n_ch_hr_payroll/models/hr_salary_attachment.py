# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models
from odoo.exceptions import UserError


class HrSalaryAttachment(models.Model):
    _inherit = 'hr.salary.attachment'

    @api.model
    def action_hr_salary_attachment_menu(self):
        if self.env.company.country_id.code == 'CH':
            raise UserError(self.env._("This feature seems to be unavailable to Swiss companies."))

        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.hr_salary_attachment_action')
        return action
