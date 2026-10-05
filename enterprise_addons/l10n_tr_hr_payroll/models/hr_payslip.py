# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models
from odoo.tools import float_round
from odoo.tools.float_utils import float_compare


L10N_TR_PAYMENT_TYPE_CODE_SELECTION = [
    ("11", "Minimum Wage Earner (Income Tax Law Art. 94/1)"),
    ("12", "Other Wages and Wage-like Payments (Income Tax Law Art. 94/1)"),
    ("13", "Severance Pay"),
    ("14", "Attendance Fee"),
    ("15", "Notice Compensation"),
    ("16", "Underground Mine Workers"),
    ("17", "Within Scope of Law No. 6550"),
    ("18", "Revolving Fund/Performance/Additional Class Payment/Extra Payment/Trustee-Expert Payment/Other"),
    ("19", "Ship Workers/Liaison Offices of Non-Resident Institutions/Building Janitors"),
    ("20", "Village Heads/Embassy Personnel/Workers under ITL Art. 23/11/Others"),
    ("302", "Documents related to payments such as salary, wage, daily allowance, attendance fee, dues, specialization bonus, bonuses, meal and housing allowances, travel allowance, compensation, and similar payments received in return for services (including advances), including receipts and documents used for transferring or paying these amounts to personal accounts or on behalf of the individuals"),
]

