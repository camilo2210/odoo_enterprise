# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import format_date


class L10n_HkIr56b(models.Model):
    _name = 'l10n_hk.ir56b'
    _inherit = ['l10n_hk.ird']
    _description = 'IR56B Sheet'
    _order = 'start_period'

    # ------------------
    # Fields declaration
    # ------------------

    year_of_employer_return = fields.Char("Year of Employer's Return",
                                compute="_compute_year_of_employer_return", store=True, readonly=False)

    @api.depends('submission_date')
    def _compute_year_of_employer_return(self):
        for sheet in self:
            sheet.year_of_employer_return = str(sheet.submission_date.year) if sheet.submission_date else str(date.today().year)

    @api.depends('year_of_employer_return', 'start_month', 'end_month')
    def _compute_period(self):
        for sheet in self:
            sheet.start_period = date(int(sheet.year_of_employer_return) - 1, int(sheet.start_month), 1)
            sheet.end_period = date(int(sheet.year_of_employer_return), int(sheet.end_month), 1) + relativedelta(day=31)

    def _compute_separate_original_from_adjustments(self):
        self.separate_original_from_adjustments = True

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('start_period', 'end_period')
    def _compute_display_name(self):
        lang_code = self.env.user.lang or 'en_US'
        for sheet in self:
            if sheet.start_period and sheet.end_period:
                sheet.display_name = sheet.env._(
                    "From %(start_period)s to %(end_period)s",
                    start_period=format_date(self.env, sheet.start_period, date_format="MMMM y", lang_code=lang_code),
                    end_period=format_date(self.env, sheet.end_period, date_format="MMMM y", lang_code=lang_code),
                )
            else:
                sheet.display_name = sheet.env._("IR56B Sheet")

    # ----------------
    # Business methods
    # ----------------

    def _get_report_version_domain(self):
        """
        Domain used to filter the employees that should appear in the report.
        This should pick all employees eligible for declarations in the report; a separate check will be done to remove
        those that were already declared in the same period.
        """
        self.ensure_one()
        relevant_payslips = self.env['hr.payslip'].search_read(
            domain=[
                ("state", "in", ["validated", "paid"]),
                ("company_id", "=", self.company_id.id),
                ("date_to", ">=", self.start_period),
                ("date_to", "<=", self.end_period),
                ("version_id.employee_type_id", "not in", [
                    self.env.ref("l10n_hk_hr_payroll.l10n_hk_contract_type_non_employee").id,
                    self.env.ref("l10n_hk_hr_payroll.l10n_hk_contract_type_contractor").id,
                ]),
            ],
            fields=['version_id'],
            order='id',
        )
        return Domain([
            ('company_id', '=', self.company_id.id),
            ('contract_date_start', '!=', False),
            ('contract_date_start', '<=', self.end_period),
            '|',
            ('contract_date_end', '=', False),
            ('contract_date_end', '>', self.end_period),
            ('id', 'in', {payslip['version_id'][0] for payslip in relevant_payslips}),
        ])

    def _get_rendering_data(self, employees):
        self.ensure_one()

        employees_error = self._check_employees(employees)
        if employees_error:
            return {'error': employees_error}

        report_info = self._get_report_info_data()

        try:
            payslip_info = self._get_employees_payslip_data(employees)
        except UserError as e:
            return {'error': str(e)}

        all_payslips = payslip_info['all_payslips']

        employee_payslips = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in all_payslips.sorted('employee_id'):
            employee_payslips[payslip.employee_id] |= payslip

        all_lines_values = all_payslips._get_line_values(set(all_payslips.line_ids.mapped('code')), compute_sum=True)

        employee_declarations = self.line_ids.grouped('employee_id')
        employees_data = []
        for sequence, employee in enumerate(employee_payslips, start=1):
            payslips = employee_payslips[employee]
            mapped_total = {
                code: sum(all_lines_values[code][p.id]['total'] for p in payslips)
                for code in all_lines_values
            }

            start_date = self.start_period if self.start_period > employee._get_first_version_date() else employee._get_first_version_date()
            _, categories_totals = payslips._l10n_hk_aggregate_totals(all_lines_values)

            employees_data.append({
                **self._get_employee_data(employee),
                **self._get_employee_spouse_data(employee),
                **self._get_employee_rental_data(employee, payslips, all_lines_values),
                **self._get_employee_rap_data(payslips, all_lines_values),
                'date_from': self.start_period,
                'date_to': self.end_period,
                'SheetNo': sequence,
                'TypeOfForm': employee_declarations.get(employee).l10n_hk_hr_payroll_type_of_form,
                'RTN_ASS_YR': self.year_of_employer_return,
                'StartDateOfEmp': start_date,
                'EndDateOfEmp': self.end_period,
                'AmtOfSalary': self._format_ird_amount(categories_totals['HK_BASIC']),
                'AmtOfLeavePay': self._format_ird_amount(categories_totals['LEAVE_PAY']),
                'AmtOfDirectorFee': self._format_ird_amount(categories_totals['DIRECTOR_FEE']),
                'AmtOfBpEtc': self._format_ird_amount(categories_totals['BACKPAY'] + categories_totals['PILON']),
                'AmtOfPayRetire': self._format_ird_amount(categories_totals['RETIREMENT']),
                'AmtOfPension': self._format_ird_amount(categories_totals['PENSION']),
                'AmtPaidOverseaCo': self._format_ird_amount(categories_totals['OVERSEAS_INCOME']),
                'AmtOfCommFee': self._format_ird_amount(categories_totals['COMMISSION']),
                'AmtOfBonus': self._format_ird_amount(categories_totals['BONUS']),
                'AmtOfSalTaxPaid': self._format_ird_amount(categories_totals['TAX_PAID']),
                'AmtOfEduBen': self._format_ird_amount(categories_totals['EDUCATION']),
                'AmtOfGainShareOption': self._format_ird_amount(categories_totals['SHARE_OPTION']),
                'TotalIncome': self._format_ird_amount(categories_totals['GROSS'] - mapped_total.get('HRA', 0)),
                'AmtOfEEMC': self._format_ird_amount(mapped_total.get('EEMC', 0)),
                'AmtOfERMC': self._format_ird_amount(mapped_total.get('ERMC', 0)),
                'AmtOfEEVC': self._format_ird_amount(mapped_total.get('EEVC', 0)),
                'AmtOfERVC': self._format_ird_amount(mapped_total.get('ERVC', 0)),
            })

        sheets_count = len(employees_data)

        total_data = {
            'NoRecordBatch': '{:05}'.format(sheets_count),
            'TotIncomeBatch': self._format_ird_amount(sum(ed['TotalIncome'] for ed in employees_data)),
        }

        return {'data': report_info, 'employees_data': employees_data, 'total_data': total_data}

    # XML export - for government submission

    def _get_xml_report_xsd_schemas(self, type_of_form):
        self.ensure_one()
        return {
            'O': self._get_xml_resource('ir56b_annual.xsd'),
            'ARS': self._get_xml_resource('ir56b_additional_replacement_supplementary.xsd'),
        }.get(type_of_form)

    def _get_xml_report_filename(self, file_number=False):
        """
        Returns the IR56B report filename.
        In case of the report generating multiple files, we will append a file number to the name.
        """
        self.ensure_one()
        company_name = self.company_id.name.replace(' ', '_')
        if file_number:
            xml_filename = f'{company_name}_IR56B_{self.year_of_employer_return}_{self.type_of_form}_{file_number}.xml'
        else:
            xml_filename = f'{company_name}_IR56B_{self.year_of_employer_return}_{self.type_of_form}.xml'
        return xml_filename

    def _get_xml_report_template(self):
        self.ensure_one()
        return 'l10n_hk_hr_payroll.ir56b_xml_report'

    # PDF export - for employee information

    def _get_pdf_report(self):
        return self.env.ref('l10n_hk_hr_payroll.action_report_employee_ir56b')

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        employee_name = employee.name.replace(' ', '_')
        return self.env._('%(employee_name)s_IR56B_%(start_year)s', employee_name=employee_name, start_year=self.start_year)

    def _post_process_rendering_data_pdf(self, rendering_data):
        result = {}
        for sheet_values in rendering_data['employees_data']:
            result[sheet_values['employee']] = {**sheet_values, **rendering_data['data']}
        return result
