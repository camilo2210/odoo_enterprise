from odoo import fields, models, _
from odoo.exceptions import RedirectWarning


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    def _get_export_format_selection(self):
        selection = super()._get_export_format_selection()
        if 'AU' in self.env.companies.country_id.mapped('code'):
            selection.extend([
                ('aba', 'ABA'),
            ])
        return selection

    def _get_default_export_format(self):
        default = super()._get_default_export_format()
        if 'AU' in self.env.companies.country_id.mapped('code'):
            default = 'aba'
        return default

    journal_id = fields.Many2one(
        string='Bank Journal', comodel_name='account.journal', required=True,
        default=lambda self: self.env['account.journal'].search([('type', '=', 'bank')], limit=1))

    def _generate_aba_file(self):
        self.ensure_one()
        aba_date = fields.Date.context_today(self).strftime('%d%m%y')
        payslip_batch = self.payslip_run_id

        payments_data = []

        for payslip in payslip_batch.slip_ids:
            employee = payslip.employee_id
            allocations = payslip._compute_salary_allocations()
            for ba in employee.bank_account_ids | payslip.salary_attachment_ids.beneficiary_bank_account_id:
                amount = allocations.get(str(ba.id), None)
                if amount is None:
                    continue
                payments_data.append({
                    'name': str(payslip.id),
                    'amount': amount,
                    'bank_account': ba,
                    'account_holder': ba.partner_id or employee,
                    'transaction_code': "53",  # PAYROLL
                    'reference': str(payslip.id),
                })

        aba_values = {
            'aba_date': aba_date,
            'aba_description': 'PAYROLL',
            'self_balancing_reference': f'PAYROLL {aba_date}',
            'payments_data': payments_data,
        }

        file_data = self.env['account.batch.payment']._create_aba_document(self.journal_id, aba_values).encode()
        return file_data

    def _perform_checks(self):
        if self.export_format == 'aba':
            self.env['account.batch.payment']._check_valid_journal_for_aba(self.journal_id)

            # Employees where any linked bank account is not valid for ABA
            employees = self.payslip_ids.employee_id.filtered(
                lambda emp: not all(
                    acc.account_type == "aba" and acc._get_clearing_number('AU')
                    for acc in emp.bank_account_ids
                )
            )
            if employees:
                raise RedirectWarning(
                    message=_("Following bank account(s) have invalid BSB or account number.\n%s",
                            "\n".join(employees.mapped("name"))),
                    action=employees._get_records_action(name=_("Configure Bank Account(s)"), target="new"),
                    button_text=_("Configure Bank Account(s)")
                )
            attachments = self.payslip_ids.salary_attachment_ids.filtered(
                lambda att:
                    att.beneficiary_bank_account_id and
                    (att.beneficiary_bank_account_id.account_type != "aba" or not att.beneficiary_bank_account_id._get_clearing_number('AU')))
            if attachments:
                raise RedirectWarning(
                    message=_("Following bank account(s) have invalid BSB or account number.\n%s",
                            "\n".join(attachments.mapped("beneficiary_bank_account_id"))),
                    action=attachments._get_records_action(name=_("Configure Bank Account(s)"), target="new"),
                    button_text=_("Configure Bank Account(s)")
                )
            return
        super()._perform_checks()

    def generate_payment_report(self):
        super().generate_payment_report()
        if self.export_format == 'aba':
            payment_report = self._generate_aba_file()
            self._write_file(payment_report, '.txt')
