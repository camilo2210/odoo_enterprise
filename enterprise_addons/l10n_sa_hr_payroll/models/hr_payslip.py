# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
from datetime import datetime, time
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_sa_wps_file_reference = fields.Char(string="WPS File Reference", copy=False)
    l10n_sa_disciplinary_action_ids = fields.One2many(
        'l10n.sa.disciplinary.action', 'payslip_id', readonly=True
    )

    @api.depends('employee_id', 'version_id', 'struct_id', 'date_from', 'date_to')
    def _compute_input_line_ids(self):
        res = super()._compute_input_line_ids()
        advance_balance_by_employee = self._get_salary_advance_balances()
        loan_balance_by_employee = self._get_loan_balances()
        for slip in self:
            if slip.employee_id and slip.date_from and slip.date_to and slip.country_code == 'SA':
                balance = (
                    advance_balance_by_employee[slip.employee_id]["ADV"]
                    + advance_balance_by_employee[slip.employee_id]["ADVDED"]
                )
                loan_deduction_balance = loan_balance_by_employee[slip.employee_id]
                leaves_to_be_recovered = max(0,
                    advance_balance_by_employee[slip.employee_id]["LEAVEADVPAY"]
                    - advance_balance_by_employee[slip.employee_id]["LEAVERECPAY"]
                )

                if balance > 0:
                    slip._set_input_value('ADVDED', balance)
                if loan_deduction_balance > 0:
                    slip._set_input_value('LOAN_DEDUCTION', loan_deduction_balance)
                total_attendance_days = sum(
                    d.number_of_days
                    for d in slip.worked_days_line_ids.filtered(
                        lambda w: w.code
                        in [
                            "002.00",
                            self.env.company.l10n_sa_annual_work_entry_type_id.code
                            if self.env.company.l10n_sa_annual_work_entry_type_id
                            else False,
                        ]
                    )
                )
                if leaves_to_be_recovered:
                    slip._set_input_value('LEAVERECPAY', min(total_attendance_days, leaves_to_be_recovered))
        return res

    @api.model
    def _issues_dependencies(self):
        dependencies = super()._issues_dependencies()
        dependencies += [
            "employee_id.bank_account_ids.clearing_number",
            "employee_id.bank_account_ids.clearing_label_id",
            "company_id.l10n_sa_bank_account_id",
            "company_id.l10n_sa_bank_account_id.clearing_number",
            "company_id.l10n_sa_bank_account_id.clearing_label_id",
            "company_id.l10n_sa_bank_account_id.l10n_sa_bank_establishment_code",
            "company_id.l10n_sa_mol_establishment_code",
            "employee_id.l10n_sa_employee_code",
        ]
        return dependencies

    def _get_salary_advance_balances(self):
        balance_by_employee = super()._get_salary_advance_balances()
        all_payslips = self.search([
            ('struct_id.country_id', '=', 'SA'),
            ('state', 'in', ('validated', 'paid')),
            ('employee_id', 'in', self.employee_id.ids),
        ])
        line_values = all_payslips._get_line_values(['ADV', 'ADVDED', 'LEAVEADVPAY', 'LEAVERECPAY'])
        for payslip in all_payslips:
            # monetary value
            balance_by_employee[payslip.employee_id]['ADV'] += line_values['ADV'][payslip.id]['total']
            balance_by_employee[payslip.employee_id]['ADVDED'] += line_values['ADVDED'][payslip.id]['total']  # negative amount

            # quantity value
            balance_by_employee[payslip.employee_id]['LEAVEADVPAY'] += payslip._get_input_line_amount('LEAVEADVPAY')
            balance_by_employee[payslip.employee_id]['LEAVERECPAY'] += payslip._get_input_line_amount('LEAVERECPAY')

        return balance_by_employee

    def _get_loan_balances(self):
        loan_balance_by_employee = defaultdict(float)
        all_payslips = self.search([
            ('struct_id.country_id', '=', 'SA'),
            ('state', 'in', ('validated', 'paid')),
            ('employee_id', 'in', self.employee_id.ids),
        ])
        line_values = all_payslips._get_line_values(['LOAN_DEDUCTION', 'LOANDPAY'])
        for payslip in all_payslips:
            loan_balance_by_employee[payslip.employee_id] += line_values['LOAN_DEDUCTION'][payslip.id]['total']
            loan_balance_by_employee[payslip.employee_id] += line_values['LOANDPAY'][payslip.id]['total']

        return loan_balance_by_employee

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_sa_hr_payroll', [
                'data/hr_salary_rule_category_data.xml',
                'data/hr_salary_rule_salary_advance_and_loan_data.xml',
                'data/hr_salary_rule_saudi_data.xml',
                'data/hr_rule_parameter_data.xml',
            ])]

    def _l10n_sa_wps_generate_file_reference(self):
        # if all were previously printed together, dont increment sequence
        if not all(self.mapped('l10n_sa_wps_file_reference')) or len(set(self.mapped('l10n_sa_wps_file_reference'))) != 1:
            # else make a new sequence
            self.l10n_sa_wps_file_reference = self.env['ir.sequence'].next_by_code("l10n_sa.wps")
        return self[:1].l10n_sa_wps_file_reference

    @api.model
    def _l10n_sa_format_float(self, val):
        currency = self.env.ref('base.SAR')
        return f'{currency.round(val):.{currency.decimal_places}f}'

    def _l10n_sa_get_wps_data(self):
        header = [
            self.env._("Employee's Net Salary"),
            self.env._("Employee's bank account"),
            self.env._("Employee's name"),
            self.env._("Employee's Bank"),
            self.env._("Payment Description"),
            self.env._("Basic Salary"),
            self.env._("Housing Allowance"),
            self.env._("Other Earnings"),
            self.env._("Deductions"),
            self.env._("Employee's ID "),
        ]
        rows = []

        all_codes = ['BASIC', 'GROSS', 'NET', 'HOUALLOW']
        all_line_values = self._get_line_values(all_codes)

        for payslip in self:
            employee_id = payslip.employee_id

            net = all_line_values['NET'][payslip.id]['total']
            basic = all_line_values['BASIC'][payslip.id]['total']
            gross = all_line_values['GROSS'][payslip.id]['total']
            housing = all_line_values['HOUALLOW'][payslip.id]['total']

            extra_income = gross - basic - housing
            deductions = gross - net

            rows.append([
                self._l10n_sa_format_float(net),
                employee_id.primary_bank_account_id.account_number or "",
                employee_id.primary_bank_account_id.holder_name or employee_id.name or "",
                employee_id.primary_bank_account_id._get_clearing_number('SA') or ""
                if employee_id.primary_bank_account_id.country_code == 'SA' or not employee_id.primary_bank_account_id
                else employee_id.primary_bank_account_id.bank_bic or "",
                payslip.name or "",
                self._l10n_sa_format_float(basic),
                self._l10n_sa_format_float(housing),
                self._l10n_sa_format_float(extra_income),
                self._l10n_sa_format_float(deductions),
                employee_id.l10n_sa_employee_code or "",
            ])
        return [header, *rows]

    def action_payslip_payment_report(self, export_format='l10n_sa_wps'):
        action = super().action_payslip_payment_report()
        if self.company_id.country_code != 'SA':
            return action
        action.update({
            'context': {
                **action['context'],
                'default_export_format': export_format,
            },
        })
        return action

    def _l10n_sa_get_valid_disciplinary_actions(self):
        return self.env['l10n.sa.disciplinary.action'].search([
            ('company_id', '=', self.company_id.id),
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'approved'),
            ('action_type', '=', 'deduction'),
            ('payslip_id', 'in', [False, self.id]),
        ])

    def _l10n_sa_has_disciplinary_action(self):
        return bool(self._l10n_sa_get_valid_disciplinary_actions())

    def _l10n_sa_get_disciplinary_action_amount(self):
        self.ensure_one()
        valid_actions = self._l10n_sa_get_valid_disciplinary_actions()
        amount = 0
        for action in valid_actions:
            amount += action._calculate_deduction_amount()
        valid_actions.write({'payslip_id': self.id})
        return amount

    def action_payslip_cancel(self):
        res = super().action_payslip_cancel()
        self.filtered(lambda p: p.struct_id.country_id.code == "SA").l10n_sa_disciplinary_action_ids.write({'payslip_id': False})
        return res

    def _issue_sa_missing_mandatory_fields(self):
        issues = []

        # Company required fields
        if not self.company_id.l10n_sa_bank_account_id:
            issues.append({
                'message': self.env._("Kindly configure the establishment's bank account"),
                'action_text': self.env._("Settings"),
                'action': self.env['ir.actions.actions']._for_xml_id('hr_payroll.action_hr_payroll_configuration'),
                'level': 'danger' if self.state == 'validated' else 'warning',
            })
        if not self.company_id.l10n_sa_mol_establishment_code:
            issues.append({
                'message': self.env._("Kindly configure the company's MoL Establishment ID"),
                'action_text': self.env._("Settings"),
                'action': self.env['ir.actions.actions']._for_xml_id('hr_payroll.action_hr_payroll_configuration'),
                'level': 'danger' if self.state == 'validated' else 'warning',
            })

        # Employee required fields
        if not self.employee_id.l10n_sa_employee_code:
            issues.append({
                'message': self.env._("Kindly set the Saudi National/IQAMA ID for the employees on the Payroll Tab"),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'danger' if self.state == 'validated' else 'warning',
            })

        return issues or None

    def _issue_sa_bank_warnings(self):
        issues = []
        # Company bank account checks
        bank_acc = self.company_id.l10n_sa_bank_account_id
        if bank_acc:
            if not bank_acc._get_clearing_number('SA'):
                issues.append({
                    'message': self.env._("Missing SARIE code on the company bank %s", bank_acc.bank_name),
                    'action_text': self.env._("Company Bank Account"),
                    'action': bank_acc._get_records_action(),
                    'level': 'warning',
                })
            if not bank_acc.l10n_sa_bank_establishment_code:
                issues.append({
                    'message': self.env._("Missing establishment code on the company bank %s", bank_acc.bank_name),
                    'action_text': self.env._("Company Bank Account"),
                    'action': bank_acc._get_records_action(),
                    'level': 'warning',
                })

        # Employee bank account checks
        emp_bank_acc = self.employee_id.primary_bank_account_id
        if not emp_bank_acc:
            issues.append({
                'message': self.env._("Missing bank account for employee"),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(),
                'level': 'warning',
            })

        elif not emp_bank_acc._get_clearing_number('SA'):
            issues.append({
                'message': self.env._("Missing SARIE code for the bank account for the following employee: %s", self.employee_id.name),
                'action_text': self.env._("Employee Bank Account"),
                'action': emp_bank_acc._get_records_action(),
                'level': 'warning',
            })

        return issues or None

    def _issue_sa_gosi_warning(self):
        issues = []
        employee = self.employee_id
        if (
                employee.l10n_sa_company_social_insurance_percentage == 0 and
                employee.l10n_sa_company_oh_insurance_percentage == 0 and
                employee.l10n_sa_company_unemployment_insurance_percentage == 0 and
                employee.l10n_sa_employee_social_insurance_percentage == 0 and
                employee.l10n_sa_employee_unemployment_insurance_percentage == 0
            ):
            issues.append({
                'message': self.env._("Kindly configure the GOSI integration from the payroll settings or manually set the contribution percentages for the employee under the payroll tab"),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'warning',
            })
        return issues or None

    def _l10n_sa_get_versions_with_effective_dates(self):
        self.ensure_one()
        versions = self.employee_id._get_versions_with_contract_overlap_with_period(self.date_from, self.date_to)
        date_from = self.date_from
        versions_with_dates = []
        for version_index in range(len(versions)):
            if version_index == len(versions) - 1:
                date_to = self.date_to
            else:
                date_to = versions[version_index + 1].date_version - relativedelta(days=1)
            versions_with_dates.append((versions[version_index], date_from, date_to))
            date_from = date_to + relativedelta(days=1)
        return versions_with_dates

    def _l10n_sa_get_theoretical_work_days(self):
        self.ensure_one()
        versions_with_dates = self._l10n_sa_get_versions_with_effective_dates()
        total_number_of_work_days = 0
        work_days_per_version = {}
        for version, date_from, date_to in versions_with_dates:
            reference_calendar = version.resource_calendar_id or version.company_id.resource_calendar_id
            work_days_per_version[version] = reference_calendar.get_work_duration_data(
                datetime.combine(date_from, time.min).replace(tzinfo=ZoneInfo(version.tz)),
                datetime.combine(date_to, time.max).replace(tzinfo=ZoneInfo(version.tz)),
                compute_leaves=False,
            )['days']
            total_number_of_work_days += work_days_per_version[version]
        return total_number_of_work_days, work_days_per_version
