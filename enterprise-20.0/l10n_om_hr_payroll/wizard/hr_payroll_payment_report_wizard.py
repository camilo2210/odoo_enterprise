from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import io


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    def _get_export_format_selection(self):
        selection = super()._get_export_format_selection()
        if 'OM' in self.env.companies.country_id.mapped('code'):
            selection.extend([
                ('l10n_om_wps', 'Oman WPS'),
            ])
        return selection

    def _get_default_export_format(self):
        default = super()._get_default_export_format()
        if 'OM' in self.env.companies.country_id.mapped('code'):
            default = 'l10n_om_wps'
        return default

    l10n_om_note = fields.Char(
        string="Notes / Comments",
        size=300,
    )

    def _l10n_om_get_company_wps(self, raise_if_multi=False):
        self.ensure_one()
        if self.payslip_run_id:
            return self.payslip_run_id.company_id
        if raise_if_multi and len(self.payslip_ids.company_id) > 1:
            raise UserError(_("WPS report can only be generated for one company at a time"))
        return self.payslip_ids.company_id[:1]

    def _l10n_om_wps_render_csv(self):
        csv_data = io.StringIO()
        csv_writer = csv.writer(csv_data, delimiter=',')

        for row in (
            self._l10n_om_get_wps_employer_header() +
            self._l10n_om_get_wps_employer_record() +
            self.payslip_ids._l10n_om_get_wps_employee_header() +
            self.payslip_ids._l10n_om_get_wps_employee_records(note=self.l10n_om_note)
        ):
            csv_writer.writerow(row)
        csv_data.seek(0)
        generated_file = csv_data.read()
        csv_data.close()
        return generated_file.encode()

    def _l10n_om_get_wps_employer_header(self):
        self.ensure_one()
        return [[
            "Employer CR-NO",
            "Payer CR-NO",
            "Payer bank short name",
            "Payer IBAN",
            "Salary year",
            "Salary month",
            "Total salaries",
            "Number of records",
            "Payment type",
        ]]

    def _l10n_om_get_wps_employer_record(self):
        self.ensure_one()
        company = self._l10n_om_get_company_wps()
        payer_bank = company.l10n_om_bank_account_id
        period = self.payslip_run_id.date_start if self.payslip_run_id else self.payslip_ids[:1].date_from
        return [[
            (company.l10n_om_company_mol_number or '') if company else '',
            (company.l10n_om_salary_payer_mol_number or '') if company else '',
            self.env['hr.payslip']._l10n_om_resolve_bank_code(payer_bank),
            payer_bank.account_number if payer_bank else '',
            period.strftime('%Y') if period else '',
            period.strftime('%m') if period else '',
            self.env['hr.payslip']._l10n_om_format_float(sum(self.payslip_ids.mapped("net_wage"))),
            len(self.payslip_ids),
            'Salary',
        ]]

    def _perform_checks(self):
        super()._perform_checks()
        if self.export_format == 'l10n_om_wps':
            company = self._l10n_om_get_company_wps(raise_if_multi=True)
            if company.country_code != 'OM':
                raise UserError(_("Oman WPS report can only be generated for Omani companies."))

    def _get_l10n_om_wps_file_reference(self):
        self.ensure_one()
        company = self._l10n_om_get_company_wps()
        mol_number = (company.l10n_om_company_mol_number or '').strip()

        bank_code = ''
        if payer_bank := company.l10n_om_bank_account_id:
            bank_code = self.env['hr.payslip']._l10n_om_resolve_bank_code(payer_bank)

        date = (self.effective_date or fields.Date.today())

        counter = self._l10n_om_next_wps_daily_counter(date)
        return f'SIF_{mol_number}_{bank_code}_{date.strftime('%Y%m%d')}_{counter}'

    def _l10n_om_next_wps_daily_counter(self, date):
        """Return the next 3-digit WPS counter, resetting to 001 at the start of each new day."""
        seq = self.env['ir.sequence'].sudo().search([('code', '=', 'l10n_om.wps')], limit=1)
        range_date = self.env['ir.sequence.date_range'].sudo().search([
            ('sequence_id', '=', seq.id),
            ('date_from', '<=', date),
            ('date_to', '>=', date),
        ], limit=1)
        if not range_date:
            self.env['ir.sequence.date_range'].sudo().create({
                'sequence_id': seq.id,
                'date_from': date,
                'date_to': date,
                'number_next_actual': 1,
            })
        return self.env['ir.sequence'].with_context(ir_sequence_date=date).next_by_code('l10n_om.wps')

    def generate_payment_report(self):
        super().generate_payment_report()
        if self.export_format == 'l10n_om_wps':
            wps_report = self._l10n_om_wps_render_csv()
            self._write_file(wps_report, '.csv', self._get_l10n_om_wps_file_reference())
