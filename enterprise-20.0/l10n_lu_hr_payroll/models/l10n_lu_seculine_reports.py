# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import BinaryBytes, float_round


class L10nLuSeculineReports(models.Model):
    _name = 'l10n.lu.seculine.reports'
    _description = 'Seculine Reports'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "LU":
            raise UserError(self.env._('You must be logged in a Luxembourger company to use this feature'))
        return super().default_get(fields)

    def _get_year_selection(self):
        end_year = (fields.Date.context_today(self) - relativedelta(months=1)).year
        return [
            (str(year), year) for year in range(end_year, end_year - 2, -1)
        ]

    report_type = fields.Selection([
        ('decsal', 'DECSAL'),
        ('decmal', 'DECMAL'),
    ], string='Report Type', default='decsal', required=True)
    report_action = fields.Selection([
        ('information', 'Send all Information'),
        ('correction', 'Correction'),
    ], string='Action', default='information', required=True)
    year = fields.Selection(selection='_get_year_selection', string='Year', required=True,
        default=lambda self: self._get_year_selection()[0][0])
    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], string='Month', required=True, default=lambda self: str((fields.Date.context_today(self) - relativedelta(months=1)).month))
    report_file = fields.Binary()
    report_sequence = fields.Integer("Sequence Number", readonly=True)
    date_start = fields.Date(compute='_compute_dates')
    date_end = fields.Date(compute='_compute_dates')
    batch_ids = fields.Many2many('hr.payslip.run', compute='_compute_batch_ids')
    situational_unemployment_ids = fields.One2many(
        'l10n.lu.situational.unemployment',
        'monthly_declaration_id',
        compute='_compute_situational_unemployment_ids',
        readonly=False,
        store=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    employee_ids = fields.Many2many('hr.employee', string='Employees', domain="[('company_id', '=', company_id)]")

    @api.depends('report_type', 'year', 'month')
    def _compute_display_name(self):
        for report in self:
            if report.month and report.year:
                report.display_name = f"{report.report_type.upper()} - {report.month}/{report.year}"
            else:
                report.display_name = f"{report.report_type.upper()} - Draft"

    @api.depends('month', 'year')
    def _compute_dates(self):
        for report in self:
            if not (report.month and report.year):
                report.date_start = report.date_end = False
                continue
            report.date_start = date(int(report.year), int(report.month), 1)
            report.date_end = report.date_start + relativedelta(months=1, days=-1)

    @api.depends('company_id', 'date_start', 'date_end')
    def _compute_batch_ids(self):
        valid_reports = self.filtered(lambda report: report.date_start and report.date_end)
        for report in self - valid_reports:
            report.batch_ids = self.env['hr.payslip.run']
        if not valid_reports:
            return
        domain = Domain.OR([
            Domain([
                ('company_id', '=', report.company_id.id),
                ('date_start', '>=', report.date_start),
                ('date_end', '<=', report.date_end),
                ('state', 'not in', ['01_ready', '04_cancel']),
            ])
            for report in valid_reports
        ])
        batch_ids_by_company = dict(self.env['hr.payslip.run']._read_group(
            domain=domain,
            groupby=['company_id'],
            aggregates=['id:recordset'],
        ))
        for report in valid_reports:
            report.batch_ids = batch_ids_by_company.get(report.company_id, self.env['hr.payslip.run'])

    @api.depends('batch_ids')
    def _compute_situational_unemployment_ids(self):
        situational_unemp = self.env.ref('hr_work_entry.l10n_lu_work_entry_type_situational_unemployment')
        for report in self:
            regular_payslips = report.batch_ids.slip_ids.filtered(lambda p: p.struct_id == p.struct_type_id.default_struct_id)
            unemp_payslips = regular_payslips.worked_days_line_ids.filtered(
                lambda w: w.work_entry_type_id.id == situational_unemp.id
            ).mapped('payslip_id')

            report.situational_unemployment_ids = [(5, 0)] + [
                (0, 0, {
                    'employee_id': payslip.employee_id.id,
                    'payslip_id': payslip.id,
                    'hours': payslip.worked_days_line_ids
                            .filtered(lambda w: w.work_entry_type_id.id == situational_unemp.id)
                            .number_of_hours,
                }) for payslip in unemp_payslips
            ]

    def action_generate_report(self):
        self.ensure_one()
        company = self.env.company
        if not (company.l10n_lu_official_social_security and company.l10n_lu_seculine):
            raise ValidationError(self.env._('Missing company\'s social security or SECUline numbers'))

        if self.report_type == 'decsal':
            self._generate_decsal_report()
        elif self.report_type == 'decmal' and self.report_action == 'information':
            self._generate_decmal_information_report()
        else:
            self._generate_decmal_correction_report()

    def _generate_decsal_report(self):
        self.ensure_one()
        if not self.batch_ids:
            raise ValidationError(self.env._("There are no payslip batches for the selected period."))
        if self.situational_unemployment_ids and any(not su.amount for su in self.situational_unemployment_ids):
            raise ValidationError(self.env._('Missing amounts for situational unemployments'))
        company = self.env.company
        payslips = self.batch_ids.slip_ids
        employees_no_id = payslips.employee_id.filtered(lambda e: not e.identification_id)
        if employees_no_id:
            raise ValidationError(self.env._('The following employees are missing an identification number:\n - %s',
                              "\n - ".join(employees_no_id.mapped('name'))))
        line_values = payslips._get_line_values(self._get_declaration_codes())
        declaration_values = self._get_monthly_salary_declaration_values(payslips, line_values)
        company_values = [f"0;{company.l10n_lu_official_social_security};{company.l10n_lu_seculine}"]
        report_content = "\r\n".join(company_values + [
            ";".join(str(value) for value in declaration.values())
            for declaration in declaration_values
        ])
        self.report_sequence = self._get_report_sequence()
        filename = f"{self.report_type.upper()}_{self.month}_{self.year}_{self.report_sequence}.dta"
        self.report_file = BinaryBytes(report_content.encode(), filename=filename)

    def _get_declaration_codes(self):
        return [
            'BASIC',
            'NET',
        ]

    def _get_report_sequence(self):
        self.ensure_one()
        # Not using ir.sequence because it would generate too many sequence values for each type/year/month combination
        last_sequence = self.env['l10n.lu.seculine.reports']._read_group(
            domain=[
                ('report_type', '=', self.report_type),
                ('year', '=', self.year),
                ('month', '=', self.month),
                ('id', '!=', self.id)
            ],
            groupby=[],
            aggregates=['report_sequence:max'],
        )[0][0] or 0
        return last_sequence + 1

    def _get_monthly_salary_declaration_values(self, payslips, line_values):
        self.ensure_one()
        declaration_values = []
        ref_period = self.date_start.strftime('%Y%m')

        sevenSSM = int(7 * float(self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_lu_min_social_pay', self.date_start)) * 100)
        grouped_payslips = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in payslips:
            grouped_payslips[payslip.employee_id.id, payslip.struct_type_id.id] |= payslip

        for payslips in grouped_payslips.values():
            situational_unemployment = self.situational_unemployment_ids.filtered(lambda s: s.payslip_id in payslips)
            regular_payslips = payslips.filtered(lambda p: p.struct_id == p.struct_type_id.default_struct_id)
            gratification_payslips = payslips.filtered(
                lambda p: p.struct_id.code in ['LUX_GRATIFICATION', 'LUX_13TH_MONTH']
            )

            worked_hours = int(float_round(sum(regular_payslips.worked_days_line_ids.filtered(
                lambda w: w.is_paid and w.amount).mapped('number_of_hours')), 0))
            contracts_start = payslips.version_id.mapped('contract_date_start')
            period_start = max(min(contracts_start), self.date_start)
            all_contracts_end = payslips.version_id.mapped('contract_date_end')
            if all(d for d in all_contracts_end):
                max_contract_end = max(d for d in all_contracts_end if d)
                period_end = max_contract_end
            else:
                period_end = self.date_end

            basic_wage = int(sum(line_values['BASIC'][p.id]['total'] for p in regular_payslips) * 100)
            total_wage = int(sum(line_values['NET'][p.id]['total'] for p in regular_payslips) * 100)
            extra_hours = int(sum(p._get_category_data('OVERTIME_PAY')['quantity'] for p in regular_payslips) * 100)
            extra_hours_amount = int(sum(p._get_category_data('OVERTIME_PAY')['total'] for p in regular_payslips) * 100)
            gratifications = int(sum(line_values['BASIC'][p.id]['total'] for p in gratification_payslips) * 100)
            complements = int(
                sum(p._get_category_data('SUPPLEMENTS_ACCESSORIES')['total'] for p in regular_payslips) * 100
            )

            payslip = payslips[0]
            # Source: https://ccss.public.lu/dam-assets/seculine/traces/ccss-seculine-trace-DECSAL.pdf
            values = {
                "1_declaration_type": 1,
                "2_company_ssn": self.env.company.l10n_lu_official_social_security,
                "3_employee_ssn": payslip.employee_id.identification_id,
                "4_reference_period": ref_period,
                "5_basic_wage_cents": basic_wage,
                "6_worked_hours": worked_hours,
                "7_complements_cents": complements,
                "8_extra_hours_cents": extra_hours_amount,
                "9_extra_hours": extra_hours,
                "10_benefits_cents": gratifications,
                "11_sit_unemp_cents": int((situational_unemployment.amount or 0) * 100),
                "12_sit_unemp_hours": int(situational_unemployment.hours),
                "13_public_sector_cents": 0,
                "14_period_start": period_start.strftime("%d"),
                "15_period_end": period_end.strftime("%d"),
                "16_7ssm": "Y" if total_wage >= sevenSSM else "",
                "17_filler1": "",
                "18_filler2": "",
                "19_filler3": "",
                "20_company_reference": self.env.company.id,
            }
            declaration_values.append(values)
        return declaration_values

    def _generate_decmal_information_report(self):
        self.ensure_one()
        company = self.env.company
        incapacity_values = self._get_monthly_work_incapacity_values()
        decmal_report_values = self._get_decmal_report_values(incapacity_values)
        report_lines = [
            f"0;{company.l10n_lu_official_social_security};{company.l10n_lu_seculine}",
            *(";" .join(map(str, line.values())) for line in decmal_report_values)
        ]
        self.report_sequence = self._get_report_sequence()
        filename = f"{self.report_type.upper()}_{self.month}_{self.year}_{self.report_sequence}.dta"
        self.report_file = BinaryBytes("\r\n".join(report_lines).encode(), filename=filename)

    def _generate_decmal_correction_report(self):
        self.ensure_one()
        if not self.employee_ids:
            raise ValidationError(self.env._('Please select at least one employee.'))

        company = self.env.company
        employer_ssn = company.l10n_lu_official_social_security
        seculine_code = company.l10n_lu_seculine
        report_period = self.date_start.strftime('%Y%m')
        employee_incapacity_value = self._get_monthly_work_incapacity_values(self.employee_ids.ids)
        decmal_report_values = self._get_decmal_report_values(employee_incapacity_value)

        incapacity_value_by_employee = defaultdict(list)
        for value in decmal_report_values:
            incapacity_value_by_employee[value['3_employee_ssn']].append(value)

        report_lines = [f"0;{employer_ssn};{seculine_code}"]
        for employee in self.employee_ids:
            employee_ssn = employee.identification_id
            report_lines.append(f"2;{employer_ssn};{employee_ssn};{report_period};;;;;")
            employee_incapacities = incapacity_value_by_employee.get(employee_ssn, [])
            report_lines.extend(';'.join(map(str, line.values())) for line in employee_incapacities)

        self.report_sequence = self._get_report_sequence()
        filename = f"{self.report_type.upper()}_{self.month}_{self.year}_{self.report_sequence}.dta"
        self.report_file = BinaryBytes("\r\n".join(report_lines).encode(), filename=filename)

    def _is_continuous_days(self, employee, date_start, date_end):
        if (date_end - date_start).days in [0, 1]:
            return True

        work_entries_vals = employee.version_ids.generate_work_entries(date_start + relativedelta(days=1), date_end + relativedelta(days=-1))
        return not work_entries_vals

    def _get_monthly_work_incapacity_values(self, employee_ids=None):
        """
        Retrieve work entries for incapacity periods and group them by employee_ssn and work entry type seculine code.
        Returns a dictionary with keys as tuples of (employee_ssn, work_entry_type_seculine_code) and
        values as lists of incapacity entries.
        """
        self.ensure_one()
        incapacity_periods = defaultdict(list)  # {(employee_ssn, work_entry_type_seculine_code): [incapacity_entries]}
        if not employee_ids:
            employees = self.env['hr.employee'].search([('company_id', '=', self.company_id.id)])
        else:
            employees = self.env['hr.employee'].browse(employee_ids)

        work_entries_vals = employees.version_ids.generate_work_entries(self.date_start, self.date_end)
        incapacity_work_entries_vals = []
        for vals in work_entries_vals:
            work_entry_type = vals['work_entry_type_id']
            date = vals['date']
            if 1 <= work_entry_type.l10n_lu_seculine_code <= 5 and self.date_start <= date <= self.date_end:
                incapacity_work_entries_vals.append(vals)
        incapacity_work_entries_vals = sorted(incapacity_work_entries_vals, key=lambda x: x['date'])
        if not incapacity_work_entries_vals:
            return incapacity_periods

        missing_identification_employee_names = set()

        for vals in incapacity_work_entries_vals:
            employee = vals['employee_id']
            if not employee.identification_id:
                missing_identification_employee_names.add(employee.name)
            work_entry_type = vals['work_entry_type_id']
            entry_date = vals['date']
            key = (employee.identification_id, work_entry_type.l10n_lu_seculine_code)
            if incapacity_periods[key]:
                last_period = incapacity_periods[key][-1]
                # check for continuous days, we can check this way because work entries are sorted by date
                if self._is_continuous_days(employee, last_period['end'], entry_date):
                    last_period['end'] = entry_date
                    last_period['duration'] += vals['duration']
                    continue
            incapacity_periods[key].append({
                'start': entry_date,
                'end': entry_date,
                'duration': vals['duration']
            })

        if missing_identification_employee_names:
            raise ValidationError(self.env._(
                "The following employees are missing an identification number:\n - %s",
                "\n - ".join(missing_identification_employee_names)
            ))
        return incapacity_periods

    def _get_decmal_report_values(self, employee_incapacity_data):
        """
        Generate the DECMAL report values based on the work incapacity data.
        Returns a list of dictionaries with the required fields for the DECMAL report.
        """
        self.ensure_one()
        decmal_report_values = []
        report_period = self.date_start.strftime('%Y%m')
        employer_ssn = self.env.company.l10n_lu_official_social_security

        for (emp_ssn, seculine_code), entries in employee_incapacity_data.items():
            for entry in entries:
                decmal_report_values.append({
                    '1_id_of_action': 1,
                    '2_employer_ssn': employer_ssn,
                    '3_employee_ssn': emp_ssn,
                    '4_period': report_period,
                    '5_seculine_code': seculine_code,
                    '6_start_date': entry['start'].strftime('%Y%m%d'),
                    '7_end_date': entry['end'].strftime('%Y%m%d'),
                    '8_duration': int(entry['duration']),
                    '9_note': '',
                })

        return decmal_report_values


class L10nLuSituationalUnemployment(models.Model):
    _name = 'l10n.lu.situational.unemployment'
    _description = "Employee Situational Unemployment"

    monthly_declaration_id = fields.Many2one('l10n.lu.seculine.reports', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='monthly_declaration_id.company_id')
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id")
    payslip_id = fields.Many2one('hr.payslip')
    employee_id = fields.Many2one('hr.employee', readonly=True)
    hours = fields.Float(readonly=True)
    amount = fields.Monetary(required=True, default=0.0)
