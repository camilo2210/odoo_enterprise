# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrEmployeeDeparture(models.Model):
    _inherit = 'hr.employee.departure'

    def action_register(self):
        res = super().action_register()
        incoming_appraisals_sudo = self.sudo().env["hr.appraisal"].search([
            ('employee_id', 'in', self.employee_id.ids),
            ('state', 'in', ['1_new', '2_pending'])])
        if incoming_appraisals_sudo:
            incoming_appraisals_sudo.action_back()
            incoming_appraisals_sudo.unlink()

        incoming_manager_appraisals_sudo = self.sudo().env["hr.appraisal"].search([
            ('manager_ids', 'in', self.employee_id.ids),
            ('state', 'in', ['1_new', '2_pending']),
        ])
        for incoming_manager_appraisal in incoming_manager_appraisals_sudo:
            incoming_manager_appraisal.write({'manager_ids': [(3, emp_id) for emp_id in self.employee_id.ids]})
            incoming_manager_appraisal.message_post(body=self.env._(
                "Appraisal's managers have been updated due to the end of collaboration with an employee."
            ))

        employee_goals_sudo = self.sudo().env["hr.appraisal.goal"].search([
            ('employee_ids', 'in', self.employee_id.ids)
        ])
        for goal in employee_goals_sudo:
            if set(goal.employee_ids.ids) <= set(self.employee_id.ids):
                goal.action_archive()
        return res
