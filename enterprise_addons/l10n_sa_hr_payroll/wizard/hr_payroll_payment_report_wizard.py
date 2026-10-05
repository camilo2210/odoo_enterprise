import xlsxwriter
from odoo import fields, models, _
from odoo.exceptions import UserError
import io
from datetime import timedelta


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    def _get_export_format_selection(self):
        selection = super()._get_export_format_selection()
        if 'SA' in self.env.companies.country_id.mapped('code'):
            selection.extend([
                ('l10n_sa_wps', 'Saudi WPS'),
            ])
        return selection

    def _get_default_export_format(self):
        default = super()._get_default_export_format()
        if 'SA' in self.env.companies.country_id.mapped('code'):
            default = 'l10n_sa_wps'
        return default

    l10n_sa_wps_value_date = fields.Date(default=lambda self: fields.Date.context_today(self) + timedelta(days=1), string="WPS Value Date", required=True,
        help="The date on which the funds are made available to the beneficiary.")

    def _l10n_sa_get_company_wps(self, raise_if_multi=False):
        """
        Return the appropriate company based on whether the
        wizard is called upon a batch or individual payslips
        :param raise_if_multi: (optional) Check and raise error if payslips belong to multiple companies
        :return: A record of res.company
        """
        self.ensure_one()
        if self.payslip_run_id:
            return self.payslip_run_id.company_id
        if raise_if_multi and len(self.payslip_ids.company_id) > 1:
            raise UserError(_("WPS report can only be generated for one company at a time"))
        return self.payslip_ids.company_id[:1]

    def _l10n_sa_wps_render_xlsx(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("WPS")
        header = self._l10n_sa_get_wps_header()
        records = self.payslip_ids._l10n_sa_get_wps_data()
        row_idx = 0
        for row in header:
            for col_idx, value in enumerate(row):
                sheet.write(row_idx, col_idx, value)
            row_idx += 1

        for row in records:
            for col_idx, value in enumerate(row):
                sheet.write(row_idx, col_idx, value)
            row_idx += 1

        workbook.close()
        output.seek(0)
        return output.read()

    def _perform_checks(self):
        super()._perform_checks()
        if self.export_format == 'l10n_sa_wps':
            company = self._l10n_sa_get_company_wps(raise_if_multi=True)
            if company.country_code != 'SA':
                raise UserError(_("Saudi WPS report can only be printed for KSA companies"))
            payslips = self.payslip_ids.filtered(lambda p: p.state == "validated" and p.net_wage > 0)
            employees = payslips.employee_id
            invalid_banks_employee_ids = employees.filtered(lambda e: not e.primary_bank_account_id._get_clearing_number('SA'))
            if invalid_banks_employee_ids:
                raise UserError(_(
                    "Missing SARIE code for the bank account for the following employees:\n%s",
                    invalid_banks_employee_ids.mapped('name')))
            company_bank_account = company.l10n_sa_bank_account_id
            if not company_bank_account:
                raise UserError(
                    self.env._(
                        "Kindly configure the establishment's bank account by navigating to:"
                        " Payroll Configuration → Settings → Saudi Arabia Payroll."
                    )
                )
            if not company_bank_account._get_clearing_number('SA'):
                raise UserError(
                    self.env._(
                        "Missing SARIE code on the company bank %s",
                        company_bank_account.bank_name,
                    )
                )
            if not company_bank_account.l10n_sa_bank_establishment_code:
                raise UserError(
                    self.env._(
                        "Missing establishment code on the company bank %s",
                        company_bank_account.bank_name,
                    )
                )
            if not company.l10n_sa_mol_establishment_code:
                raise UserError(
                    self.env._(
                        "Kindly configure the company's MoL Establishment ID by navigating to:"
                        " Payroll Configuration → Settings → Saudi Arabia Payroll."
                    )
                )

            if self.effective_date and self.l10n_sa_wps_value_date and self.effective_date >= self.l10n_sa_wps_value_date:
                raise UserError(self.env._("The Payment Date cannot be later than the Value Date, please make sure that the correct dates are set."))

            if employees.filtered(lambda e: not e.l10n_sa_employee_code):
                raise UserError(
                    self.env._(
                        "Kindly set the Saudi National/IQAMA ID for the employees by navigating to:"
                        " the Employee Form → Payroll Tab → Saudi Payroll Information section."
                    )
                )

    def generate_payment_report(self):
        super().generate_payment_report()
        if self.export_format == 'l10n_sa_wps':
            wps_report = self._l10n_sa_wps_render_xlsx()
            self._write_file(wps_report, ".xlsx", self._get_l10n_sa_wps_file_reference())

    def _get_l10n_sa_wps_file_reference(self):
        if self.payslip_run_id:
            return self.payslip_run_id._l10n_sa_wps_generate_file_reference()
        return self.payslip_ids._l10n_sa_wps_generate_file_reference()

    def _l10n_sa_get_wps_header(self):
        self.ensure_one()
        company = self._l10n_sa_get_company_wps()
        company_bank_account = company.l10n_sa_bank_account_id

        header = [
            self.env._("Establishment's Bank"),
            self.env._("Establishment's ID"),
            self.env._("Establishment 's bank account"),
            self.env._("Currency Code"),
            self.env._("Value Date"),
            self.env._("Total Amount"),
            self.env._("Debit Date"),
            self.env._("File Rejection Code"),
            self.env._("MoL Establishment ID"),
        ]
        row = [
            company_bank_account._get_clearing_number('SA') or "",
            company_bank_account.l10n_sa_bank_establishment_code or "",
            company_bank_account.account_number or "",
            "SAR",
            (self.l10n_sa_wps_value_date or fields.Date.context_today(self)).strftime("%Y%m%d"),
            self.env['hr.payslip']._l10n_sa_format_float(sum(self.payslip_ids.mapped('net_wage'))),
            self.effective_date.strftime("%Y%m%d") if self.effective_date else '',
            '',  # Rejection Code: Required blank cell
            company.l10n_sa_mol_establishment_code or "",
        ]

        return [header, row]
