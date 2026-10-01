from odoo import models, _
from odoo.exceptions import UserError


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    def _perform_checks(self):
        super()._perform_checks()

        payslips = self.payslip_ids.filtered(lambda p: p.state == "done" and p.net_wage > 0)
        employees = payslips.employee_id

        invalid_iban_employee_ids = employees.filtered(lambda e: any((ba.account_type == 'iban' and not self.env['res.partner.bank']._is_iban_valid(ba.account_number)) for ba in e.bank_account_ids))
        if invalid_iban_employee_ids:
            raise UserError(_(
                'Invalid IBAN for the following employees:\n%s',
                '\n'.join(invalid_iban_employee_ids.mapped('name'))))

        invalid_iban_attachment_ids = payslips.salary_attachment_ids.filtered(lambda att: att.beneficiary_bank_account_id
                                                                            and not self.env['res.partner.bank']._is_iban_valid(att.beneficiary_bank_account_id.account_number))
        if invalid_iban_attachment_ids:
            raise UserError(self.env._(
                'Invalid IBAN for the following Beneficiaries:\n%s',
                '\n'.join(invalid_iban_attachment_ids.mapped('beneficiary_bank_account_id'))))
