# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import fields, models
from odoo.exceptions import UserError, ValidationError


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    def _get_export_format_selection(self):
        selection = super()._get_export_format_selection()
        if 'HK' in self.env.companies.country_id.mapped('code'):
            selection.extend([
                ('l10n_hk_mri', 'HSBC / Hang Seng (HKMRI)'),
                ('l10n_hk_boc', 'Bank of China iGTB (KC05 - Payment Type)'),
                ('l10n_hk_boc_non_payment', 'Bank of China iGTB (KC05 - Non-Payment Type)'),
                ('l10n_hk_bea_csv', 'Bank Of East Asia (CSV)'),
            ])
        return selection

    def _get_default_export_format(self):
        default = super()._get_default_export_format()
        if 'HK' in self.env.companies.country_id.mapped('code'):
            default = 'l10n_hk_mri'
        return default

    l10n_hk_autopay_payment_set_code = fields.Char(string="Payment Set Code", help="Payment Set Code required by AutoPay file.")
    l10n_hk_autopay_first_party_reference = fields.Char(string="First Party Reference", help="First Party Reference required by AutoPay file.")
    l10n_hk_autopay_partner_bank_id = fields.Many2one(related='company_id.l10n_hk_autopay_partner_bank_id', string="Company Autopay Account", readonly=False)

    def _perform_checks(self):
        super()._perform_checks()
        if self.export_format.startswith('l10n_hk_'):
            payslips = self.payslip_ids.filtered(lambda p: p.state == "validated" and p.net_wage > 0)
            currencies = payslips.currency_id
            employees = payslips.employee_id
            companies = payslips.company_id

            if not self.l10n_hk_autopay_partner_bank_id:
                raise UserError(self.env._("Please set the Company Autopay Account."))
            invalid_payslips = payslips.filtered(lambda p: p.currency_id.name not in ['HKD', 'CNY'])
            if invalid_payslips:
                raise UserError(self.env._("Only accept HKD or CNY currency.\nInvalid currency for the following payslips:\n%s", '\n'.join(invalid_payslips.mapped('name'))))
            if len(companies) > 1:
                raise UserError(self.env._("Only support generating the autopay report for one company."))
            if len(currencies) > 1:
                raise UserError(self.env._("Only support generating the autopay report for one currency"))
            invalid_employees = employees.filtered(lambda e: not e.bank_account_ids)
            if invalid_employees:
                raise UserError(self.env._("Some employees (%s) don't have a bank account.", ','.join(invalid_employees.mapped('name'))))
            invalid_employees = employees.filtered(lambda e: not e.l10n_hk_autopay_account_type)
            if invalid_employees:
                raise UserError(self.env._("Some employees (%s) haven't set the autopay type.", ','.join(invalid_employees.mapped('name'))))
            invalid_bank_accounts = employees.bank_account_ids.filtered(lambda b: b._get_clearing_number('HK') is False)
            if invalid_bank_accounts:
                raise UserError(self.env._("Some banks accounts (%s) don't have a bank code", ','.join(invalid_bank_accounts.mapped('account_number'))))
            invalid_bank_accounts = employees.filtered(
                lambda e: e.l10n_hk_autopay_account_type in ['bban', 'hkid'] and not e.primary_bank_account_id.holder_name)
            if invalid_bank_accounts:
                raise UserError(self.env._("Some bank accounts (%s) don't have a bank account name.", ','.join(invalid_bank_accounts.primary_bank_account_id.mapped('account_number'))))

    def generate_payment_report(self):
        super().generate_payment_report()
        if self.export_format.startswith('l10n_hk_'):
            payment_data = []
            for payslip in self.payslip_ids.filtered(lambda p: p.state == "validated" and p.net_wage > 0):
                month_year = payslip.date_to.strftime('%b %Y').upper()
                employee = payslip.employee_id
                payment_data.append({
                    "account_proxy_id": employee._get_proxy_type(),
                    "autopay_account_type": employee.l10n_hk_autopay_account_type,
                    "amount": payslip.net_wage,
                    "bank_account": employee.primary_bank_account_id,
                    "identifier": re.sub(
                        r"[^a-zA-Z0-9]",
                        "",
                        (employee.identification_id or employee.passport_id or "").strip().upper(),
                    ),
                    "reference": f"SALARY {month_year}",
                })

            if self.payslip_run_id:
                document_name = self.payslip_run_id.name
            else:
                document_name = f"{self.payslip_ids[0]._get_period_name({})} - {self.payslip_ids[0].employee_id.legal_name}"

            payload = {
                "document_name": document_name,
                "company_name": self.company_id.name,
                "creation_date": fields.Datetime.now(),
                'batches': [{
                    "header": {
                        "effective_date": self.effective_date,
                        "amount_total": sum(self.payslip_ids.mapped("net_wage")),
                        "bank_account": self.company_id.l10n_hk_autopay_partner_bank_id,
                        "currency": self.payslip_ids.currency_id.name,
                        "nb_payments": len(self.payslip_ids),
                        "payment_code": self.l10n_hk_autopay_payment_set_code,
                        "reference": self.l10n_hk_autopay_first_party_reference,
                    },
                    "payments": payment_data,
                }],
            }

            errors = self.env['l10n_hk.bank.format']._validate(self.export_format, payload)
            if errors:
                raise ValidationError("\n".join(errors))

            file_content, file_extension, file_name = self.env['l10n_hk.bank.format']._generate(self.export_format, payload)
            self._write_file(file_content, file_extension, file_name)
