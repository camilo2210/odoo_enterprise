from odoo import fields, models


class HrSalaryAttachment(models.Model):
    _inherit = 'hr.salary.attachment'

    other_input_type_code = fields.Char(related="salary_rule_id.code", string="Other Input Type Code")

    def action_create_loan_payslip(self):
        """
        Create a payslip for the loan.
        """
        payslip_data = {
            'title': self.env._('Loan Payslip'),
            'employee_id': self.employee_id.id,
            'date_from': self.date_start,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan').id,
        }
        payslip = self.env['hr.payslip'].create(payslip_data)
        payslip._set_input_value('LOANDPAY', self.total_amount)
        payslip.message_post(
            body=self.env._("Loan payslip created from this attachment: %s", self._get_html_link()),
        )

        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Loan Payslip'),
            'res_model': 'hr.payslip',
            'view_mode': 'form',
            'res_id': payslip.id,
            'target': 'current',
        }
