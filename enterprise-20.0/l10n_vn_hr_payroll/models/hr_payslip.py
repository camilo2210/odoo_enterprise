# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import float_compare

# Premium pay categories deciding the day type of a worked day line, most specific first.
L10N_VN_DAY_TYPE_PREMIUM_PAYS = [
    ('public_holiday', 'VN_PREMIUM_PAY_PUBLIC_HOLIDAY'),
    ('weekly_rest', 'VN_PREMIUM_PAY_WEEKLY_REST'),
]
L10N_VN_NIGHT_PREMIUM_PAY = 'VN_PREMIUM_PAY_NIGHT'
# Employee deductions borne by the employer under a net salary agreement
L10N_VN_GROSS_UP_CODES = ('SI_EMP', 'HI_EMP', 'UI_EMP', 'PIT')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_vn_hr_payroll', [
                'data/hr_salary_rule_category_data.xml',
                'data/hr_rule_parameter_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]

    def _get_localdict(self, work_entries=None):
        res = super()._get_localdict(work_entries)
        if self.country_code == 'VN' or self.struct_id.country_code == 'VN':
            # Net salary agreement: the gross-up of the iteration in progress, see _get_payslip_lines
            res['l10n_vn_gross_up'] = self.env.context.get('l10n_vn_gross_up', 0.0)
        return res

    # -------------------------------------------------------------------------
    # Worked days
    # -------------------------------------------------------------------------

    def _l10n_vn_get_day_type(self, premium_pay_codes):
        for day_type, code in L10N_VN_DAY_TYPE_PREMIUM_PAYS:
            if code in premium_pay_codes:
                return day_type
        return 'normal'

    def _l10n_vn_get_worked_days_amount(self, overtime=None, day_type=None, night=None):
        """Sum the amounts (hourly wage x hours) of the worked day lines matching the criteria.

        The premium pay options carried by a worked day line describe the circumstances of the
        hours: overtime lines are split by day type and night work, so each line is paid at its
        own rate by the overtime and night work salary rules.

        :param overtime: True for the overtime lines, False for the other lines, None for all
        :param day_type: 'normal', 'weekly_rest' or 'public_holiday', None for all
        :param night: True for the lines carrying the night premium pay, False for the others, None for all
        """
        self.ensure_one()
        if self.ignore_worked_day_lines:
            return 0.0
        total = 0.0
        for line in self.worked_days_line_ids:
            if overtime is not None and line.work_entry_type_id.is_extra_hours != overtime:
                continue
            codes = line.category_options_ids._get_codes_with_ancestors()
            if night is not None and (L10N_VN_NIGHT_PREMIUM_PAY in codes) != night:
                continue
            if day_type is not None and self._l10n_vn_get_day_type(codes) != day_type:
                continue
            total += line.amount
        return total

    def _l10n_vn_get_unpaid_days(self):
        """Working days of the period without work nor wage (unpaid leaves, leaves compensated by the
        social insurance fund, days out of contract)."""
        self.ensure_one()
        if self.ignore_worked_day_lines:
            return 0.0
        return sum(self.worked_days_line_ids.filtered(lambda line: not line.is_paid).mapped('number_of_days'))

    # -------------------------------------------------------------------------
    # Compulsory insurance
    # -------------------------------------------------------------------------

    def _l10n_vn_is_insured(self):
        """The compulsory insurance contributions are due for the month unless the employee is outside
        the schemes or did not work and received no wage for 14 working days or more."""
        self.ensure_one()
        if self.version_id.l10n_vn_insurance_exempt:
            return False
        return self._l10n_vn_get_unpaid_days() < self._rule_parameter('l10n_vn_si_unpaid_days_threshold')

    def _l10n_vn_get_unpaid_days_wage(self):
        """Wage the working days without wage would have earned, at the hourly wage of the paid time.

        The contributions are never prorated: a month with fewer than 14 unpaid working days
        contributes on the full monthly wage of the labour contract, so the wage of the unpaid
        days is added back to the contribution base.
        """
        self.ensure_one()
        if self.ignore_worked_day_lines:
            return 0.0
        lines = self.worked_days_line_ids.filtered(lambda line: not line.work_entry_type_id.is_extra_hours)
        paid_lines = lines.filtered('is_paid')
        paid_hours = sum(paid_lines.mapped('number_of_hours'))
        if not paid_hours:
            return 0.0
        unpaid_hours = sum((lines - paid_lines).mapped('number_of_hours'))
        return sum(paid_lines.mapped('amount')) / paid_hours * unpaid_hours

    def _l10n_vn_get_insurance_base(self, contribution_wage, fund='si'):
        """Clamp the monthly contribution wage between the legal floor and the ceiling of the fund.

        The floor is the higher of the reference level and the regional minimum wage of the place
        of work. Social and health insurance are capped at 20 times the reference level while
        unemployment insurance is capped at 20 times the regional minimum wage.

        :param fund: 'si' for social and health insurance, 'ui' for unemployment insurance
        """
        self.ensure_one()
        if not contribution_wage:
            return 0.0
        reference_level = self._rule_parameter('l10n_vn_reference_level')
        regional_minimum_wage = self._rule_parameter('l10n_vn_regional_minimum_wage')[self.version_id.l10n_vn_minimum_wage_region]
        if fund == 'ui':
            ceiling = regional_minimum_wage * self._rule_parameter('l10n_vn_ui_ceiling_multiplier')
        else:
            ceiling = reference_level * self._rule_parameter('l10n_vn_si_ceiling_multiplier')
        return min(max(contribution_wage, reference_level, regional_minimum_wage), ceiling)

    # -------------------------------------------------------------------------
    # Personal income tax
    # -------------------------------------------------------------------------

    def _l10n_vn_compute_progressive_tax(self, assessable_income):
        """Apply the monthly progressive schedule: list of (upper bound, rate), the last upper bound is None."""
        self.ensure_one()
        tax = 0.0
        lower_bound = 0.0
        for upper_bound, rate in self._rule_parameter('l10n_vn_pit_progressive_schedule'):
            if upper_bound is not None and assessable_income > upper_bound:
                tax += (upper_bound - lower_bound) * rate / 100
                lower_bound = upper_bound
            else:
                tax += max(assessable_income - lower_bound, 0.0) * rate / 100
                break
        return tax

    def _l10n_vn_get_ytd_line_total(self, codes):
        """Total of the given rule codes on the validated payslips of the same calendar year ending
        before this payslip, e.g. to apply a yearly exemption cap."""
        self.ensure_one()
        payslips = self.env['hr.payslip'].search([
            ('id', '!=', self.id),
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', self.date_to.replace(month=1, day=1)),
            ('date_to', '<', self.date_to),
        ])
        line_values = payslips._get_line_values(codes, compute_sum=True)
        return sum(line_values[code]['sum']['total'] for code in codes)

    # -------------------------------------------------------------------------
    # Net salary agreement
    # -------------------------------------------------------------------------

    def _get_payslip_lines(self, force_categories_by_code=None):
        net_payslips = self.filtered(lambda payslip: payslip.country_code == 'VN' and payslip.version_id.l10n_vn_net_salary)
        res = super(HrPayslip, self - net_payslips)._get_payslip_lines(force_categories_by_code=force_categories_by_code)
        for payslip in net_payslips:
            res.extend(payslip._l10n_vn_get_grossed_up_payslip_lines(force_categories_by_code=force_categories_by_code))
        return res

    def _l10n_vn_get_grossed_up_payslip_lines(self, force_categories_by_code=None):
        """The GROSS_UP line must cover exactly the compulsory insurance contributions and the
        personal income tax borne by the employer. Both depend on the grossed-up income, so the
        computation is repeated with the deductions of the previous iteration as gross-up until it
        is stable: the marginal rate of the deductions is below 100%, the iteration converges fast.
        """
        self.ensure_one()
        rounding = self.currency_id.rounding or 0.01
        gross_up = 0.0
        for _iteration in range(50):
            lines = super(HrPayslip, self.with_context(l10n_vn_gross_up=gross_up))._get_payslip_lines(
                force_categories_by_code=force_categories_by_code)
            deductions = -sum(line['total'] for line in lines if line['code'] in L10N_VN_GROSS_UP_CODES)
            if not float_compare(deductions, gross_up, precision_rounding=rounding):
                return lines
            gross_up = deductions
        raise UserError(self.env._(
            "The net salary of %(employee)s could not be grossed up, check the salary rules of the structure.",
            employee=self.employee_id.name))
