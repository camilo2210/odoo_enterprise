from datetime import date, datetime

from odoo import api, fields, models

_L10N_OM_WPS_BIC_TO_BANK_CODE = {
    'OMABOMRU':    'OAB',
    'BARBOMMX':    'BOB',
    'MELIOMRX':    'BMI',
    'BSIROMRX':    'BSI',
    'BBMEOMRX':    'HSBC',
    'SCBLOMRX':    'SCB',
    'NBADOMRX':    'NBAD',
    'HABBOMRX':    'HABB',
    'NBOMOMRX':    'NBO',
    'BDIFIMRU':    'BDOF',
    'BMUSOMRX':    'BMCT',
    'SBINOMRX':    'SBI',
    'BABEOMRX':    'BBUT',
    'BSHROMRU':    'BSHR',
    'AUBOOMRU':    'AHLI',
    'QNBAOMRX':    'QNB',
    'BNZWOMRX':    'BNZW',
    'BMUSOMRXISL': 'MTHQ',
    'NBOMOMRXIBS': 'MUZN',
    'BDOFOMRUMIB': 'MISR',
    'AUBOOMRUALH': 'HLAL',
    'BSHROMRUISL': 'SHRI',
    'OMABOMRUYSR': 'YUSR',
    'ODBLOMRX':    'ODB',
    'IZZBOMRU':    'IZZB',
    'OHBLOMRX':    'OHB',
}


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    sickleaves_in_year_upto_slip_date = fields.Float(compute="_compute_sickleaves_in_year_upto_slip_date")

    @api.model
    def _issues_dependencies(self):
        dependencies = super()._issues_dependencies()
        dependencies += [
            "company_id.l10n_om_company_mol_number",
            "company_id.l10n_om_salary_payer_mol_number",
            "company_id.l10n_om_bank_account_id",
            "company_id.l10n_om_bank_account_id.clearing_number",
            "company_id.l10n_om_bank_account_id.bank_bic",
            "employee_id.l10n_om_identification_type",
            "employee_id.identification_id",
            "employee_id.passport_id",
            "struct_id.schedule_pay",
        ]
        return dependencies

    def action_payslip_payment_report(self, export_format='l10n_om_wps'):
        action = super().action_payslip_payment_report()
        if self.company_id.country_code != 'OM':
            return action
        action.update({
            'context': {
                **action['context'],
                'default_export_format': export_format,
            },
        })
        return action

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_om_hr_payroll', [
                'data/hr_salary_rule_data.xml',
            ])]

    def _l10n_om_calculate_working_days_of_payslip_period(self):
        self.ensure_one()
        employee = self.employee_id
        resource = employee.resource_id
        calendar = resource.calendar_id
        return float(
            calendar.get_work_duration_data(
                datetime.combine(self.date_from, datetime.min.time()),
                datetime.combine(self.date_to, datetime.max.time()),
                compute_leaves=False,
            )["days"],
        )

    @api.depends("date_from", "date_to", "state")
    def _compute_sickleaves_in_year_upto_slip_date(self):
        all_employee_ids = self.mapped("employee_id").ids
        all_matching_leaves = self.env["hr.leave"].search([
            ("employee_id", "in", all_employee_ids),
            ("state", "=", "validate"),
            ("work_entry_type_id.code", "=", "013.00"),
        ])

        for slip in self:
            total_leave_days = 0
            current_year = slip.date_to.year
            ytd_start = date(current_year, 1, 1)
            ytd_end = slip.date_to

            overlapping_leaves = all_matching_leaves.filtered(
                lambda leave: leave.employee_id == slip.employee_id
                and leave.request_date_from <= ytd_end
                and leave.request_date_to >= ytd_start,
            )

            for leave in overlapping_leaves:
                actual_start_date = max(leave.request_date_from, ytd_start)
                actual_end_date = min(leave.request_date_to, ytd_end)

                if actual_start_date <= actual_end_date:
                    actual_start = datetime.combine(actual_start_date, datetime.min.time())
                    actual_end = datetime.combine(actual_end_date, datetime.max.time())
                    work_data = slip.employee_id._get_work_days_data_batch(
                        actual_start,
                        actual_end,
                        compute_leaves=False,
                    )[slip.employee_id.id]
                    total_leave_days += work_data.get("days", 0)

            slip.sickleaves_in_year_upto_slip_date = total_leave_days

    @api.model
    def _l10n_om_format_float(self, val):
        currency = self.env.ref('base.OMR')
        return f'{currency.round(val):.{currency.decimal_places}f}'

    @api.model
    def _l10n_om_resolve_bank_code(self, bank_account):
        if not bank_account:
            return ''
        code = bank_account._get_clearing_number('OM')
        if code:
            return code
        bic = (bank_account.bank_bic or '').upper()
        return _L10N_OM_WPS_BIC_TO_BANK_CODE.get(bic, '')

    @api.model
    def _l10n_om_get_wps_employee_header(self):
        return [[
            "Employee ID Type",
            "Employee ID",
            "Employee Name",
            "Employee BIC",
            "Employee IBAN",
            "Salary Frequency",
            "Number of Working Days",
            "Net Salary",
            "Basic Salary",
            "Extra Hours",
            "Extra Income",
            "Deductions",
            "Social Security Deductions",
            "Notes",
        ]]

    def _l10n_om_get_wps_employee_records(self, note=''):
        all_codes = ['BASIC', 'NET', 'DEDUCTION', 'SPF_EMP']
        all_line_values = self._get_line_values(all_codes)

        rows = []
        for payslip in self:
            employee = payslip.employee_id
            bank_account = employee.primary_bank_account_id

            id_type = 'C' if employee.l10n_om_identification_type == 'civil_status_card' else 'P'
            id_number = (employee.identification_id if id_type == 'C' else employee.passport_id) or ''
            schedule_pay = payslip.struct_id.schedule_pay if payslip.struct_id else ''
            salary_frequency = 'B' if schedule_pay == 'bi-weekly' else 'M' if schedule_pay == 'monthly' else ''
            basic = all_line_values['BASIC'][payslip.id]['total']
            net = all_line_values['NET'][payslip.id]['total']
            alw_codes = payslip.struct_id.rule_ids.filtered_domain([
                ('category_ids', 'child_of', payslip.env.ref('hr_payroll.ALW').id)
            ]).mapped('code')
            extra_income = sum(
                line.total
                for line in payslip.line_ids
                if line.salary_rule_id.code in alw_codes
            )
            deduction = abs(all_line_values['DEDUCTION'][payslip.id]['total'])
            spf_emp = abs(all_line_values['SPF_EMP'][payslip.id]['total'])
            extra_hours = sum(
                line.number_of_hours
                for line in payslip.worked_days_line_ids
                if line.work_entry_type_id.is_extra_hours
            )
            unpaid_days = sum(
                line.number_of_days
                for line in payslip.worked_days_line_ids
                if line.code in ('158.00', '000.00')
            )

            rows.append([
                id_type,
                id_number,
                employee.name or '',
                bank_account.bank_bic if bank_account else '',
                bank_account.account_number if bank_account else '',
                salary_frequency,
                30 - unpaid_days,
                self._l10n_om_format_float(net),
                self._l10n_om_format_float(basic),
                f'{extra_hours:.2f}',
                self._l10n_om_format_float(extra_income),
                self._l10n_om_format_float(deduction),
                self._l10n_om_format_float(spf_emp),
                note or '',
            ])
        return rows