L10N_TR_DOCUMENT_NATURE_SELECTION = [
    ("A", "Original"),
    ("E", "Additional"),
    ("I", "Cancellation"),
]


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_tr_ytd_gross = fields.Monetary(string='Year to Date Gross', compute='_compute_l10n_tr_ytd_amounts', currency_field='currency_id')
    l10n_tr_ytd_tax = fields.Monetary(string='Year to Date Tax', compute='_compute_l10n_tr_ytd_amounts', currency_field='currency_id')
    l10n_tr_current_month_gross = fields.Monetary(compute='_compute_l10n_tr_current_month_gross', currency_field='currency_id')
    l10n_tr_payment_type_code = fields.Selection(string="Payment Type Code", selection=L10N_TR_PAYMENT_TYPE_CODE_SELECTION, default="11", help="The SGK-defined payment category that applies to this salary payment")
    l10n_tr_document_nature = fields.Selection(string="Document Nature", selection=L10N_TR_DOCUMENT_NATURE_SELECTION, default="A", help="The insurance document category under which this payslip is issued (as per SGK classifications)")

    @api.model
    def _issues_dependencies(self):
        return super()._issues_dependencies() + [
            "company_id.l10n_tr_sgk_workspace_registration_no",
            "company_id.l10n_tr_tax_reponsible_id",
            "company_id.l10n_tr_sgk_intermediary_code",
            "company_id.l10n_tr_old_unit_code",
            "company_id.l10n_tr_new_unit_code",
            "employee_id.l10n_tr_social_insurance_number",
            "employee_id.l10n_tr_occupational_code",
        ]

    @api.depends('employee_id', 'date_from')
    def _compute_l10n_tr_ytd_amounts(self):
        self.l10n_tr_ytd_gross = 0
        self.l10n_tr_ytd_tax = 0

        tr_slips = self.filtered(lambda p: p.country_code == 'TR')
        if not tr_slips:
            return

        reference_dates = tr_slips.mapped('date_from')
        min_date = min(reference_dates).replace(month=1, day=1)
        max_date = max(reference_dates)
        current_year_payslips_raw = self.env['hr.payslip']._read_group(
            domain=[('employee_id', 'in', self.employee_id.ids),
                    ('date_from', '>=', min_date),
                    ('date_to', '<', max_date),
                    ('state', 'in', ('validated', 'paid'))],
            groupby=['employee_id', 'date_from:year'],
            aggregates=['id:recordset']
        )

        current_year_payslips = {}
        for employee, date, payslips in current_year_payslips_raw:
            current_year_payslips.setdefault(employee, {})[date.year] = payslips

        for payslip in tr_slips.sorted("date_from"):
            reference_date = payslip.date_from
            ytd_payslips = current_year_payslips.get(payslip.employee_id, {}).get(reference_date.year, self.env['hr.payslip']).filtered(lambda ps: ps.date_to < reference_date)
            ytd_amounts = ytd_payslips._get_line_values(['CURTAXABLE', 'BTAXNET'], compute_sum=True)
            payslip.l10n_tr_ytd_gross = ytd_amounts['CURTAXABLE']['sum']['total']
            payslip.l10n_tr_ytd_tax = ytd_amounts['BTAXNET']['sum']['total']

    def _l10n_tr_calculate_net_guess_accuracy(self, guess, target):
        self.ensure_one()
        self.l10n_tr_current_month_gross = guess
        expected_ntg = next((line for line in self._get_payslip_lines() if line.get('code') == 'EXPNET'), {'amount': 0.0})
        return float_round(expected_ntg['amount'], precision_rounding=self.currency_id.rounding) - target

    def _estimate_l10n_tr_gross_from_net(self, target, max_iterations=50, tolerance=0.001):
        """
        A safe version of Newton's method using the secant method to avoid division by zero.
        """
        self.ensure_one()
        guess1, guess2 = self.version_id.wage, self.version_id.wage * 2
        for _ in range(max_iterations):
            value1 = self._l10n_tr_calculate_net_guess_accuracy(guess1, target)
            value2 = self._l10n_tr_calculate_net_guess_accuracy(guess2, target)

            if abs(value1) < tolerance:
                return guess1

            # prevent division by zero
            if float_compare(value1, value2, precision_digits=self.currency_id.decimal_places) == 0:
                break

            # Estimate the slope (secant) and update guess using the secant method
            slope = (value2 - value1) / (guess2 - guess1)
            next_guess = guess1 - value1 / slope

            guess1, guess2 = guess2, next_guess

        return guess1

    @api.depends('version_id')
    def _compute_l10n_tr_current_month_gross(self):
        for payslip in self:
            if payslip.country_code == 'TR' and payslip.version_id.l10n_tr_is_net_to_gross:
                payslip.l10n_tr_current_month_gross = payslip._estimate_l10n_tr_gross_from_net(payslip.version_id.wage)
            else:
                payslip.l10n_tr_current_month_gross = 0

    def _compute_input_line_ids(self):
        res = super()._compute_input_line_ids()
        balance_by_employee = self._get_salary_advance_balances()
        for slip in self:
            if not slip.employee_id or not slip.date_from or not slip.date_to or slip.country_code != 'TR':
                continue
            if slip.struct_id.code == 'TRMONTHLY':
                input_advance_recovery_rule_code = self.env.ref('l10n_tr_hr_payroll.hr_payroll_structure_tr_employee_salary_salary_advance_recovery').code
                balance = (
                    balance_by_employee[slip.employee_id]['SALARYADV']
                    + balance_by_employee[slip.employee_id]['SICKLEAVEADV']
                    + balance_by_employee[slip.employee_id]['ANNUALLEAVEADV']
                    - balance_by_employee[slip.employee_id]['SALARYADVREC']
                )
                if balance <= 0:
                    continue
                slip._set_input_value(input_advance_recovery_rule_code, balance)
            elif slip.struct_id.code == 'TRADV':
                sick_leave_adv_rule_code = self.env.ref('l10n_tr_hr_payroll.l10n_tr_advance_pay_sick_leave').sudo().code
                annual_leave_adv_rule_code = self.env.ref('l10n_tr_hr_payroll.l10n_tr_advance_pay_annual_leave').sudo().code
                slip._set_input_values({
                    sick_leave_adv_rule_code: self.worked_days_line_ids.filtered(lambda wd: wd.code == '013.00').number_of_days,
                    annual_leave_adv_rule_code: self.worked_days_line_ids.filtered(lambda wd: wd.code == '016.00').number_of_days,
                })
        return res

    def _get_salary_advance_balances(self):
        balance_by_employee = super()._get_salary_advance_balances()
        input_advance_recovery_rule_code = self.env.ref('l10n_tr_hr_payroll.hr_payroll_structure_tr_employee_salary_salary_advance_recovery').sudo().code
        input_salary_advance_rule_code = self.env.ref('l10n_tr_hr_payroll.l10n_tr_advance_pay_salary_advance').sudo().code
        sick_leave_adv_rule_code = self.env.ref('l10n_tr_hr_payroll.l10n_tr_advance_pay_sick_leave').sudo().code
        annual_leave_adv_rule_code = self.env.ref('l10n_tr_hr_payroll.l10n_tr_advance_pay_annual_leave').sudo().code
        # Pre-refactor this used payslip_properties JSON keys. After the input.type → rule
        # refactor, per-payslip property values live as hr.payslip.input rows whose .code
        # equals the rule's code.
        tr_codes = (
            input_advance_recovery_rule_code,
            input_salary_advance_rule_code,
            sick_leave_adv_rule_code,
            annual_leave_adv_rule_code,
        )
        payslips_by_employee = self._read_group(
            domain=[
                ('struct_id.country_id', '=', 'TR'),
                ('state', 'in', ('validated', 'paid')),
                ('employee_id', 'in', self.employee_id.ids),
                ('input_line_ids.code', 'in', list(tr_codes)),
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset']
        )
        for employee_id, payslips in payslips_by_employee:
            for payslip in payslips:
                # Check for ADV (Salary Advance)
                adv_amount = payslip._get_line_values(['SALARYADV'], compute_sum=True)['SALARYADV']['sum']['total']
                sick_amount = payslip._get_line_values(['SICKLEAVEADV'], compute_sum=True)['SICKLEAVEADV']['sum']['total']
                annual_amount = payslip._get_line_values(['ANNUALLEAVEADV'], compute_sum=True)['ANNUALLEAVEADV']['sum']['total']
                if adv_amount or sick_amount or annual_amount:
                    balance_by_employee[employee_id]['SALARYADV'] += adv_amount
                    balance_by_employee[employee_id]['SICKLEAVEADV'] += sick_amount
                    balance_by_employee[employee_id]['ANNUALLEAVEADV'] += annual_amount
                # Check for ADVREC (Advance Recovery)
                advrec_amount = payslip._get_line_values(['SALARYADVREC'], compute_sum=True)['SALARYADVREC']['sum']['total']
                if advrec_amount:
                    balance_by_employee[employee_id]['SALARYADVREC'] += advrec_amount
        return balance_by_employee

    def _l10n_tr_get_tax(self, taxable_amount):
        self.ensure_one()
        total_tax = 0
        rates = iter(self._rule_parameter('l10_tr_tax_rates'))
        lower, upper, rate = next(rates)
        while lower < taxable_amount:
            total_tax += min((taxable_amount - lower, float(upper) - lower)) * rate
            lower, upper, rate = next(rates)
        return total_tax

    def _issue_tr_missing_mandatory_fields(self):
        self.ensure_one()
        issues = []
        level = "danger" if self.state == "validated" else "warning"
        settings_action = self.env['ir.actions.actions']._for_xml_id('hr_payroll.action_hr_payroll_configuration')

        # Company required fields
        for field_name, message in (
            ("l10n_tr_sgk_workspace_registration_no", self.env._("Missing SGK Workspace Registration Number on payroll settings.")),
            ("l10n_tr_tax_reponsible_id", self.env._("Missing Tax Responsible on payroll settings.")),
            ("l10n_tr_sgk_intermediary_code", self.env._("Missing Intermediary Code on payroll settings.")),
            ("l10n_tr_old_unit_code", self.env._("Missing Old Unit Code on payroll settings.")),
            ("l10n_tr_new_unit_code", self.env._("Missing New Unit Code on payroll settings.")),
        ):
            if not self.company_id[field_name]:
                issues.append({
                    'message': message,
                    'action_text': self.env._("Payroll Settings"),
                    'action': settings_action,
                    'level': level,
                })

        # Employee required fields
        employee_action = self.employee_id._get_records_action(
            name=self.env._("Employee"),
            context={**self.env.context, 'version_id': self.version_id.id},
        )
        for field_name, message in (
            ("l10n_tr_occupational_code", self.env._("Missing Occupation Code on Employee Work tab under the Employee Insurance section.")),
            ("l10n_tr_social_insurance_number", self.env._("Missing Social Insurance Number on employee Personal details tab.")),
        ):
            if not self.employee_id[field_name]:
                issues.append({
                    'message': message,
                    'action_text': self.env._("Employee"),
                    'action': employee_action,
                    'level': level,
                })

        return issues or None

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_tr_hr_payroll', [
                'data/hr_rule_parameter_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]
