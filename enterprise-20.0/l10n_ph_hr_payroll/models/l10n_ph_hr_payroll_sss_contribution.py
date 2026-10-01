# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import BinaryBytes

from odoo import fields, models

# The SSS does not accept these characters anywhere in the file.
INVALID_CHARACTERS = re.compile(r"""[/\\*\-‘’“”'"%$&()@#!{}~`^;]""")


class L10nPhHrPayrollSSSContribution(models.Model):
    _name = 'l10n_ph_hr_payroll.sss_contribution'
    _inherit = 'l10n_ph_hr_payroll.declaration'
    _description = 'SSS Contribution'

    txt_file = fields.Binary(string='TXT File', readonly=True, attachment=False)
    txt_filename = fields.Char(readonly=True)

    def _get_declaration_name(self):
        self.ensure_one()
        return self.env._("SSS Contribution")

    def _get_report_sheet_domain(self):
        """
        Confirmed reports overlapping this period, whose employees are already filed and must be excluded.

        Contributions for a period are filed only once, so once a report is confirmed its employees are left out of
        any later overlapping report (e.g. the whole month after a first partial one). Drafts lock nothing.
        """
        self.ensure_one()
        return Domain([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'done'),
            ('period_start_date', '<=', self.period_end_date),
            ('period_end_date', '>=', self.period_start_date),
            ('id', '!=', self.id),
        ])

    def action_open_declarations(self):
        action = super().action_open_declarations()
        action['views'] = [(self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_sss_declaration_view_list').id, 'list')]
        return action

    def action_generate_txt(self):
        """ Validate the data, build the SSS file, store it on the report and log it to the chatter. """
        self.ensure_one()
        self._l10n_ph_sss_validate_data()

        amounts = self._l10n_ph_sss_get_amounts(self.line_ids.employee_id)
        rows = [
            self._l10n_ph_sss_prepare_row(line, amounts[line.employee_id]['compensation'])
            for line in self.line_ids
        ]
        file_data = "\r\n".join(";".join(row) for row in rows).encode()

        employer_number = self._l10n_ph_sss_sanitize(self.company_id.l10n_ph_hr_payroll_sss_number)
        self.write({
            'txt_file': BinaryBytes(file_data),
            'txt_filename': f"SSS_{employer_number}_{self.period_end_date.strftime('%m%Y')}.txt",
        })

        self.message_post(
            body=self.env._("SSS contribution file generated."),
            attachments=[(self.txt_filename, file_data)],
        )

    def action_draft_declaration(self):
        """ Reset to draft and drop the generated file, which no longer matches the report. """
        super().action_draft_declaration()
        self.write({'txt_file': False, 'txt_filename': False})

    def _l10n_ph_sss_prepare_row(self, line, compensation):
        """ Build the eleven ';'-separated fields of one employee row """
        self.ensure_one()
        employee = line.employee_id
        remark = line.l10n_ph_sss_remarks
        remark_date = self._l10n_ph_sss_get_remark_date(employee, remark)
        middle_name = employee.l10n_ph_legal_middle_name

        return [
            self._l10n_ph_sss_sanitize(self.company_id.l10n_ph_hr_payroll_sss_number),
            self._l10n_ph_sss_sanitize(self.company_id.l10n_ph_hr_payroll_sss_branch_code or '000').zfill(3),
            self._l10n_ph_sss_sanitize(employee.l10n_ph_hr_payroll_sss_number),
            self._l10n_ph_sss_sanitize(employee.l10n_ph_legal_last_name),
            self._l10n_ph_sss_sanitize(employee.l10n_ph_legal_first_name),
            self._l10n_ph_sss_sanitize(employee.l10n_ph_legal_suffix),
            self._l10n_ph_sss_sanitize(middle_name[0] if middle_name else ''),
            f"{self.currency_id.round(compensation):.2f}",
            remark,
            remark_date.strftime('%m%d%Y') if remark_date else 'NULL',
            self._l10n_ph_sss_sanitize(line.version_id.job_title) if remark == '1' else 'NULL',
        ]

    def _l10n_ph_sss_validate_data(self):
        """ Raise a single error listing everything that would make the file invalid. """
        self.ensure_one()
        errors = []
        if not self.company_id.l10n_ph_hr_payroll_sss_number:
            errors.append(self.env._("The Employer's SS Number is not set."))

        for line in self.line_ids:
            employee = line.employee_id
            employee_errors = []
            if not employee.l10n_ph_hr_payroll_sss_number:
                employee_errors.append(self.env._("The SS Number is not set."))
            if not employee.l10n_ph_legal_last_name:
                employee_errors.append(self.env._("The Last Name is not set."))
            if not employee.l10n_ph_legal_first_name:
                employee_errors.append(self.env._("The Given Name is not set."))
            # The SSS expects the position of the employees reported as newly hired, and nothing for the others.
            if line.l10n_ph_sss_remarks == '1' and not line.version_id.job_title:
                employee_errors.append(self.env._("The Position is required for a newly hired employee."))
            remark_date = self._l10n_ph_sss_get_remark_date(employee, line.l10n_ph_sss_remarks)
            if line.l10n_ph_sss_remarks in ('1', '2') and not remark_date:
                employee_errors.append(self.env._("A Hire/Termination Date is required for this remark."))
            if employee_errors:
                errors.append(f"{employee.name}:\n- " + "\n- ".join(employee_errors))

        if errors:
            raise UserError(self.env._(
                "The SSS contribution file cannot be generated. Please fix the following errors:\n%(errors)s",
                errors="\n".join(errors),
            ))

    def _l10n_ph_sss_get_remark(self, employee, earnings):
        """ Return the SSS status for the period: 1 - newly hired, 2 - left, 3 - no earnings, else N. """
        self.ensure_one()
        hire_date = employee._get_first_contract_date()
        if hire_date and self.period_start_date <= hire_date <= self.period_end_date:
            return '1'
        departure_date = employee.departure_date
        if departure_date and self.period_start_date <= departure_date <= self.period_end_date:
            return '2'
        if self.currency_id.is_zero(earnings):
            return '3'
        return 'N'

    def _l10n_ph_sss_get_remark_date(self, employee, remark):
        """ Return the hire date (remark 1) or termination date (remark 2) to report, else False. """
        self.ensure_one()
        if remark == '1':
            return employee._get_first_contract_date()
        if remark == '2':
            return employee.departure_date
        return False

    def _l10n_ph_sss_get_amounts(self, employees):
        """
        Return per employee the amounts the report needs over the period:
            - compensation: the taxable cash earnings, reported to the SSS as the actual compensation.
            - earnings: all cash earnings, used to spot who has nothing to report.

        Basic salary is tax-exempt for minimum wage earners, so the taxable salary can't be used to spot them.
        """
        self.ensure_one()
        all_payslips = self.env['hr.payslip'].search([
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', self.period_start_date),
            ('date_to', '<=', self.period_end_date),
            ('employee_id', 'in', employees.ids),
            ('struct_id', 'in', self._get_relevant_structures().ids),
            ('company_id', '=', self.company_id.id),
        ])
        line_values = all_payslips._get_line_values(set(all_payslips.line_ids.mapped('code')), compute_sum=True)
        payslips_per_employee = all_payslips.grouped('employee_id')

        amounts = {}
        for employee in employees:
            payslips = payslips_per_employee.get(employee, self.env['hr.payslip'])
            _, categories_totals = payslips._l10n_ph_hr_payroll_aggregate_totals(line_values)
            amounts[employee] = {
                'compensation': categories_totals['TAX_CASH_EARNINGS']['total'],
                'earnings': categories_totals['CASH_EARNINGS']['total'],
            }
        return amounts

    def _l10n_ph_sss_sanitize(self, value):
        """ Upper-case the value and drop the characters the SSS rejects, or 'NULL' if nothing remains. """
        if not value:
            return 'NULL'
        return INVALID_CHARACTERS.sub('', value).strip().upper() or 'NULL'
