# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io
from datetime import date
from functools import reduce

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import BinaryBytes, float_compare, format_date

from .utils import format_amount, format_char, format_digits, join_record
from odoo.addons.phone_validation.tools import phone_validation

FINANCIAL_YEAR_QUARTERS = {
    #  q: [(start_date, end_date, due_date)]
    'q1': [(1, 4), (30, 6), (31, 7)],
    'q2': [(1, 7), (30, 9), (31, 10)],
    'q3': [(1, 10), (31, 12), (31, 1)],
    'q4': [(1, 1), (31, 3), (31, 5)],  # year = financial_year_start + 1
}


class L10nInPayrollForm138(models.Model):
    _name = 'l10n.in.payroll.form.138'
    _description = 'Form 138'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'financial_year_start desc, quarter asc'

    def _compute_display_name(self):
        for form in self:
            form.display_name = self.env._(
                "Form 138 %(fy_start)s-%(fy_end)s %(quarter)s",
                fy_start=form.financial_year_start,
                fy_end=int(form.financial_year_start) + 1,
                quarter=form.quarter.capitalize(),
            )

    @api.model
    def _default_financial_year_start(self):
        today = fields.Date.context_today(self)
        return today.year if today.month > 3 else today.year - 1

    def _get_financial_year_start_selection(self):
        current_start_year = self._default_financial_year_start()
        selection = []
        for year_offset in range(-1, 2):
            target_year = current_start_year + year_offset
            selection.append((str(target_year), f'{target_year}-{target_year + 1}'))
        return selection

    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        domain=[('partner_id.country_id.code', '=', 'IN')],
    )
    financial_year_start = fields.Selection(
        selection='_get_financial_year_start_selection',
        default=_default_financial_year_start,
        string="Financial Year",
        required=True,
    )
    quarter = fields.Selection(selection=[
        ('q1', "Q1"),
        ('q2', "Q2"),
        ('q3', "Q3"),
        ('q4', "Q4"),
    ], string="Quarter", default='q1', required=True, tracking=True)
    quarter_date_start = fields.Date("Start Date", compute='_compute_quarter_dates', store=True)
    quarter_date_end = fields.Date("End Date", compute='_compute_quarter_dates', store=True)
    quarter_due_date = fields.Date("Due Date", compute='_compute_quarter_dates', store=True)
    state = fields.Selection(selection=[
        ('draft', "Draft"),
        ('done', "Done"),
    ], string="State", default='draft', required=True, tracking=True)
    challan_ids = fields.One2many('l10n.in.tds.challan', 'form_138_id', string="Challans")
    has_regular_statement_for_earlier_period = fields.Boolean(
        string="Earlier Regular Statement",
        help="Check this when filing a regular statement for a previous period.",
    )
    previous_regular_statement_token_no = fields.Char(
        string="Previous Regular Statement Token No.",
        help="Token number of the immediate previous regular statement for Form 138.",
    )
    has_employer_address_changed = fields.Boolean(string="Change of Address of Employer Since Last Return")
    has_responsible_person_address_changed = fields.Boolean(string="Change of Address of Responsible Person Since Last Return")
    txt_file = fields.Binary(string="Text File", readonly=True, copy=False, attachment=False)
    txt_filename = fields.Char(string="Text Filename", default=lambda self: self.env._("Not Generated"), readonly=True, copy=False)

    _unique_form_fy_quarter = models.Constraint(
        'UNIQUE (company_id, financial_year_start, quarter)',
        "There shouldn't be duplicate forms for the same quarter in same FY.",
    )

    @api.depends('financial_year_start', 'quarter')
    def _compute_quarter_dates(self):
        for form in self:
            quarter_dates = FINANCIAL_YEAR_QUARTERS.get(form.quarter)
            if not form.financial_year_start or not quarter_dates:
                form.quarter_date_start, form.quarter_date_end, form.quarter_due_date = [None] * 3
            fy_start = int(form.financial_year_start)
            form.quarter_date_start = date(year=fy_start, month=quarter_dates[0][1], day=quarter_dates[0][0])
            form.quarter_date_end = date(year=fy_start, month=quarter_dates[1][1], day=quarter_dates[1][0])
            form.quarter_due_date = date(year=fy_start, month=quarter_dates[2][1], day=quarter_dates[2][0])
            if form.quarter == 'q4':
                form.quarter_date_start += relativedelta(years=1)
                form.quarter_date_end += relativedelta(years=1)
                form.quarter_due_date += relativedelta(years=1)

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "IN":
            raise UserError(self.env._('You must be logged in a Indian company to use this feature'))
        return super().default_get(fields)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_state_done(self):
        if any(form.state == 'done' for form in self):
            raise UserError(self.env._("Form cannot be deleted in 'done' state."))

    @api.model
    def _create_forms_138_for_current_year(self):
        current_year = fields.Date.context_today(self).year
        existing_forms = self.search([
            ('company_id', '=', self.env.company.id),
            ('financial_year_start', 'in', current_year),
            ('quarter', 'in', FINANCIAL_YEAR_QUARTERS.keys()),
        ])
        quarter_data_vals = []
        for quarter in FINANCIAL_YEAR_QUARTERS.keys() - set(existing_forms.mapped('quarter')):
            quarter_data_vals.append({
                'company_id': self.env.company.id,
                'financial_year_start': current_year,
                'quarter': quarter,
            })
        self.create(quarter_data_vals)

    def action_open_details(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.in.payroll.form.138',
            'view_mode': 'form',
            'res_id': self.id,
        }

    def action_mark_as_done(self):
        if not self.challan_ids:
            raise UserError(self.env._("There should be at least one challan to mark form as done."))
        self.challan_ids.action_mark_as_done()
        self.state = 'done'

    def action_set_to_draft(self):
        self.state = 'draft'
        self.txt_file = None
        self.txt_filename = self.env._("Not Generated")

    def _get_filing_period(self):
        self.ensure_one()
        financial_year_start = int(self.financial_year_start)
        financial_year = f'{financial_year_start}{str(financial_year_start + 1)[-2:]}'
        assessment_year = f'{financial_year_start + 1}{str(financial_year_start + 2)[-2:]}'
        return assessment_year, financial_year, self.quarter.upper()

    def _get_salary_section_code(self):
        self.ensure_one()
        if self.company_id.l10n_in_deductor_type in ('S', 'E', 'H', 'N'):
            return '1001'
        if self.company_id.l10n_in_deductor_type in ('A', 'D', 'G', 'L'):
            return '1003'
        return '1002'

    def _prepare_fh_record(self):
        self.ensure_one()
        company = self.company_id
        return [
            '1',  # Line Number
            'FH',  # Record Type
            'SL1',  # File Type
            'R',  # Upload Type
            format_date(self.env, fields.Date.context_today(self), date_format='ddMMY'),  # File Creation Date
            '',  # File Sequence No.
            'D',  # Uploader Type
            company.l10n_in_deductor_tan,  # TAN of Employer
            '1',  # Total No. of Batches
            'Odoo',  # Name of Return Preparation Utility
            '',  # Record Hash (not applicable)
            '',  # FVU Version (not applicable)
            '',  # File Hash (not applicable)
            '',  # Sam Version (not applicable)
            '',  # SAM Hash (not applicable)
            '',  # SCM Version (not applicable)
            '',  # SCM Hash (not applicable)
            '',  # Consolidated file hash (not applicable)
        ]

    def _validate_fields_with_size_constraints(self, fields_with_size_contraints):
        field_str_with_size = []
        for field, size, field_str in fields_with_size_contraints:
            if isinstance(field, list):
                for f, f_str in zip(field, field_str):
                    if f and len(f) > size:
                        field_str_with_size.append([f_str, size])
            elif field and len(field) > size:
                field_str_with_size.append([field_str, size])

        if field_str_with_size:
            error_msg = self.env._("Following fields don't adhere to the size constraints:\n")
            for field_str, size in field_str_with_size:
                error_msg += self.env._("- %(field_str)s's length should be less than %(size)d\n", field_str=field_str, size=size)
            raise ValidationError(error_msg)

    def _prepare_bh_record(self):
        """Prepare the Form 138 Batch Header (BH) record containing the employer,
        filing period, responsible person, and aggregate challan information.

        Format reference: https://tinpan.proteantech.in/downloads/e-tds/eTDS-download-regular.html
        """
        self.ensure_one()

        company = self.company_id
        company_partner = company.partner_id
        responsible = company.l10n_in_responsible_person_id

        company_address_lines = company_partner._get_address_lines()
        responsible_address_lines = responsible._get_address_lines()
        responsible_pan = responsible.l10n_in_pan
        company_email = company.email or company_partner.email
        responsible_email = responsible.work_email or responsible.private_email

        company_phone_data = phone_validation.phone_get_region_data_for_number(company_partner.phone or company.phone)
        company_phone_country_code = company_phone_data['phone_code']
        company_phone_number = company_phone_data['national_number']

        responsible_phone_data = phone_validation.phone_get_region_data_for_number(responsible.work_phone or responsible.private_phone)
        responsible_phone_country_code = responsible_phone_data['phone_code']
        responsible_phone_number = responsible_phone_data['national_number']

        company_state_code = company_partner.state_id.l10n_in_tds_numeric_code if company_partner.state_id else ''
        responsible_state_code = responsible.private_state_id.l10n_in_tds_numeric_code if responsible.private_state_id else ''
        state_name_code = company_state_code if company.l10n_in_deductor_type in ('S', 'E', 'H', 'N') else ''
        address_line_names = [
            self.env._("Street 1"),
            self.env._("Street 2"),
            self.env._("City"),
            self.env._("State"),
            self.env._("Country"),
        ]
        fields_with_size_contraints = [
            (company.name, 75, self.env._("Company's Name")),
            (company_email, 75, self.env._("Company's Email")),
            (company_phone_number, 10, self.env._("Company's Contact Number")),
            (responsible.name, 75, self.env._("Responsible Person's Name")),
            ((responsible.job_title or responsible.job_id.name or 'NA'), 20, self.env._("Responsible Person's Job Title")),
            (responsible_pan, 10, self.env._("Responsible Person's PAN")),
            (responsible_email, 75, self.env._("Responsible Person's Email")),
            (responsible_phone_number, 10, self.env._("Responsible Person's Contact Number")),
            (self.previous_regular_statement_token_no or '', 15, self.env._("Previous Regular Statement Token No.")),
            (company_address_lines, 25, address_line_names),
            (responsible_address_lines, 25, address_line_names),
        ]
        self._validate_fields_with_size_constraints(fields_with_size_contraints)
        if self.has_regular_statement_for_earlier_period and not self.previous_regular_statement_token_no:
            raise ValidationError(self.env._("The previous regular statement token number is required when filing a regular statement for an earlier period."))

        assessment_year, financial_year, quarter = self._get_filing_period()

        return [
            '2',  # Line Number
            'BH',  # Record Type
            '1',  # Batch Number
            str(len(self.challan_ids)),  # Count of Challan/transfer voucher Records
            '138',  # Form Number
            '',  # Transaction Type (not applicable)
            '',  # Batch Updation Indicator (not applicable)
            '',  # Original Token Number (not applicable)
            self.previous_regular_statement_token_no if self.has_regular_statement_for_earlier_period else '',  # Token no. of previous regular statement
            '',  # Token Number of the statement submitted (not applicable)
            '',  # Token Number date (not applicable)
            '',  # Last TAN of Deductor / Employer / Collector (not applicable)
            company.l10n_in_deductor_tan,  # TAN of Deductor / Employer
            '',  # Receipt number provided by TIN (not applicable)
            company.l10n_in_deductor_pan,  # PAN of Deductor / Employer
            assessment_year,  # Assessment Yr
            financial_year,  # Financial Yr
            quarter,  # Period
            company.name,  # Name of Employer / Deductor
            company_partner.country_id.name,  # Employer / Deductor Address6 / Country-Region
            company_address_lines[0],  # Employer / Deductor Address1
            company_address_lines[1],  # Employer / Deductor Address2
            company_address_lines[2],  # Employer / Deductor Address3
            company_address_lines[3],  # Employer / Deductor Address4
            company_address_lines[4],  # Employer / Deductor Address5
            company_state_code,  # Employer / Deductor State
            format_digits(company_partner.zip, 6),  # Employer / Deductor PIN
            company_email,  # Employer / Deductor Email ID
            company_phone_country_code,  # Employer / Deductor Contact Country Code
            company_phone_number,  # Employer / Deductor Contact Number
            '',  # Filler 1
            company.l10n_in_deductor_type,  # Deductor Type
            responsible.name,  # Name of Person responsible for paying salary / Deduction
            responsible.job_title or responsible.job_id.name or 'NA',  # Designation of the Person responsible for paying salary / Deduction
            responsible_address_lines[0],  # Responsible Person's Address1
            responsible_address_lines[1],  # Responsible Person's Address2
            responsible_address_lines[2],  # Responsible Person's Address3
            responsible_address_lines[3],  # Responsible Person's Address4
            responsible_address_lines[4],  # Responsible Person's Address5
            responsible_state_code,  # Responsible Person's State
            format_digits(responsible.private_zip, 6),  # Responsible Person's PIN
            responsible_email,  # Responsible Person's Email ID -1
            responsible.private_country_id.name or '',  # Responsible Persons country region
            responsible_phone_country_code,  # Responsible Person Contact Country/Region
            responsible_phone_number,  # Responsible Person Contact Number
            '',  # Filler 3
            format_amount(
                sum(challan._get_challan_amounts()['deposit_amount'] for challan in self.challan_ids),
            ),  # Batch Total of - Total of Deposit Amount as per Challan
            '',  # Unmatched challan count
            '',  # Count of Salary Details Records (Not applicable)
            '',  # Batch Total of - Gross Total Income as per Salary Detail (Not applicable)
            '',  # Filler 4
            'Y' if self.has_regular_statement_for_earlier_period else 'N',  # Whether regular statement for Form 138 filed for earlier period
            '',  # Last Deductor Type
            state_name_code,  # State Name
            '',  # Filler 5
            '',  # Filler 6
            '',  # Ministry Name
            '',  # Ministry Name (Others)
            responsible_pan,  # PAN of Responsible Person
            '',  # Filler 7
            '',  # Filler 8
            '',  # Filler 9
            '',  # Filler 10
            '',  # Filler 11
            '',  # Filler 12
            '',  # Filler 13
            '',  # Filler 14
            '',  # Account Office Identification Number (AIN) of PAO/ TO/ CDDO
            '',  # Goods and Service Tax Number (GSTN)
            '',  # Count of Section 194P Detail Records (Not applicable)
            '',  # Batch Total of - Gross Total Income as per Section 194P Detail (Not applicable)
            '',  # Record Hash (not applicable)
        ]

    def _validate_before_export(self):
        self.ensure_one()
        company = self.company_id
        company_partner = company.partner_id
        responsible = company.l10n_in_responsible_person_id

        mandatory_company_fields = {
            self.env._("- Company PAN No."): company.l10n_in_deductor_pan,
            self.env._("- Company TAN No."): company.l10n_in_deductor_tan,
            self.env._("- Deductor Type"): company.l10n_in_deductor_type,
            self.env._("- Responsible Person"): company.l10n_in_responsible_person_id,
            self.env._("- Company State"): company_partner.state_id,
            self.env._("- Company Country/Region"): company_partner.country_id,
            self.env._("- Company PIN"): company_partner.zip,
            self.env._("- Company Contact Number"): company_partner.phone or company.phone,
            self.env._("- Responsible Person State"): responsible.private_state_id,
            self.env._("- Responsible Person Country/Region"): responsible.private_country_id,
            self.env._("- Responsible Person PIN Code"): responsible.private_zip,
            self.env._("- Responsible Person Contact Number"): responsible.private_phone or responsible.work_phone,
        }

        missing_company_fields = []
        for field, value in mandatory_company_fields.items():
            if not value:
                missing_company_fields.append(field)

        if missing_company_fields:
            raise ValidationError(self.env._(
                "Please set following values in configuration:\n%(missing_company_fields)s",
                missing_company_fields='\n'.join(missing_company_fields),
            ))

        challans_with_issues = []
        for challan in self.challan_ids:
            challan_issues = []
            amounts = challan._get_challan_amounts()
            if not challan.paid_date:
                challan_issues.append(self.env._("- Challan paid date is required."))
            if float_compare(amounts['deductee_deposit_amount'], amounts['deposit_amount'], precision_digits=2) > 0:
                challan_issues.append(self.env._(
                    "- total tax deposited as per deductee annexure (%(deductee).2f) cannot exceed total deposit amount as per challan (%(challan_amount).2f).",
                    challan=challan.challan_number,
                    deductee=amounts['deductee_deposit_amount'],
                    challan_amount=amounts['deposit_amount'],
                ))
            if challan_issues:
                issues_joined = '\n'.join(challan_issues)
                challans_with_issues.append(self.env._("challan #%(challan_number)s has following issues:\n%(issues)s", challan_number=challan.challan_number, issues=issues_joined))

        if challans_with_issues:
            raise ValidationError('\n'.join(challans_with_issues))

    def _prepare_q4_salary_detail_values(self):
        self.ensure_one()
        if self.quarter != 'q4':
            return []

        financial_year_start = int(self.financial_year_start)
        fy_date_start, fy_date_end = date(financial_year_start, 4, 1), date(financial_year_start + 1, 3, 31)
        standard_deduction = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_in_standard_deduction', date=fy_date_start)
        salary_details = []

        # Base domain for fetching FY payslips
        grouped_payslips = self.env['hr.payslip']._read_group(
            domain=[
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'paid'),
                ('date_from', '>=', fy_date_start),
                ('date_to', '<=', fy_date_end),
                ('is_refund_payslip', '=', False),
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset'],
        )
        if len(grouped_payslips) > 1:
            employee_ids = reduce(lambda emp_slip_1, emp_slip_2: emp_slip_1[0] + emp_slip_2[0], grouped_payslips)
        else:
            employee_ids = grouped_payslips[0][0]
        version_map = dict(self.env['hr.version']._read_group(
            domain=[
                ('employee_id', 'in', employee_ids.ids),
                ('contract_date_start', '<=', fy_date_end),
                '|',
                    ('contract_date_end', '=', False),
                    ('contract_date_end', '>=', fy_date_start),
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset'],
        ))
        gross_map = self.env['hr.payslip']._l10n_in_taxable_gross_total(grouped_payslips)
        tax_parameters = self.env['hr.employee']._l10n_in_get_tax_parameters(fy_date_start)
        for employee in employee_ids:
            if not (employee_version := version_map.get(employee)):
                continue
            tax_inputs = employee._l10n_in_get_tax_input_values(employee_version, date=fy_date_start)
            current_year_salary, employee_current_year_tds = gross_map[employee.id]
            previous_year_salary = tax_inputs.get('income_previous_employment', 0.0)
            total_salary = current_year_salary + previous_year_salary

            section_16_records = []
            if standard_deduction_amount := standard_deduction:
                section_16_records.append(('16(ia)', standard_deduction_amount))
            section_16_total = sum(amount for _section, amount in section_16_records)
            income_chargeable_salaries = total_salary - section_16_total

            income_other_heads = (
                tax_inputs.get('income_from_other_sources', 0.0)
                + tax_inputs.get('income_let_out_property', 0.0)
                + tax_inputs.get('interest_fd_deposit', 0.0)
                + tax_inputs.get('interest_national_savings', 0.0)
            )
            income_other_sources = max(
                tax_inputs.get('income_from_other_sources', 0.0)
                + tax_inputs.get('interest_fd_deposit', 0.0)
                + tax_inputs.get('interest_national_savings', 0.0),
                0.0,
            )

            gross_total_income = income_chargeable_salaries + income_other_heads
            tax_totals = employee._l10n_in_get_tax_totals(gross_total_income, tax_parameters)
            previous_employer_tds = tax_inputs.get('tax_paid_previous_employer', 0.0)
            total_tax_deducted = employee_current_year_tds + previous_employer_tds
            employment_start, employment_end = employee_version._get_tds_q4_employment_period(fy_date_start, fy_date_end)

            salary_details.append({
                'employee': employee,
                'employee_version': employee_version,
                'category': employee._get_tds_q4_category(fy_date_end),
                'employment_start': employment_start,
                'employment_end': employment_end,
                'total_salary': total_salary,
                'section_16_records': section_16_records,
                'section_16_total': section_16_total,
                'income_chargeable_salaries': income_chargeable_salaries,
                'income_other_heads': income_other_heads,
                'gross_total_income': gross_total_income,
                'tax_on_taxable_income': tax_totals.get('tax_on_taxable_income', 0.0),
                'surcharge': tax_totals.get('surcharge', 0.0),
                'cess': tax_totals.get('cess', 0.0),
                'rebate': tax_totals.get('rebate', 0.0),
                'net_tax_payable': tax_totals.get('net_tax_payable', 0.0),
                'total_tax_deducted': total_tax_deducted,
                'shortfall_or_excess': tax_totals.get('net_tax_payable', 0.0) - total_tax_deducted,
                'current_year_salary': current_year_salary,
                'previous_year_salary': previous_year_salary,
                'employee_current_year_tds': employee_current_year_tds,
                'previous_employer_tds': previous_employer_tds,
                'income_other_sources': income_other_sources,
            })

        return salary_details

    def _prepare_q4_sd_record(self, salary_detail, line_number, salary_sequence):
        """Prepare a Q4 Form 138 Salary Detail (SD) record containing an employee's
        annual salary, deductions, taxable income, and tax reconciliation.

        Format reference: https://tinpan.proteantech.in/downloads/e-tds/eTDS-download-regular.html
        """
        employee = salary_detail['employee']
        return [
            str(line_number),  # Line Number
            'SD',  # Record Type
            '1',  # Batch Number
            str(salary_sequence),  # Salary Details Record No
            'A',  # Mode
            '',  # Filler 7
            employee.l10n_in_pan or 'PANNOTAVBL',  # Employee PAN
            '',  # Pan Reference Number (not applicable)
            format_char(employee.name, 75),  # Name of Employee
            salary_detail['category'],  # Category of Employee
            format_date(self.env, salary_detail['employment_start'], date_format='ddMMY'),  # Period of Employment From
            format_date(self.env, salary_detail['employment_end'], date_format='ddMMY'),  # Period of Employment To
            format_amount(salary_detail['total_salary']),  # Total amount of salary
            '',  # Filler 8
            str(len(salary_detail['section_16_records'])),  # Count of Section 16 Detail Records
            format_amount(salary_detail['section_16_total']),  # Gross Total of Section 16 deductions
            format_amount(salary_detail['income_chargeable_salaries']),  # Income chargeable under salaries
            format_amount(salary_detail['income_other_heads']),  # Other heads income/loss offered for TDS
            format_amount(salary_detail['gross_total_income']),  # Gross Total Income
            '',  # Last Gross Total Income (not applicable)
            '0',  # Count of Chapter VI-A Detail Records
            '0.00',  # Gross Total of Chapter VI-A deductions
            format_amount(salary_detail['gross_total_income']),  # Total Taxable Income
            format_amount(salary_detail['tax_on_taxable_income']),  # Income Tax on Total Income
            format_amount(salary_detail['surcharge']),  # Surcharge
            format_amount(salary_detail['cess']),  # Education Cess
            '0',  # Income Tax Relief u/s 89
            format_amount(salary_detail['net_tax_payable']),  # Net Income Tax payable
            format_amount(salary_detail['total_tax_deducted']),  # Total tax deducted/collected for the whole year
            format_amount(salary_detail['shortfall_or_excess']),  # Shortfall / Excess tax deduction
            '',  # Aggregate 80C/80CCC/80CCD(1) deductions
            '',  # Remarks for future use
            '',  # Remarks for future use
            format_amount(salary_detail['current_year_salary']),  # Taxable amount current employer
            format_amount(salary_detail['previous_year_salary']),  # Reported taxable amount previous employer
            format_amount(salary_detail['employee_current_year_tds']),  # Employee current year TDS
            format_amount(salary_detail['previous_employer_tds']),  # Previous employer TDS
            'N' if employee.l10n_in_pan else 'Y',  # Whether tax deducted at higher rate due to non-furnishing of PAN
            'N',  # Whether aggregate rent payment exceeds one lakh
            '0',  # Count of landlord PANs
            '',  # Landlord PAN 1
            '',  # Landlord Name 1
            '',  # Landlord PAN 2
            '',  # Landlord Name 2
            '',  # Landlord PAN 3
            '',  # Landlord Name 3
            '',  # Landlord PAN 4
            '',  # Landlord Name 4
            'N',  # Whether interest paid to lender under house property
            '0',  # Count of lender PANs
            '',  # Lender PAN 1
            '',  # Lender Name 1
            '',  # Lender PAN 2
            '',  # Lender Name 2
            '',  # Lender PAN 3
            '',  # Lender Name 3
            '',  # Lender PAN 4
            '',  # Lender Name 4
            'N',  # Whether superannuation fund contribution was repaid
            '',  # Superannuation fund name
            '',  # Superannuation contribution from date
            '',  # Superannuation contribution to date
            '',  # Superannuation principal/interest repayment amount
            '',  # Average rate of deduction of tax during preceding three years
            '',  # Tax deducted on superannuation repayment
            '',  # Gross total income including superannuation repayment
            format_amount(salary_detail['current_year_salary']),  # Gross Salary u/s 17(1)
            '0.00',  # Value of perquisites u/s 17(2)
            '0.00',  # Profits in lieu of salary u/s 17(3)
            '',  # Travel concession or assistance u/s 10(5)
            '0.00',  # Death-cum-retirement gratuity u/s 10(10)
            '0.00',  # Commuted value of pension u/s 10(10A)
            '0.00',  # Leave salary encashment u/s 10(10AA)
            '',  # HRA u/s 10(13A)
            '0.00',  # Other exemption u/s 10
            '0.00',  # Total exemption claimed u/s 10
            format_amount(salary_detail['income_other_sources']),  # Other sources offered for TDS
            format_amount(salary_detail['rebate']),  # Rebate u/s 87A
            'N',  # 15BAC option should come from employee declaration; assume new regime default
            '0.00',  # Other special allowances u/s 10(14)
            '0.00',  # Other TDS/TCS reported u/s 192(2B), other than previous employer TDS
            '',  # Filler 10
            '',  # Filler 11
            '',  # Filler 12
            '',  # Filler 13
            '',  # Filler 14
            '',  # Filler 15
            '',  # Record Hash (not applicable)
        ]

    def _prepare_q4_s16_record(self, line_number, salary_sequence, s16_sequence, section, amount):
        return [
            str(line_number),  # Line Number
            'S16',  # Record Type
            '1',  # Batch Number
            str(salary_sequence),  # Salary Detail Record No
            str(s16_sequence),  # Salary Detail - Section 16 Details Record No
            section,  # Section 16 section ID
            format_amount(amount),  # Total Deduction under Section 16
            '',  # Record Hash (not applicable)
        ]

    def generate_138_txt_file(self):
        self.ensure_one()
        _, financial_year, quarter = self._get_filing_period()
        self._validate_before_export()
        q4_salary_details = self._prepare_q4_salary_detail_values()
        output = io.StringIO()

        output.write(join_record(self._prepare_fh_record()) + '\r\n')
        output.write(join_record(self._prepare_bh_record()) + '\r\n')

        sorted_challans = self.challan_ids.sorted('paid_date')
        record_count = 2

        for challan_sequence, challan in enumerate(sorted_challans, start=1):
            record_count += 1
            output.write(join_record(challan._prepare_cd_record(record_count, challan_sequence)) + '\r\n')

            sorted_lines = challan.challan_line_ids.sorted('employee_name')
            for deductee_sequence, challan_line in enumerate(sorted_lines, start=1):
                record_count += 1
                output.write(join_record(challan_line._prepare_dd_record(
                    record_count, challan_sequence, deductee_sequence,
                )) + '\r\n')

        for salary_sequence, salary_detail in enumerate(q4_salary_details, start=1):
            record_count += 1
            output.write(join_record(self._prepare_q4_sd_record(salary_detail, record_count, salary_sequence)) + '\r\n')

            for s16_sequence, (section, amount) in enumerate(salary_detail['section_16_records'], start=1):
                record_count += 1
                output.write(join_record(self._prepare_q4_s16_record(
                    record_count, salary_sequence, s16_sequence, section, amount,
                )) + '\r\n')

        content = output.getvalue()
        output.close()
        txt_file = BinaryBytes(content.encode('ascii', 'ignore'))

        self.write({
            'txt_file': txt_file,
            'txt_filename': f'{financial_year}{quarter}.txt',
        })
