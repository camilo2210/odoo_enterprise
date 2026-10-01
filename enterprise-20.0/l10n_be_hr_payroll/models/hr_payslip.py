# Part of Odoo. See LICENSE file for full copyright and licensing details.

from calendar import monthrange, isleap
from collections import defaultdict, Counter
from datetime import date, datetime, time, timedelta, UTC
from zoneinfo import ZoneInfo
import math

from dateutil import rrule
from dateutil.relativedelta import relativedelta, MO, SU

from odoo import api, models, fields, Command
from odoo.tools import date_utils, float_compare, float_round, float_is_zero, pdf
from odoo.tools.safe_eval import expr_eval
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.misc import frozendict
from odoo.tools.intervals import Intervals


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Company Car',
        compute='_compute_vehicle_id', store=True, readonly=False,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    l10n_be_is_double_pay = fields.Boolean(compute='_compute_l10n_be_is_double_pay')
    l10n_be_is_december = fields.Boolean(compute='_compute_l10n_be_is_december')
    l10n_be_joint_committee_id = fields.Many2one(related='version_id.l10n_be_joint_committee_id')
    l10n_be_effective_marital = fields.Selection(
        selection=lambda self: self.env['hr.version']._get_marital_status_selection(), compute="_compute_effective_marital")
    l10n_be_meal_vouchers_report_id = fields.Many2one('l10n_be.meal.vouchers.report', index=True, readonly=True, copy=False)
    l10n_be_sum_additional_hours = fields.Float(compute='_compute_l10n_additional_hours_checks', store=True)
    l10n_be_wrong_additional_hours_on_sundays_or_public_holidays = fields.Boolean(compute='_compute_l10n_additional_hours_checks', store=True)
    l10n_be_working_hours_limit_per_day_exceeded = fields.Boolean(compute='_compute_l10n_additional_hours_checks', store=True)
    l10n_be_working_hours_limit_per_week_exceeded = fields.Boolean(compute='_compute_l10n_additional_hours_checks', store=True)
    l10n_be_additional_hours_during_working_time = fields.Boolean(compute='_compute_l10n_additional_hours_checks', store=True)
    l10n_be_arrear_salary = fields.Boolean(string="Arrears Salary", help="Employee's remuneration that is paid or awarded late due to a public authority's default, negligence, or exceptional measure, or because of a dispute between the employer and the worker.")
    l10n_be_is_arrear_eligible = fields.Boolean(compute='_compute_l10n_be_is_arrear_eligible')
    l10n_be_needs_flxwage_declaration = fields.Boolean(related='version_id.l10n_be_needs_flxwage_declaration', store=True)
    l10n_be_flexi_declaration_id = fields.One2many('l10n.be.flexi.at.work', 'payslip_id', string="Flexi@Work", readonly=True)
    l10n_be_273_line_ids = fields.One2many('l10n_be.273_xx.line', 'payslip_id', copy=False)
    l10n_be_281_xx_ids = fields.Many2many('l10n_be.281_xx', 'l10n_be_281_xx_hr_payslip_rel', 'payslip_id', 'l10n_be_281_xx_id')
    l10n_be_onss_contribution = fields.Monetary(compute='_compute_line_values_dependent_fields', string='NSSO')
    l10n_be_withholding_taxes = fields.Monetary(compute='_compute_line_values_dependent_fields', string='Withholding Taxes')
    l10n_be_is_reported = fields.Boolean(compute='_compute_l10n_be_is_reported', help="Indicates whether this payslip is declared in any finalized Belgian declaration report (e.g. 273.XX).")
    l10n_be_is_dmfa_reported = fields.Boolean()
    l10n_be_dmfa_id = fields.Many2one('l10n_be.dmfa', string='DMFA Report', index=True, readonly=True)
    l10n_be_274_xx_ids = fields.Many2many(
        'l10n_be.274_xx', 'l10n_be_274_xx_hr_payslip_rel', 'payslip_id', 'sheet_id',
        string="274.XX Sheets", copy=False)
    l10n_be_fiscal_date = fields.Date(
        string="Fiscal Date", compute='_compute_l10n_be_fiscal_date', store=True, readonly=False, copy=False,
        help="Period this payslip must be fiscally attached to. It defaults to the pay period, and is "
             "deferred to the confirmation date for remunerations paid late, either because they are "
             "arrears or because their pay period has already been declared.")

    def _get_basic_wage_line_codes(self):
        codes = super()._get_basic_wage_line_codes()
        return codes | {'BASIC', 'BONUS_BASIC', 'DH_BASIC', 'WARRANT_BASIC', 'TERM_BASIC'}

    def _get_salary_wage_line_codes(self):
        return {'SALARY', 'BONUS_SALARY', 'DH_SALARY', 'TERM_SALARY', 'PAY_SIMPLE', 'WARRANT_SALARY'}

    def _get_onss_line_codes(self):
        return {'ONSS', 'ONSS_SOLIDARITY_BONUS', 'ONSS_BONUS', 'ONSS_DOUBLE_HOLIDAY', 'ONSS_TERM', 'ONSS_HOLIDAY_TERM_SIMPLE', 'ONSS_HOLIDAY_TERM_DOUBLE', 'WARRANT_ONSS'}

    def _get_gross_wage_line_codes(self):
        codes = super()._get_gross_wage_line_codes()
        return codes | {'GROSS', 'GROSS_NP', 'BONUS_GROSS', 'DH_GROSS', 'WARRANT_GROSS', 'TERM_GROSS', 'HOLIDAY_TERM_GROSS'}

    def _get_total_basic_wage_without_double_holiday(self):
        basic_codes = self._get_basic_wage_line_codes() - {'DH_BASIC'}
        line_values = self._get_line_values(basic_codes, compute_sum=True)
        return sum(line_values[code]['sum']['total'] for code in basic_codes)

    @api.depends('version_id.car_id.future_driver_id')
    def _compute_vehicle_id(self):
        for slip in self.filtered(lambda s: s.state not in ['validated', 'cancel']):
            contract_sudo = slip.version_id.sudo()
            if contract_sudo.car_id:
                future_driver = contract_sudo.car_id.future_driver_id
                if future_driver and future_driver == slip.employee_id.work_contact_id:
                    tmp_vehicle = self.env['fleet.vehicle'].search(
                        [('driver_id', '=', contract_sudo.car_id.future_driver_id.id)], limit=1)
                    slip.vehicle_id = tmp_vehicle
                else:
                    slip.vehicle_id = contract_sudo.car_id

    @api.depends('employee_id', 'version_id', 'struct_id', 'date_from', 'date_to')
    def _compute_input_line_ids(self):
        res = super()._compute_input_line_ids()
        balance_by_employee = self._get_salary_advance_balances()
        mobility_payment_by_slip = self._get_l10n_be_mobility_amounts()

        for slip in self:
            if not slip.employee_id or not slip.date_from or not slip.date_to or slip.country_code != 'BE':
                continue
            # Collect the BE-specific input amounts by code, then materialise them
            # in a single write (same pattern as the base _compute_input_line_ids)
            # rather than one self.update per value.
            amount_by_code = {}
            # If a double holiday pay should be recovered
            if slip.struct_id.code == 'BEDOUBLE':
                amount_by_code['EU_LEAVE_DEDUC'] = slip._get_sum_european_time_off_days()
                amount_by_code['DOUBLERECOVERY'] = slip._get_double_pay_to_recover()
            elif slip.struct_id.code == 'BEMONTHLY':
                if slip.l10n_be_is_december and slip.version_id.l10n_be_egov3_code == '200':
                    december_regularization = slip._l10n_be_get_december_holiday_regularization()
                    amount_by_code['SIMPLE_DECEMBER'] = december_regularization.get('simple', 0)
                    amount_by_code['DOUBLE_DECEMBER_BASIC'] = december_regularization.get('double', 0)
                if (
                    slip.version_id.fuel_card_personal_use
                    and slip.version_id.fuel_card
                    and not slip.version_id.transport_mode_car
                    and not slip.version_id.l10n_be_mobility_budget
                ):
                    amount_by_code['FUEL_CARD_PRIV'] = slip.version_id.fuel_card_personal_use
                balance = (
                    balance_by_employee[slip.employee_id]["SALARYADVREC"]
                    + balance_by_employee[slip.employee_id]["SALARYADV"]
                )
                if balance > 0:
                    amount_by_code['SALARYADVREC'] = balance
                if (slip.l10n_be_is_december or slip._is_last_monthly_payslip()) and slip in mobility_payment_by_slip:
                    mobility_remaining = mobility_payment_by_slip[slip]['MOBILITY_REMAINING']
                    mobility_remaining -= sum(slip.input_line_ids.filtered(lambda l: l.code == 'MOBILITY_TO_PAY').mapped('amount'))
                    amount_by_code['MOBILITY_PAYMENT'] = max(0.0, mobility_remaining)

            # CCT90BONUSPLAN (BECCT90 structure) is entered manually via the payslip inputs section.
            # This BE-specific compute has no amount to contribute for it, so it stays untouched here.
            auto_input_codes = {'EU_LEAVE_DEDUC', 'DOUBLERECOVERY', 'SIMPLE_DECEMBER', 'DOUBLE_DECEMBER_BASIC', 'FUEL_CARD_PRIV', 'SALARYADVREC', 'MOBILITY_PAYMENT'}
            rules_by_code = {rule.code: rule for rule in slip.struct_id.rule_ids}
            input_line_vals = [
                Command.unlink(line.id)
                for line in slip.input_line_ids
                if line.code in auto_input_codes
            ]
            allow_zero_input_codes = {'MOBILITY_PAYMENT'}
            for code, amount in amount_by_code.items():
                rule = rules_by_code.get(code)
                if not rule or (not amount and code not in allow_zero_input_codes):
                    continue
                input_line_vals.append(Command.create({
                    'salary_rule_id': rule.id,
                    'amount': amount,
                }))
            if input_line_vals:
                slip.update({'input_line_ids': input_line_vals})
        return res

    @api.depends('date_from')
    def _compute_l10n_be_is_arrear_eligible(self):
        current_year = fields.Date.context_today(self).year
        for slip in self:
            slip.l10n_be_is_arrear_eligible = bool(slip.date_from) and current_year > slip.date_from.year

    @api.depends('l10n_be_273_line_ids.sheet_id.state', 'l10n_be_281_xx_ids.state')
    def _compute_l10n_be_is_reported(self):
        for payslip in self:
            payslip.l10n_be_is_reported = (
                any(report.state in ['ready', 'done'] for report in payslip.l10n_be_273_line_ids.sheet_id) or
                any(report.state in ['ready', 'done'] for report in payslip.l10n_be_281_xx_ids)
            )

    @api.depends('date_to')
    def _compute_l10n_be_fiscal_date(self):
        # A remuneration is fiscally attached to its pay period until it turns out to be paid
        # late, in which case the deferral happens on confirmation. See _l10n_be_defer_fiscal_date.
        for payslip in self:
            payslip.l10n_be_fiscal_date = payslip.date_to

    def _get_gross_wage_base_categories(self):
        """Salary rule category each gross wage code totals.

        A declaration adds the base up itself instead of reading the aggregate line, so it needs
        to know which category that line totals. Kept per code, because a rule may belong to two
        bases at once and the payslip computation then counts it in both.
        """
        return {
            'GROSS': 'WITHHOLDING_BASE',
            'GROSS_NP': 'YEARLY_WITHHOLDING_BASE',
            'BONUS_GROSS': 'BONUS_WITHHOLDING_BASE',
            'DH_GROSS': 'DH_WITHHOLDING_BASE',
            'WARRANT_GROSS': 'WARRANT_WITHHOLDING_BASE',
            'TERM_GROSS': 'TERMINATION_WITHHOLDING_BASE',
            'HOLIDAY_TERM_GROSS': 'TERMINATION_HOLIDAY_WITHHOLDING_BASE',
        }

    def _l10n_be_get_declaration_base(self, category_code, date_from, date_to):
        """Rebuild per payslip the amounts of a base that belong to [date_from, date_to].

        A declaration cannot add up the aggregate line that displays a base: the aggregate carries
        a single period attachment, while the amounts inside it each follow their own. So the base
        is rebuilt from the two sources the payslip computation accumulates it from, the payslip
        lines and the worked day amounts, each tagged with the category or one of its children.

        The payslip lines follow their own attachment. The worked days have none of their own:
        they are the remuneration of the period being paid, so they follow their payslip.
        """
        result = defaultdict(float)
        category_codes = list(self._get_child_category_ids(category_code))
        if not self or not category_codes:
            return result
        lines = Domain([
            ('slip_id', 'in', self.ids),
            ('salary_rule_id.category_ids.code', 'in', category_codes),
        ]) & self._l10n_be_get_fiscal_line_domain(date_from, date_to)
        for payslip, total in self.env['hr.payslip.line']._read_group(lines, ['slip_id'], ['total:sum']):
            result[payslip.id] += total or 0.0

        attached_payslips = self.filtered(
            lambda p: not p.ignore_worked_day_lines and p.l10n_be_fiscal_date
            and date_from <= p.l10n_be_fiscal_date <= date_to)
        if attached_payslips:
            worked_days = Domain([
                ('payslip_id', 'in', attached_payslips.ids),
                ('work_entry_type_id.category_ids.code', 'in', category_codes),
            ])
            for payslip, amount in self.env['hr.payslip.worked_days']._read_group(worked_days, ['payslip_id'], ['amount:sum']):
                result[payslip.id] += amount or 0.0
        return result

    @api.model
    def _l10n_be_get_fiscal_period_domain(self, date_from, date_to):
        """Payslips a fiscal declaration covering [date_from, date_to] must take into account:
        those attached to it by their fiscal date, and those attached to it by their pay period.

        Nothing here keeps a payslip out of a declaration that already reported it: a payslip
        belongs to a single period per declaration stream, and it is its fiscal date that moves
        when its own pay period is closed. Each report family excludes its own finalized
        declarations where it needs to, which the annual recaps deliberately do not.
        """
        fiscal_period = Domain([
            ('l10n_be_fiscal_date', '>=', date_from),
            ('l10n_be_fiscal_date', '<=', date_to),
        ])
        pay_period = Domain([
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
        ])
        return fiscal_period | pay_period

    @api.model
    def _l10n_be_get_fiscal_line_domain(self, date_from, date_to):
        """Payslip lines a fiscal declaration covering [date_from, date_to] must add up.

        Both halves of the declaration period are covered: the amounts following the fiscal
        period of their payslip, and the amounts staying attached to its pay period.
        """
        fiscal_period = Domain([
            ('l10n_be_follow_pay_period', '=', False),
            ('slip_id.l10n_be_fiscal_date', '>=', date_from),
            ('slip_id.l10n_be_fiscal_date', '<=', date_to),
        ])
        pay_period = Domain([
            ('l10n_be_follow_pay_period', '=', True),
            ('slip_id.date_from', '>=', date_from),
            ('slip_id.date_to', '<=', date_to),
        ])
        return fiscal_period | pay_period

    @api.depends('line_ids.total')
    def _compute_line_values_dependent_fields(self):
        all_line_values = self._get_line_values(['P.P', 'DH_PP', 'ONSS', 'ONSS_DOUBLE_HOLIDAY'], vals_list=['total'])
        for payslip in self:
            payslip.l10n_be_onss_contribution = -(all_line_values['ONSS'][payslip.id]['total'] + all_line_values['ONSS_DOUBLE_HOLIDAY'][payslip.id]['total'])
            payslip.l10n_be_withholding_taxes = -(all_line_values['P.P'][payslip.id]['total'] + all_line_values['DH_PP'][payslip.id]['total'])

    def _get_common_localdict(self):
        """
        Values put in this dict will be shared accross all of self's records so
        that they are only fetched once per batch, rather than once per payslip
        """
        common_localdict = super()._get_common_localdict()
        be_payslips = self.filtered(lambda p: p.struct_id.country_id.code == 'BE')
        if not be_payslips:
            return common_localdict

        def year_payslips_domain(payslip):
            return Domain([
                ('employee_id', '=', payslip.employee_id.id),
                ('date_to', '>=', date(payslip.date_to.year, 1, 1)),
                ('date_to', '<=', date(payslip.date_to.year, 12, 31)),
            ])

        def quarter_payslips_domain(payslip):
            quarter_start, quarter_end = date_utils.get_quarter(payslip.date_to)
            return Domain([
                ('employee_id', '=', payslip.employee_id.id),
                ('date_to', '>=', quarter_start),
                ('date_to', '<=', quarter_end),
            ])

        def month_payslips_domain(payslip):
            month_start = date(payslip.date_to.year, payslip.date_to.month, 1)
            month_end = month_start + relativedelta(months=1, days=-1)
            return Domain([
                ('employee_id', '=', payslip.employee_id.id),
                ('date_to', '>=', month_start),
                ('date_to', '<=', month_end),
            ])

        def previous_month_domain(payslip):
            prev_month = payslip.date_from + relativedelta(day=1, days=-1)
            return Domain([
                ('employee_id', '=', payslip.employee_id.id),
                ('date_to', '>=', prev_month.replace(day=1)),
                ('date_to', '<=', prev_month),
                ('state', 'in', ('validated', 'paid')),
            ])

        if self.env.context.get('salary_simulation'):
            # salary simluation should not be affected by other payslips
            all_year_payslips = self.env['hr.payslip']
        else:
            # all the keys reusing the year payslips care about validated/paid
            # payslips only
            all_year_payslips = self.search(Domain.OR([
                year_payslips_domain(be_payslip) for be_payslip in be_payslips
            ]) & Domain('state', 'in', ('validated', 'paid')))

        # use these keys to easily get self's validated/paid payslips during
        # self's current year/quarter/month
        common_localdict['l10n_be_year_payslips_by_payslip'] = {
            be_payslip: all_year_payslips.filtered_domain(year_payslips_domain(be_payslip))
            for be_payslip in be_payslips
        }
        common_localdict['l10n_be_quarter_payslips_by_payslip'] = {
            be_payslip: all_year_payslips.filtered_domain(quarter_payslips_domain(be_payslip))
            for be_payslip in be_payslips
        }
        common_localdict['l10n_be_month_payslips_by_payslip'] = {
            payslip: quarter_payslips.filtered_domain(month_payslips_domain(payslip))
            for payslip, quarter_payslips in common_localdict['l10n_be_quarter_payslips_by_payslip'].items()
        }

        wanted_line_codes = (
            'SALARY', 'BONUS_SALARY', 'EmpBonus.A', 'EmpBonus.B', 'EmpBonus.1', 'GROSS', 'P.P', 'P.P.DED',
            'EMP_BONUS_SALARY', 'SECTORIAL.BONUS', 'CANTEEN',
        )
        common_localdict['l10n_be_month_line_values_by_payslip'] = {
            payslip: month_payslips._get_line_values(wanted_line_codes, compute_sum=True)
            for payslip, month_payslips in common_localdict['l10n_be_month_payslips_by_payslip'].items()
        }

        all_month_exemption_payslips = self.search([
            ('date_to', '>=', min(be_payslips.mapped('date_from')) + relativedelta(day=1)),
            ('date_to', '<=', min(be_payslips.mapped('date_from')) + relativedelta(day=31)),
            ('struct_id.country_id.code', '=', 'BE'),
            '|',
                ('state', 'in', ('validated', 'paid')),
                '&',
                    ('state', 'in', ('draft')),
                    ('payslip_run_id', 'in', be_payslips.payslip_run_id.ids),
                    ('id', 'not in', be_payslips.ids)
        ])
        wanted_line_codes = (
            'WITHHOLDING_TAX_EX_274_32', 'WITHHOLDING_TAX_EX_274_33', 'WITHHOLDING_TAX_EX_274_34',
            'T_WITHHOLDING_TAX_EX_274_74', 'WITHHOLDING_TAX_EX_274_74', 'T_WITHHOLDING_TAX_EX_274_75', 'WITHHOLDING_TAX_EX_274_75', 'PPTOTAL',
        )
        common_localdict['l10n_be_exemptions_month_payslips'] = all_month_exemption_payslips
        common_localdict['l10n_be_exemptions_month_line_values'] = all_month_exemption_payslips._get_line_values(
            wanted_line_codes, compute_sum=True
        )

        common_localdict['l10n_be_prev_month_line_values_by_payslip'] = {
            payslip: all_year_payslips.filtered_domain(previous_month_domain(payslip))._get_line_values(
                ['EmpBonus.A.CO', 'EmpBonus.B.CO', 'EmpBonus.Total.CO'], compute_sum=True
            ) for payslip in be_payslips
        }

        # The transportation exemption is granted on the monthly total, whatever rule fed it
        common_localdict['l10n_be_month_transportation_base_by_payslip'] = {
            payslip: sum(month_payslips.line_ids.filtered(
                lambda line: 'TRANSPORTATION_BASE' in line.salary_rule_id.category_ids.mapped('code')
            ).mapped('total'))
            for payslip, month_payslips in common_localdict['l10n_be_month_payslips_by_payslip'].items()
        }

        # DPV optimization: prefetch previous year work entries once for the whole batch
        be_dpv_payslips = be_payslips.filtered(lambda p: p.struct_id.code == "CP200DOUBLE")
        entries_by_employee = defaultdict(list)
        if be_dpv_payslips:
            year = min(be_dpv_payslips.mapped("date_from")).year - 1
            date_from = date(year, 1, 1)
            date_to = date(year, 12, 31)
            previous_year_work_entries = be_dpv_payslips.employee_id.version_ids.filtered('resource_calendar_id').generate_work_entries(date_from, date_to)
            for entry in previous_year_work_entries:
                entries_by_employee[entry['employee_id']].append(entry)
        common_localdict['l10n_be_prev_year_work_entries'] = dict(entries_by_employee)

        work_hours_by_calendar_and_period = {}

        for payslip in self:
            ref_calendar = payslip.version_id._get_reference_calendar()
            # The number of expected work hours depends both on the calendar and on the period
            key = (ref_calendar, payslip.date_from, payslip.date_to)

            if key not in work_hours_by_calendar_and_period:
                work_hours_by_calendar_and_period[key] = ref_calendar.get_work_hours_count(payslip.date_from, payslip.date_to)

        common_localdict['work_hours_by_calendar_and_period'] = work_hours_by_calendar_and_period

        # Sectoral bonus optimization: prefetch the reference period work entries once for the whole batch
        be_sectorial_payslips = be_payslips.filtered(
            lambda p: p.struct_id.code == "BEMONTHLY" and p._is_cp200_annual_sectorial_bonus_eligible())
        sectorial_entries_by_employee = defaultdict(list)
        if be_sectorial_payslips:
            reference_periods = [p._get_cp200_annual_bonus_reference_period() for p in be_sectorial_payslips]
            ref_start = min(period[0] for period in reference_periods)
            ref_end = max(period[1] for period in reference_periods)
            sectorial_work_entries = be_sectorial_payslips.employee_id.version_ids.filtered('resource_calendar_id').generate_work_entries(ref_start, ref_end)
            for entry in sectorial_work_entries:
                sectorial_entries_by_employee[entry['employee_id']].append(entry)
        common_localdict['l10n_be_sectorial_bonus_work_entries'] = dict(sectorial_entries_by_employee)

        # Intellectual property: yearly IP of the validated/paid payslips, fetched once for the batch
        # (one grouped query): total of the current year (yearly limit, artist lump-sum costs) and
        # average of the 4 previous years (above the yearly limit, the IP is a regular remuneration)
        ip_payslips = be_payslips.filtered(lambda p: p.version_id.ip_wage_rate > 0)
        ip_totals_by_employee_year = defaultdict(float)
        if ip_payslips and not self.env.context.get('salary_simulation'):
            years = {p.date_to.year for p in ip_payslips}
            for employee, year_start, total in self.env['hr.payslip.line']._read_group(
                [
                    ('employee_id', 'in', ip_payslips.employee_id.ids),
                    ('code', '=', 'IP'),
                    ('slip_id.state', 'in', ('validated', 'paid')),
                    ('date_to', '>=', date(min(years) - 4, 1, 1)),
                    ('date_to', '<=', date(max(years), 12, 31)),
                ],
                ['employee_id', 'date_to:year'],
                ['total:sum'],
            ):
                ip_totals_by_employee_year[employee.id, year_start.year] += total
        common_localdict['l10n_be_ip_year_total_by_payslip'] = {
            payslip: ip_totals_by_employee_year[payslip.employee_id.id, payslip.date_to.year]
            for payslip in ip_payslips
        }
        common_localdict['l10n_be_ip_previous_years_average_by_payslip'] = {
            payslip: sum(
                ip_totals_by_employee_year[payslip.employee_id.id, payslip.date_to.year - n]
                for n in range(1, 5)
            ) / 4
            for payslip in ip_payslips
        }

        # Compute mobility amounts once for the whole batch to avoid per-payslip queries
        common_localdict['l10n_be_mobility_amounts_by_payslip'] = be_payslips._get_l10n_be_mobility_amounts()

        return common_localdict

    def _get_bachelor_274_34_exemptions(self, common_localdict, round_localdict):
        valid_274_34_payslips = self.env['l10n_be.274_xx']._get_valid_274_34_payslips(self)

        global_line_values = common_localdict['global_line_values']

        # Get total master + doctor exemption for the current month
        total_32_33_exemption = \
            global_line_values['WITHHOLDING_TAX_EX_274_32']['sum']['total'] + \
            global_line_values['WITHHOLDING_TAX_EX_274_33']['sum']['total'] + \
            common_localdict['l10n_be_exemptions_month_line_values']['WITHHOLDING_TAX_EX_274_32']['sum']['total'] + \
            common_localdict['l10n_be_exemptions_month_line_values']['WITHHOLDING_TAX_EX_274_33']['sum']['total']

        prev_bachelor_exemption = common_localdict['l10n_be_exemptions_month_line_values']['WITHHOLDING_TAX_EX_274_34']['sum']['total']

        bachelor_34_exemption_by_slip = {}
        total_bachelor_exemption = 0

        for payslip in valid_274_34_payslips:
            _, _, exemption = self.env['l10n_be.274_xx']._get_rd_basic_exemption_vals(payslip, global_line_values)
            bachelor_34_exemption_by_slip[payslip] = exemption
            total_bachelor_exemption += exemption

        bachelor_rate = self.env['l10n_be.274_xx']._get_bachelor_exemption_rate(min(self.mapped('date_from')))
        max_exemption = (total_32_33_exemption * bachelor_rate) - prev_bachelor_exemption
        capped_bachelor_total = min(total_bachelor_exemption, max_exemption)
        capping_ratio = capped_bachelor_total / total_bachelor_exemption if total_bachelor_exemption else 1

        for payslip in valid_274_34_payslips:
            bachelor_34_exemption_by_slip[payslip] *= capping_ratio

        round_localdict.update({
            'bachelor_34_exemption_by_slip': bachelor_34_exemption_by_slip
        })

    def _get_l10n_be_full_pay_worked_hours(self):
        """
        Total hours of the period that are remunerated at 100% (e.g. attendances,
        fully paid time off), used as the reference for the Night/Team/Continuous
        Team withholding tax exemption eligibility (274.74/274.75). Unpaid time off
        and partially paid time off (e.g. a worker's guaranteed salary relapse) are
        excluded.
        """
        self.ensure_one()
        return sum(
            line.number_of_hours
            for line in self.worked_days_line_ids
            if line.work_entry_type_id.amount_rate == 1
        )

    def _get_l10n_be_category_option_hours(self, category_code):
        """
        Total worked day hours tagged with the given premium pay category option (or one of
        its descendants). Reads the worked day lines directly (rather than going through
        ``_get_category_options_data``, which needs a live ``work_entries`` list and is
        therefore unusable for already validated payslips), so it works uniformly for this
        batch and for previously validated payslips alike.
        """
        self.ensure_one()
        return sum(
            line.number_of_hours
            for line in self.worked_days_line_ids
            if category_code in line.category_options_ids._get_codes_with_ancestors()
        )

    def _get_l10n_be_category_option_amount(self, category_code):
        """Same as ``_get_l10n_be_category_option_hours`` but summing the worked day line amount."""
        self.ensure_one()
        return sum(
            line.amount
            for line in self.worked_days_line_ids
            if category_code in line.category_options_ids._get_codes_with_ancestors()
        )

    def _get_team_night_274_74_75_exemptions(self, common_localdict, round_localdict):
        """
        WITHHOLDING_TAX_EX_274_74 (Team/Continuous Team) and WITHHOLDING_TAX_EX_274_75 (Night) are
        "mutualized" exemptions: the money isn't computed employee per employee but
        capped on the sum of the withholding tax of every eligible employee of the
        month (this batch + already validated payslips earlier this month).

        The amount already granted on previously validated payslips this month is
        kept as-is (no retroactive recomputation). Only the room left in the pool is distributed to
        this batch's eligible payslips, each capped at its own withholding tax.
        """
        global_line_values = common_localdict['global_line_values']
        month_line_values = common_localdict['l10n_be_exemptions_month_line_values']

        left_to_distribute_team = month_line_values['T_WITHHOLDING_TAX_EX_274_74']['sum']['total'] - month_line_values['WITHHOLDING_TAX_EX_274_74']['sum']['total']
        left_to_distribute_night = month_line_values['T_WITHHOLDING_TAX_EX_274_75']['sum']['total'] - month_line_values['WITHHOLDING_TAX_EX_274_75']['sum']['total']

        team_74_exemption_by_slip = {}
        night_75_exemption_by_slip = {}

        localdicts = common_localdict['localdicts']

        for payslip in self:
            theoretical_team_exemption = global_line_values['T_WITHHOLDING_TAX_EX_274_74'][payslip.id]['total']
            if theoretical_team_exemption:
                remaining_available_pp = global_line_values['PPTOTAL'][payslip.id]['total'] - localdicts[payslip.id]['categories']['TAX_EXEMPTION_GRANTED']
                if remaining_available_pp > theoretical_team_exemption:
                    extra_amount = min(remaining_available_pp - theoretical_team_exemption, left_to_distribute_team)
                    left_to_distribute_team -= extra_amount
                    theoretical_team_exemption += extra_amount
                else:
                    left_to_distribute_team += theoretical_team_exemption - remaining_available_pp
                team_74_exemption_by_slip[payslip] = min(remaining_available_pp, theoretical_team_exemption)
                continue

            theoretical_night_exemption = global_line_values['T_WITHHOLDING_TAX_EX_274_75'][payslip.id]['total']
            if theoretical_night_exemption:
                remaining_available_pp = global_line_values['PPTOTAL'][payslip.id]['total'] - localdicts[payslip.id]['categories']['TAX_EXEMPTION_GRANTED']
                if remaining_available_pp > theoretical_night_exemption:
                    extra_amount = min(remaining_available_pp - theoretical_night_exemption, left_to_distribute_night)
                    left_to_distribute_night -= extra_amount
                    theoretical_night_exemption += extra_amount
                else:
                    left_to_distribute_night += theoretical_night_exemption - remaining_available_pp
                night_75_exemption_by_slip[payslip] = min(remaining_available_pp, theoretical_night_exemption)

        round_localdict.update({
            'team_74_exemption_by_slip': team_74_exemption_by_slip,
            'night_75_exemption_by_slip': night_75_exemption_by_slip
        })

    def _get_round_common_localdict(self, round_nb, common_localdict):
        round_common_localdict = super()._get_round_common_localdict(round_nb, common_localdict)

        if round_nb == 2:
            self._get_bachelor_274_34_exemptions(common_localdict, round_common_localdict)

        if round_nb == 3:
            self._get_team_night_274_74_75_exemptions(common_localdict, round_common_localdict)

        return round_common_localdict

    @api.ormcache('self.employee_id', 'self.date_from', 'self.date_to')
    def _get_period_contracts(self):
        # Returns all the employee contracts over the same payslip period, to avoid
        # double remunerations for some line codes
        self.ensure_one()
        if self.env.context.get('salary_simulation') and self.env.context.get('origin_version_id'):
            return self.env.context['origin_version_id']
        contracts = self.employee_id._get_versions_with_contract_overlap_with_period(
            self.date_from,
            self.date_to,
        ).sorted('date_start')
        return contracts.ids

    def _get_payslip_line_total(self, amount, quantity, rate, rule):
        total = super()._get_payslip_line_total(amount, quantity, rate, rule)
        if self.company_id.country_id.code != 'BE':
            return total
        return float_round(total, precision_rounding=0.01, rounding_method='HALF-UP')

    def _get_max_basic_salary_contract(self, versions):
        self.ensure_one()
        if len(versions) == 1:
            return versions
        for version in versions:
            date_from = max([version.date_start, self.date_from])
            date_end = min([version.date_end, self.date_to]) if version.date_end else self.date_to
            work_entries_vals = version.filtered('resource_calendar_id').generate_work_entries(date_from, date_end)
            all_work_hours = version.get_work_hours(self.date_from, date_end, work_entries_vals)
            work_hours = sum(
                hours for (work_entry_type_id, _options), hours in all_work_hours.items()
                if work_entry_type_id.amount_rate != 0)
            if not float_is_zero(work_hours, precision_digits=2):
                return version
        return versions[0]

    @api.depends('struct_id', 'date_from')
    def _compute_l10n_be_is_december(self):
        for payslip in self:
            payslip.l10n_be_is_december = payslip.struct_id.code == "BEMONTHLY" and payslip.date_from and payslip.date_from.month == 12

    @api.depends('struct_id')
    def _compute_l10n_be_is_double_pay(self):
        for payslip in self:
            payslip.l10n_be_is_double_pay = payslip.struct_id.code == "BEDOUBLE"

    def _l10n_be_get_holiday_pay_provision_base(self, gross):
        """ Return the base on which the holiday pay tax provision is computed.
        We start from the monthly gross salary and add back the days that count for the
        double holiday pay but were not paid on this payslip (legal leave, public holidays, ...).
        Without this top up the provision would stop growing whenever the employee is on such an absence.
        """
        self.ensure_one()
        non_assimilated_codes = self.env['hr.work.entry.type'].search([('category_ids.code', '=', 'UNASSIMILATED')]).mapped('code')
        wage = self.version_id._get_contract_wage()
        # Assimilated but unpaid days have been deducted from the gross salary: add
        # their value back with the same daily factor so that the deduction cancels
        # out and a fully assimilated month reaches the same base as a worked month.
        assimilated_unpaid = self.worked_days_line_ids.filtered(
            lambda wd: not wd.is_paid
            and wd.code not in non_assimilated_codes
            and wd.code != '202.00'
            and not wd.work_entry_type_id.is_extra_hours
            and not wd.work_entry_type_id.l10n_be_is_time_credit
            and not wd.work_entry_type_id.l10n_be_economic_unemployment,
        )
        top_up = sum(wd._l10n_be_get_workday_amount(wage) for wd in assimilated_unpaid)
        return gross + top_up

    def _get_eco_vouchers_amount(self, get_explanation=False):
        self.ensure_one()
        eco_config = self.env['hr.rule.parameter']._get_parameter_from_code('eco_voucher_config', self.date_to, raise_if_not_found=False) or {}

        # Reference period: 12 months ending month before payment
        # E.g. Month 6 -> Ref: 1st June Prev -> 31st May Curr
        ref_date_end = self.date_from - relativedelta(months=1, day=31)
        ref_date_start = ref_date_end + relativedelta(days=1, months=-12)

        # Broad search to identify JCs in history
        all_contracts = self.employee_id._get_versions_with_contract_overlap_with_period(ref_date_start, self.date_to)
        relevant_jcs = all_contracts.mapped('l10n_be_joint_committee_id')

        current_month = self.date_from.month
        is_departing = self._l10n_be_is_last_payslip()
        matching_jc_codes = [
            code for code, cfg in eco_config.items()
            if (cfg.get('month') == current_month or is_departing) and code in relevant_jcs.mapped('egov3_code')
        ]

        if not matching_jc_codes:
            return (0.0, {'jc_codes': 'None', 'total': 0.0}) if get_explanation else 0.0

        # 128.00 (maternity), 128.05 (paternity) and 135.00 (unpredictable) are
        # assimilated periods: the days they cover remain valid. 147.00 (credit
        # time), 147.05 (parental time off) and 142.99 (youth time off) are
        # structural reductions of the working time already reflected in the
        # version's work_time_rate (and thus in the granted amount), so they
        # must not be counted again as absence days.
        assimilated_codes = ['128.00', '128.05', '135.00']
        structural_codes = ['147.00', '147.05', '142.99']
        unpaid_work_entry_types = self.env['hr.work.entry.type'].search([
            ('amount_rate', '=', 0.0),
            ('code', 'not in', assimilated_codes + structural_codes),
            ('country_id.code', 'in', [False, 'BE']),
        ])
        # Work entry types that don't testify of the occupation state on their own:
        # structural reductions behave like days off for the employee, public
        # holidays (006.00) happen whether the employee is absent or not, and out
        # of contract (000.00) days are not part of the occupation. Those days are not
        # working days: like week-ends, they enter neither the valid nor the
        # invalid count.
        neutral_codes = structural_codes + ['006.00', '000.00']

        total_amount = 0
        for jc_code in matching_jc_codes:
            jc_config = eco_config.get(jc_code)
            jc_month = jc_config.get('month')

            # Targeted fix for departing employees: adjust ref period to match JC cycle
            jc_ref_end, jc_ref_start = ref_date_end, ref_date_start
            if is_departing and jc_month != current_month:
                target_year = self.date_from.year
                if self.date_from.month > jc_month:
                    target_year += 1
                jc_ref_end = date(target_year, jc_month, 1) - relativedelta(days=1)
                jc_ref_start = jc_ref_end - relativedelta(months=12) + relativedelta(days=1)

            # Filter versions for this specific JC using the standard contract helper
            all_contracts_jc = self.employee_id._get_versions_with_contract_overlap_with_period(jc_ref_start, jc_ref_end)
            jc_versions = all_contracts_jc.filtered(lambda v: v.l10n_be_joint_committee_id.egov3_code == jc_code)
            if not jc_versions:
                continue

            # Generate the work entries over the reference period once for every
            # version of the joint committee: the working days actually performed
            # or assimilated are counted from the work entry dates.
            work_entries_vals_by_version = defaultdict(list)
            for vals in jc_versions.filtered('resource_calendar_id').generate_work_entries(jc_ref_start, jc_ref_end):
                work_entries_vals_by_version[vals['version_id'].id].append(vals)

            # The granted amount depends on the weekly working time, which may change
            # from one version to the next, so each version is prorated on its own
            # (with its own work time rate and its own valid/invalid working days).
            theoretical_days_by_calendar = {}
            for version in jc_versions.sorted('date_start'):
                work_time_rate = version.work_time_rate
                # skip versions with 0% work time rate such as full parental time off or credit time
                if not work_time_rate:
                    continue
                version_from = max(jc_ref_start, version.date_start)
                version_to = min(jc_ref_end, version.date_end or jc_ref_end)
                if version_from > version_to:
                    continue
                # The proration is expressed in working days: the days the employee
                # actually worked or that are assimilated, over the days the
                # calendar theoretically schedules for the whole reference period,
                # so that a full reference period yields exactly the granted amount.
                valid_days, invalid_days = self._get_eco_vouchers_working_days(
                    work_entries_vals_by_version[version.id], unpaid_work_entry_types, neutral_codes)
                calendar = version.resource_calendar_id
                if calendar not in theoretical_days_by_calendar:
                    theoretical_days_by_calendar[calendar] = self._get_eco_vouchers_theoretical_working_days(
                        calendar, jc_ref_start, jc_ref_end)
                theoretical_days = theoretical_days_by_calendar[calendar]

                if 'amount_from_rate' in jc_config:
                    amount = jc_config['amount_from_rate'][-1][1]
                    for rate_threshold, rate_amount in jc_config['amount_from_rate']:
                        if work_time_rate >= rate_threshold:
                            amount = rate_amount
                            break
                    if theoretical_days:
                        total_amount += max(0, (valid_days / theoretical_days) * amount)
                elif jc_code == '302':
                    # - Full-time: 250 * complete_months/12 + 250 * partial_working_days/divisor
                    # - Part-time: 250 * working_days/divisor
                    # Divisor: 260 for 5-day week, 312 for 6-day week (company reference).
                    max_amount = jc_config['max_amount']
                    days_per_week = version.resource_calendar_id.days_per_week
                    if not days_per_week:
                        reference_calendar = version.reference_calendar_id or version.company_id.resource_calendar_id
                        half_day_hours_threshold = reference_calendar.hours_per_day * 3 / 4
                        days_per_week = version.resource_calendar_id._get_days_per_week_for_period(
                            version_from, version_to, half_day_hours_threshold
                        )
                    if not days_per_week:
                        days_per_week = 5
                    divisor = 312 if days_per_week >= 6 else 260

                    def _count_working_days(d_from, d_to, calendar=version.resource_calendar_id):
                        return calendar.get_work_duration_data(
                            datetime.combine(d_from, time.min).replace(tzinfo=UTC),
                            datetime.combine(d_to, time.max).replace(tzinfo=UTC),
                            compute_leaves=False,
                        )['days']

                    if work_time_rate >= 1.0:
                        # Full-time: complete months use months/12 (contract-based, attendance
                        # irrelevant). Only the first and last months can be partial.
                        total_months = (version_to.year - version_from.year) * 12 + (version_to.month - version_from.month) + 1
                        first_month_end = date(version_from.year, version_from.month, 1) + relativedelta(day=31)
                        last_month_start = date(version_to.year, version_to.month, 1)
                        last_month_end = last_month_start + relativedelta(day=31)
                        complete_months = 0
                        partial_working_days = 0

                        if total_months == 1:
                            if version_from.day == 1 and version_to == first_month_end:
                                complete_months = 1
                            else:
                                partial_working_days = _count_working_days(version_from, version_to)
                        else:
                            if version_from.day == 1:
                                complete_months += 1
                            else:
                                partial_working_days += _count_working_days(version_from, first_month_end)
                            complete_months += total_months - 2
                            if version_to == last_month_end:
                                complete_months += 1
                            else:
                                partial_working_days += _count_working_days(last_month_start, version_to)

                        amount = max_amount * complete_months / 12
                        if partial_working_days:
                            amount += max_amount * max(0, partial_working_days - invalid_days) / divisor
                    else:
                        # Part-time: count actual working days (each day = 1 regardless of
                        # duration); do NOT scale by work_time_rate — days_per_week already
                        # captures how many distinct days/week the employee works.
                        working_days = max(0, _count_working_days(version_from, version_to) - invalid_days)
                        amount = max_amount * working_days / divisor
                    total_amount += max(0, min(amount, max_amount))
                else:
                    if theoretical_days:
                        total_amount += max(0, (valid_days / theoretical_days) * jc_config['max_amount'] * min(1, work_time_rate))

        explanation_info = {
            'jc_codes': ', '.join(matching_jc_codes),
            'total': float_round(total_amount, precision_digits=2),
        }
        return (total_amount, explanation_info) if get_explanation else total_amount

    def _get_eco_vouchers_working_days(self, work_entries_vals, unpaid_work_entry_types, neutral_codes):
        """ Count the valid and invalid working days over the given (already
        generated) work entry values.

        A date carrying a non neutral work entry is a working day: it is valid
        when actually worked or covered by an assimilated absence (sick time
        off, paid time off, maternity, ...), invalid when covered by a non
        assimilated (unpaid) absence. Neutral entries (public holidays,
        structural reductions such as credit time) are not working days at all,
        like week-ends.

        :return: (valid working days, invalid working days)
        """
        working_dates = set()
        unpaid_dates = set()
        for vals in work_entries_vals:
            work_entry_type = vals.get('work_entry_type_id')
            if not work_entry_type or work_entry_type.code in neutral_codes:
                continue
            working_dates.add(vals['date'])
            if work_entry_type in unpaid_work_entry_types:
                unpaid_dates.add(vals['date'])
        return len(working_dates - unpaid_dates), len(unpaid_dates)

    def _get_eco_vouchers_theoretical_working_days(self, calendar, date_from, date_to):
        """ Number of days the calendar theoretically schedules real work over
        ``[date_from, date_to]``: week-ends, public holidays (through the
        calendar global leaves) and structural slots (e.g. credit time) are
        excluded, so that the result is directly comparable with the working
        days counted from the work entries. An employee occupied over the whole
        period without any non assimilated absence gets exactly the full
        granted amount.
        """
        work_intervals = calendar._work_intervals_batch(
            datetime.combine(date_from, time.min).replace(tzinfo=UTC),
            datetime.combine(date_to, time.max).replace(tzinfo=UTC),
        )[False]
        return len({
            start.date()
            for start, dummy, attendances in work_intervals
            if any(
                not attendance.work_entry_type_id or attendance.work_entry_type_id.count_as == 'working_time'
                for attendance in attendances
            )
        })

    def _get_l10n_be_max_seizable_amount(self, expected_net, localdict):
        # Source: https://emploi.belgique.be/fr/themes/remuneration/protection-de-la-remuneration/saisie-et-cession-sur-salaires
        self.ensure_one()
        if localdict.get('l10n_be_max_seizable_amount', False):
            return localdict['l10n_be_max_seizable_amount']
        rates = self.env['hr.rule.parameter']._get_parameter_from_code('seizable_percentages', self.date_to, raise_if_not_found=False)
        child_increase = self.env['hr.rule.parameter']._get_parameter_from_code('seizable_amount_child', self.date_to, raise_if_not_found=False)
        if not rates or not child_increase:
            localdict['l10n_be_max_seizable_amount'] = expected_net
            return expected_net
        dependent_children = self.employee_id.l10n_be_dependent_children_attachment
        max_seizable_amount = 0
        for left, right, rate in rates:
            if dependent_children:
                left += dependent_children * child_increase
                right += dependent_children * child_increase
            if left <= expected_net:
                max_seizable_amount += (min(expected_net, right) - left) * rate
        localdict['l10n_be_max_seizable_amount'] = max_seizable_amount
        return max_seizable_amount

    @api.depends("date_from", "employee_id.marital")
    def _compute_effective_marital(self):
        for slip in self:
            slip.l10n_be_effective_marital = slip.employee_id._get_effective_marital_at_date(slip.date_from)

    def _get_salary_advance_balances(self):
        balance_by_employee = super()._get_salary_advance_balances()
        all_payslips = self.search([
            ('struct_id.country_id', '=', 'BE'),
            ('state', 'in', ('validated', 'paid')),
            ('employee_id', 'in', self.employee_id.ids),
        ])
        line_values = all_payslips._get_line_values(['SALARYADVREC', 'SALARYADV'])
        for payslip in all_payslips:
            balance_by_employee[payslip.employee_id]['SALARYADV'] += line_values['SALARYADV'][payslip.id]['total']
            balance_by_employee[payslip.employee_id]['SALARYADVREC'] += line_values['SALARYADVREC'][payslip.id]['total']  # negative amount
        return balance_by_employee

    def _get_worked_day_lines_hours_per_day(self, version):
        self.ensure_one()
        if version.l10n_be_time_credit:
            return version._get_reference_calendar().hours_per_day
        return super()._get_worked_day_lines_hours_per_day(version)

    def _get_out_of_contract_calendar(self, version):
        self.ensure_one()
        if version.l10n_be_time_credit:
            return version._get_reference_calendar()
        return super()._get_out_of_contract_calendar(version)

    def _get_worked_day_lines_values(self, version, work_entries_vals):
        self.ensure_one()
        res = []
        if self.struct_id.country_id.code != 'BE':
            return super()._get_worked_day_lines_values(version, work_entries_vals)
        # If a belgian payslip has half-day attendances/time off, it the worked days lines should
        # be separated
        work_hours = version._get_work_hours_split_half(self.date_from, self.date_to, work_entries_vals)
        work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
        for worked_days_data, duration_data in work_hours_ordered:
            work_entry_type_id, category_options = worked_days_data
            number_of_days, number_of_hours = duration_data
            work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
            attendance_line = {
                'version_id': version.id,
                'sequence': work_entry_type.sequence,
                'work_entry_type_id': work_entry_type_id,
                'number_of_days': number_of_days,
                'number_of_hours': number_of_hours,
                'category_options_ids': category_options,
            }
            res.append(attendance_line)
        return res

    def _l10n_be_get_loss_on_commission_amount_public_holiday(self, localdict):
        self.ensure_one()
        first_contract_date = self.employee_id._get_first_contract_date()
        if not self.version_id.commission_on_target or not first_contract_date:
            return 0

        worked_day_line_values = self._get_worked_days_line_values(
            ['006.00', '002.00'], ['number_of_days'], compute_sum=True
        )
        public_holiday_number_of_days = worked_day_line_values['006.00']['sum']['number_of_days']

        if first_contract_date.year == self.date_from.year and first_contract_date.month == self.date_from.month:
            # If employee joined during current month, average variable salary = commissions / # worked days
            commissions = localdict['result_rules']['COMMISSION']['total'] + localdict['result_rules']['COMMISSION_ADV']['total']
            worked_days = worked_day_line_values['002.00']['sum']['number_of_days']
            return (commissions / worked_days) * public_holiday_number_of_days if worked_days else 0
        elif first_contract_date.year == self.date_from.year:
            # If employee joined during current year, compute monthly average variable salary of current year
            average_monthly_variable_revenue_ref = self._get_last_year_average_variable_revenues(
                excluded_codes={'COM_LOSS_PH'}
            )
        else:
            # Else compute last civil year monthly average variable salary
            average_monthly_variable_revenue_ref = self.with_context(
                variable_revenue_date_from=date(year=self.date_from.year, month=1, day=1)
            )._get_last_year_average_variable_revenues(excluded_codes={'COM_LOSS_PH'})
        days_per_week = self.version_id.resource_calendar_id.days_per_week
        if not days_per_week:
            return 0
        average_daily_variable_revenue = average_monthly_variable_revenue_ref / (25 * days_per_week / 6)
        return average_daily_variable_revenue * public_holiday_number_of_days

    def _l10n_be_get_loss_on_commission_amount_sickness(self):
        self.ensure_one()
        last_year_monthly_variable_revenue = self._get_last_year_average_variable_revenues()
        days_per_week = self.version_id.resource_calendar_id.days_per_week
        if not self.version_id.commission_on_target or not days_per_week:
            return 0
        last_year_daily_variable_revenue = last_year_monthly_variable_revenue / (25 * days_per_week / 6)
        work_entry_type_codes = self.env['hr.work.entry.type'].search([('category_ids.code', '=', 'VARIABLE_SALARY_LOSS')]).mapped('code')
        worked_day_line_values = self._get_worked_days_line_values(
            work_entry_type_codes, ['number_of_days'], compute_sum=True
        )
        number_of_days = sum(worked_day_line_values[code]['sum']['number_of_days'] for code in work_entry_type_codes)
        return last_year_daily_variable_revenue * number_of_days

    def _get_last_year_average_variable_revenues(self, excluded_codes=None):
        date_from = self.env.context.get('variable_revenue_date_from', self.date_from)
        first_version_date = self.employee_id._get_first_contract_date()
        if not first_version_date:
            return 0
        start = first_version_date
        end = date_from + relativedelta(day=31, months=-1)
        number_of_month = (end.year - start.year) * 12 + (end.month - start.month) + 1
        number_of_month = min(12, number_of_month)
        if number_of_month <= 0:
            return 0
        return self.employee_id._get_last_year_variable_revenues(date_from=date_from, excluded_codes=excluded_codes) / number_of_month

    def _get_l10n_be_double_holiday_variable_revenues(self, work_entries=None):
        self.ensure_one()
        force_avg_variable_revenues = self._get_input_line_amount('VARIABLE')
        if force_avg_variable_revenues:
            return force_avg_variable_revenues

        versions = self.employee_id.version_ids.filtered(lambda v: v.structure_type_id == self.struct_id.type_id)
        if not versions:
            return 0.0

        last_year_variable_per_month = self.with_context(
            variable_revenue_date_from=self.date_from
        )._get_last_year_average_variable_revenues()

        # We should then prorate the amount regarding leave rights.
        # Example: 5000€ commissions, employee arrived in october
        # Monthly commission = 5000€ / 8 = 625€
        # Then we need to check the legal leaves right (from January to December)
        # He worked 3 months at this company and 3 months from the holiday attest
        # Double variable base = 625 * 10/20 = 287.5€

        year = self.date_from.year - 1
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)

        number_of_months = self._compute_double_holiday_assimilated_months(date_from, date_to, versions, work_entries=work_entries)

        attestations = self.employee_id.l10n_be_holiday_attest_ids.filtered(
            lambda attest: attest.year == year and attest.prev_double_holiday_pay_paid > 0,
        )

        if attestations:
            for attest in attestations:
                number_of_months += attest._get_number_of_months() * attest.prev_work_time_rate

        return last_year_variable_per_month * (number_of_months / 12)

    def _get_l10n_be_simple_holiday_variable_revenues(self):
        self.ensure_one()
        force_avg_variable_revenues = self._get_input_line_amount('VARIABLE')
        if force_avg_variable_revenues:
            last_year_variable_per_month = force_avg_variable_revenues
        else:
            last_year_variable_per_month = self.with_context(
                variable_revenue_date_from=self.date_from
            )._get_last_year_average_variable_revenues()

        last_year_variable_per_day = last_year_variable_per_month / 20.83

        legal_time_off_work_entry_types = self.env['hr.work.entry.type'].search([
            ('code', '=', '016.00')
        ])

        legal_leaves_allocations = sum(self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id),
            ('work_entry_type_id', 'in', legal_time_off_work_entry_types.ids),
            ('state', '=', 'validate'),
            ('date_from', '>', date(self.date_from.year - 1, 12, 31)),
            ('date_from', '<', date(self.date_from.year + 1, 1, 1))
        ]).mapped('number_of_days'))
        result = last_year_variable_per_day * legal_leaves_allocations
        explanation_info = {'explanation': self.env._(
            "Result = Average Variable Revenue per Day (%(last_year)s €) * Legal Leave Allocation Days (%(legal_leaves)s)",
            last_year=float_round(last_year_variable_per_day, precision_digits=2),
            legal_leaves=float_round(legal_leaves_allocations, precision_digits=2)
        )}

        return result, explanation_info

    def _get_last_year_average_warrant_revenues(self):
        warrant_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('struct_id.code', '=', 'BEWARRANT'),
            ('date_from', '>=', self.date_from + relativedelta(months=-12, day=1)),
            ('date_from', '<', self.date_from),
        ], order="date_from asc")
        total_amount = warrant_payslips._get_line_values(['WARRANT_BASIC'], compute_sum=True)['WARRANT_BASIC']['sum']['total']
        first_version_date = self.employee_id._get_first_contract_date()
        if not first_version_date:
            return 0
        # Only complete months count
        if first_version_date.day != 1:
            start = first_version_date + relativedelta(day=1, months=1)
        else:
            start = first_version_date
        end = self.date_from + relativedelta(day=31, months=-1)
        number_of_month = (end.year - start.year) * 12 + (end.month - start.month) + 1
        number_of_month = min(12, number_of_month)
        return total_amount / number_of_month if number_of_month else 0

    def _compute_number_complete_months_of_work(self, date_from, date_to, versions, use_work_rate=False):
        days_by_version_by_year = defaultdict(lambda: defaultdict(dict))
        for day in rrule.rrule(rrule.DAILY, dtstart=date_from + relativedelta(day=1), until=date_to + relativedelta(day=31)):
            days_by_version_by_year[day.year][day.month][day.date()] = None

        public_holidays = [(leave.date_from.date(), leave.date_to.date()) for leave in self.employee_id._get_public_holidays(date_from, date_to)]
        for version in versions:
            attendances_by_date = version.resource_calendar_id._get_attendances_by_date(date_from, date_to)

            previous_week_start = max(version.date_start + relativedelta(weeks=-1, weekday=MO(-1)), date_from + relativedelta(day=1))
            next_week_end = min(version.date_end + relativedelta(weeks=+1, weekday=SU(+1)) if version.date_end else date.max, date_to)
            days_to_check = rrule.rrule(rrule.DAILY, dtstart=previous_week_start, until=next_week_end)
            for day in days_to_check:
                day = day.date()

                # Full time credit time doesn't count
                if version.l10n_be_time_credit and not version.work_time_rate:
                    continue
                if version.date_start <= day <= (version.date_end or date.max):
                    days_by_version_by_year[day.year][day.month][day] = version
                elif (not attendances_by_date[day].filtered(lambda a: a._is_work_period()) or
                        any(date_from <= day <= date_to for date_from, date_to in public_holidays)):
                    days_by_version_by_year[day.year][day.month][day] = 'holiday'

        months = 0
        for invalid_days_by_months in days_by_version_by_year.values():
            for days in invalid_days_by_months.values():
                counter = Counter(days.values())
                if None in counter:
                    continue
                if use_work_rate:
                    under_contract_days = sum(counter.values()) - counter.pop('holiday', 0)
                    for version, n_days in counter.items():
                        months += n_days / under_contract_days * version.work_time_rate
                else:
                    months += 1
        return months

    @api.depends('worked_days_line_ids', 'worked_days_line_ids.number_of_hours', 'date_from', 'date_to', 'employee_id', 'version_id')
    def _compute_l10n_additional_hours_checks(self):
        # The hours a part time worker performs on top of their own schedule, up to a full
        # time one: the plain ones and the ones already paid at +50% / +100%.
        additional_hours_codes = ['003.00', '003.12', '003.08']
        # Additional hours and overtime both carry the "Extra Hours" salary rule category,
        # but overtime is authorized beyond the legal daily and weekly maxima, so it never
        # counts towards them.
        overtime_codes = set(self.env['hr.work.entry.type'].search([
            ('is_extra_hours', '=', True),
            ('country_id.code', '=', 'BE'),
        ]).mapped('code')) - set(additional_hours_codes)

        valid_payslips = self.filtered(lambda p: p.date_from and p.date_to and p.employee_id and p.version_id)
        worked_days_data = valid_payslips._get_worked_days_line_values(additional_hours_codes, vals_list=['number_of_hours'])

        calendar_work_intervals = {}
        if valid_payslips:
            global_datetime_from = fields.Datetime.to_datetime(
                min(valid_payslips.mapped('date_from')) + relativedelta(weekday=MO(-1))).replace(tzinfo=UTC)
            global_datetime_to = fields.Datetime.to_datetime(
                max(valid_payslips.mapped('date_to')) + relativedelta(days=1)).replace(tzinfo=UTC)
            all_versions = valid_payslips.mapped('employee_id.version_ids').filtered('resource_calendar_id')

            for calendar in all_versions.mapped('resource_calendar_id'):
                calendar_version = all_versions.filtered(lambda v: v.resource_calendar_id == calendar)
                resources_per_tz = {}
                for version in calendar_version:
                    for tz, tz_resources in version._get_resources_per_tz().items():
                        resources_per_tz[tz] = resources_per_tz.get(tz, self.env['resource.resource']) | tz_resources
                calendar_work_intervals[calendar.id] = calendar._work_intervals_batch(
                    global_datetime_from, global_datetime_to, resources_per_tz
                )

        # Batch work entries generation
        global_date_from = min(valid_payslips.mapped('date_from')) + relativedelta(weekday=MO(-1))
        global_date_to = max(valid_payslips.mapped('date_to'))
        all_versions = valid_payslips.mapped('employee_id.version_ids').filtered('resource_calendar_id')

        all_work_entries_vals = all_versions.generate_work_entries(global_date_from, global_date_to)

        entries_by_version = defaultdict(list)
        for entry in all_work_entries_vals:
            entries_by_version[entry.get('version_id')].append(entry)

        for payslip in valid_payslips:
            payslip.l10n_be_sum_additional_hours = 0
            payslip.l10n_be_wrong_additional_hours_on_sundays_or_public_holidays = False
            payslip.l10n_be_additional_hours_during_working_time = False
            payslip.l10n_be_working_hours_limit_per_day_exceeded = False
            payslip.l10n_be_working_hours_limit_per_week_exceeded = False

            has_additional_hours = any(
                worked_days_data[code][payslip.id]['number_of_hours'] for code in additional_hours_codes)
            if not has_additional_hours:
                continue
            payslip.l10n_be_sum_additional_hours = worked_days_data['003.00'][payslip.id]['number_of_hours']

            public_leaves = payslip.version_id.resource_calendar_id.global_leave_ids.filtered(
                lambda leave: leave.work_entry_type_id.code == '006.00')
            public_holidays_dates = {l.date() for l in public_leaves.mapped('date_from')}

            # If the month doesn't start with Monday, take the rest of the first week from the previous month:
            first_week_monday = payslip.date_from + relativedelta(weekday=MO(-1))
            work_entries_vals = []
            for version in payslip.employee_id.version_ids.filtered('resource_calendar_id'):
                for entry in entries_by_version.get(version, []):
                    entry_date = entry['date']
                    if first_week_monday <= entry_date <= payslip.date_to:
                        work_entries_vals.append(entry)

            work_entries_vals_by_date = defaultdict(float)
            work_entries_vals_by_week = defaultdict(float)

            for entry in work_entries_vals:
                if entry['work_entry_type_id'].count_as == 'absence' or entry['work_entry_type_id'].code in overtime_codes:
                    continue

                _, week_number, _ = entry['date'].isocalendar()
                work_entries_vals_by_week[week_number] += entry['duration']

                if entry['date'] < payslip.date_from:
                    continue

                work_entries_vals_by_date[entry['date']] += entry['duration']
                if entry['work_entry_type_id'].code in additional_hours_codes:
                    entry_version = entry.get('version_id')

                    effective_version = entry_version if entry_version else payslip.version_id
                    entry_calendar = effective_version.resource_calendar_id

                    cal_intervals_dict = calendar_work_intervals.get(entry_calendar.id, {}) if entry_calendar else {}
                    employee_intervals = cal_intervals_dict.get(effective_version.employee_id.resource_id.id, Intervals())

                    standard_work_duration_on_date = sum(
                        attendance.duration_hours
                        for attendance in entry_calendar.attendance_ids._filter_by_date(entry['date'])
                    )

                    if standard_work_duration_on_date > 0:
                        for leave in entry['leave_ids']:
                            leave_start = fields.Datetime.to_datetime(leave.date_from).replace(tzinfo=UTC)
                            leave_end = fields.Datetime.to_datetime(leave.date_to).replace(tzinfo=UTC)

                            leave_interval = Intervals([(leave_start, leave_end, leave)])

                            if employee_intervals & leave_interval:
                                payslip.l10n_be_additional_hours_during_working_time = True
                                break

                    is_sunday_or_public_holiday = entry['date'].weekday() == 6 or entry['date'] in public_holidays_dates
                    if is_sunday_or_public_holiday and entry['work_entry_type_id'].code != '003.08':
                        payslip.l10n_be_wrong_additional_hours_on_sundays_or_public_holidays = True

            day_limit = 9
            week_limit = payslip.version_id.reference_calendar_id.full_time_required_hours if payslip.version_id.reference_calendar_id else 40
            if any(d > day_limit for d in work_entries_vals_by_date.values()):
                payslip.l10n_be_working_hours_limit_per_day_exceeded = True
            if any(w > week_limit for w in work_entries_vals_by_week.values()):
                payslip.l10n_be_working_hours_limit_per_week_exceeded = True

    def _l10n_be_get_work_entry_vals_by_date(self, date_from, date_to, work_entries=None):
        work_entries_vals = work_entries or self.employee_id.version_ids.filtered('resource_calendar_id').generate_work_entries(
            date_from, date_to)
        work_entries_vals_by_date = defaultdict(list)
        for vals in work_entries_vals:
            work_entries_vals_by_date[vals['date']].append(vals)
        return work_entries_vals_by_date

    def _l10n_be_get_version_by_date(self, date_from, date_to, versions):

        def is_less_or_first_work_day_of_month(calendar, d):
            current_date = date(d.year, d.month, 1)
            while not calendar._works_on_date(current_date):
                current_date += timedelta(days=1)
                if current_date.month != d.month:
                    return False
            return d <= current_date

        version_by_date = defaultdict(lambda: defaultdict(dict))
        for day in rrule.rrule(rrule.DAILY, dtstart=date_from, until=date_to):
            version_by_date[day.year][day.month][day.date()] = None

        for idx, version in enumerate(versions):
            calendar = version.resource_calendar_id
            date_start = max(version.date_start, date_from)
            next_version_start = versions[idx + 1].date_start if idx < len(versions) - 1 else date.max
            date_end = min(
                version.date_end or date.max,
                version.departure_date or date.max,
                date_to,
                next_version_start - relativedelta(days=1),
            )
            if is_less_or_first_work_day_of_month(calendar, date_start):
                new_date_start = date_start - relativedelta(days=1)
                while new_date_start.month == date_start.month and not calendar._works_on_date(new_date_start) and date_from <= new_date_start:
                    date_start = new_date_start
                    new_date_start -= relativedelta(days=1)

            new_date_end = date_end + relativedelta(days=1)
            while not calendar._works_on_date(new_date_end) and new_date_end <= date_to and new_date_end < next_version_start:
                date_end = new_date_end
                new_date_end += relativedelta(days=1)

            days_to_check = rrule.rrule(rrule.DAILY, dtstart=date_start, until=date_end)

            for day in days_to_check:
                day = day.date()
                if version_by_date[day.year][day.month][day]:
                    continue
                version_by_date[day.year][day.month][day] = version
        return version_by_date

    def _compute_13th_month_presence_prorated_fixed_wage(self, date_from, date_to, versions):
        self.ensure_one()

        def round_half_days(duration):
            return round(duration * 2) / 2

        unpaid_work_entry_types = self.env['hr.work.entry.type'].search(
            domain=[
                ('code', 'in', ('158.00', '155.00')),
                ('country_code', '=', 'BE'),
            ]
        )

        work_entries_vals_by_date = self._l10n_be_get_work_entry_vals_by_date(date_from, date_to)
        fte_basic = self.version_id._get_contract_wage() / self.version_id.work_time_rate if self.version_id.work_time_rate else 0
        company_avg_hours_per_day = self.version_id._get_reference_calendar().hours_per_day

        payslip_amount = 0
        n_months = 0

        sick_work_entry_types = [
            self.env.ref('hr_work_entry.be_work_entry_type_sick_leave'),  # Sick Time Off
            self.env.ref('hr_work_entry.l10n_be_work_entry_type_long_sick'),  # Long Term Sick
            self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period'),  # days of illness after 30th day
            self.env.ref('hr_work_entry.l10n_be_work_entry_type_partial_incapacity'),  # Partial Incapacity
        ]
        unpredictable_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_unpredictable')

        covered_time_offs = self.env['hr.leave']
        pfa_calendar_sick_days_remaining = 60
        pfa_sick_calendar_days_to_defer = 0  # used to report time off to deduct to next month
        pfa_unpredictable_days_remaining = 10

        all_work_entry_vals = [vals for vals_by_date in work_entries_vals_by_date.values() for vals in vals_by_date]
        sick_work_entries_vals = [vals for vals in all_work_entry_vals if vals['work_entry_type_id'] in sick_work_entry_types]
        unpredictable_work_entries_vals = [vals for vals in all_work_entry_vals if vals['work_entry_type_id'] == unpredictable_work_entry_type]

        # If the first work entry of the year is a sick work entry, check for last year work entries
        # If already sick in december last year, we should deduct these days, except if there is a period of 14 calendar days of work
        first_date_of_year = min(work_entries_vals_by_date)
        work_entries_first_day = [vals for vals in all_work_entry_vals if vals['date'] == first_date_of_year]
        if work_entries_vals_by_date.values() and all(we['work_entry_type_id'] in sick_work_entry_types for we in work_entries_first_day):
            last_year_work_entries_vals = self.employee_id.version_ids.filtered('resource_calendar_id').generate_work_entries(
                date_from - relativedelta(years=1),
                date_to - relativedelta(years=1))
            last_date_of_last_year = max(vals['date'] for vals in last_year_work_entries_vals) if last_year_work_entries_vals else False
            work_entries_last_day = [vals for vals in last_year_work_entries_vals if vals['date'] == last_date_of_last_year]
            if last_year_work_entries_vals and all(we['work_entry_type_id'] in sick_work_entry_types for we in work_entries_last_day):
                last_year_sick_work_entries_vals = [vals for vals in last_year_work_entries_vals if vals['work_entry_type_id'] in sick_work_entry_types]
                # Check if has worked for 14 consecutive days. If yes, then do not deduct last year sick days
                # We ignore half days of sickness, as sick time off are not taken in half days in Belgium
                has_worked_consecutive_14_days = False
                consecutive_work_days_counter = 0
                current_date = date_from
                while current_date < date_to:
                    work_entries_vals_date = work_entries_vals_by_date.get(current_date)
                    if not work_entries_vals_date or any(vals['work_entry_type_id'] not in sick_work_entry_types for vals in work_entries_vals_date):
                        consecutive_work_days_counter += 1
                    else:
                        consecutive_work_days_counter = 0
                        leave_ids = self.env['hr.leave']
                        for vals in work_entries_vals_date:
                            if vals['leave_ids']:
                                leave_ids |= vals['leave_ids']
                        if leave_ids:
                            current_date = max(leave_ids.mapped('date_to')).date() + relativedelta(days=1)
                            continue

                    # If worked 14 calendar consecutive days, counter is set to 60 days for the year
                    if consecutive_work_days_counter >= 14:
                        has_worked_consecutive_14_days = True
                        break
                    current_date += relativedelta(days=1)

                if not has_worked_consecutive_14_days:
                    last_year_sick_calendar_days = 0
                    last_year_covered_time_offs = self.env['hr.leave']
                    last_year_sick_work_entries_vals_by_date = defaultdict(list)
                    for vals in last_year_sick_work_entries_vals:
                        last_year_sick_work_entries_vals_by_date[vals['date']].append(vals)

                    for sick_wes_vals in last_year_sick_work_entries_vals_by_date.values():
                        for sick_we_vals in sick_wes_vals:
                            if 'leave_ids' in sick_we_vals:
                                if sick_we_vals['leave_ids'] not in last_year_covered_time_offs:
                                    leaves = sick_we_vals['leave_ids']
                                    last_year_sick_calendar_days += leaves._get_calendar_days(
                                        date_from - relativedelta(years=1),
                                        date_to - relativedelta(years=1)
                                    )
                                    last_year_covered_time_offs |= leaves
                            else:
                                last_year_sick_calendar_days += round_half_days(sick_we_vals['duration'] / company_avg_hours_per_day)

                    pfa_calendar_sick_days_remaining = max(0, pfa_calendar_sick_days_remaining - last_year_sick_calendar_days)

        version_by_date = self._l10n_be_get_version_by_date(date_from, date_to, versions)
        for year, versions_by_month in version_by_date.items():
            for month, version_by_day in versions_by_month.items():

                is_month_dropped = False
                for day, version in version_by_day.items():
                    if not version:
                        is_month_dropped = True
                        break
                    is_calendar_day = version.resource_calendar_id._works_on_date(day)
                    work_entries_vals_date = work_entries_vals_by_date.get(day)
                    if is_calendar_day and (not work_entries_vals_date or all(vals['work_entry_type_id'] in unpaid_work_entry_types for vals in work_entries_vals_date)):
                        is_month_dropped = True
                        break

                if is_month_dropped:
                    continue

                days_in_month = monthrange(year, month)[1]
                monthly_calendar_sick_time_off_days = 0
                monthly_covered_time_offs = self.env['hr.leave']
                days_by_version_counter = Counter(version_by_day.values())
                for version, n_days in days_by_version_counter.items():
                    month_sick_work_entries_vals = [
                        vals for vals in sick_work_entries_vals if vals['date'].month == month and vals['version_id'] == version
                    ]
                    calendar_sick_time_off_days = 0
                    month_sick_work_entries_vals_by_date = defaultdict(list)
                    for vals in month_sick_work_entries_vals:
                        month_sick_work_entries_vals_by_date[vals['date']].append(vals)
                    for sick_wes_vals in month_sick_work_entries_vals_by_date.values():
                        for sick_we_vals in sick_wes_vals:
                            if 'leave_ids' in sick_we_vals:
                                if sick_we_vals['leave_ids'] not in covered_time_offs:
                                    leaves = sick_we_vals['leave_ids']
                                    calendar_sick_time_off_days += leaves._get_calendar_days(
                                        date_from, date_to
                                    )
                                    covered_time_offs |= leaves
                            else:
                                calendar_sick_time_off_days += round_half_days(sick_we_vals['duration'] / company_avg_hours_per_day)

                            # Used to know how many days worked in month
                            if 'leave_ids' in sick_we_vals:
                                if sick_we_vals['leave_ids'] not in monthly_covered_time_offs:
                                    leaves = sick_we_vals['leave_ids']
                                    monthly_calendar_sick_time_off_days += leaves._get_calendar_days(
                                        date(year, month, 1), date(year, month, days_in_month)
                                    )
                                    monthly_covered_time_offs |= leaves
                            else:
                                monthly_calendar_sick_time_off_days += round_half_days(sick_we_vals['duration'] / company_avg_hours_per_day)

                    month_unpredictable_work_entries_vals = [vals for vals in unpredictable_work_entries_vals if vals['date'].month == month]
                    unpredictable_days = len(list({vals['date'] for vals in month_unpredictable_work_entries_vals}))

                    max_sick_days_to_remove = min(monthly_calendar_sick_time_off_days, calendar_sick_time_off_days)
                    sick_days_to_remove = min(n_days, pfa_sick_calendar_days_to_defer + max_sick_days_to_remove)
                    if calendar_sick_time_off_days > sick_days_to_remove:
                        pfa_sick_calendar_days_to_defer += calendar_sick_time_off_days - sick_days_to_remove
                    else:
                        pfa_sick_calendar_days_to_defer -= max(0, sick_days_to_remove - max_sick_days_to_remove)

                    # Remove sick days
                    non_assimilated_days = max(0, sick_days_to_remove - pfa_calendar_sick_days_remaining)
                    pfa_calendar_sick_days_remaining = max(0, pfa_calendar_sick_days_remaining - sick_days_to_remove)

                    # Remove unpredictable days
                    non_assimilated_days += max(0, unpredictable_days - pfa_unpredictable_days_remaining)
                    pfa_unpredictable_days_remaining = max(0, pfa_unpredictable_days_remaining - unpredictable_days)

                    n_days -= non_assimilated_days

                    work_time_rate = version.work_time_rate
                    # Compute the real work time rate if partial incapacity. Partial incapacity should count in the work time rate in the PFA
                    if version.l10n_be_time_credit:
                        work_time_rate = version.resource_calendar_id._l10n_be_get_work_time_rate_med_included(date_from, date_to, version._get_reference_calendar())

                    payslip_amount += ((n_days / days_in_month) / 12) * (fte_basic * work_time_rate)
                    n_months += (n_days / days_in_month)

        first_version_date = self.employee_id._get_first_contract_date()
        if first_version_date.year == self.date_from.year and first_version_date.month >= 7:
            return 0, 0
        return payslip_amount, n_months

    def _l10n_be_get_sick_leave_twelve_months_cutoff_date(self, employee, reference_date):
        return employee._l10n_be_get_sick_leave_twelve_months_cutoff_date(reference_date)

    def _compute_double_holiday_assimilated_months(self, date_from, date_to, versions, base_version=False, work_entries=None):
        self.ensure_one()

        work_entries_vals_by_date = self._l10n_be_get_work_entry_vals_by_date(date_from, date_to, work_entries=work_entries)

        non_assimilated_work_entry_type_codes = self.env['hr.work.entry.type'].search([('category_ids.code', '=', 'UNASSIMILATED')]).mapped('code')
        already_processed_leaves = self.env['hr.leave']
        deductions_by_month = defaultdict(float)  # {month: calendar days to deduct}

        version_by_date = self._l10n_be_get_version_by_date(date_from, date_to, versions)
        number_of_months = 0
        current_work_time_rate = (base_version or self.version_id).work_time_rate
        twelve_months_sick_cutoff = self._l10n_be_get_sick_leave_twelve_months_cutoff_date(self.employee_id, date_to)

        for year, versions_by_month in version_by_date.items():
            for month, version_by_day in versions_by_month.items():
                days_by_version_counter = Counter(version_by_day.values())
                days_in_month = monthrange(year, month)[1]

                # ------ Step 1 ------
                # On first encounter of each leave, fill the deductions_by_month for every month it contributes
                # non-assimilated days to. Future months are therefore already populated when reached.
                for day in version_by_day:
                    for work_entry in work_entries_vals_by_date.get(day, []):
                        leaves = work_entry.get('leave_ids', self.env['hr.leave'])
                        for leave in leaves:
                            if leave in already_processed_leaves:
                                continue
                            work_entry_type = work_entry.get('work_entry_type_id') or self.env['hr.work.entry.type']
                            already_processed_leaves |= leave

                            # Non-assimilated: every calendar day of this leave counts.
                            if work_entry_type.code in non_assimilated_work_entry_type_codes:
                                leave_from = max(leave.request_date_from, date_from)
                                leave_end = min(leave.request_date_to, date_to)
                                for dt in rrule.rrule(rrule.MONTHLY, dtstart=leave_from.replace(day=1), until=leave_end):
                                    month_start = dt.date()
                                    deductions_by_month[month_start.month] += leave._get_calendar_days(
                                        month_start, min(leave_end, month_start + relativedelta(day=31))
                                    )

                # ------ Step 2 ------
                # Apply this month's deduction across versions
                month_deduction = deductions_by_month.get(month, 0)
                for version, n_days in days_by_version_counter.items():
                    if version is None:
                        continue
                    actual_deduction = min(n_days, month_deduction)
                    n_days -= actual_deduction
                    # Note: Should consider the real days to reflect on correct version
                    # instead of a arbitrary count for the month
                    month_deduction = max(month_deduction - actual_deduction, 0)

                    work_time_rate = min(1, version.work_time_rate / current_work_time_rate) if current_work_time_rate else 0
                    # Compute the real work time rate if partial incapacity. Partial incapacity should count in the work time rate in the PFA
                    if version.l10n_be_time_credit and twelve_months_sick_cutoff >= date(year, month, 1):
                        assimilated_days = min(n_days, (twelve_months_sick_cutoff - max(version.date_start, date(year, month, 1))).days + 1)
                        non_assimilated_days = n_days - assimilated_days
                        non_assimilated_work_time_rate = work_time_rate * non_assimilated_days / n_days
                        work_time_rate_with_sickness = min(1, version.resource_calendar_id._l10n_be_get_work_time_rate_med_included(date_from, date_to, version._get_reference_calendar()) / current_work_time_rate) if current_work_time_rate else 0
                        assimilated_work_time_rate = work_time_rate_with_sickness * assimilated_days / n_days
                        work_time_rate = non_assimilated_work_time_rate + assimilated_work_time_rate

                    number_of_months += ((n_days / days_in_month) * work_time_rate)
        return number_of_months

    def _get_paid_amount_13th_month(self):
        versions = self.employee_id.version_ids.filtered(lambda v:
            v.contract_date_start and v.structure_type_id == self.struct_id.type_id
        )
        first_version_date = min(self.employee_id._get_first_versions().mapped('date_start') or [False])
        if not versions or not first_version_date:
            return 0.0

        if first_version_date.year == self.date_from.year and first_version_date.month > 6:
            return 0.0

        date_from = max(first_version_date + relativedelta(day=1), self.date_from + relativedelta(day=1, month=1))
        date_to = self.date_to + relativedelta(day=31)

        force_months = self._get_input_line_amount('MONTH')
        if force_months:
            n_months = force_months
            if n_months < 6:
                return 0.0
            fixed_salary = self.version_id._get_contract_wage() * n_months / 12
        else:
            fixed_salary, n_months = self._compute_13th_month_presence_prorated_fixed_wage(date_from, date_to, versions)

        force_avg_variable_revenues = self._get_input_line_amount('VARIABLE')
        if force_avg_variable_revenues:
            avg_variable_revenues = force_avg_variable_revenues
        else:
            avg_variable_revenues = self.with_context(
                variable_revenue_date_from=self.date_from
            )._get_last_year_average_variable_revenues()

        # Fixed salary is already prorated according to n_months, no need to do it again
        paid_amount = fixed_salary + (avg_variable_revenues * n_months / 12)

        # For sales representatives (CP200), there is a limit for the PFA
        if self.version_id.l10n_be_egov3_code == '200' and self.version_id.l10n_be_is_sale_representative:
            category_d_min_salary = self.version_id._get_employee_min_wage(reference_date=self.date_to, salary_scale='D')
            paid_amount = min(paid_amount, max(self.version_id._get_contract_wage(), category_d_min_salary))

        return paid_amount

    def _l10n_be_get_category_dict(self):
        """
        Returns the dict that groups work entry type codes per category:
        {category_name<str>, {code1, code2, code3}<set[str]>
        """
        self.ensure_one()
        return self._rule_parameter('l10n_be_work_entry_categories')

    def _l10n_be_get_we_category(self, work_entry) -> str | None:
        """
        Returns what category (defined in the cp302 docs) a work entry is in
        based on its work entry type code
        """
        self.ensure_one()
        we_categories = self._l10n_be_get_category_dict()
        for category, codes in we_categories.items():
            if work_entry['work_entry_type_id'].code in codes:
                return category
        return None

    def _l10n_be_get_uninterrupted_leave_of_category(self, category: str, reference_datetime) -> dict | None:
        """
        Returns the range of datetime of uninterrupted leave of `category` around
        `reference_time`, or None if none is found.
        An uninterrupted can be a series of leaves that are not interrupted by
        another leave of another category, or by a work time.

        The given category's work entry type codes should be only leave with
        `count_as` set to `absence`
        """
        self.ensure_one()

        date_from = None
        date_to = None

        all_leaves = self.env['hr.leave'].search([
            ('work_entry_type_id.code', 'in', self._l10n_be_get_category_dict()[category]),
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ('validate', 'validate1')),
            ('company_id', 'in', self.env.companies.ids),
            ('work_entry_type_id.count_as', '=', 'absence'),
            ('date_from', '!=', False),
            ('date_to', '!=', False),
        ])
        leaves_before = all_leaves.filtered_domain([('date_from', '<=', reference_datetime)])
        leaves_after = all_leaves.filtered_domain([('date_to', '>=', reference_datetime)])

        # set date_from to start date of earliest consecutive leave
        for leave_before in leaves_before.sorted('date_from', reverse=True):
            work_hours_between_leaves = self.version_id.resource_calendar_id.get_work_hours_count(
                leave_before.date_to,
                date_from or reference_datetime,
                compute_leaves=False,
            )
            if work_hours_between_leaves:
                break  # not consecutive
            date_from = leave_before.date_from

        # set date_to to end date of latest consecutive leave
        for leave_after in leaves_after.sorted('date_from'):
            work_hours_between_leaves = self.version_id.resource_calendar_id.get_work_hours_count(
                date_to or reference_datetime,
                leave_after.date_from,
                compute_leaves=False,
            )
            if work_hours_between_leaves:
                break  # not consecutive
            date_to = leave_after.date_to

        if not date_from or not date_to:
            # reference_datetime is not in a leave of given category
            return None

        return {'start': date_from, 'stop': date_to}

    def _l10n_be_get_uninterrupted_leaves_of_category_in_range(self, category: str, date_start, date_stop) -> list[dict]:
        """
        Return a sorted list of all uninterrupted ranges of leaves that cover
        the given period. The return value is not capped.
        The returned uninterrupted leaves are leave of work entry type of `category`.
        """
        self.ensure_one()

        # convert date_start and date_stop to timezone-naive datetimes
        date_start = date_start.astimezone(UTC).replace(tzinfo=None)
        date_stop = date_stop.astimezone(UTC).replace(tzinfo=None)

        # ranges are of format {'start': date, 'stop': date}
        ranges = []

        category_codes = self._l10n_be_get_category_dict()[category]
        in_category_domain = Domain('work_entry_type_id.code', 'in', category_codes)

        # first leave in the given range
        leave = self.env['hr.leave'].search(
            in_category_domain
            & Domain('employee_id', '=', self.employee_id.id)
            & Domain('date_from', '<=', date_stop)
            & Domain('date_to', '>=', date_start),
            order="date_from asc",
            limit=1,
        )

        while leave:
            ranges.append(
                self._l10n_be_get_uninterrupted_leave_of_category(category, leave.date_from),
            )
            if not ranges[-1]['stop'] or ranges[-1]['stop'] >= date_stop:
                break  # we reached end of range. No need to continue
            # get the leave just after the uninterrupted range
            leave = self.env['hr.leave'].search(Domain([
                    in_category_domain,
                    ('employee_id', '=', self.employee_id.id),
                    ('company_id', 'in', self.env.companies.ids),
                    ('state', 'in', ('validate', 'validate1')),
                    ('date_from', '<=', date_stop),
                    ('date_to', '>', ranges[-1]['stop']),
                ]),
                order="date_from asc",
                limit=1,
            )

        return ranges

    def _cp302_get_assimilable_sick_leaves(self, work_entries_of_year, last_work_day: date) -> list[dict]:
        """
        Only one sick period can be assimilated (at a rate of 50%) per year,
        following these conditions:
        - Should be uninterrupted of at least 6 months (even accross years)
        - Only assimilate the days of the current year
        - If the sick period is > than a year, then this whole period can be
        assimilated only once.
        - No more than 6 months per year can be assimilated

        (The above values are from 2026. They're store as rule parameters
        as they're subject to change)

        This function will return the assimilable time of these sick periods

        :param work_entries_of_year: a sorted list of all the work entries from
            the beginning of the year up to the last day of work of the year
        :param last_work_day: the last day worked in the year
        """
        self.ensure_one()

        employee_tz = ZoneInfo(self.employee_id._get_tz())

        # get uninterrupted sick leave ranges in current year
        year = last_work_day.year
        beginning_of_year = datetime(year, 1, 1, tzinfo=employee_tz)
        sick_leave_ranges = self._l10n_be_get_uninterrupted_leaves_of_category_in_range(
            'sick_leave',
            beginning_of_year,
            datetime.combine(last_work_day, time.max, tzinfo=employee_tz),
        )

        if not sick_leave_ranges:
            return []  # no sick leave in current year

        # uninterrupted sick leaves longer than `multi_assimilation_threshold`
        # cannot be assimilated more than once. So we need to know what sick
        # leaves have been assimilated for previous years each time there is a
        # sick leave accross two years
        while sick_leave_ranges[0]['start'].astimezone(employee_tz) < beginning_of_year:
            year -= 1
            beginning_of_year = datetime(year, 1, 1, tzinfo=employee_tz)
            end_of_year = datetime.combine(date(year, 12, 31), time.max, tzinfo=employee_tz)
            uninterrupted_leaves = self._l10n_be_get_uninterrupted_leaves_of_category_in_range(
                'sick_leave', beginning_of_year, end_of_year,
            )
            if uninterrupted_leaves[-1] == sick_leave_ranges[0]:
                # last leave of year is the first leave of the year after.
                uninterrupted_leaves.pop()
            sick_leave_ranges = uninterrupted_leaves + sick_leave_ranges

        # the rest of the function only cares about the date (no need for hours)
        sick_leave_ranges = [
            {'start': range['start'].date(), 'stop': range['stop'].date()}
            for range in sick_leave_ranges
        ]

        # group each range per year they cover
        ranges_per_year = defaultdict(list)
        for date_range in sick_leave_ranges:
            years = range(date_range['start'].year, date_range['stop'].year + 1)
            for year in years:
                ranges_per_year[year].append(date_range)

        def is_assimilable_once(range):
            if not range['stop']:
                return True
            # consecutive sick leaves > this rule param cannot be assimilated twice
            multi_assimilation_threshold = self._rule_parameter('cp302_13th_month_sick_leaves_multi_assimilation_threshold')
            return range['stop'] >= range['start'] + relativedelta(**multi_assimilation_threshold)

        def is_long_enough_to_be_assimilated(range):
            if not range['stop']:
                return True
            # consecutive sick leaves < this rule param cannot be assimilated
            min_uninterrupted_period = self._rule_parameter('cp302_13th_month_sick_leaves_min_uninterrupted_period')
            return range['stop'] >= range['start'] + relativedelta(**min_uninterrupted_period) - relativedelta(days=-1)

        # ranges longer than multi_assimilation_threshold cannot be assimilated
        # more than once, so let's keep track of them when they're assimilated
        ranges_assimilable_once = set()

        # Will contain the actual ranges where sick leaves can be assimilated
        assimilated_ranges = []

        for year in sorted(ranges_per_year.keys()):
            # removing ranges that cannot be assimilated again
            year_ranges = [
                range for range in ranges_per_year[year]
                if frozendict(range) not in ranges_assimilable_once
            ]
            # only ranges >= `min_uninterrupted_period` up to end of year are assimilable
            year_ranges = [
                range for range in year_ranges
                if is_long_enough_to_be_assimilated({
                    'start': range['start'],
                    'stop': min(range['stop'] or date.max, date(year, 12, 31)),
                })
            ]
            if not year_ranges:
                continue  # no range >= 6 months in this year

            # workaround for relativedelta's lack of relational operators
            def is_relativedelta_lte_zero(relative_delta):
                reference = date(2000, 1, 1)
                return reference + relative_delta <= reference

            # all the remaining ranges can be assimilated, but no more than this
            # duration can be assimilated per year
            max_year_assimilable_time = self._rule_parameter('cp302_13th_month_sick_leaves_max_year_assimilable_time')
            remaining_assimilable_time = relativedelta(**max_year_assimilable_time)
            for assimilable_range in sorted(year_ranges, key=lambda r: r['start']):
                if is_relativedelta_lte_zero(remaining_assimilable_time):
                    break  # all time already assimilated for this year
                if is_assimilable_once(assimilable_range):
                    ranges_assimilable_once.add(frozendict(assimilable_range))
                assimilation_start = max(assimilable_range['start'], date(year, 1, 1))
                assimilation_end = min(
                    assimilable_range['stop'] or date.max,
                    assimilation_start + remaining_assimilable_time - relativedelta(days=1),
                    date(year, 12, 31),
                )
                assimilated_ranges.append({'start': assimilation_start, 'stop': assimilation_end})
                # remove the assimilated time from the yearly quota
                remaining_assimilable_time -= relativedelta(assimilation_end + relativedelta(days=1), assimilation_start)

        # work entries in the ranges are the assimilable long sick leaves
        def is_in_assimilated_ranges(date):
            for assimilated_range in assimilated_ranges:
                if assimilated_range['start'] <= date <= assimilated_range['stop']:
                    return True
            return False

        # all the sick leaves in the ranges are the ones we can assimilate
        sick_leave_codes = self._l10n_be_get_category_dict()['sick_leave']
        sick_leave_work_entries = (
            we for we in work_entries_of_year
            if we['work_entry_type_id'].code in sick_leave_codes and is_in_assimilated_ranges(we['date'])
        )

        return [{
            'date': we['date'],
            'hours': we['duration'],
            'rate': self._rule_parameter('cp302_13th_month_sick_leaves_assimilation_rate'),
        } for we in sick_leave_work_entries]

    def _cp302_get_always_assimilable_time(self, work_entries) -> list[dict]:
        """
        Some specific kinds of work entries are always assimilated to the
        employee's worked days.
        This function will return the assimilable time of these work entries
        """
        self.ensure_one()
        always_assimilable_categories = {
            'legal_leave',
            'extra_legal_leave',
            'public_holiday',
            'small_unemployment',
            'compensatory_rest',
            'civic_duty',
            'public_mandate',
            'union_obligation',
            'strike',
            'temporary_unemployment',
            'unemployment_force_majeure',
            'working_time',
        }
        category_dict = self._l10n_be_get_category_dict()
        always_assimilable_codes = {
            code
            for category in always_assimilable_categories
            for code in category_dict[category]
        }
        return [
            {
                'date': we['date'],
                'hours': we['duration'],
                'rate': 1,
            } for we in work_entries
            if we['work_entry_type_id'].code in always_assimilable_codes
        ]

    def _cp302_get_limited_calendar_assimilable_time(self, work_entries_of_year, last_work_day) -> list[dict]:
        """
        Some work entries are limited, not by fixed amount of days per year,
        but rather per calendar period per uninterrupted work entry range.

        e.g.: military service limited to 6 calendar months means that all
        periods of military service can be assimilated up to six months per
        uninterrupted period. Years and working days don't matter.

        This function will return the assimilable time of these work entries

        :param last_work_day: The last day worked by the employee in the year.
        :param work_entries_of_year: a sorted list of all the work entries from
            the beginning of the year up to the last day of work of the year
        """
        self.ensure_one()

        maternity_leave_limit = self._rule_parameter('cp302_13th_month_maternity_leave_calendar_limit')
        military_service_limit = self._rule_parameter('cp302_13th_month_military_service_calendar_limit')
        categories_calendar_limit = {
            'maternity_leave': relativedelta(**maternity_leave_limit),
            'military_service': relativedelta(**military_service_limit),
        }

        # ranges are of format {'start': date, 'stop': date}
        assimilated_ranges = []
        for category, limit in categories_calendar_limit.items():
            # get ranges of consecutive leaves current category in year (not capped to year)
            ranges = self._l10n_be_get_uninterrupted_leaves_of_category_in_range(
                category,
                datetime(last_work_day.year, 1, 1).astimezone(ZoneInfo(self.employee_id._get_tz())),
                datetime.combine(last_work_day, time.max, tzinfo=ZoneInfo(self.employee_id._get_tz())),
            )
            # cap the ranges's stop dates to the categories limit
            for range in ranges:
                max_stop = min(range['start'] + limit - relativedelta(days=1), datetime.combine(last_work_day, time.max))
                if not range['stop'] or range['stop'] > max_stop:
                    range['stop'] = max_stop
            assimilated_ranges += ranges

        def is_in_assimilated_ranges(work_entry):
            for range in assimilated_ranges:
                if range['start'].date() <= work_entry['date'] <= range['stop'].date():
                    return True
            return False

        return [{
            'date': we['date'],
            'hours': we['duration'],
            'rate': 1,
        } for we in work_entries_of_year if is_in_assimilated_ranges(we)]

    def _cp302_get_yearly_limited_assimilable_time(self, work_entries_of_year) -> list[dict]:
        """
        Some specific kind of work entries can only be assimilated with a yearly
        limit (e.g.: max 10 days of paternity leave).
        This function will return the assimilable time of these work entries

        :param work_entries_of_year: a sorted list of all the work entries from
            the beginning of the year up to the last day of work of the year
        """
        self.ensure_one()

        work_hours_per_day = self.version_id.resource_calendar_id.hours_per_day
        # limit per year per work entry category
        remaining_hours = {
            'union_education': work_hours_per_day * self._rule_parameter('cp302_13th_month_union_education_day_limit'),
            'compelling_reason': work_hours_per_day * self._rule_parameter('cp302_13th_month_compelling_reason_day_limit'),
            'paternity_leave': work_hours_per_day * self._rule_parameter('cp302_13th_month_paternity_leave_day_limit'),
            'military_reserve_call': work_hours_per_day * self._rule_parameter('cp302_13th_month_military_reserve_call_day_limit'),
        }

        assimilable_time = []
        for work_entry in work_entries_of_year:
            category = self._l10n_be_get_we_category(work_entry)
            if category not in remaining_hours:
                continue  # work entry is not relevant
            if remaining_hours[category] <= 0:
                continue  # all assimilable hours have been counted
            assimilable_time.append({
                'date': work_entry['date'],
                'hours': min(work_entry['duration'], remaining_hours[category]),
                'rate': 1,
            })
            remaining_hours[category] -= work_entry['duration']

        return assimilable_time

    def _cp302_get_assimilable_partial_incapacities(self, work_entries_of_year):
        """
        The first 12 months of partial incapacity (of at least 66%), following a
        total incapacity, can be assimilated.

        :param work_entries_of_year: a sorted list of all the work entries from
            the beginning of the year up to the last day of work of the year
        """
        # NOTE Odoo currently lacks a way to define partial incapacities
        # correctly. This cannot be reliably implemented as of now.
        return []

    def _cp302_get_prestated_and_assimilated_time(self, date_from, last_work_day):
        """
        For the computation of the thirteenth month for the Joint Committee 302,
        we need to know the number of days that can be counted as days of work.
        There are two categories:
        - Prestated days (days where real work has been done)
        - Assimilated days:
           - Always assimilated (legal leaves, strikes, etc.)
           - Assimilated up to a calendar limit per uninterrupted period
           - Assimilated up to N days/year
           - 12 first months of partial incapacity following total incapacity
           - Six consecutive months of sick leave (with some conditions)
           - Up to 7 days of uninterrupted sick leave (with some conditions)

        :param date_from: the first day where hours can be assimilated. Usually
            the beginning of the year
        :param last_work_day: The last day worked by the employee in the year.
        :return: a list of dict of this format:
            [{
                'date': day of prestated/assimilated time,
                'hours': number of hours prestated/assimilated by self.employee_id,
                'rate': rate of which the hours can be assimilated
            }]
        """
        self.ensure_one()
        work_entries = self.employee_id.generate_work_entries(date_from, last_work_day)
        work_entries.sort(key=lambda we: we['date'])
        return sorted([
            *self._cp302_get_always_assimilable_time(work_entries),
            *self._cp302_get_limited_calendar_assimilable_time(work_entries, last_work_day),
            *self._cp302_get_yearly_limited_assimilable_time(work_entries),
            *self._cp302_get_assimilable_partial_incapacities(work_entries),
            *self._cp302_get_assimilable_sick_leaves(work_entries, last_work_day),
        ], key=lambda pa: pa['date'])

    def _cp302_can_get_13th_month(self, worked_days_in_year: float, last_work_day: date) -> bool:
        """
        Returns whether the employee has the requirements to get a 13th month
        The conditions have been taken from Partena's sectorial documentation
        """
        self.ensure_one()

        # these are the values of hr.departure_reason.l10n_be_reason_code
        departures = {
            'resigned': 343,
            'fired': 342,
            'fired_serious_misconduct': 355,
            'resigned_serious_employer_misconduct': 356,
            'resigned_force_majeure': 352,
            'resigned_retired': 340,
            'resigned_anitcipated_retirement': 354,
            'fired_early_retirement': 353,  # prépension
        }

        # According to the joint committeee, a worker should at least have
        # worked two months in the year, if not, we can count accross previous
        # years for uninterrupted seniority. This the same as regular seniority
        seniority = last_work_day - min(self.employee_id._get_last_consecutive_versions(self.date_to).mapped('date_start')) + timedelta(days=1)
        required_seniority = self._rule_parameter('cp302_13th_month_required_seniority')
        if (
            seniority < timedelta(**required_seniority)
            # limit doesn't apply to temporary workers
            and self.version_id.l10n_be_dimona_category != 'ext'
        ):
            return False

        # NOTE for flexi-jobs, you can only have your thirteenth month if your
        # contract is > than a period, or if you have many successive contracts
        # (< 1 work day between them) for more than this period.
        # This is basically the same as how we compute regular seniority, so we
        # can compare the duration against the seniority
        flx_required_seniority = self._rule_parameter('cp302_13th_month_flx_required_seniority')
        if self.version_id.is_flexi() and seniority < timedelta(**flx_required_seniority):
            return False

        beginning_of_year = date(self.date_to.year, 1, 1)
        seniority_in_year = min(seniority, last_work_day - beginning_of_year + timedelta(days=1))
        departure_reason_code = self.employee_id.departure_reason_id.l10n_be_reason_code

        # an employee resigning due to force majeure can get his 13th month if
        # he worked at least two months during the year
        force_majeure_required_seniority = self._rule_parameter('cp302_13th_month_force_majeure_required_seniority')
        if (
            departure_reason_code == departures['resigned_force_majeure']
            and seniority_in_year < timedelta(**force_majeure_required_seniority)
        ):
            return False

        # fired employees still have their 13th month if they worked a certain period in the year,
        # or if their contract lasted more than a certain period (not their seniority)
        fired_min_y_seniority = self._rule_parameter('cp302_13th_month_fired_min_eligible_year_seniority')
        fired_min_contract_duration = self._rule_parameter('cp302_13th_month_fired_min_eligible_contract_duration')
        if (
            departure_reason_code == departures['fired']
            and not (
                seniority_in_year >= timedelta(**fired_min_y_seniority)
                or last_work_day >= self.employee_id.contract_date_start + relativedelta(**fired_min_contract_duration) - relativedelta(days=1)
            )
        ):
            return False
        # same thing if employee resigned due to a serious employer misconduct
        emp_mis_min_y_seniority = self._rule_parameter('cp302_13th_month_emp_mis_min_eligible_year_seniority')
        emp_mis_min_contract_duration = self._rule_parameter('cp302_13th_month_emp_mis_min_eligible_contract_duration')
        if (
            departure_reason_code == departures['resigned_serious_employer_misconduct']
            and not (
                seniority_in_year >= timedelta(**emp_mis_min_y_seniority)
                or last_work_day >= self.employee_id.contract_date_start + relativedelta(**emp_mis_min_contract_duration) - relativedelta(days=1)
            )
        ):
            return False

        # resigned employees can have their 13th months if they still work up to
        # the end of the year (including the notice period)
        if departure_reason_code == departures['resigned']:
            return last_work_day >= date(self.date_to.year, 12, 31)

        # fired employees for "faute grave" never get their 13th month
        if departure_reason_code == departures['fired_serious_misconduct']:
            return False

        # employees with determined contract duration (CDD) don't get their 13th
        # month if they end their contract sooner than expected
        if (
            self.employee_id.fixed_term
            and departure_reason_code is not False
            and self.employee_id.departure_date
            and self.employee_id.departure_date < self.employee_id.contract_date_end
        ):
            return False

        # temporary workers must have worked at least a certain amount of days
        # (prestated & assimilated) in the payment year to get their 13th month
        min_year_worked_days = self._rule_parameter('cp302_13th_month_temporary_workers_min_worked_days_in_year')
        if self.version_id.l10n_be_dimona_category == 'ext' and worked_days_in_year < min_year_worked_days:
            return False

        # students cannot have a 13th month
        if self.version_id.l10n_be_dimona_category == 'stu':
            return False

        # cases explicitly allowed in the documentation:
        if departure_reason_code in (
            departures['resigned_anitcipated_retirement'],
            departures['fired_early_retirement'],
            departures['resigned_retired'],
        ):
            return True

        return True

    def _cp302_get_assimilable_hours_after_contract(self) -> float:
        """
        Per the Joint Committee 302, if the worker stops working for some
        specific reasons, then some days after the end of the contract can still
        be assimilated

        :return: number of hours, after the contract end, in the year, that
                should be assimilated.
        """
        self.ensure_one()

        departure_reason_code = self.employee_id.departure_reason_id.l10n_be_reason_code

        # all the following cases depend on departure reasons
        if not departure_reason_code:
            return 0
        if not (self.date_from <= self.employee_id.departure_date <= self.date_to):
            # this payslip and the employee's departure are not at the same time.
            # this is probably a misconfiguration on the user's side.
            return 0

        # these are the values of hr.departure_reason.l10n_be_reason_code
        departures = {
            'dead': 357,
            'resigned_retired': 340,
            'resigned_anitcipated_retirement': 354,
            'fired_early_retirement': 353,
        }

        work_hours_to_eoy = self.version_id.resource_calendar_id.get_work_hours_count(
            self.employee_id.departure_date,
            date(self.date_to.year, 12, 31),
            compute_leaves=False,
        )

        # days after the end of the contract are still assimilated for retired personnel
        if departure_reason_code in (
            departures['resigned_anitcipated_retirement'],
            departures['resigned_retired'],
        ):
            return work_hours_to_eoy

        # days after the end of the contract are still assimilated (at a certain
        # rate) for early retired personnel (prépension)
        if departure_reason_code == departures['fired_early_retirement']:
            assimilation_rate = self._rule_parameter('cp302_13th_month_early_retirement_assimilation_rate')
            return work_hours_to_eoy * assimilation_rate

        # a time period after the death of the personnel can still be assimilated
        if departure_reason_code == departures['dead']:
            assimilable_death_time = self._rule_parameter('cp302_13th_month_assimilable_death_time')
            work_hours_in_six_mo = self.version_id.resource_calendar_id.get_work_hours_count(
                self.employee_id.departure_date,
                self.employee_id.departure_date + relativedelta(**assimilable_death_time) - relativedelta(days=1),
                compute_leaves=False,
            )
            return min(work_hours_to_eoy, work_hours_in_six_mo)

        return 0

    def _cp302_get_paid_amount_13th_month(self, localdict):
        """
        Computes and returns the value of the 13th month the worker should receive
        from the Horeca Social Fund, following the rules defined for the Joint Committee 302.
        """
        self.ensure_one()

        last_work_day = min(
            self.employee_id.l10n_be_get_last_work_day_of_year(self.date_to.year) or date.max,
            self.date_to,
        )
        prestated_and_assimilated_time = self._cp302_get_prestated_and_assimilated_time(
            date(self.date_to.year, 1, 1), last_work_day,
        )

        # we need to know how many days were worked in the year, no matter the
        # duration of the prestations for some conditions for the 13th month
        worked_days_in_year = len({time['date'] for time in prestated_and_assimilated_time})
        if not self._cp302_can_get_13th_month(worked_days_in_year, last_work_day):
            return 0

        accounted_hours = sum(time['hours'] * time['rate'] for time in prestated_and_assimilated_time)

        # if the contract ends before the eoy, then, under some conditions,
        # hours between the end of contract and the eoy can be assimilated
        if last_work_day != date(self.date_to.year, 12, 31):
            accounted_hours += self._cp302_get_assimilable_hours_after_contract()

        # NOTE "personnel rémunéré au pourcentage de service"'s max 13th month would
        # be the (monthly) ONSS contribution, but this worker type is not supported by Odoo
        if self.wage_type == 'hourly':
            # personnel paid per hour (usually workers) should have a base 13th
            # month equal to 4.333 weeks of pay
            weeks_per_month = 4 + 1 / 3
            hours_per_month = self.version_id.resource_calendar_id.hours_per_week * weeks_per_month
            full_13th_month = hours_per_month * self.version_id._get_contract_wage()
        else:
            # personnel paid per month (usually employees) should have a base
            # 13th month equal to their last monthly pay
            full_13th_month = self.version_id._get_contract_wage()

        max_workable_hours_in_year = self.version_id.resource_calendar_id.get_work_hours_count(
            date(self.date_to.year, 1, 1),
            date(self.date_to.year, 12, 31),
            compute_leaves=False,
        )

        # proratise the result and get the 13th month for the whole year up to self.date_to
        worked_hours_ratio = (accounted_hours / max_workable_hours_in_year) if max_workable_hours_in_year else 0
        thirteen_month = min(full_13th_month, full_13th_month * worked_hours_ratio)

        # we need to deduct what has already been paid during the year if needed
        previous_payslips_of_year = localdict['l10n_be_year_payslips_by_payslip'][self].filtered_domain(
            [('date_to', '<', self.date_to)],
        )
        already_paid_13th_month = sum(previous_payslips_of_year.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).mapped('total'))
        return thirteen_month - already_paid_13th_month

    def _l10n_be_get_paid_double_holiday(self, base_month=False, work_entries=None, get_explanation=False):
        self.ensure_one()
        versions = self.employee_id.version_ids.filtered(lambda v:
            v.contract_date_start and v.structure_type_id == self.struct_id.type_id
        )
        if not versions:
            return (0.0, {}) if get_explanation else 0.0

        if not base_month or base_month > self.date_from:
            base_version = self.version_id
        else:
            base_version = self.employee_id._get_version(base_month)

        basic = base_version._get_contract_wage()
        force_months = self._get_input_line_amount('MONTH')

        year = self.date_from.year - 1
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)
        pre_attestation = 0

        if force_months:
            number_of_months = force_months
            fixed_salary = basic * number_of_months / 12
        else:
            number_of_months = self._compute_double_holiday_assimilated_months(date_from, date_to, versions, base_version, work_entries)
            fixed_salary = (number_of_months / 12) * basic
            attests = self.employee_id.l10n_be_holiday_attest_ids.filtered(lambda a: a.year == year and a.prev_double_holiday_pay_paid > 0)
            for attest in attests:
                attestation = basic * (attest._get_number_of_months() / 12) * attest.prev_work_time_rate
                fixed_salary += attestation
                pre_attestation += attestation

        explanation_info = {k: float_round(v, precision_digits=2) for k, v in [('basic', basic), ('months', number_of_months), ('pre_attestation', pre_attestation)]}
        return (fixed_salary, explanation_info) if get_explanation else fixed_salary

    def _get_paid_amount_cct90_bonus_plan(self):
        self.ensure_one()
        return self._get_input_line_amount('CCT90BONUSPLAN')

    def _is_active_belgian_languages(self):
        active_langs = self.env['res.lang'].with_context(active_test=True).search([]).mapped('code')
        return any(lang in ['fr_BE', 'fr_FR', 'nl_BE', 'nl_NL', 'de_DE'] for lang in active_langs)

    def _get_postponed_time_off_to_pay(self):
        self.ensure_one()
        return self.env['hr.leave.allocation']._read_group([
            ('employee_id', '=', self.employee_id.id),
            ('state', '!=', 'refuse'),
            ('work_entry_type_id.code', '=', '142.24'),
            ('date_from', '>=', self.date_from + relativedelta(years=1, month=1, day=1)),
            ('date_from', '<=', self.date_from + relativedelta(years=1, month=12, day=31)),
        ],
            aggregates=['number_of_days:sum']
        )[0][0]

    def _get_sum_european_time_off_days(self, check=False):
        self.ensure_one()
        two_years_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_to', '<=', date(self.date_from.year, 12, 31)),
            ('date_from', '>=', date(self.date_from.year - 2, 1, 1)),
            ('state', 'in', ['validated', 'paid']),
        ])
        european_time_off_amount = two_years_payslips.filtered(lambda p: p.date_from.year < self.date_from.year)._get_worked_days_line_values(['142.20'], ['amount'], True)['142.20']['sum']['amount']
        already_recovered_amount = two_years_payslips._get_line_values(['EU_LEAVE_DEDUC'], compute_sum=True)['EU_LEAVE_DEDUC']['sum']['total']
        return european_time_off_amount + already_recovered_amount

    def _is_invalid(self):
        invalid = super()._is_invalid()
        if not invalid and self.country_code == 'BE' and self._is_active_belgian_languages():
            is_translated = self.env.context.get('is_translated')
            if (is_translated):
                return self.env._('This document is a translation. This is not a legal document.')
        return invalid

    def _get_negative_net_rule(self):
        self.ensure_one()
        if self.struct_id.code == 'BEMONTHLY':
            return self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_negative_net')
        return super()._get_negative_net_rule()

    def _issues_dependencies(self):
        return super()._issues_dependencies() + ['payroll_config_id.l10n_be_employer_category_id']

    def action_confirm_arrear_payslip_done(self):
        return self.with_context(l10n_be_arrear_validation_confirmed=True).action_payslip_done()

    def action_payslip_done(self):
        if self._is_active_belgian_languages():
            belgian_payslips = self.filtered(lambda p: p.struct_id.country_id.code == "BE")
            if belgian_payslips:
                pdf_langs = belgian_payslips._get_payslips_pdf_lang()
                valid_langs = ["fr_BE", "fr_FR", "nl_BE", "nl_NL", "de_DE"]
                bad_language_slips = belgian_payslips.filtered(
                    lambda slip: pdf_langs.get(slip, (None, None))[0] not in valid_langs
                )
                if bad_language_slips:
                    payslip_lang = bad_language_slips.company_id.dmfa_location_unit_ids.payslip_language_id.code
                    if payslip_lang:
                        bad_language_slips.employee_id.write({'lang': payslip_lang})
                    else:
                        action = self.env['ir.actions.act_window'].\
                        _for_xml_id('l10n_be_hr_payroll.l10n_be_hr_payroll_employee_lang_wizard_action')
                        ctx = dict(self.env.context)
                        ctx.update({
                            'employee_ids': bad_language_slips.employee_id.ids,
                            'default_slip_ids': self.ids,
                        })
                        action['context'] = ctx
                        return action

        arrear_slips = self.filtered('l10n_be_arrear_salary')
        res = super().action_payslip_done()
        belgian_slips = self.filtered(lambda p: p.country_code == 'BE')
        belgian_slips._l10n_be_defer_fiscal_date()
        belgian_slips._l10n_be_apply_correction_fiscal_period()
        belgian_slips._l10n_be_flag_274_corrections()
        for slip in arrear_slips:
            quarter = (slip.date_from.month - 1) // 3 + 1
            slip.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=self.env._('Generate DmfA correction'),
                note=self.env._(
                    'This arrears payslip targets %(year)s Q%(quarter)s. '
                    'Please manually generate a DmfA correction for that quarter.',
                    year=slip.date_from.year, quarter=quarter),
            )

        zero_net_payslips = self.filtered(lambda slip: slip.country_code == 'BE' and slip.net_wage <= 0)
        if zero_net_payslips:
            zero_net_payslips.action_payslip_paid()

        existing_dmfa_reports = self.env['l10n_be.dmfa'].sudo().search([
            ('state', 'in', ['done', 'paid']),
            ('declaration_type', '=', 'original'),
        ])

        report_date_boundaries = []
        for report in existing_dmfa_reports:
            report_date_boundaries.append((report, report.quarter_start, report.quarter_end))

        for ps in self:
            for report, start_date, end_date in report_date_boundaries:
                if ps.date_from <= end_date and ps.date_to >= start_date:
                    ps.l10n_be_is_dmfa_reported = False
                    report.is_correction_needed = True

        self._l10n_be_generate_termination_documents()
        return res

    def _l10n_be_flag_274_corrections(self):
        """A filed 274.XX whose period these payslips belong to no longer matches payroll."""
        payslips = self.filtered(lambda p: p.date_from and p.date_to)
        if not payslips:
            return
        filed_reports = self.env['l10n_be.274_xx'].sudo().search([
            ('state', 'in', ['ready', 'done']),
            ('declaration_type', '=', 'original'),
            ('company_id', 'in', payslips.company_id.root_id.ids),
            ('date_start', '<=', max(payslips.mapped('date_to'))),
            ('date_end', '>=', min(payslips.mapped('date_from'))),
        ])
        for report in filed_reports:
            declared = payslips.filtered(
                lambda p: (p.l10n_be_fiscal_date and report.date_start <= p.l10n_be_fiscal_date <= report.date_end)
                or (report.date_start <= p.date_from and p.date_to <= report.date_end))
            if declared and declared.company_id.root_id == report.company_id:
                report.is_correction_needed = True

    def action_payslip_unpaid(self):
        res = super().action_payslip_unpaid()
        self.filtered(lambda p: p.country_code == 'BE')._l10n_be_flag_274_corrections()
        return res

    def action_payslip_cancel(self):
        res = super().action_payslip_cancel()
        self.filtered(lambda p: p.country_code == 'BE')._l10n_be_flag_274_corrections()
        latest_273_xx_report = self.l10n_be_273_line_ids.sheet_id.filtered(
            lambda r: r.state in ['ready', 'done']
        ).sorted('id', reverse=True)[:1]
        if latest_273_xx_report:
            latest_273_xx_report.is_correction_needed = True

        latest_281_xx_report = self.l10n_be_281_xx_ids.filtered(
            lambda r: r.state in ['ready', 'done']
        ).sorted('id', reverse=True)[:1]
        if latest_281_xx_report:
            latest_281_xx_report.is_correction_needed = True
        return res

    def _get_payslips_pdf_lang(self):
        belgian_payslips = self.filtered(lambda p: p.company_id.country_code == 'BE')
        non_belgian_payslips = self - belgian_payslips
        lang_map = {}
        # Non-BE payslips fallback
        if non_belgian_payslips:
            lang_map.update(super(HrPayslip, non_belgian_payslips)._get_payslips_pdf_lang())
        if not belgian_payslips:
            return lang_map

        # Prefetch needed fields
        employees = belgian_payslips.employee_id
        addresses = employees.address_id

        # Fetch related DMFA units
        dmfa_units = self.env['hr.work.location'].search([
            ('address_id', 'in', addresses.ids),
            ('location_type', '=', 'dmfa_unit'),
        ])
        dmfa_unit_by_partner = {unit.address_id.id: unit for unit in dmfa_units}

        # Build language preferences for each DMFA unit
        lang_pref_map = {
            unit.id: unit.payslip_language_id.code
            for unit in dmfa_units
        }

        # Compute lang pair per Belgian payslip
        for payslip in belgian_payslips:
            address = payslip.employee_id.address_id
            dmfa_unit = dmfa_unit_by_partner.get(address.id)
            dmfa_lang = lang_pref_map.get(dmfa_unit.id, []) if dmfa_unit else []

            res = super()._get_payslips_pdf_lang()  # (user_lang, None)
            if res[payslip][0] == dmfa_lang:
                lang_map[payslip] = res[payslip]
            elif dmfa_lang:
                lang_map[payslip] = (dmfa_lang, res[payslip][0])
            else:
                lang_map[payslip] = res[payslip]

        return lang_map

    def _prepare_payslip_pdf_content(self, report, languages):
        self.ensure_one()
        if self.company_id.country_code != 'BE':
            return super()._prepare_payslip_pdf_content(report, languages)
        main_lang, second_lang = languages

        pdf_parts = []

        # Main official payslip
        pdf_parts.append(self._generate_payslip_pdf(main_lang, report))

        # Optional second translated payslip
        if second_lang and main_lang != second_lang:
            pdf_parts.append(self._generate_payslip_pdf(second_lang, report, True))

        return pdf.merge_pdf(pdf_parts)

    def _generate_payslip_pdf(self, lang, report, is_translated=False):
        pdf_content, _ = self.env['ir.actions.report'].sudo().with_context(
            lang=lang,
            is_translated=is_translated
        )._render_qweb_pdf(report, self.id)
        return pdf_content

    def _get_pdf_reports(self):
        res = super()._get_pdf_reports()
        report_n = self.env.ref('l10n_be_hr_payroll.action_report_termination_holidays_n')
        report_n1 = self.env.ref('l10n_be_hr_payroll.action_report_termination_holidays_n1')
        for payslip in self:
            if payslip.struct_id.code == 'BEHOLN1':
                res[report_n1] |= payslip
            elif payslip.struct_id.code == 'BEHOLN':
                res[report_n] |= payslip
        return res

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_be_hr_payroll', [
                'data/hr_rule_parameters_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]

    def _get_versions_with_company_car_within_payslip_period(self):
        self.ensure_one()

        versions = self.env['hr.version'].browse(self._get_period_contracts()).filtered(lambda c: c.transport_mode_car)
        return versions

    def _get_be_contract_days_in_payslip_range_prorata(self, date_start, date_end):
        """
        Return the ratio of the payslip month during which the given
        contract period overlaps with the payslip period.
        """
        self.ensure_one()
        if not date_start:
            return 0

        payslip_start = self.date_from
        payslip_end = self.date_to

        overlap_start = max(payslip_start, date_start)
        overlap_end = min(payslip_end, date_end or payslip_end)
        if overlap_start > overlap_end:
            return 0

        days_in_month = monthrange(payslip_end.year, payslip_end.month)[1]
        return ((overlap_end - overlap_start).days + 1) / days_in_month

    @api.model
    def _l10n_be_reduction_beta_g(self, mu_glob, at_least_half_time):
        """Target-group βg factor per μ(glob). Shared between the payslip
        estimation and the DMFA quarterly computation."""
        if mu_glob < 0.275 and not at_least_half_time:
            return 0.0
        if mu_glob < 0.55:
            return 1.0
        if mu_glob < 0.80:
            return 1.0 + (mu_glob - 0.55)
        return 1.0 / mu_glob if mu_glob else 0.0

    @api.model
    def _l10n_be_elderly_reduction_params(self, employee, date_ref, competence):
        """Return (brackets, quarterly_wage_cap) for a given employee / region
        competence ('br', 'wa', ...) at date_ref. Each bracket is a
        (dmfa_code, age_min, age_max, G) tuple; the 'pension' sentinel is
        resolved to the statutory pension age for date_ref.

        Wallonia-specific per-employee overrides:
        - Workers hired pre-2023-07 and aged 55-65 at that date
          keep the legacy 8320 brackets afterwards.
        - Workers hired or became eligible on/after 2026-04-01 have the 8321/8322
        """
        region_map = {'br': 'brussels', 'wa': 'wallonia'}
        region_key = region_map.get(competence)
        if not region_key:
            return [], 0.0
        # this reduction is removed from brussels starting Q3 2026
        if competence == 'br' and date_ref >= date(2026, 7, 1):
            return [], 0.0

        rule_param = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code
        hire_date = employee.first_contract_date
        # transition date from the old code 8320 (transition state) to 8321/8322 (permanant codes)
        # if an employee was already under code 8320 he should stay in it , if he only became eligibile after the cutoff date , then he moves to the new codes 8321/8322
        cutoff = date(2023, 7, 1)
        brackets_param_date = date_ref
        if competence == 'wa' and hire_date and employee.birthday:
            eligibility_date = max(
                employee.birthday + relativedelta(years=55),
                hire_date,
            )
            if eligibility_date < cutoff:
                brackets_param_date = cutoff - timedelta(days=1)
        brackets_raw = rule_param(
            f'l10n_be_elderly_reduction_brackets_{region_key}',
            date=brackets_param_date, raise_if_not_found=False,
        ) or []
        pension_age = rule_param(
            'l10n_be_pension_age', date=date_ref, raise_if_not_found=False,
        )
        brackets = [
            (code, amin, pension_age if amax == 'pension' else amax, g)
            for (code, amin, amax, g) in brackets_raw
        ]
        if competence == 'wa' and hire_date and hire_date >= date(2026, 4, 1):
            brackets = [
                (code, 57 if (code == 8321 and g == 'G2') else amin, amax, g)
                for (code, amin, amax, g) in brackets
            ]
        g_amounts = rule_param('l10n_be_target_group_g_amounts', date=date_ref) or {}
        brackets = [
            (code, amin, amax, g_amounts[g.lower()])
            for (code, amin, amax, g) in brackets
        ]
        age = employee._l10n_be_age_at_quarter_end(employee, date_ref)
        brackets = [b for b in brackets if b[1] <= age <= b[2]]
        if competence == 'wa':
            cap_code = 'l10n_be_elderly_reduction_cap_wallonia'
        else:
            quarter_end_month = ((date_ref.month - 1) // 3 + 1) * 3
            cap_code = (
                'l10n_be_elderly_reduction_cap_q4'
                if quarter_end_month == 12 and date_ref >= date(2024, 7, 1)
                else 'l10n_be_elderly_reduction_cap_standard'
            )
        cap = rule_param(cap_code, date=date_ref)
        return brackets, cap

    @api.model
    def _l10n_be_elderly_reduction_codes(self):
        """DMFA deduction codes used by the elderly-worker target-group
        reduction, collected from the dated bracket rule parameters so the
        deduction filtering stays in sync with the parameter tables instead
        of a hardcoded list."""
        bracket_values = self.env['hr.rule.parameter.value'].sudo().search([
            ('code', 'in', [
                'l10n_be_elderly_reduction_brackets_brussels',
                'l10n_be_elderly_reduction_brackets_wallonia',
            ]),
        ])
        return {
            bracket[0]
            for value in bracket_values
            for bracket in expr_eval(value.parameter_value)
        }

    @api.model
    def _l10n_be_target_group_reductions(self):
        """Target-group reductions declared in the DMFA. Each entry is a suffix
        's' such that '_l10n_be_reduction_s' is a method on hr.payslip that
        gates one reduction from the real quarterly aggregates ('mu_global',
        'ss_quarter') and returns declaration specs ({'code', 'g', optional
        'p_max'}); the amounts (Pg = G x mu x beta_g) are computed DMFA-side.
        Extend this list to add a reduction."""
        return ['elderly', 'artist', 'unexperienced_flander', 'acs']

    def _l10n_be_target_group_reduction_elderly(self, employee, quarter_start, aggregates):
        self.ensure_one()
        if not employee or not employee.birthday:
            return []
        competence = self.version_id.l10n_be_working_region
        if not competence:
            return []
        brackets, cap = self._l10n_be_elderly_reduction_params(employee, quarter_start, competence)
        if not brackets:
            return []
        if not aggregates['ss_quarter'] or aggregates['ss_quarter'] > cap:
            return []
        # TODO : When service_exemption_notion are implemented, in case of wallonia reduction , it should only apply when 0, 7 or 8 are mentionned in service_exemption_notion
        return [{'code': int(code), 'g': G} for (code, _amin, _amax, G) in brackets]

    def _l10n_be_target_group_reduction_unexperienced_flander(self, employee, quarter_start, aggregates):
        def _quarter_start(d):
            return date_utils.get_quarter(d)[0]

        def _next_quarter(d):
            quarter_end = date_utils.get_quarter(d)[1]
            return _quarter_start(quarter_end + relativedelta(days=1))

        def _quarter_diff(q1, q2):
            return (q1.year - q2.year) * 4 + (q1.month - q2.month) // 3

        versions = aggregates['versions']
        if not versions:
            return []

        if not any(v.l10n_be_onss_reduction_unexperienced_employees_flander for v in versions):
            return []

        employee = versions[0].employee_id
        first_contract_date = employee.sudo()._get_first_contract_date()
        if not first_contract_date:
            return []

        current_quarter = _quarter_start(quarter_start)

        all_versions = employee.sudo().version_ids.filtered(
            lambda v: v.contract_date_start).sorted('date_version')

        contract_end_by_start = {}
        for version in all_versions:
            contract_end_by_start[version.contract_date_start] = version.contract_date_end

        active_quarters = set()
        for contract_start, contract_end in contract_end_by_start.items():
            c_start_q = _quarter_start(contract_start)
            c_end_q = _quarter_start(contract_end) if contract_end else current_quarter
            q = c_start_q
            while _quarter_diff(current_quarter, q) >= 0:
                active_quarters.add(q)
                if _quarter_diff(c_end_q, q) <= 0:
                    break
                q = _next_quarter(q)

        sorted_active = sorted(active_quarters)
        if not sorted_active:
            return []

        # Identify the start of the current cycle: any gap of ≥ 4 consecutive inactive
        # quarters between two employment periods triggers a new cycle.
        cycle_start_idx = 0
        for i in range(1, len(sorted_active)):
            gap = _quarter_diff(sorted_active[i], sorted_active[i - 1]) - 1
            if gap >= 4:
                cycle_start_idx = i

        # Count the active quarters strictly before the current quarter within the
        # current cycle to know how many reductions have already been granted.
        active_before_current = sum(
            1 for q in sorted_active[cycle_start_idx:]
            if _quarter_diff(current_quarter, q) > 0
        )

        # Only the first 4 active quarters of each cycle are eligible for the reduction.
        if active_before_current >= 4:
            return []

        g_amount = (
            self.env["hr.rule.parameter"]
            .sudo()
            ._get_parameter_from_code("l10n_be_target_group_g_amounts", date=quarter_start, raise_if_not_found=False)[
                "g1"
            ]
        )
        p_max = (
            self.env["hr.rule.parameter"]
            .sudo()
            ._get_parameter_from_code(
                "l10n_be_unexperienced_salary_ceiling", date=quarter_start, raise_if_not_found=False
            )
        )
        return [{'code': 6340, 'g': g_amount, 'p_max': p_max, 'starting_date': first_contract_date.isoformat()}]

    def _is_l10n_be_onss_elderly_eligible(self):
        """Eligibility gate for the elderly-worker NSSO target-group reduction G1.
        Estimation only - final calculation happens on DMFA."""
        self.ensure_one()
        version = self.version_id
        employee = self.employee_id
        if not employee.birthday or version.is_student() or version.is_PFI():
            return False
        competence = version.l10n_be_working_region
        if not competence:
            return False
        brackets, _cap = self._l10n_be_elderly_reduction_params(employee, self.date_to, competence)
        return bool(brackets)

    def _get_l10n_be_onss_elderly_reduction(self, localdict):
        """Estimate the monthly share of the quarterly NSSO target-group
        reduction G1 for elderly workers.

        Pg = sum_over_matching_brackets(G x mu x beta_g).
        Returned value is Pg_quarter / 3 (monthly estimation)."""
        self.ensure_one()
        employee = self.employee_id
        if not employee.birthday:
            return 0.0
        competence = self.version_id.l10n_be_working_region
        brackets, cap_quarterly = self._l10n_be_elderly_reduction_params(employee, self.date_to, competence)
        if not brackets:
            return 0.0

        result_rules = localdict['result_rules']
        version = localdict['version']
        if result_rules['ONSS_BASE_TOTAL']['total'] * 3 > cap_quarterly:
            return 0.0

        ref_calendar = version._get_reference_calendar()
        U_weekly = ref_calendar.full_time_required_hours
        Z_month = sum(wd.number_of_hours for wd in self.worked_days_line_ids)
        # Quarterly-equivalent prestation fraction estimated from monthly hours:
        # mu_quarter = (3 x Z_month) / (13 x U) = Z_month / ((13/3) x U)
        denom = (13.0 / 3.0) * U_weekly
        mu = (Z_month / denom) if denom else 0.0
        mu = math.floor(mu * 100 + 0.5) / 100

        hours_per_week = version.resource_calendar_id.hours_per_week or 0.0
        at_least_half_time = hours_per_week >= (U_weekly / 2.0)
        beta_g = self._l10n_be_reduction_beta_g(mu, at_least_half_time)

        pg_quarter = round(sum(G for (_c, _a, _b, G) in brackets) * mu * beta_g, 2)
        return round(pg_quarter / 3.0, 2)

    def _l10n_be_target_group_reduction_artist(self, employee, quarter_start, aggregates):
        # https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/instructions/deductions/structuralreduction_targetgroupreductions/artists.html
        self.ensure_one()
        threshold = 3 * (self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(code='l10n_be_average_guaranteed_minimum_monthly_income', date=quarter_start, raise_if_not_found=False) or 0.0)
        if aggregates['ss_quarter'] >= threshold and self.version_id.l10n_be_worker_code_id.dmfa_code in ['046', '047'] and self.version_id.l10n_be_working_region != 'fl':
            g_amount = self._rule_parameter('l10n_be_target_group_g_amounts')['g12']
            reduction_max_cap = self._rule_parameter('l10n_be_onss_employer_reduction_artist_cap')
            return [{'code': 4300, 'g': g_amount, 'p_max': reduction_max_cap}]
        return []

    def _get_l10n_be_onss_artist_reduction(self, localdict):
        self.ensure_one()
        threshold = (self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(code='l10n_be_average_guaranteed_minimum_monthly_income', date=self.date_to, raise_if_not_found=False) or 0.0)
        if localdict['result_rules']['ONSS_BASE_TOTAL']['total'] >= threshold and self.version_id.l10n_be_worker_code_id.dmfa_code in ['046', '047'] and self.version_id.l10n_be_working_region != 'fl':
            g_amount = self._rule_parameter('l10n_be_target_group_g_amounts')['g12']
            reduction_max_cap = self._rule_parameter('l10n_be_onss_employer_reduction_artist_cap')
            version = localdict['version']
            ref_calendar = version._get_reference_calendar()
            U_weekly = ref_calendar.full_time_required_hours
            Z_month = sum(wd.number_of_hours for wd in self.worked_days_line_ids)
            # Quarterly-equivalent prestation fraction estimated from monthly hours:
            # mu_quarter = (3 x Z_month) / (13 x U) = Z_month / ((13/3) x U)
            denom = (13.0 / 3.0) * U_weekly
            mu = (Z_month / denom) if denom else 0.0
            mu = math.floor(mu * 100 + 0.5) / 100

            hours_per_week = version.resource_calendar_id.hours_per_week or 0.0
            at_least_half_time = hours_per_week >= (U_weekly / 2.0)
            beta_g = self._l10n_be_reduction_beta_g(mu, at_least_half_time)

            pg_quarter = min(round(g_amount * mu * beta_g, 2), reduction_max_cap)
            return round(pg_quarter / 3.0, 2)
        return 0.0

    def _l10n_be_get_quarterly_structural_deduction(self, localdict):
        """
        To accurately compute the quarterly structural deduction, we use:
        1. All finalized (validated or paid) payslips for the quarter.
        2. Any draft payslips belonging to the current payrun (batch).

        Including draft payslips from the current run handles edge cases like batch corrections
        or multiple contracts in a single month. Because a payrun computes payslips sequentially,
        earlier draft payslips in the batch will have already generated the payslip lines.
        Since we compute the structural deduction for each month and check the previously claimed
        amounts, the total across the payslips in the quarter will be accurate.
        """
        self.ensure_one()
        quarter_start, quarter_end = date_utils.get_quarter(self.date_to)
        quarter_payslips = localdict['l10n_be_quarter_payslips_by_payslip'].get(self, self.env['hr.payslip'])
        payslips = quarter_payslips.filtered(
            lambda p: p.version_id.structure_type_id == self.version_id.structure_type_id
            and p.company_id == self.company_id
            and p.line_ids
        ) | self

        if self.payslip_run_id:
            batch_slips = self.payslip_run_id.slip_ids.filtered(
                lambda p: p.employee_id == self.employee_id
                and p.date_from >= quarter_start
                and p.date_to <= quarter_end
                and p.state == 'draft'
                and p.line_ids
                and p.version_id.structure_type_id == self.version_id.structure_type_id
            )
            payslips |= batch_slips

        # Divide into occupations - based on the working schedule since the working hours affect the structural deduction computation
        occupation_groups = []
        occupation_data = self.employee_id.version_ids.sorted('date_start', reverse=True)._get_occupation_dates()
        for versions, _, _ in occupation_data:
            slips = payslips.filtered(lambda p, versions=versions: p.version_id in versions)
            if slips:
                occupation_groups.append((versions, slips))

        # mu global and total structural deduction is computed as the sum of all mu's and deductions for each occupation
        mu_global = sum(self.env['l10n_be.dmfa']._get_l10n_be_mu(slips[:1].version_id, payslips=slips) for _, slips in occupation_groups)
        quarterly_deduction = sum(
            self.env['l10n_be.dmfa']._get_l10n_be_structural_deduction_3000(slips, mu_global, localdict['result_rules'])
            for _, slips in occupation_groups
        )
        return quarterly_deduction, payslips

    def _l10n_be_get_monthly_regularized_structural_deduction(self, localdict):
        """
        Compute the monthly structural deduction based on the target quarterly deduction, and regularize it
        based on the deductions already applied in the current quarter.
        """
        self.ensure_one()
        # Compute the deductions that were applied in the previous payslips and subtract from the total deduction to find the
        # deduction (or correction) to apply for the current payslip
        target_quarterly_deduction, payslips = self._l10n_be_get_quarterly_structural_deduction(localdict)
        already_deducted = sum(line.total for line in payslips.line_ids.filtered(lambda line: line.code == "ONSS_STRUCTURAL"))
        return -target_quarterly_deduction - already_deducted

    def _l10n_be_target_group_reduction_acs(self, employee, quarter_start, aggregates):
        self.ensure_one()
        if not aggregates['versions'][:1]._l10n_be_is_eligible_for_acs_deduction():
            return []
        quarter_start, quarter_end = date_utils.get_quarter(self.date_to)
        code = 4001 if self.version_id.company_id.current_payroll_config_id.l10n_be_sector in ['public_federal_regional', 'public_other'] else 4000

        payslips = self.env['hr.payslip'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', 'in', ['validated', 'paid']),
                ('date_from', '>=', quarter_start),
                ('date_to', '<=', quarter_end),
                ('company_id', '=', self.company_id.id),
                ('version_id.structure_type_id', '=', self.version_id.structure_type_id.id)
            ])
        g_amount = sum(line.total for line in payslips.line_ids.filtered(lambda line: line.code == "ONSSEMPLOYERBASIC"))
        for payslip in payslips:
            if payslip.date_to.month in (3, 6, 9, 12):
                payslips = self.env['hr.payslip'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('state', 'in', ['validated', 'paid']),
                    ('date_from', '>=', quarter_start),
                    ('date_to', '<=', quarter_end),
                    ('company_id', '=', payslip.company_id.id),
                    ('version_id.structure_type_id', '=', payslip.version_id.structure_type_id.id)
                ])
                g_amount -= self.env['l10n_be.dmfa']._get_l10n_be_structural_deduction_3000(payslips, aggregates['mu_global'])
        return [{'code': code, 'g': g_amount}]

    def _get_l10n_be_onss_acs_reduction(self, localdict):
        self.ensure_one()
        result_rules = localdict['result_rules']

        if self.version_id._l10n_be_is_eligible_for_acs_deduction():
            result = -result_rules['ONSSEMPLOYERBASIC']['total'] if result_rules['ONSSEMPLOYERBASIC'] else 0.0
            if self.date_to.month in (3, 6, 9, 12):  # compute and substract ded3000 amount based on niss
                total_quarter_structural_deduction, _ = self._l10n_be_get_quarterly_structural_deduction(localdict)
                result += total_quarter_structural_deduction
            return round(result, 2)
        return 0.0

    def _get_l10n_be_atn_car_regularization_amount(self, localdict):
        """
        Compute the ATN car regularization for the current payslip.

        The regularization compares:
            - the theoretical ATN after applying the legal minimum &
            - the total ATN already paid on previous payslips plus the current month's ATN,
        over the days covered by the payslips of the year in Odoo. Days without a
        payslip in Odoo (e.g. before the company started using it) are left alone
        as nothing is known about what was paid for them.

        The rule is triggered on:
            - the December payslip, or
            - the employee's final payslip when leaving the company.
        Differences below 1 EUR are ignored.
        """
        self.ensure_one()

        min_legal_car_atn = self.env['hr.rule.parameter']._get_parameter_from_code('min_car_atn', self.date_to, raise_if_not_found=False)
        year_start = self.date_from.replace(month=1, day=1)
        year_end = self.date_to  # can be end of the year or end of the contract
        days_in_year = 366 if isleap(year_start.year) else 365

        versions = self.employee_id._get_versions_with_contract_overlap_with_period(year_start, year_end)
        versions = versions.filtered(lambda v: v.transport_mode_car and v.car_id)
        if not versions:
            return 0.0

        previous_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('struct_id', '=', self.struct_id.id),
            ('credit_note', '=', False),
            ('date_from', '>=', year_start),
            ('date_to', '<', self.date_from),
            ('state', 'in', ['validated', 'paid']),
        ])

        covered_days = 0
        theoretical_atn = 0.0
        for payslip in previous_payslips | self:
            for version in versions:
                overlap_start = max(payslip.date_from, version.date_start)
                overlap_end = min(payslip.date_to, version.date_end or payslip.date_to)
                if overlap_start > overlap_end:
                    continue
                days = (overlap_end - overlap_start).days + 1
                theoretical_atn += version.car_id._get_theoretical_car_atn(date=overlap_start) * days / days_in_year
                covered_days += days

        # the final ATN that should have been paid, after applying the legal minimum on the covered period
        atn_to_pay = max(theoretical_atn, min_legal_car_atn * covered_days / days_in_year)
        atn_paid = previous_payslips._get_line_values(['ATN.CAR'], compute_sum=True)['ATN.CAR']['sum']['total']
        atn_paid += localdict['result_rules']['ATN.CAR']['total'] if 'ATN.CAR' in localdict['result_rules'] else 0.0

        # negative: the employee paid too much and is refunded, positive: he has to pay the difference
        regularization = atn_to_pay - atn_paid
        return regularization if abs(regularization) >= 1.0 else 0.0

    def _get_be_private_car_reimursement_amount(self, localdict):
        self.ensure_one()
        code = self.version_id.l10n_be_joint_committee_id.egov3_code
        result_qty = self._get_be_benefit_count('PRIVATE_CAR', localdict)
        result_rate = 100

        if code in ['200', '302'] and self.date_from >= date(2026, 2, 1):
            daily_amount = self.version_id._get_private_car_daily_amount(ref_date=self.date_from)
            return (daily_amount, result_qty, result_rate)

        reference_working_days = len([a for a in self.version_id._get_reference_calendar()._get_attendances_by_date(
            self.date_from + relativedelta(day=1),
            self.date_from + relativedelta(day=31),
        ).values() if a])
        result = self.version_id.with_context(payslip_date=self.date_from)._get_private_car_reimbursed_amount()
        if result_qty == reference_working_days:
            return (result / result_qty, result_qty, result_rate)
        else:
            return (result * 3 / 13 / 5, result_qty, result_rate)

    def _get_be_bike_reimbursement_amounts(self, localdict):
        # Returns the daily bike reimbursement split into its exempt and taxable parts, both
        # capped together on the yearly maximum: only what is actually paid may be taxed.
        self.ensure_one()
        version = self.version_id
        result_rules = localdict['result_rules']
        quantity = self._get_be_benefit_count('PRIVATE_CAR', localdict)
        if not result_rules['BASIC']['total'] or not quantity:
            return (0, 0)
        joint_committee_code = self.l10n_be_joint_committee_id.egov3_code or '200'
        yearly_maximum = self._rule_parameter(
            'bike_max_reimbursement_yearly_cp200' if joint_committee_code == '200' else 'bike_max_reimbursement_yearly_cp302')
        # ytd includes the current payslip once the rule had its turn, and this helper is called
        # by both rules: substracting the running total gives the previous payslips in both cases.
        already_reimbursed = sum(
            result_rules[code]['ytd'] - result_rules[code]['total'] for code in ('CYCLE', 'CYCLE.TAX'))
        amount = version._get_bike_reimbursed_amount()
        amount = min(yearly_maximum - already_reimbursed, amount * quantity) / quantity
        exempt_rate = self._rule_parameter('bike_exempt_reimbursement_per_km', raise_if_not_found=False)
        taxable_amount = 0
        if exempt_rate:
            taxable_amount = max(0, amount - exempt_rate * version.bike_transport_employee_kilometer * 2)
        return (amount - taxable_amount, taxable_amount)

    def _get_be_cp999_flat_rate_social_contributions(self, localdict):

        payslip = localdict['payslip']

        monthly_revenues = localdict['result_rules']['GROSS.M']['total']

        min_amount = payslip._rule_parameter('l10n_be_dir_flat_rate_deduction_min', raise_if_not_found=False)
        max_amount = payslip._rule_parameter('l10n_be_dir_flat_rate_deduction_max', raise_if_not_found=False)
        rate_by_threshold = payslip._rule_parameter('l10n_be_dir_flat_rate_deduction', raise_if_not_found=False)

        if not min_amount or not max_amount or not rate_by_threshold:
            return 0

        base_amount = min_amount
        previous_threshold = 0

        for threshold, rate in sorted(rate_by_threshold.items()):
            if monthly_revenues <= threshold:
                result = base_amount + (monthly_revenues - previous_threshold) * rate
                break
            base_amount += (threshold - previous_threshold) * rate
            previous_threshold = threshold
        else:
            result = min(monthly_revenues, max_amount)
        return min(monthly_revenues, result)

    def _is_extra_hours_qualifying(self, work_entry_type):
        """
        Check if a work entry type qualifies as an extra hour line.
        - Must be marked as extra hours (`is_extra_hours = True`)
        - AND either `amount_rate >= 1.0` OR (amount_rate + child premium percentage > 1.0)
        """
        if not work_entry_type.is_extra_hours:
            return False

        if work_entry_type.amount_rate >= 1.0:
            return True

        assigned_categories = work_entry_type.category_ids | work_entry_type.optional_category_ids
        for category in assigned_categories:
            for child in category.children_ids:
                if child.is_premium_pay and (work_entry_type.amount_rate + child.premium_percentage_hourly_rate) > 1.0:
                    return True

        return False

    def _check_withholding_extra_hours_reduction(self):
        self.ensure_one()
        return any(self._is_extra_hours_qualifying(line.work_entry_type_id) for line in self.worked_days_line_ids)

    def _get_withholding_extra_hours_reduction(self):
        self.ensure_one()

        overtime_threshold_code = 'overtime_withholding_tax_reduction_threshold_white_cash_register' if self.company_id.l10n_be_has_white_cash_register else 'overtime_withholding_tax_reduction_threshold_not_white_cash_register'
        annual_cap = self.env['hr.rule.parameter']._get_parameter_from_code(overtime_threshold_code, self.date_to, raise_if_not_found=False)

        tier1_rate = self.env['hr.rule.parameter']._get_parameter_from_code(
            'overtime_withholding_tax_reduction_rate_tier1', self.date_to, raise_if_not_found=False
        )
        tier2_rate = self.env['hr.rule.parameter']._get_parameter_from_code(
            'overtime_withholding_tax_reduction_rate_tier2', self.date_to, raise_if_not_found=False
        )

        previous_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', max(date(self.date_from.year, 1, 1), self.version_id.contract_date_start)),
            ('date_to', '<', self.date_from),
            ('state', 'in', ['validated', 'paid']),
        ])

        used_extra_hours = sum(
            line.number_of_hours
            for line in previous_payslips.mapped('worked_days_line_ids')
            if self._is_extra_hours_qualifying(line.work_entry_type_id))

        remaining_hours_cap = max(0.0, annual_cap - used_extra_hours)
        if remaining_hours_cap <= 0:
            return 0.0

        basic_hourly_wage = 0.0
        if self.version_id.hourly_wage:
            basic_hourly_wage = self.version_id.hourly_wage
        else:
            monthly_hours = sum(self.worked_days_line_ids.mapped('number_of_hours'))
            basic_hourly_wage = self.version_id._get_contract_wage() / monthly_hours if monthly_hours else 0.0

        total_deduction = 0.0
        for line in self.worked_days_line_ids:
            if not self._is_extra_hours_qualifying(line.work_entry_type_id):
                continue

            line_rate = line.work_entry_type_id.amount_rate - 1.0
            assigned_categories = line.work_entry_type_id.category_ids | line.work_entry_type_id.optional_category_ids
            for category in assigned_categories:
                for child in category.children_ids:
                    if child.is_premium_pay and child.premium_percentage_hourly_rate > 0:
                        line_rate += child.premium_percentage_hourly_rate

            if line_rate < 0.2:
                continue

            extra_hours = min(line.number_of_hours, remaining_hours_cap)
            if extra_hours <= 0:
                break

            if 0.2 <= line_rate < 0.5:
                deduction_rate = tier1_rate
            else:
                deduction_rate = tier2_rate

            base_amount = extra_hours * basic_hourly_wage
            total_deduction += base_amount * deduction_rate
            remaining_hours_cap -= extra_hours

        return total_deduction

    def _get_be_withholding_taxes_transport_deduction(self, localdict):
        self.ensure_one()

        version = self.version_id

        if version.private_car_employee_kilometer or version.transport_mode_car:
            yearly_transport_amount = 0
            if version.transport_mode_car:
                yearly_transport_amount += version.car_atn
            if version.private_car_employee_kilometer:
                result, result_qty, result_rate = self._get_be_private_car_reimursement_amount(localdict)
                private_car_amount = result * result_qty * result_rate / 100
                yearly_transport_amount += private_car_amount * 12

            yearly_exemption_amount = self._rule_parameter('pricate_car_taxable_threshold')
            return min(yearly_transport_amount, yearly_exemption_amount)

        return 0

    def _l10n_be_is_isolated(self):
        self.ensure_one()
        return self.l10n_be_effective_marital in ('divorced', 'single', 'widower', 'separated')

    def _l10n_be_is_coupled(self):
        self.ensure_one()
        return self.l10n_be_effective_marital in ('married', 'cohabitant')

    def _get_be_withholding_taxes_marital_deduction(self):
        self.ensure_one()
        version = self.version_id
        if not version.is_non_resident:
            if version.l10n_be_resident_situation == 'cross_border':
                return 0
            if self._is_eligible_for_bareme_I():
                return self._get_bareme_I_deduction()
            if self._is_eligible_for_bareme_II():
                return self._get_bareme_II_deduction()
            return 0

        # contract non convering all the year
        current_year = self.date_from.year
        if not (version.contract_date_start <= date(current_year, 1, 1) and (not version.contract_date_end or version.contract_date_end >= date(current_year, 12, 31))):
            return self._get_bareme_III_deduction()

        # contract covering all the year
        if version.work_in_belgium_over_75:
            if self._is_eligible_for_bareme_I():
                return self._get_bareme_I_deduction()
            if self._is_eligible_for_bareme_II():
                return self._get_bareme_II_deduction()
            return 0

        return self._get_bareme_III_deduction()

    def _get_bareme_I_deduction(self):
        self.ensure_one()
        return self._rule_parameter('deduct_single_with_income')

    def _get_bareme_II_deduction(self):
        self.ensure_one()
        return 2 * self._rule_parameter('deduct_single_with_income')

    def _get_bareme_III_deduction(self):
        self.ensure_one()
        return 0

    def _is_eligible_for_bareme_I(self):
        return self._l10n_be_is_isolated() or (self._l10n_be_is_coupled() and self.version_id.spouse_fiscal_status != 'without_income' and not self.version_id.disabled_spouse_bool)

    def _is_eligible_for_bareme_II(self):
        return self._l10n_be_is_coupled() and (self.version_id.spouse_fiscal_status == 'without_income' or self.version_id.disabled_spouse_bool)

    def _get_be_withholding_taxes_family_charges_deduction(self):
        self.ensure_one()

        version = self.version_id
        total_reduction = 0

        if self._is_eligible_for_bareme_I() or self._is_eligible_for_bareme_II():
            if version.disabled:
                total_reduction += self._rule_parameter('disabled_dependent_deduction')
            if version.other_senior_dependent:
                total_reduction += self._rule_parameter('dependent_senior_deduction') * version.other_senior_dependent
            if version.dependent_juniors:
                total_reduction += self._rule_parameter('disabled_dependent_deduction') * version.dependent_juniors

        if self._is_eligible_for_bareme_I():
            if self._l10n_be_is_isolated() and version.dependent_children:
                total_reduction += self._rule_parameter('disabled_dependent_deduction')
            if self._l10n_be_is_coupled() and version.spouse_fiscal_status == 'low_income':
                total_reduction += self._rule_parameter('spouse_low_income_deduction')
            if self._l10n_be_is_coupled() and version.spouse_fiscal_status == 'low_pension':
                total_reduction += self._rule_parameter('spouse_other_income_deduction')

        if self._is_eligible_for_bareme_II():
            if version.disabled_spouse_bool:
                total_reduction += self._rule_parameter('disabled_dependent_deduction')

        # Child Allowances
        n_children = version.dependent_children
        if n_children > 0:
            children_deduction = self._rule_parameter('dependent_basic_children_deduction')
            if n_children <= 8:
                total_reduction += children_deduction.get(n_children, 0.0)
            if n_children > 8:
                total_reduction += children_deduction.get(8, 0.0) + (n_children - 8) * self._rule_parameter('dependent_children_deduction')

        return total_reduction

    def _compute_basic_bareme(self, yearly_net_taxable_amount):
        """ Apply the progressive bareme to a yearly net taxable amount, with the Scale II income split for married employees with a non-working spouse. """
        def apply_brackets(value):
            rates = self._rule_parameter('basic_bareme_rates')
            # The last bracket has no upper limit in the parameter table, so float('inf') is used as a stand-in.
            rates = [(limit or float('inf'), rate) for limit, rate in rates]
            rates = sorted(rates)
            basic_bareme = 0
            previous_limit = 0
            for limit, rate in rates:
                # Tax only the slice of income that falls within this bracket at its marginal rate.
                basic_bareme += max(min(value, limit) - previous_limit, 0) * rate
                previous_limit = limit
            return float_round(basic_bareme, precision_rounding=0.01)

        version = self.version_id
        if not version.is_non_resident and self._is_eligible_for_bareme_II():
            # Scale II allocates up to 30 percent of income to the non-working spouse, reducing the total tax.
            max_spouse_income = self._rule_parameter('max_spouse_income')
            amount_for_spouse = min(yearly_net_taxable_amount * 0.3, max_spouse_income)
            return apply_brackets(amount_for_spouse) + apply_brackets(yearly_net_taxable_amount - amount_for_spouse)
        return apply_brackets(yearly_net_taxable_amount)

    def _get_be_withholding_taxes_basic_bareme(self, localdict):
        self.ensure_one()

        version = self.version_id

        gross_code = 'GROSS.NET.Y' if self.struct_id.code == 'BEMONTHLY' else 'TERM_GROSS_NET_Y'
        yearly_net_taxable_revenue = localdict['result_rules'][gross_code]['total']  # Base imposable nette

        # Only the termination structure lacks a CAR.PRIV line, so it still needs the private-car reimbursement fictively added to the taxable base.
        termination_struct = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        if self.struct_id == termination_struct and version.private_car_employee_kilometer:
            result, result_qty, result_rate = self._get_be_private_car_reimursement_amount(localdict)
            private_car_amount = result * result_qty * result_rate / 100
            yearly_net_taxable_revenue += private_car_amount * 12

        return self._compute_basic_bareme(yearly_net_taxable_revenue)

    def _l10n_be_is_last_payslip(self):
        """ Check if this payslip is the last one of the employee (leaving the company). """
        self.ensure_one()
        employee = self.employee_id
        contract_end = employee.contract_date_end
        # The employee leaves through an explicit departure date falling in this slip.
        leaves_on_departure_date = bool(employee.departure_date and self.date_from <= employee.departure_date <= self.date_to)
        # Or a fixed term contract ends in this slip with no later version starting after it.
        contract_ends_in_slip = bool(contract_end and self.date_from <= contract_end <= self.date_to)
        # Only look for a later version when there is a contract end to compare against.
        has_later_version = contract_end and employee.version_ids.filtered(lambda v: v.date_start > contract_end)
        ends_fixed_term_contract = contract_ends_in_slip and not has_later_version
        return leaves_on_departure_date or ends_fixed_term_contract

    def _l10n_be_is_last_payslip_of_quarter(self, localdict):
        """
        If a validated/paid payslip (or self) is at the end of the current
        quarter, then self is the last payslip of the quarter
        e.g.:
          - we have validated payslips in Jan, Feb and Mar, Mar is the last
            payslip of the quarter
          - if we then correct the Feb payslip (so we make a new one), then Feb2
            is also a last payslip of the quarter (as no payslip is supposed to
            be generated afterwards)
        """
        self.ensure_one()
        # all validated/paid payslips of self's quarter
        quarter_payslips = localdict['l10n_be_quarter_payslips_by_payslip'][self]

        # if the employee stops working before the end of quarter, then we
        # consider his last work day as the end of the quarter
        _, quarter_end = date_utils.get_quarter(self.date_to)
        last_quarter_month = min(
            self.employee_id.l10n_be_get_last_work_day_of_year(self.date_to.year) or date.max,
            quarter_end,
        ).month
        if last_quarter_month != max(p.date_to.month for p in (quarter_payslips | self)):
            return False

        # 13th month payslips are considered the last payslip of the quarter only
        # if there is already a monthly payslip in the same month
        is_thirteen = self.struct_id.code == 'BETHIRTEEN'
        return not is_thirteen or self._l10n_be_has_monthly_payslip_in_same_month(localdict)

    def _l10n_be_has_monthly_payslip_in_same_month(self, localdict):
        self.ensure_one()
        month_payslips = localdict['l10n_be_month_payslips_by_payslip'][self]
        return any(p.struct_id.code == 'BEMONTHLY' for p in month_payslips - self)

    def _l10n_be_csss_get_total_contribution(self, frequency: str, taxable_amount: float) -> float:
        """
        Returns the total special social contribution (CSSS) that should be paid
        if the employee has gained `taxable_amount`. This function does not
        deduct the already paid CSSS for the quarter.
        :param frequency: 'monthly' or 'quarterly' to use the corresponding rates
        """
        self.ensure_one()
        # there are different contribution rates per marital status
        if self._l10n_be_is_isolated():
            rates = self._rule_parameter(f'special_social_contribution_{frequency}_rate_single')
        elif self._l10n_be_is_coupled():
            if self.version_id.spouse_fiscal_status == 'without_income':
                rates = self._rule_parameter(f'special_social_contribution_{frequency}_rate_couple_single_income')
            else:
                rates = self._rule_parameter(f'special_social_contribution_{frequency}_rate_couple_dual_income')
        else:
            raise UserError(self.env._(
                'Employee "%(name)s" has an unsupported marital status "%(status)s" for the computation of the special social contribution',
                name=self.employee_id.name,
                status=self.l10n_be_effective_marital,
            ))

        special_social_contrib = 0
        # we need to apply the values of the first matching rate only
        for rate in sorted(rates, key=lambda r: r['from'], reverse=True):
            if rate['from'] > taxable_amount:
                continue
            # rate percentage must be applied on any cent >= rate beginning
            exceeding_amount = taxable_amount - max(0, rate['from'] - 0.01)
            contribution = rate['amount'] + exceeding_amount * (rate.get('percentage', 0) / 100)
            special_social_contrib = min(rate.get('max', float('inf')), max(contribution, rate.get('min', 0)))
            break
        return special_social_contrib

    def _l10n_be_csss_get_gross_onss_wage(self, localdict, validated_payslips_in_period):
        """
        Any gross salary received during the month (or quarter) must be subject
        to the Special Social Contribution (CSSS). The wage is increased by 8%
        for workers.
        The IRC (wage on termination fees) is not returned here as it is used
        for another part of the computation
        """
        self.ensure_one()
        relevant_codes = ('SALARY', 'BONUS_SALARY', 'CP302THIRTEEN', 'WARRANT_SALARY')
        line_values = validated_payslips_in_period._get_line_values(relevant_codes, compute_sum=True)
        gross_onss_salary = sum(line_values[code]['sum']['total'] for code in relevant_codes)
        if self not in validated_payslips_in_period:
            gross_onss_salary += sum(localdict.get(code, 0) for code in relevant_codes)
        if self.version_id.is_worker():
            gross_onss_salary *= 1.08
        return gross_onss_salary

    def _l10n_be_csss_get_simple_holiday_pay(self, localdict, validated_payslips_in_period):
        """
        Any simple holiday pay (simple pécule de vacances) received during the
        month (or quarter) must be subject to the Special Social Contribution (CSSS).
        """
        self.ensure_one()
        simple_holiday_pay = validated_payslips_in_period._get_line_values(['PAY_SIMPLE'], compute_sum=True)['PAY_SIMPLE']['sum']['total']
        if self not in validated_payslips_in_period:
            simple_holiday_pay += localdict.get('PAY_SIMPLE', 0)
        return simple_holiday_pay

    def _l10n_be_csss_get_irc_per_quarter(self, localdict, validated_payslips_in_period) -> dict[tuple, float]:
        """
        When an employee does not do all of his notice period, and instead
        receives all of it in the termination fees (indemnité de rupture de
        contrat, IRC), this sum is subject to the CSSS, but, the amount has to
        be split per quarter of the notice period, and the CSSS must be applied
        per quarter instead of all at once.
        :return dict: the irc split per quarter in this format:
            {(quarter_start, quarter_stop): irc_amount}
        """
        self.ensure_one()

        if not self.employee_id.departure_date or not self.employee_id.l10n_be_notice_period_theoretical_end:
            return {}  # no possible irc if we don't have a notice

        irc = validated_payslips_in_period._get_line_values(['TERM_SALARY'], compute_sum=True)['TERM_SALARY']['sum']['total']
        if self not in validated_payslips_in_period:
            irc += localdict.get('TERM_SALARY', 0)

        unprestated_notice_start = self.employee_id.departure_date + relativedelta(days=1)
        unprestated_notice_end = self.employee_id.l10n_be_notice_period_theoretical_end

        def notice_hours_in_period(date_from, date_to):
            date_from = max(date_from, unprestated_notice_start)
            date_to = min(date_to, unprestated_notice_end)
            return self.version_id.resource_calendar_id.get_work_hours_count(date_from, date_to, compute_leaves=False)

        work_hours_in_notice = notice_hours_in_period(unprestated_notice_start, unprestated_notice_end)
        if not work_hours_in_notice:
            return {}

        # the IRC should be divided by each quarter of the notice period. We can
        # acheive it by doing a proratization on the workable hours.
        quarters_in_notice: dict[tuple, float] = {}
        quarter_start, quarter_end = date_utils.get_quarter(unprestated_notice_start)
        while quarter_start < unprestated_notice_end:
            irc_in_quarter = irc * (notice_hours_in_period(quarter_start, quarter_end) / work_hours_in_notice)
            quarters_in_notice[quarter_start, quarter_end] = irc_in_quarter
            quarter_start, quarter_end = date_utils.get_quarter(quarter_start + relativedelta(months=3))

        return quarters_in_notice

    def _l10n_be_get_special_social_contribution(self, localdict, frequency: str):
        """
        The Special Social Contribution (CSSS) is a quarterly tax on the gross
        wage of the employee.
        To avoid reducing the salary too much at the end of a quarter, we take
        monthly advances with adapted rates to spread the tax on the quarter.
        :param frequency: either 'monthly' or 'quarterly' to get either the
            monthly estimation, or the real CSSS based on quarterly rates
        """
        self.ensure_one()
        if self.version_id.is_non_resident:
            return 0

        if frequency not in ('monthly', 'quarterly'):
            raise UserError(self.env._(
                "Invalid special social contribution frequency (%(invalid_freq)s)",
                invalid_freq=frequency,
            ))

        if frequency == 'quarterly':
            validated_payslips_in_period = localdict['l10n_be_quarter_payslips_by_payslip'][self]
        else:
            validated_payslips_in_period = localdict['l10n_be_month_payslips_by_payslip'][self]

        gross_onss_salary = self._l10n_be_csss_get_gross_onss_wage(localdict, validated_payslips_in_period)
        simple_holiday_pay = self._l10n_be_csss_get_simple_holiday_pay(localdict, validated_payslips_in_period)

        # get notice period paid sum (IRC), split per quarter
        irc_per_quarter = self._l10n_be_csss_get_irc_per_quarter(localdict, validated_payslips_in_period)

        # if we have an IRC for this payslip's quarter, we have to use it for
        # the main CSSS computation
        additional_irc = 0
        quarter_start, quarter_end = date_utils.get_quarter(self.date_to)
        if (quarter_start, quarter_end) in irc_per_quarter:
            additional_irc = irc_per_quarter[quarter_start, quarter_end]
            if self.version_id.is_worker():
                additional_irc *= 1.08  # worker uplift on ONSS wages
            # we will remove this quarter's irc to avoid counting it again later
            irc_per_quarter.pop((quarter_start, quarter_end))

        special_social_contribution = self._l10n_be_csss_get_total_contribution(
            frequency, gross_onss_salary + simple_holiday_pay + additional_irc,
        )

        # any IRC during the notice period is subject to the CSSS. Since no
        # other payslip will be generated for that salary, we have to compute it
        # now and add it to this payslip's CSSS
        for quarter_irc in irc_per_quarter.values():
            if self.version_id.is_worker():
                quarter_irc *= 1.08  # worker uplift on ONSS wages
            special_social_contribution += self._l10n_be_csss_get_total_contribution('quarterly', quarter_irc)

        # we should deduct what has already been paid during the period
        other_validated_payslips_in_period = validated_payslips_in_period - self
        advances = -other_validated_payslips_in_period._get_line_values(['M.ONSS'], compute_sum=True)['M.ONSS']['sum']['total']

        return special_social_contribution - advances

    def _get_be_benefit_count(self, benefit, localdict):
        # Note:
        # meal_voucher / private car returns the number of days granting the advantage
        self.ensure_one()
        if self.env.context.get('salary_simulation'):
            if benefit in ['MEAL_VOUCHER', 'PRIVATE_CAR']:
                return 20

        benefit_category = self.env.ref(f'l10n_be_hr_payroll.{benefit}', raise_if_not_found=False)
        if not benefit_category:
            return 0
        granting_days = list({vals['date'] for vals in localdict['work_entries'] if benefit_category.id in (vals['work_entry_type_id'].category_ids | vals.get('category_options_ids', self.env['hr.salary.rule.category'])).ids})
        if benefit in ['MEAL_VOUCHER', 'PRIVATE_CAR']:
            return len(granting_days)
        return 0

    def _get_be_ip(self, localdict):
        self.ensure_one()
        if self.version_id.ip_wage_rate <= 0:
            return 0.0
        return localdict['result_rules']['BASIC']['total'] * self.version_id.ip_wage_rate

    def _get_be_ip_values(self, localdict):
        """ Split the intellectual property (IP) of the payslip.

        The values are computed once per payslip (memoized in the localdict) so that every IP rule
        relies on the same figures. The first call comes from the `IP.EXEMPT` rule (sequence 535),
        i.e. once the ONSS base is complete but still contains the whole IP.

        - ip: the gross IP (BASIC x ip_wage_rate), capped on the room left under the yearly limit: the
          exceeding part is paid as a regular remuneration
        - total_remuneration: the remuneration subject to ONSS, IP included
        - onss_exempt: the part of the IP exempt from ONSS, i.e. the IP up to the maximum share
          (30 %) of the total remuneration, unless the ONSS contributions are forced on the contract
        - onss_part: the part of the IP subject to ONSS
        - within_limits: whether the IP withholding tax applies, i.e. the IP doesn't exceed the
          maximum share of the total remuneration and the average IP received during the 4 previous
          years doesn't exceed the yearly limit. Otherwise the IP is taxed as a regular remuneration.

        The share and the yearly limit only exist since 2026: without a rule parameter value, the
        related conditions don't apply and the whole IP is subject to ONSS.
        """
        self.ensure_one()
        cache = localdict.setdefault('l10n_be_ip_values', {})
        if self.id in cache:
            return cache[self.id]
        ip = self._get_be_ip(localdict)
        yearly_limit = self._rule_parameter('ip_limit', raise_if_not_found=False)
        if ip > 0 and yearly_limit:
            # yearly cap: only the room left under the limit is paid as IP
            year_ip = localdict.get('l10n_be_ip_year_total_by_payslip', {}).get(self, 0.0)
            ip = max(0.0, min(ip, float_round(yearly_limit - year_ip, precision_digits=2)))
        values = {
            'ip': ip,
            'total_remuneration': 0.0,
            'onss_exempt': 0.0,
            'onss_part': 0.0,
            'within_limits': False,
        }
        if ip > 0:
            # the ONSS base still contains the IP, unless the exemption line was already computed
            total = localdict['categories']['ONSS_BASE'] - localdict['result_rules']['IP.EXEMPT']['total']
            max_share = self._rule_parameter('ip_max_remuneration_share', raise_if_not_found=False)
            max_ip = float_round(max_share * total, precision_digits=2) if max_share else 0.0
            share_ok = not max_share or float_compare(ip, max_ip, precision_digits=2) <= 0
            previous_years_average = localdict.get('l10n_be_ip_previous_years_average_by_payslip', {}).get(self, 0.0)
            average_ok = not yearly_limit or float_compare(previous_years_average, yearly_limit, precision_digits=2) <= 0
            onss_exempt = 0.0 if not max_share or self.version_id.ip_onss else min(ip, max_ip)
            values.update({
                'total_remuneration': total,
                'onss_exempt': onss_exempt,
                'onss_part': ip - onss_exempt,
                'within_limits': share_ok and average_ok,
            })
        cache[self.id] = values
        return values

    def _get_be_ip_flat_rate_costs(self, localdict):
        """ Lump-sum professional costs on the IP, only granted to the owners of a certificate of
        artistic work: 50 % of the yearly IP up to the first bracket, 25 % between the first and
        the second bracket, nothing above. The brackets are yearly amounts: the costs are assessed
        on the IP of this payslip on top of the IP of the validated payslips of the year.
        """
        self.ensure_one()
        ip = self._get_be_ip_values(localdict)['ip']
        if ip <= 0:
            return 0.0
        bracket_1 = self._rule_parameter('ip_deduction_bracket_1')
        bracket_2 = self._rule_parameter('ip_deduction_bracket_2')
        year_ip = localdict.get('l10n_be_ip_year_total_by_payslip', {}).get(self, 0.0)

        def tranche(lower, upper):
            # part of the IP of this payslip falling between both yearly amounts
            return max(0.0, min(year_ip + ip, upper) - max(year_ip, lower))

        return 0.5 * tranche(0.0, bracket_1) + 0.25 * tranche(bracket_1, bracket_2)

    def _get_be_ip_deduction(self, localdict):
        self.ensure_one()
        # the IP subject to the IP withholding tax (IP_WT category) is the whole IP of the payslip
        ip_values = self._get_be_ip_values(localdict)
        ip = ip_values['ip']
        if ip <= 0 or not localdict['categories']['IP_WT']:
            return 0.0
        # the withholding tax applies on the IP net of its ONSS part
        onss_rate = self._get_onss_global_rates()['personal_rate']
        taxable_amount = ip - ip_values['onss_part'] * onss_rate / 100
        if self.version_id.ip_artist:
            taxable_amount -= self._get_be_ip_flat_rate_costs(localdict)
        return - max(taxable_amount, 0.0) * self._rule_parameter('ip_tax_rate')

    def _l10n_be_init_work_bonus_explanation(self, localdict):
        no_worked_days = self.env._("No worked days")
        localdict['explanation_info'].update({
            'salary_formula': no_worked_days,
            'reference_salary': 0,
            'base_bonus_formula': no_worked_days,
            'base_bonus': 0,
            'proration_formula': no_worked_days,
            'onss': 0,
            'calculated_bonus': 0,
            'already_paid': 0,
            'carry_over': 0,
        })

    def _l10n_be_update_work_bonus_explanation(self, localdict, gross, salary, base_bonus, base_bonus_formula,
                                               is_full_time, paid_days, total_days, paid_hours, total_hours):
        """
        Details how the work bonus reference salary (S) and the granted amount (P) are obtained.
        A full time worker is prorated on days (J/D), a part time one on hours (H/U).
        """
        gross = float_round(gross, precision_digits=4)
        base_bonus = float_round(base_bonus, precision_digits=4)
        if not is_full_time:
            paid, total = float_round(paid_hours, precision_digits=4), float_round(total_hours, precision_digits=4)
            salary_formula = self.env._(
                "(Gross (%(gross)s) / Paid hours (%(paid)s), rounded (2-digits)) * Total hours (%(total)s)",
                gross=gross, paid=paid, total=total)
            proration_formula = self.env._(
                "Basic bonus (%(base_bonus)s) * (Paid hours (%(paid)s) / Total hours (%(total)s), rounded (2-digits))",
                base_bonus=base_bonus, paid=paid, total=total)
        elif paid_days < total_days:
            paid, total = float_round(paid_days, precision_digits=4), float_round(total_days, precision_digits=4)
            salary_formula = self.env._(
                "(Gross (%(gross)s) / Paid days (%(paid)s), rounded (2-digits)) * Total days (%(total)s)",
                gross=gross, paid=paid, total=total)
            proration_formula = self.env._(
                "Basic bonus (%(base_bonus)s) * (Paid days (%(paid)s) / Total days (%(total)s), rounded (2-digits))",
                base_bonus=base_bonus, paid=paid, total=total)
        else:
            salary_formula = self.env._("Gross (%(gross)s), complete month", gross=gross)
            proration_formula = self.env._(
                "Basic bonus (%(base_bonus)s), complete month", base_bonus=base_bonus)
        localdict['explanation_info'].update({
            'salary_formula': salary_formula,
            'reference_salary': float_round(salary, precision_digits=4),
            'base_bonus_formula': base_bonus_formula,
            'base_bonus': base_bonus,
            'proration_formula': proration_formula,
        })

    @api.model
    def _get_employment_bonus_excluded_codes(self):
        return ['147.00', '147.05', '147.07', '040.27', '040.28', '039.23', '147.04', '147.08', '147.13']

    def _get_employment_bonus_employees_volet_A(self, localdict):
        self._l10n_be_init_work_bonus_explanation(localdict)
        result_rules = localdict['result_rules']
        prev_monthly_payslips = localdict['l10n_be_month_payslips_by_payslip'][self]
        worked_days_payslip = (self | prev_monthly_payslips).filtered('worked_days_line_ids')
        if not worked_days_payslip and not self.env.context.get('salary_simulation') and result_rules['SECTORIAL.BONUS']['total'] == 0:  # in case we want a payslip with only the sectorial bonus
            return {'result': 0, 'remaining_bonus': 0, 'explanation_info': localdict['explanation_info']}

        # S = (W / H) * U
        # W = salaire brut
        # H = le nombre d'heures de travail déclarées avec un code prestations 1, 3, 4, 5 et 20;
        # U = le nombre maximum d'heures de prestations pour le mois concerné dans le régime de travail concerné
        # J = The number of days declared for the worker with a performance (work) code of 1, 3, 4, 5, and 20
        # D = The maximum number of working (performance) days for the relevant month under the relevant work regime
        is_full_time = self.version_id.work_time_rate >= 1.0
        if self.env.context.get('salary_simulation') or not worked_days_payslip:
            paid_hours = total_hours = paid_days = total_days = 1
        else:
            excluded_codes = self._get_employment_bonus_excluded_codes()
            all_worked_days = worked_days_payslip.worked_days_line_ids.filtered(lambda wd: wd.code not in excluded_codes)
            ref_worked_days = worked_days_payslip[0].worked_days_line_ids.filtered(lambda wd: wd.code not in excluded_codes)
            paid_hours = round(sum(all_worked_days.filtered(lambda wd: wd.amount).mapped('number_of_hours')), 2)  # H
            total_hours = round(sum(ref_worked_days.mapped('number_of_hours')), 2)  # U
            paid_days = sum(all_worked_days.filtered(lambda wd: wd.amount).mapped('number_of_days'))  # J
            total_days = sum(ref_worked_days.mapped('number_of_days'))  # D
            if (not is_full_time and not paid_hours) or (is_full_time and not paid_days):
                return {'result': 0, 'remaining_bonus': 0, 'explanation_info': localdict['explanation_info']}

        # 1. - Détermination du salaire mensuel de référence (S)
        basic = result_rules['ONSS_BASE_TOTAL']['total'] - result_rules['HolPayRec']['total']
        if is_full_time:
            if paid_days < total_days:
                salary = float_round(basic / paid_days, precision_digits=2) * total_days  # S = (W/J) x D
            else:
                salary = basic  # S = W
        else:
            salary = float_round(basic / paid_hours, precision_digits=2) * total_hours  # S = (W/H) x U

        # 2. - Détermination du montant de base de la réduction (R)
        key = 'worker' if self.version_id.is_worker() else 'employee'
        bonus_basic_amount_volet_A = self._rule_parameter('work_bonus_basic_amount_volet_A')[key]
        wage_lower_bound = self._rule_parameter('work_bonus_reference_wage_low')
        wage_middle_bound = self._rule_parameter('l10n_be_work_bonus_reference_wage_middle')
        wage_higher_bound = self._rule_parameter('work_bonus_reference_wage_high')

        if salary <= wage_lower_bound:
            result = bonus_basic_amount_volet_A
            base_bonus_formula = self.env._(
                "Reference salary (%(salary)s) <= %(bound)s: full basic amount (%(basic_amount)s)",
                salary=float_round(salary, precision_digits=4),
                bound=float_round(wage_lower_bound, precision_digits=4),
                basic_amount=float_round(bonus_basic_amount_volet_A, precision_digits=4))
        elif salary <= wage_middle_bound:
            result = bonus_basic_amount_volet_A
            base_bonus_formula = self.env._(
                "Reference salary (%(salary)s) <= %(bound)s: full basic amount (%(basic_amount)s)",
                salary=float_round(salary, precision_digits=4),
                bound=float_round(wage_middle_bound, precision_digits=4),
                basic_amount=float_round(bonus_basic_amount_volet_A, precision_digits=4))
        elif salary <= wage_higher_bound:
            coeff = self._rule_parameter('work_bonus_coeff')[key]
            result = bonus_basic_amount_volet_A - (coeff * (salary - wage_middle_bound))
            base_bonus_formula = self.env._(
                "Basic amount (%(basic_amount)s) - Coefficient (%(coeff)s) * (Reference salary (%(salary)s) - Threshold (%(bound)s))",
                basic_amount=float_round(bonus_basic_amount_volet_A, precision_digits=4), coeff=coeff,
                salary=float_round(salary, precision_digits=4),
                bound=float_round(wage_middle_bound, precision_digits=4))
        else:
            result = 0
            base_bonus_formula = self.env._(
                "Reference salary (%(salary)s) > %(bound)s: no bonus",
                salary=float_round(salary, precision_digits=4),
                bound=float_round(wage_higher_bound, precision_digits=4))

        self._l10n_be_update_work_bonus_explanation(
            localdict, basic, salary, result, base_bonus_formula,
            is_full_time, paid_days, total_days, paid_hours, total_hours)
        # 3. - Détermination du montant de la réduction (P)
        if is_full_time:
            if paid_days < total_days:  # If J=D result will remain same
                result = float_round(paid_days / total_days, precision_digits=2) * result  # P = (J/D) x R
        else:
            result = float_round(paid_hours / total_hours, precision_digits=2) * result  # P = (H/U) x R

        already_paid = localdict['l10n_be_month_line_values_by_payslip'][self]['EmpBonus.A']['sum']['total']
        carry_over = localdict['l10n_be_prev_month_line_values_by_payslip'][self]['EmpBonus.A.CO']['sum']['total']
        onss = result_rules['ONSS']['total'] + result_rules['ONSS_BONUS']['total'] + result_rules['ONSSRESTRUCTURING']['total']
        localdict['explanation_info'].update({'onss': -float_round(onss, precision_digits=4), 'calculated_bonus': float_round(result, precision_digits=4), 'already_paid': float_round(already_paid, precision_digits=4), 'carry_over': float_round(carry_over, precision_digits=4)})
        result = result - already_paid + carry_over
        remaining_bonus = max(0, result + onss)
        return {'result': min(-onss, result), 'remaining_bonus': remaining_bonus, 'explanation_info': localdict['explanation_info']}

    def _get_employment_bonus_employees_volet_B(self, localdict):
        self._l10n_be_init_work_bonus_explanation(localdict)
        result_rules = localdict['result_rules']
        prev_monthly_payslips = localdict['l10n_be_month_payslips_by_payslip'][self]
        worked_days_payslip = (self | prev_monthly_payslips).filtered('worked_days_line_ids')
        if not worked_days_payslip and not self.env.context.get('salary_simulation') and result_rules['SECTORIAL.BONUS']['total'] == 0:
            return {'result': 0, 'remaining_bonus': 0, 'explanation_info': localdict['explanation_info']}

        # S = (W / H) * U
        # W = salaire brut
        # H = le nombre d'heures de travail déclarées avec un code prestations 1, 3, 4, 5 et 20;
        # U = le nombre maximum d'heures de prestations pour le mois concerné dans le régime de travail concerné
        # J = The number of days declared for the worker with a performance (work) code of 1, 3, 4, 5, and 20
        # D = The maximum number of working (performance) days for the relevant month under the relevant work regime
        is_full_time = self.version_id.work_time_rate >= 1.0
        if self.env.context.get('salary_simulation') or not worked_days_payslip:
            paid_hours = total_hours = paid_days = total_days = 1
        else:
            excluded_codes = self._get_employment_bonus_excluded_codes()
            all_worked_days = worked_days_payslip.worked_days_line_ids.filtered(lambda wd: wd.code not in excluded_codes)
            ref_worked_days = worked_days_payslip[0].worked_days_line_ids.filtered(lambda wd: wd.code not in excluded_codes)
            paid_hours = round(sum(all_worked_days.filtered(lambda wd: wd.amount).mapped('number_of_hours')), 2)  # H
            total_hours = round(sum(ref_worked_days.mapped('number_of_hours')), 2)  # U
            paid_days = sum(all_worked_days.filtered(lambda wd: wd.amount).mapped('number_of_days'))  # J
            total_days = sum(ref_worked_days.mapped('number_of_days'))  # D
            if (not is_full_time and not paid_hours) or (is_full_time and not paid_days):
                return {'result': 0, 'remaining_bonus': 0, 'explanation_info': localdict['explanation_info']}

        # 1. - Détermination du salaire mensuel de référence (S)
        basic = result_rules['ONSS_BASE_TOTAL']['total'] - result_rules['HolPayRec']['total']
        if is_full_time:
            if paid_days < total_days:
                salary = float_round(basic / paid_days, precision_digits=2) * total_days  # S = (W/J) x D
            else:
                salary = basic  # S = W
        else:
            salary = float_round(basic / paid_hours, precision_digits=2) * total_hours  # S = (W/H) x U

        # 2. - Détermination du montant de base de la réduction (R)
        key = 'worker' if self.version_id.is_worker() else 'employee'
        bonus_basic_amount = self._rule_parameter('work_bonus_basic_amount')[key]
        wage_lower_bound = self._rule_parameter('work_bonus_reference_wage_low')
        wage_middle_bound = self._rule_parameter('l10n_be_work_bonus_reference_wage_middle')
        wage_higher_bound = self._rule_parameter('work_bonus_reference_wage_high')

        if salary <= wage_lower_bound:
            result = bonus_basic_amount
            base_bonus_formula = self.env._(
                "Reference salary (%(salary)s) <= %(bound)s: full basic amount (%(basic_amount)s)",
                salary=float_round(salary, precision_digits=4),
                bound=float_round(wage_lower_bound, precision_digits=4),
                basic_amount=float_round(bonus_basic_amount, precision_digits=4))
        elif salary <= wage_middle_bound:
            coeff = self._rule_parameter('l10n_be_work_bonus_coeff_low')[key]
            result = bonus_basic_amount - (coeff * (salary - wage_lower_bound))
            base_bonus_formula = self.env._(
                "Basic amount (%(basic_amount)s) - Coefficient (%(coeff)s) * (Reference salary (%(salary)s) - Threshold (%(bound)s))",
                basic_amount=float_round(bonus_basic_amount, precision_digits=4), coeff=coeff,
                salary=float_round(salary, precision_digits=4),
                bound=float_round(wage_lower_bound, precision_digits=4))
        elif salary <= wage_higher_bound:
            result = 0
            base_bonus_formula = self.env._(
                "Reference salary (%(salary)s) > %(bound)s: no bonus",
                salary=float_round(salary, precision_digits=4),
                bound=float_round(wage_middle_bound, precision_digits=4))
        else:
            result = 0
            base_bonus_formula = self.env._(
                "Reference salary (%(salary)s) > %(bound)s: no bonus",
                salary=float_round(salary, precision_digits=4),
                bound=float_round(wage_higher_bound, precision_digits=4))

        self._l10n_be_update_work_bonus_explanation(
            localdict, basic, salary, result, base_bonus_formula,
            is_full_time, paid_days, total_days, paid_hours, total_hours)
        # 3. - Détermination du montant de la réduction (P)
        if is_full_time:
            if paid_days < total_days:  # If J=D result will remain same
                result = float_round(paid_days / total_days, precision_digits=2) * result  # P = (J/D) x R
        else:
            result = float_round(paid_hours / total_hours, precision_digits=2) * result  # P = (H/U) x R

        already_paid = localdict['l10n_be_month_line_values_by_payslip'][self]['EmpBonus.B']['sum']['total']
        carry_over = localdict['l10n_be_prev_month_line_values_by_payslip'][self]['EmpBonus.B.CO']['sum']['total']
        onss = result_rules['ONSS']['total'] + result_rules['ONSS_BONUS']['total'] + result_rules['ONSSRESTRUCTURING']['total'] + result_rules['EmpBonus.A']['total']
        localdict['explanation_info'].update({'onss': -float_round(onss, precision_digits=4), 'calculated_bonus': float_round(result, precision_digits=4), 'already_paid': float_round(already_paid, precision_digits=4), 'carry_over': float_round(carry_over, precision_digits=4)})
        result = result - already_paid + carry_over
        remaining_bonus = max(0, result + onss)
        return {'result':  min(-onss, result), 'remaining_bonus': remaining_bonus, 'explanation_info': localdict['explanation_info']}

    # ref: https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/instructions/deductions/workers_reductions/workbonus.html
    def _get_employment_bonus_employees(self, localdict):
        self.ensure_one()
        result_rules = localdict['result_rules']
        if self.date_from >= date(2024, 4, 1):
            bonus_volet_A = result_rules['EmpBonus.A']['total']
            bonus_volet_B = result_rules['EmpBonus.B']['total']
            return {'result': bonus_volet_A + bonus_volet_B, 'remaining_bonus': 0}

        prev_monthly_payslips = localdict['l10n_be_month_payslips_by_payslip'][self]
        worked_days_payslip = (self | prev_monthly_payslips).filtered('worked_days_line_ids')
        if not worked_days_payslip and not self.env.context.get('salary_simulation') and result_rules['SECTORIAL.BONUS']['total'] == 0:
            return {'result': 0, 'remaining_bonus': 0}

        # S = (W / H) * U
        # W = salaire brut
        # H = le nombre d'heures de travail déclarées avec un code prestations 1, 3, 4, 5 et 20;
        # U = le nombre maximum d'heures de prestations pour le mois concerné dans le régime de travail concerné
        # J = The number of days declared for the worker with a performance (work) code of 1, 3, 4, 5, and 20
        # D = The maximum number of working (performance) days for the relevant month under the relevant work regime
        is_full_time = self.version_id.work_time_rate >= 1.0
        if self.env.context.get('salary_simulation') or not worked_days_payslip:
            paid_hours = 1
            total_hours = 1
            paid_days = 1
            total_days = 1
        else:
            excluded_codes = self._get_employment_bonus_excluded_codes()
            all_worked_days = worked_days_payslip.worked_days_line_ids.filtered(lambda wd: wd.code not in excluded_codes)
            ref_worked_days = worked_days_payslip[0].worked_days_line_ids.filtered(lambda wd: wd.code not in excluded_codes)
            paid_hours = round(sum(all_worked_days.filtered(lambda wd: wd.amount).mapped('number_of_hours')), 2)  # H
            total_hours = round(sum(ref_worked_days.mapped('number_of_hours')), 2)  # U
            paid_days = sum(all_worked_days.filtered(lambda wd: wd.amount).mapped('number_of_days'))  # J
            total_days = sum(ref_worked_days.mapped('number_of_days'))  # D
            if (not is_full_time and not paid_hours) or (is_full_time and not paid_days):
                return {'result': 0, 'remaining_bonus': 0}

        # 1. - Détermination du salaire mensuel de référence (S)
        basic = result_rules['ONSS_BASE_TOTAL']['total'] - result_rules['HolPayRec']['total']
        if is_full_time:
            if paid_days < total_days:
                salary = float_round(basic / paid_days, precision_digits=2) * total_days  # S = (W/J) x D
            else:
                salary = basic  # S = W
        else:
            salary = float_round(basic / paid_hours, precision_digits=2) * total_hours  # S = (W/H) x U

        # 2. - Détermination du montant de base de la réduction (R)
        key = 'worker' if self.version_id.is_worker() else 'employee'
        bonus_basic_amount = self._rule_parameter('work_bonus_basic_amount')[key]
        wage_lower_bound = self._rule_parameter('work_bonus_reference_wage_low')
        wage_higher_bound = self._rule_parameter('work_bonus_reference_wage_high')

        if self.date_from < date(2023, 7, 1):
            if salary <= wage_lower_bound:
                result = bonus_basic_amount
            elif salary <= wage_higher_bound:
                coeff = self._rule_parameter('work_bonus_coeff')[key]
                result = bonus_basic_amount - (coeff * (salary - wage_lower_bound))
            else:
                result = 0
        else:
            wage_middle_bound = self._rule_parameter('l10n_be_work_bonus_reference_wage_middle')
            if salary <= wage_lower_bound:
                result = bonus_basic_amount
            elif salary <= wage_middle_bound:
                coeff = self._rule_parameter('l10n_be_work_bonus_coeff_low')[key]
                result = bonus_basic_amount - (coeff * (salary - wage_lower_bound))
            elif salary <= wage_higher_bound:
                coeff = self._rule_parameter('work_bonus_coeff')[key]
                result = bonus_basic_amount - (coeff * (salary - wage_lower_bound))
            else:
                result = 0

        # 3. - Détermination du montant de la réduction (P)
        if is_full_time:
            if paid_days < total_days:  # If J=D result will remain same
                result = float_round(paid_days / total_days, precision_digits=2) * result  # P = (J/D) x R
        else:
            result = float_round(paid_hours / total_hours, precision_digits=2) * result  # P = (H/U) x R

        carry_over = localdict['l10n_be_prev_month_line_values_by_payslip'][self]['EmpBonus.Total.CO']['sum']['total']
        result += carry_over
        if self.date_from < date(2024, 4, 1):
            already_paid = localdict['l10n_be_month_line_values_by_payslip'][self]['EmpBonus.1']['sum']['total']
            result -= already_paid
        onss = result_rules['ONSS']['total'] + result_rules['ONSS_BONUS']['total'] + result_rules['ONSSRESTRUCTURING']['total']
        remaining_bonus = max(0, result + onss)
        return {'result': min(-onss, result), 'remaining_bonus': remaining_bonus}

    def _get_termination_children_exoneration(self, children, taxable_reference_salary):
        children_exoneration = self._rule_parameter('holiday_pay_pp_exoneration')
        total = 0
        if children > 0 and taxable_reference_salary <= children_exoneration.get(children, children_exoneration[12]):
            total += children_exoneration.get(children, children_exoneration[12]) - taxable_reference_salary
        return total

    def _get_withholding_taxes_after_child_allowances(self, rates, gross, apply_reduction=True):
        version = self.version_id
        if self.date_to.year >= 2024 and rates == self._rule_parameter('termination_fees_pp_rates'):
            yearly_revenue = gross
        else:
            monthly_revenue = version._get_contract_wage()
            deduct_rate = self._get_starterjob_deduction_rate()
            if deduct_rate != 0:
                monthly_revenue *= (100 - deduct_rate) / 100
            # Count ANT in yearly remuneration
            if version.internet:
                monthly_revenue += self._rule_parameter('bik_internet_amount')
            if version.mobile:
                monthly_revenue += self._rule_parameter('bik_phone_sub_amount')
            if version.laptop:
                monthly_revenue += self._rule_parameter('bik_laptop_amount')
            if version.tablet:
                monthly_revenue += self._rule_parameter('bik_tablet_amount')
            if version.mobile_amount:
                monthly_revenue += self._rule_parameter('bik_phone_amount')

            yearly_revenue = monthly_revenue * (1 - 0.1307) * 12.0

            if version.transport_mode_car:
                if 'vehicle_id' in self:
                    yearly_revenue += self.vehicle_id._get_car_atn(date=self.date_from)
                else:
                    yearly_revenue += version.car_atn
        children_exoneration = self._rule_parameter('holiday_pay_pp_exoneration')
        # Exoneration
        children = version.dependent_children
        if children > 0 and yearly_revenue <= children_exoneration.get(children, children_exoneration[12]):
            yearly_revenue -= children_exoneration.get(children, children_exoneration[12]) - yearly_revenue
            yearly_revenue = max(yearly_revenue, 0)

        children_reduction = self._rule_parameter('holiday_pay_pp_rate_reduction')

        rate = self._l10n_be_find_withholding_tax_rates(yearly_revenue, rates)
        withholding_tax_amount = gross * rate
        # Reduction
        if (apply_reduction and
            children > 0 and
            yearly_revenue <= children_reduction.get(children, children_reduction[5])[1]
        ):
            withholding_tax_amount *= (1 - children_reduction.get(children, children_reduction[5])[0] / 100.0)

        return - withholding_tax_amount

    def _get_theoretical_exceptional_monthly_withholding_tax(self, localdict, exceptional_gross):
        """ Estimate what the monthly professional withholding tax would be on regular contract income topped up by one twelfth of the exceptional gross. """
        version = self.version_id
        monthly_contract_wage = version._get_contract_wage()

        # Add each recurring taxable benefit in kind to the monthly contract wage.
        if version.internet:
            monthly_contract_wage += self._rule_parameter('bik_internet_amount')
        if version.mobile:
            monthly_contract_wage += self._rule_parameter('bik_phone_sub_amount')
        if version.laptop:
            monthly_contract_wage += self._rule_parameter('bik_laptop_amount')
        if version.tablet:
            monthly_contract_wage += self._rule_parameter('bik_tablet_amount')
        if version.mobile_amount:
            monthly_contract_wage += self._rule_parameter('bik_phone_amount')

        # The 13.07 percent personal ONSS contribution is deducted to get the monthly taxable base.
        monthly_taxable = monthly_contract_wage * (1 - 0.1307)
        # The exceptional gross is already net of ONSS at this point, so dividing by 12 gives the monthly share to add.
        monthly_taxable += exceptional_gross / 12.0
        # The bareme brackets work on a yearly basis, so the monthly base is multiplied back up.
        yearly_taxable_gross = monthly_taxable * 12.0

        # The company car ATN is not subject to ONSS, so it is added directly to the yearly taxable base.
        # The version field is used on purpose, as the transport deduction below reads the very same one.
        if version.transport_mode_car:
            yearly_taxable_gross += version.car_atn

        # The taxable share of private car kilometre reimbursements is annualised and included here.
        if version.private_car_employee_kilometer:
            car_result, car_result_qty, car_result_rate = self._get_be_private_car_reimursement_amount(localdict)
            yearly_taxable_gross += car_result * car_result_qty * car_result_rate / 100 * 12

        # Flat-rate professional fees, same lookup as the F_PROFESSIONAL_FEES rule, are deducted before the bareme
        # applies. This deduction is always granted, so skipping it would overstate the theoretical tax.
        joint_committee_code = self.l10n_be_joint_committee_id.egov3_code or '200'
        fees_max = (
            self._rule_parameter(f'flat_rate_professional_fees_max_cp{joint_committee_code}', raise_if_not_found=False)
            or self._rule_parameter('flat_rate_professional_fees_max_cp200', raise_if_not_found=False)
            or 0
        )
        fees_rate = (
            self._rule_parameter(f'flat_rate_professional_fees_rate_cp{joint_committee_code}', raise_if_not_found=False)
            or self._rule_parameter('flat_rate_professional_fees_rate_cp200', raise_if_not_found=False)
            or 0
        )
        yearly_net_taxable = yearly_taxable_gross - min(yearly_taxable_gross * fees_rate, fees_max)
        # The transport withholding tax exemption offsets car ATN and private car reimbursements, capped at the
        # gross taxable base, same as the TRANSPORT_TAX_DED rule.
        yearly_net_taxable -= min(yearly_taxable_gross, self._get_be_withholding_taxes_transport_deduction(localdict))

        # Run the bareme on the full yearly base, then remove the marital and family charge deductions.
        yearly_theoretical_tax = self._compute_basic_bareme(yearly_net_taxable)
        yearly_theoretical_tax -= self._get_be_withholding_taxes_marital_deduction()
        yearly_theoretical_tax -= self._get_be_withholding_taxes_family_charges_deduction()

        # Floor at zero and divide by twelve, as a negative monthly tax makes no sense.
        return max(0.0, yearly_theoretical_tax) / 12.0

    def _is_exceptional_withholding_tax_exempted(self, localdict, exceptional_gross):
        """
        Return True when the flat-rate professional withholding tax on double holiday or 13th month pay can be skipped.
        SSCUM for the year and the theoretical monthly tax on regular income must both be zero for the exemption to fire.
        The marital and family charge deductions reused by the theoretical computation cover every scale, so the
        exemption applies to any employee, not only Scale II ones.
        """
        version = self.version_id
        # A CP999 executive can have their monthly tax set as a fixed amount or as a rate on the whole base.
        is_cp999 = version.l10n_be_egov3_code == '999'
        has_fixed_withholding_tax = version.l10n_be_withholding_tax_type == 'fixed' and version.l10n_be_withholding_tax_amount
        has_withholding_tax_rate = version.l10n_be_withholding_tax_type == 'percentage' and version.l10n_be_withholding_tax_percentage
        pays_flat_withholding_tax = is_cp999 and (has_fixed_withholding_tax or has_withholding_tax_rate)

        # Students, PFI employees and those CP999 executives do not pay their monthly tax through the bareme,
        # so the theoretical computation says nothing about them and no exemption is granted.
        if version.is_student() or version.is_PFI() or pays_flat_withholding_tax:
            return False

        # Check that no cumulated professional withholding tax (SSCUM) was paid on BEMONTHLY payslips this year.
        # The year key holds every validated payslip of the year, so the monthly structure is filtered here.
        year_payslips = localdict['l10n_be_year_payslips_by_payslip'][self].filtered(
            lambda p: p.struct_id.code == 'BEMONTHLY',
        )
        if year_payslips:
            line_values = year_payslips._get_line_values(['PPTOTAL'], compute_sum=True)
            # PPTOTAL negates the PP category, so it is already the positive amount actually withheld.
            cumulated_professional_withholding_tax = line_values['PPTOTAL']['sum']['total']
            if not float_is_zero(cumulated_professional_withholding_tax, precision_digits=2):
                # Even one monthly payslip with a positive withholding tax is enough to block the exemption.
                return False

        # Simulate what the monthly tax would be on regular income topped up by one twelfth of the exceptional gross.
        theoretical_monthly_tax = self._get_theoretical_exceptional_monthly_withholding_tax(localdict, exceptional_gross)
        # A zero theoretical tax means the employee genuinely owes nothing on this exceptional payment.
        return theoretical_monthly_tax <= 0

    def _get_be_double_holiday_withholding_taxes(self, localdict):
        self.ensure_one()
        # See: https://www.securex.eu/lex-go.nsf/vwReferencesByCategory_fr/52DA120D5DCDAE78C12584E000721081?OpenDocument

        gross = localdict['categories']['DH_WITHHOLDING_BASE']
        if gross <= 0:
            return 0
        # Skip the flat-rate tax entirely if the exemption conditions are met.
        if self._is_exceptional_withholding_tax_exempted(localdict, gross):
            return 0
        rates = self._rule_parameter('holiday_pay_pp_rates')

        return self._get_withholding_taxes_after_child_allowances(rates, gross)

    def _get_thirteen_month_withholding_taxes(self, localdict):
        self.ensure_one()
        # See: https://www.securex.eu/lex-go.nsf/vwReferencesByCategory_fr/52DA120D5DCDAE78C12584E000721081?OpenDocument

        gross = localdict['categories']['BONUS_WITHHOLDING_BASE']
        if gross <= 0:
            return 0
        # Skip the flat-rate tax entirely if the exemption conditions are met.
        if self._is_exceptional_withholding_tax_exempted(localdict, gross):
            return 0
        rates = self._rule_parameter('exceptional_allowances_pp_rates')

        return self._get_withholding_taxes_after_child_allowances(rates, gross)

    def _is_cp200_annual_sectorial_bonus_eligible(self, localdict=None):
        self.ensure_one()
        if localdict:
            line_values = localdict['l10n_be_month_line_values_by_payslip'][self]
            if line_values['SECTORIAL.BONUS']['sum']['total'] > 0:
                return False
        EXCLUDED_EMPLOYER_DMFA_CODES = {'024', '026', '044', '054', '114'}
        if (
            self.version_id.l10n_be_reason_code == 355
            or self.date_to < date(2023, 1, 1)
            or self.payroll_config_id.l10n_be_employer_category_id.dmfa_code in EXCLUDED_EMPLOYER_DMFA_CODES
        ):
            return False
        if self.date_to.month == 6:
            return True
        return self._l10n_be_is_last_payslip()

    def _get_cp200_annual_bonus_reference_period(self):
        """
        Reference period of the CP200 Annual Sectorial Bonus: June 1st Y-1 → May 31st Y.

        On a June payslip, the bonus pays the reference period that just ended. On
        a departure payslip, it pays the running reference period the departure
        falls into.
        """
        self.ensure_one()
        year = self.date_to.year if self.date_to.month == 6 else self.date_to.year + 1
        return date(year - 1, 6, 1), date(year, 5, 31)

    def _get_cp200_annual_bonus_prorata(self, work_entries=None):
        """
        Returns the prorata coefficient for the CP200 Annual Sectorial Bonus.

        Computed per version, then summed:
            sum of (ref_calendar_days / C) * (assimilated_hours / H_ref_v)

        Per version:
        - ref_calendar_days: calendar days under that version during reference period (June 1 Y-1 → May 31 Y)
        - total_calendar_days: total calendar days in reference period (365 or 366)
        - assimilated_hours: assimilated hours for that version (paid + maternity/paternity)
        - full_time_hours: reference full-time hours from version's reference_calendar_id
        """
        self.ensure_one()
        ref_start, ref_end = self._get_cp200_annual_bonus_reference_period()

        total_calendar_days = (ref_end - ref_start).days + 1  # 365 or 366

        versions = self.employee_id._get_versions_with_contract_overlap_with_period(ref_start, ref_end)
        if not versions:
            return 0.0

        # https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/instructions/fill_in_dmfa/dmfa_fillinrules/servicedatadeclaration/workingtimecodification.html
        excluded = self.env['hr.work.entry.type'].search([('l10n_be_egov3_code', 'not in', ['1101001', '1202001', '1202003', '1203001', '1203002', '1203003',
                                                                                            '1204001', '1204002', '1204003', '1205001', '1205002', '1205003',
                                                                                            '1205005', '1205006', '1206002', '1206003', '1206004', '1209002',
                                                                                            '1298001', '1298004', '1298006', '1298099', '2210002', '2210004',
                                                                                            '2210005', '2210006'])])
        maternity_leave = self.env.ref('hr_work_entry.l10n_be_work_entry_type_maternity')
        paternity_leave = self.env.ref('hr_work_entry.l10n_be_work_entry_type_paternity_legal')
        final_excluded_ids = (excluded - maternity_leave - paternity_leave).ids

        prorata = 0.0
        work_entries_vals = work_entries or versions.filtered('resource_calendar_id').generate_work_entries(ref_start, ref_end)
        for v in versions:
            v_start = max(v.date_start, ref_start)
            # date_end ignores departure_date, which is the only end date set until the departure is applied
            v_end = min(v.date_end or self.employee_id.departure_date or ref_end, ref_end)
            if v_end < v_start:
                continue

            ref_calendar_days = (v_end - v_start).days + 1

            ref_calendar = v._get_reference_calendar()
            if not ref_calendar:
                continue
            v_start_dt = datetime.combine(v_start, time.min)
            v_end_dt = datetime.combine(v_end, time.max)

            full_time_hours = ref_calendar.get_work_hours_count(v_start_dt, v_end_dt, compute_leaves=False)
            if not full_time_hours:
                continue

            all_hours = v.get_work_hours(v_start, v_end, work_entries_vals)
            assimilated_hours = sum(
                hours for (work_entry_type_id, _options), hours in all_hours.items()
                if work_entry_type_id.id not in final_excluded_ids)
            if total_calendar_days == 0 or full_time_hours == 0:
                continue
            prorata += (ref_calendar_days / total_calendar_days) * (assimilated_hours / full_time_hours)

        return prorata

    def _get_termination_fees_withholding_taxes(self, localdict):
        # See: https://www.securex.eu/lex-go.nsf/vwReferencesByCategory_fr/52DA120D5DCDAE78C12584E000721081?OpenDocument
        if self.date_from.year >= 2024:
            self.ensure_one()

            rates = self._rule_parameter('termination_fees_pp_rates')
            gross = localdict['categories']['TERMINATION_WITHHOLDING_BASE']

            return self._get_withholding_taxes_after_child_allowances(rates, gross, apply_reduction=False)

        else:
            yearly_tax_amount = self._get_be_withholding_taxes_basic_bareme(localdict)
            yearly_tax_amount -= self._get_be_withholding_taxes_marital_deduction()
            yearly_tax_amount -= self._get_be_withholding_taxes_family_charges_deduction()
            return -max(0, float_round(yearly_tax_amount / 12.0, precision_rounding=0.01, rounding_method='DOWN'))

    def _get_replacement_revenue_withholding_taxes(self, localdict):
        self.ensure_one()

        rates = self._rule_parameter('exceptional_allowances_pp_rates')
        gross = localdict['categories']['REPLACEMENT_REVENUE_BASE']
        return self._get_withholding_taxes_after_child_allowances(rates, gross)

    def _l10n_be_get_warrant_atn_rate(self, localdict):
        # The optional payslip input overrides the legal percentage (18%)
        atn_percent_input = localdict['inputs'].get('WARRANT_ATN_PERCENT')
        if atn_percent_input and atn_percent_input.amount:
            return atn_percent_input.amount
        return self._rule_parameter('warrant_atn_percentage')

    def _get_warrant_withholding_taxes(self, localdict):
        self.ensure_one()

        rates = self._rule_parameter('exceptional_allowances_pp_rates')
        gross = localdict['categories']['WARRANT_WITHHOLDING_BASE']
        return self._get_withholding_taxes_after_child_allowances(rates, gross)

    def _get_withholding_reduction(self, localdict):
        self.ensure_one()
        result_rules = localdict['result_rules']
        categories = localdict['categories']
        previous_payslips_line_values = localdict['l10n_be_month_line_values_by_payslip'][self]
        reduction_explanation = ''
        if result_rules['EmpBonus.1']:
            bonus_volet_A_rate = self.env['hr.rule.parameter']._get_parameter_from_code('work_bonus_volet_A_rate', date=self.date_to, raise_if_not_found=False) or 0.3314
            if self.date_from >= date(2024, 4, 1):
                bonus_volet_A = localdict['result_rules']['EmpBonus.A']['total']
                bonus_volet_B = localdict['result_rules']['EmpBonus.B']['total']
                bonus_volet_B_rate = self.env['hr.rule.parameter']._get_parameter_from_code('work_bonus_volet_B_rate', date=self.date_to, raise_if_not_found=False) or 0.5254
                if previous_payslips_line_values:
                    bonus_volet_A += previous_payslips_line_values['EmpBonus.A']['sum']['total']
                    bonus_volet_B += previous_payslips_line_values['EmpBonus.B']['sum']['total']
                reduction = bonus_volet_A * bonus_volet_A_rate + bonus_volet_B * bonus_volet_B_rate
                reduction_explanation = self.env._(
                    "Reduction (%(value)s) = EmpBonus.A (%(bonus_volet_A)s) * Rate.A (%(bonus_volet_A_rate)s) + EmpBonus.B (%(bonus_volet_B)s) * Rate.B (%(bonus_volet_B_rate)s)\n",
                    value=float_round(reduction, precision_digits=2),
                    bonus_volet_A=float_round(bonus_volet_A, precision_digits=2),
                    bonus_volet_B=float_round(bonus_volet_B, precision_digits=2),
                    bonus_volet_A_rate=float_round(bonus_volet_A_rate, precision_digits=2),
                    bonus_volet_B_rate=float_round(bonus_volet_B_rate, precision_digits=2)
                )
            else:
                bonus = result_rules['EmpBonus.1']['total']
                if previous_payslips_line_values:
                    bonus += previous_payslips_line_values['EmpBonus.1']['sum']['total']
                reduction = bonus * bonus_volet_A_rate
                reduction_explanation = self.env._(
                    "Reduction (%(value)s) = EmpBonus.1 (%(bonus)s) * Rate (%(bonus_volet_A_rate)s)\n",
                    value=float_round(reduction, precision_digits=2),
                    bonus=float_round(bonus, precision_digits=2),
                    bonus_volet_A_rate=float_round(bonus_volet_A_rate, precision_digits=2),
                )

            explanation_info = {'reduction_explanation': reduction_explanation, 'reduction': float_round(reduction, precision_digits=2), 'ded_pp': float_round(abs(categories['PP']), precision_digits=2)}
            return min(abs(categories['PP']), reduction), explanation_info
        return 0.0, {'reduction_explanation': reduction_explanation, 'reduction': 0.0, 'ded_pp': float_round(abs(categories['PP']), precision_digits=2)}

    def _get_impulsion_plan_amount(self, localdict):

        def _get_working_coefficient(payslips, date_from, date_to):
            full_time_calendar = (
                    self.employee_id.reference_calendar_id
                    or self.structure_type_id.default_resource_calendar_id
            )
            numerator = sum(wd.number_of_hours for wd in payslips.mapped('worked_days_line_ids') if wd.amount > 0)
            denominator = full_time_calendar.get_work_hours_count(
                fields.Datetime.to_datetime(date_from),
                fields.Datetime.to_datetime(date_to) + relativedelta(days=1),
            )
            return numerator / denominator if denominator else 0

        def _get_deduction_value_from_parameter(param_code, value):
            parameter_values = self.env['hr.rule.parameter']._get_parameter_from_code(param_code, date=impulsion_start_date) or 0.0
            for interval_max_number, discount_amount in parameter_values:
                if value <= interval_max_number:
                    return discount_amount
            return 0

        self.ensure_one()
        impulsion_start_date = self.version_id.contract_date_start
        if not impulsion_start_date:
            return 0, 0
        month_end = self.date_to
        number_of_months = (month_end.year - impulsion_start_date.year) * 12 + (month_end.month - impulsion_start_date.month)
        coefficient = _get_working_coefficient(self, self.date_from, self.date_to)

        if self.version_id.l10n_be_impulsion_plan == '25yo':
            if self.employee_id._get_age(impulsion_start_date) < 25:
                theoretical_amount = _get_deduction_value_from_parameter('impulsion25_deduction', number_of_months)
                return theoretical_amount, min(coefficient, 1.0) * 100
        if self.version_id.l10n_be_impulsion_plan == '12mo':
            theoretical_amount = _get_deduction_value_from_parameter('impulsion12_deduction', number_of_months)
            return theoretical_amount, min(coefficient, 1.0) * 100
        return 0, 0

    def _get_onss_restructuring(self, localdict):
        self.ensure_one()
        # Source: https://www.onem.be/fr/documentation/feuille-info/t115

        # 1. Grant condition
        # A worker who has been made redundant following a restructuring benefits from a reduction in his personal contributions under certain conditions:
        # - The engagement must take place during the validity period of the reduction card. The reduction card is valid for 9 months, calculated from date to date, following the termination of the employment contract.
        # - The gross monthly reference salary does not exceed
        # o 3.071.90: if the worker is under 30 years of age at the time of entry into service
        # o 4,504.93: if the worker is at least 30 years old at the time of entry into service
        # 2. Amount of reduction
        # Lump sum reduction of € 133.33 per month (full time - full month) in personal social security contributions.
        # If the worker does not work full time for a full month or if he works part time, this amount is reduced proportionally.

        # So the reduction is:
        # 1. Full-time worker: P = (J / D) x 133.33
        # - Full time with full one month benefits: € 133.33

        # Example the worker entered service on 02/01/2021 and worked the whole month
        # - Full time with incomplete services: P = (J / D) x 133.33
        # Example: the worker entered service on February 15 -> (10/20) x 133.33 = € 66.665
        # P = amount of reduction
        # J = the number of worker's days declared with a benefit code 1, 3, 4, 5 and 20 .;
        # D = the maximum number of days of benefits for the month concerned in the work scheme concerned.

        # 2. Part-time worker: P = (H / U) x 133.33
        # Example: the worker starts 02/01/2021 and works 19 hours a week.
        # (76/152) x 133.33 = € 66.665
        # Example: the worker starts 02/15/2021 and works 19 hours a week.
        # (38/155) x 133.33 = 33.335 €

        # P = amount of reduction
        # H = the number of working hours declared with a service code 1, 3, 4, 5 and 20;
        # U = the number of monthly hours corresponding to D.

        # 3. Duration of this reduction
        # The benefit applies to all periods of occupation that fall within the period that:
        # starts to run on the day you start your first occupation during the validity period of the restructuring reduction card;
        # and which ends on the last day of the third quarter following the start date of this first occupation.
        # 4. Formalities to be completed
        # The employer deducts the lump sum from the normal amount of personal contributions when paying the remuneration.
        # The ONEM communicates to the ONSS the data concerning the identification of the worker and the validity date of the card.

        # 5. Point of attention
        # If the worker also benefits from a reduction in his personal contributions for low wages, the cumulation between this reduction and that for restructuring cannot exceed the total amount of personal contributions due.

        # If this is the case, we must first reduce the restructuring reduction.

        # Example:
        # - personal contributions = 200 €
        # - restructuring reduction = € 133.33
        # - low salary reduction = 100 €

        # The total amount of reductions exceeds the contributions due. We must therefore first reduce the restructuring reduction and then the balance of the low wage reduction.
        if not self.worked_days_line_ids:
            return 0, {'restruct_amount': 0.0, 'restruct_ratio': 0.0}

        employee = self.version_id.employee_id
        if employee._get_age(employee.contract_date_start) < 30:
            threshold = self._rule_parameter('onss_restructuring_before_30')
        else:
            threshold = self._rule_parameter('onss_restructuring_after_30')

        salary = localdict['result_rules']['BASIC']['total']
        if salary > threshold:
            return 0, {'restruct_amount': 0.0, 'restruct_ratio': 0.0}

        amount = self._rule_parameter('onss_restructuring_amount')

        if self.version_id.is_worker():
            amount = amount * 1.08

        paid_hours = sum(self.worked_days_line_ids.filtered(lambda wd: wd.amount).mapped('number_of_hours'))
        total_hours = sum(self.worked_days_line_ids.mapped('number_of_hours'))
        ratio = paid_hours / total_hours if total_hours else 0

        start = employee.restructuring_reduction_date_start
        end = self.date_to

        quarter_start, _ = date_utils.get_quarter(start)
        expiration_date = quarter_start + relativedelta(months=9)

        if start <= end < expiration_date:
            result = amount * ratio
            return result, {'restruct_amount': float_round(amount, precision_digits=2), 'restruct_ratio': float_round(ratio, precision_digits=2)}

        return 0, {'restruct_amount': float_round(amount, precision_digits=2), 'restruct_ratio': 0.0}

    def _get_onss_rates(self, worker_code=None, contribution_type='0'):
        self.ensure_one()
        employer_class = self.payroll_config_id.l10n_be_employer_category_id.dmfa_code
        worker_code = worker_code or self.version_id.l10n_be_worker_code_id.dmfa_code
        rates = self._rule_parameter(f'l10n_be_onss_rates_{employer_class}_{worker_code}_{contribution_type}',
                                    self.date_to, raise_if_not_found=False)
        return rates or {"personal_rate": 0, "employer_rate": 0, "salary_moderation_rate": 0, "total_rate": 0}

    def _with_salary_moderation(self):
        self.ensure_one()
        contribution_type = '1' if self.version_id.is_worker() else '0'
        return bool(self._get_onss_rates(contribution_type=contribution_type)['salary_moderation_rate'])

    def _get_owedness_codes(self, contribution_worker_code):
        self.ensure_one()
        employer_class = self.payroll_config_id.l10n_be_employer_category_id.dmfa_code
        worker_code = self.version_id.l10n_be_worker_code_id.dmfa_code
        combinations = self._rule_parameter(f'l10n_be_onss_combinations_{employer_class}_{worker_code}',
                                            self.date_to, raise_if_not_found=False)
        return combinations.get(contribution_worker_code, []) if combinations else []

    def _should_apply_owedness(self, contribution_worker_code, owedness):
        self.ensure_one()
        match owedness:
            case '0':  # apply to everybody
                return True
            case '1':  # do not apply for employee with Dimona Category ALT that are younger than 18 year old
                return (self.employee_id.l10n_be_dimona_category != 'alt' or
                        self.employee_id._get_age(self.date_to + relativedelta(month=1, day=1, days=-1)) >= 18)
            case '2':  # conditional, the condition is specific per rule
                return True
            case '6':  # rule 809 applies only if commercial purpose, 811 applies if no commercial purpose
                return ((contribution_worker_code == '809' and self.payroll_config_id.l10n_be_ffe_employer_type == 'C') or
                        (contribution_worker_code == '811' and self.payroll_config_id.l10n_be_ffe_employer_type == 'B'))
            case '7':  # not for occasional worker (Dimona Category = EXT)
                return self.employee_id.l10n_be_dimona_category != 'ext'
            case '8' | '9':  # public sector, not yet handled
                return False
            case _:
                return False

    def _should_apply_onss_contribution(self, contribution_worker_code):
        self.ensure_one()
        owedness_codes = self._get_owedness_codes(contribution_worker_code)
        return (bool(owedness_codes) and
                all(self._should_apply_owedness(contribution_worker_code, owedness) for owedness in owedness_codes))

    def _must_contribute_retirement_fund(self):
        self.ensure_one()
        retirement_date = self.version_id.l10n_be_retirement_date
        quarter_start = date_utils.get_quarter(self.date_from)[0]
        return not retirement_date or retirement_date >= quarter_start or self.version_id.l10n_be_contribute_to_fse

    def _get_number_repr_fees_units(self, unit, localdict):
        """
        This function is aimed at returning the effective amount of units
        that allow representation fees.

        The unit keyword can be either 'days' or 'hours' and determines
        wether we return how many days or how many hours admit
        representation fees.
        """
        self.ensure_one()
        if unit == 'days':
            field = 'number_of_days'
        elif unit == 'hours':
            field = 'number_of_hours'
        else:
            return 0
        benefit_category = self.env.ref('l10n_be_hr_payroll.REPRESENTATION_FEES')
        result = 0
        # Representation fees aren't paid if there's no basic pay or every day is an absence
        if localdict['result_rules']['BASIC']['total'] and (not all((days.mapped('work_entry_type_id.count_as') == ['absence']) for days in localdict['worked_days'].values())):
            def filter(wdl): return benefit_category.id in wdl.work_entry_type_id.category_ids.mapped('id')
            result = sum(self.worked_days_line_ids.filtered(filter).mapped(field))
        return result

    def _get_repr_fees_proration_rate(self, localdict):
        if self.env.context.get('salary_simulation_full_time'):
            return 100

        # The rate is the percentage of the expected work time according to the full-time calendar for the company that is actually being worked
        number_of_hours_worked = self._get_number_repr_fees_units('hours', localdict)
        expected_number_of_hours = localdict['work_hours_by_calendar_and_period'][self.version_id._get_reference_calendar(), self.date_from, self.date_to]
        return min(((number_of_hours_worked / expected_number_of_hours) * 100), 100)

    def _get_holiday_pay_recovery(self, localdict):
        """
            See: https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/intermediates#intermediate_row_196b32c7-9d98-4233-805d-ca9bf123ff48

            When an employee changes employer, he receives the termination pay and a vacation certificate
            stating his vacation rights. When he subsequently takes vacation with his new employer, the latter
            must, when paying the simple vacation pay, take into account the termination pay that the former
            employer has already paid.

            From an exchange of letters with the SPF ETCS and the Inspectorate responsible for the control of
            social laws, it turned out that when calculating the simple vacation pay, the new employer must
            deduct the exit pay based on the number of vacation days taken. The rule in the ONSS instructions
            according to which the new employer must take into account the exit vacation pay only once when the
            employee takes his main vacation is abolished.

            When the salary of an employee with his new employer is higher than the salary he had with his
            previous employer, his new employer will have, each time he takes vacation days, to make a
            calculation to supplement the nest egg. exit from these days up to the amount of the simple vacation
            pay to which the worker is entitled.

            Concretely:

            2020 vacation certificate (full year):
            - simple allowance 1,917.50 EUR
                - this amounts to 1917.50 / 20 EUR = 95.875 EUR per day of vacation
                - holidays 2021, for example when taking 5 days in April 2021
            - monthly salary with the new employer: 3000.00 EUR / month
                - simple nest egg:
                     - remuneration code 12: 5/20 x 1917.50 = 479.38 EUR
                     - remuneration code 1: (5/22 x 3000.00) - 479.38 = 202.44 EUR
                - ordinary days for the month of April:
                    - remuneration code 1: 17/22 x 3000.00 = 2318.18 EUR
                    - The examples included in the ONSS instructions will be adapted in the next publication.

            We now recover only 90% of the calculated amount.
            Additionally, the recovered amount may exceed the initial amount to recover
            if the employee's current salary is higher than their previous one!
        """
        self.ensure_one()
        explanation_info = {'remaining_day_amount': 0.0, 'holiday_amount': 0.0}
        worked_days = localdict['worked_days']
        if '016.00' not in worked_days or not sum(worked_days['016.00'].mapped('amount')):
            return 0, explanation_info

        number_of_days_allocated = sum(
            self.employee_id.l10n_be_holiday_attest_ids
                .filtered(lambda att: att.year == self.date_from.year - 1)
                .mapped("days_to_allocate"),
        )

        all_payslips_during_civil_year = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', date(self.date_from.year, 1, 1)),
            ('date_to', '<=', date(self.date_from.year, 12, 31)),
            ('state', 'in', ['validated', 'paid']),
        ])
        paid_leave_days = all_payslips_during_civil_year._get_worked_days_line_values(['016.00'], ['number_of_days'], True)['016.00']['sum']['number_of_days']
        remaining_days = number_of_days_allocated - paid_leave_days
        if remaining_days <= 0:
            return 0, explanation_info
        if self.wage_type == 'hourly':
            employee_hourly_cost = self.version_id.hourly_wage
        else:
            if self.date_from.year < 2024:
                employee_hourly_cost = self.version_id._get_contract_wage() / self.sum_worked_hours
            else:
                hours_per_week = self.version_id._l10n_be_get_hours_per_week(self.date_from.year)
                if not hours_per_week:
                    return 0, explanation_info
                weekly_wage = self.version_id._get_contract_wage() * 3 / 13
                employee_hourly_cost = weekly_wage / hours_per_week
        remaining_day_amount = remaining_days * employee_hourly_cost * self.version_id.resource_calendar_id.hours_per_day
        paid_leave_data = self._get_worked_days_line_values(['016.00'], ['amount', 'number_of_hours'], True)['016.00']['sum']
        holiday_amount = min(paid_leave_data['amount'], employee_hourly_cost * paid_leave_data['number_of_hours'])
        explanation_info.update({'remaining_day_amount': float_round(remaining_day_amount, precision_digits=2), 'holiday_amount': float_round(holiday_amount, precision_digits=2)})
        return - min(remaining_day_amount, holiday_amount) * 0.9, explanation_info

    def _get_termination_n_basic_double(self, localdict):
        self.ensure_one()
        result_qty = 1
        result_rate = 6.8
        result = localdict['payslip']._get_input_line_amount('GROSS_REF')
        date_from = self.date_from
        if self.struct_id.code == "BEHOLN1":
            existing_double_pay = self.env['hr.payslip'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', 'in', ['validated', 'paid']),
                ('struct_id', '=', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id),
                ('date_from', '>=', date(date_from.year, 1, 1)),
                ('date_to', '<=', date(date_from.year, 12, 31)),
            ])
            if existing_double_pay:
                result = 0
        return (result_qty, result_rate, result)

    def _get_upcoming_public_holiday_count(self, public_holidays):
        self.ensure_one()
        if not public_holidays:
            return 0

        version = self.version_id
        end_date = False
        if not version.employee_id.version_ids.filtered(lambda v: v.date_start > (version.date_end or self.employee_id.departure_date)):
            end_date = self.employee_id.departure_date or version.contract_date_end
        if not end_date or not (self.date_from <= end_date <= self.date_to):
            return 0

        number_of_upcoming_public_holidays = 0

        for public_holiday in public_holidays:
            upcoming_period = 30 if version.contract_date_start + relativedelta(months=1) <= end_date else 15
            if (public_holiday.date_from.date() - version.contract_date_start).days >= 15\
                and (0 < (public_holiday.date_from.date() - end_date).days <= upcoming_period):
                number_of_upcoming_public_holidays += 1

        return number_of_upcoming_public_holidays

    def _get_double_pay_to_recover(self):
        self.ensure_one()

        attests = self.employee_id.l10n_be_holiday_attest_ids.filtered(lambda a: a.year == self.date_from.year - 1)

        return sum(attest._get_double_holiday_pay_cap(self.date_from) for attest in attests)

    def _get_holiday_pay_regularization(self, localdict):
        """Compute the annual holiday pay regularization for previous year's holiday attestations (N-1).

        Throughout the year, taking legal leave (`016.00`) deducts 90% of the hourly wage via the
        `HolPayRec` salary rule up to the earned attestation hours. During year-end regularization
        (typically December), this method calculates the final adjustment required to reach 100%
        of the gross leave wage equivalent, capped by the total simple holiday pay attestation limit
        (`amount_to_recover`).

        Why Ground-Truth Chronological Recomputation:
            Legacy databases may contain payslips that deducted recovery at 100% instead of 90% (or used
            custom rates). Relying on DB line totals (`recovered / 0.9`) on mixed histories distorts the
            100% wage base calculation.

            To solve this cleanly without trusting historical line values:
            1. `actual_recovered_amount` reads what was *actually deducted* from the employee on DB lines.
            2. `total_100_pct_wage` recomputes the true 100% gross leave wage chronologically
               across past payslips using each payslip's contract version wage (`version.wage`) and the
               Belgian hourly wage formula:
                   hourly_cost = (version._get_contract_wage() * 3.0 / 13.0) / hours_per_week

        Formula & Logic Flow:
            - max_recoverable = min(total_100_pct_wage, amount_to_recover)
            - regularization_amount = max_recoverable - actual_recovered_amount
            - Return value = -regularization_amount

        Sign Convention & Auto-Correction:
            - Negative return value (-): Deducts the remaining 10% (or missing adjustment) from the employee.
            - Positive return value (+): Refunds over-recovered amounts to the employee if historical
              deductions exceeded `max_recoverable`.

        Args:
            localdict (dict): Payroll evaluation context containing 'l10n_be_year_payslips_by_payslip'
                              and 'result_rules'.

        Returns:
            tuple:
                - float: Regularization amount (-regularization_amount) for the payslip line.
                - dict: Explanation info breakdown ('recovered', 'total_100_pct_wage',
                        'amount_to_recover', 'max_amount').
        """
        self.ensure_one()

        employee = self.employee_id
        attestations = employee.l10n_be_holiday_attest_ids.filtered(lambda a: a.year == self.date_from.year - 1)
        amount_to_recover = sum(attestations.mapped("simple_holiday_pay_cap"))

        if not amount_to_recover:
            return 0.0, {}

        days_to_recover = sum(attestations.mapped("prev_days_earned"))
        hours_to_recover = days_to_recover * self.version_id.resource_calendar_id.hours_per_day
        if not hours_to_recover:
            return 0.0, {}

        year_payslips = localdict['l10n_be_year_payslips_by_payslip'][self]
        all_payslips = (year_payslips | self).sorted('date_from')

        line_values = year_payslips._get_line_values(['HolPayRec'], compute_sum=True)
        actual_recovered_amount = -line_values['HolPayRec']['sum']['total']

        result_rules = localdict['result_rules']
        if 'HolPayRec' in result_rules:
            actual_recovered_amount += -result_rules['HolPayRec']['total']

        remaining_attest_hours = hours_to_recover
        total_100_pct_wage = 0.0

        for payslip in all_payslips:
            if remaining_attest_hours <= 0:
                break

            leave_wd = payslip.worked_days_line_ids.filtered(lambda w: w.code == '016.00')
            leave_hours = sum(leave_wd.mapped('number_of_hours'))

            if leave_hours > 0:
                version = payslip.version_id
                if payslip.wage_type == 'hourly':
                    hourly_cost = version.hourly_wage
                else:
                    hours_per_week = version._l10n_be_get_hours_per_week(payslip.date_from.year)
                    if not hours_per_week:
                        continue
                    weekly_wage = version._get_contract_wage() * 3.0 / 13.0
                    hourly_cost = weekly_wage / hours_per_week

                covered_hours = min(leave_hours, remaining_attest_hours)
                total_100_pct_wage += covered_hours * hourly_cost
                remaining_attest_hours -= covered_hours

        max_recoverable = min(total_100_pct_wage, amount_to_recover)
        regularization_amount = max_recoverable - actual_recovered_amount

        explanation_info = {
            k: float_round(v, precision_digits=2)
            for k, v in {
                'recovered': actual_recovered_amount,
                'total_100_pct_wage': total_100_pct_wage,
                'amount_to_recover': amount_to_recover,
                'max_amount': max_recoverable,
            }.items()
        }

        return -regularization_amount, explanation_info

    def add_upcoming_public_holiday_on_termination(self):
        self.ensure_one()
        number_of_public_holidays = self.env.context.get('number_of_public_holidays', 0)
        if number_of_public_holidays <= 0:
            return
        upcomming_public_holiday_type = self.env['hr.work.entry.type'].search([
                ('code', '=', '202.00'),
                ('country_id.code', '=', 'BE')
            ], limit=1)
        days_per_week = self.version_id.resource_calendar_id.days_per_week
        hours_per_day = self.version_id.resource_calendar_id.hours_per_day
        result = self.version_id._get_contract_wage() * 3 / 13 / days_per_week
        unlink_records = self.worked_days_line_ids.filtered_domain([('work_entry_type_id', '=', upcomming_public_holiday_type.id)])
        if unlink_records:
            unlink_records.unlink()
        self.env['hr.payslip.worked_days'].create({
            'payslip_id': self.id,
            'version_id': self.version_id.id,
            'number_of_days': number_of_public_holidays,
            'number_of_hours': number_of_public_holidays * hours_per_day,
            'amount': result * number_of_public_holidays,
            'work_entry_type_id': upcomming_public_holiday_type.id,
        })
        self.compute_sheet()

    def _get_current_quarter_sum(self, rule_codes, localdict, include_current_payslip=True):
        self.ensure_one()
        quarter_prev_payslips = localdict['l10n_be_quarter_payslips_by_payslip'][self]
        # TODO: to keep old behavior, the following line was added but we need make sure this is intended
        #  (for example the termination payslip was not regulating the ONSS with regular payslips,
        #  ~800€ difference in the 'test test_06_declaration_employee_no_notice_period')
        quarter_prev_payslips = quarter_prev_payslips.filtered(lambda p: p.struct_id == self.struct_id)
        line_values = quarter_prev_payslips._get_line_values(rule_codes, compute_sum=True)
        total_prev_payslips = sum(line_values[rule_code]['sum']['total'] for rule_code in rule_codes)
        total_current_payslip = sum(localdict['result_rules'].get(rule_code, {'total': 0})['total'] for rule_code in rule_codes)
        return total_prev_payslips + (total_current_payslip if include_current_payslip else 0)

    def _get_onss_contribution_amount(self, base_amount, rate):
        self.ensure_one()
        employer_category = self.payroll_config_id.l10n_be_employer_category_id.dmfa_code
        if self.version_id.is_worker() and employer_category not in ['036', '320']:
            base_amount *= 1.08
        return float_round(base_amount * rate / 100, 2)

    def _get_regularised_onss_contribution_amount(self, contribution_code, rate, localdict, base_codes=None, quarter_base=None):
        self.ensure_one()
        if base_codes is None:
            base_codes = self._get_salary_wage_line_codes() - {'DH_SALARY'}
        if quarter_base is None:
            quarter_base = self._get_current_quarter_sum(base_codes, localdict)
        quarter_contribution = self._get_onss_contribution_amount(quarter_base, rate)
        already_paid_contribution = self._get_current_quarter_sum([contribution_code], localdict)
        return quarter_contribution - already_paid_contribution

    def _calculate_dmfa_occupation_fraction(self, quarter_payslips):
        self.ensure_one()
        uu = self.employee_id.version_id._get_reference_calendar().hours_per_week
        employer_category = self.payroll_config_id.l10n_be_employer_category_id.dmfa_code
        match employer_category:
            case '024' | '026' | '044' | '054' | '224' | '226' | '244' | '254':
                excluded_codes = {10, 11, 50, 51, 53, 60, 61}
            case '521' | '621' | '721' | '121' | '221' | '421':
                excluded_codes = {13, 21, 22, 24, 25, 26, 30}
            case '036':
                excluded_codes = {4, 21, 22, 25, 26, 30, 72, 73, 74}
            case '320':
                excluded_codes = {21, 25, 30, 72, 73}
            case '083' | '091':
                excluded_codes = {12, 30, 73}
            case '084':
                excluded_codes = {30, 50, 51, 53, 60}
            case _:
                excluded_codes = set()

        zz = sum(
            wl.number_of_hours
            for payslip in quarter_payslips
            for wl in payslip.worked_days_line_ids
            if int(wl.work_entry_type_id.dmfa_code) not in excluded_codes and wl.sequence != 99
        )

        mu_c = zz / (13 * uu)
        return float_round(min(mu_c, 1.0) * 100, precision_digits=2)

    def _get_ffe_contribution_type(self):
        self.ensure_one()
        is_ACS = self.version_id.l10n_be_worker_code_id.dmfa_code == '484'
        if self.payroll_config_id.onss_importance_code in ['1', '2', '3']:
            contribution_type = '0' if self._with_salary_moderation() and not is_ACS else '2'
        else:
            contribution_type = '5' if self._with_salary_moderation() and not is_ACS else '4'
        return contribution_type

    def _l10n_be_defer_fiscal_date(self):
        """Attach to the confirmation period the remunerations paid after their own pay period
        has already been declared: they can no longer be added to that declaration."""
        # A refund reverses an already declared period on its own: deferring it would declare a
        # negative amount alone in the fiscal period. It follows its correction instead, if any.
        late_slips = self.filtered(
            lambda p: p.date_to and p.done_date and p.done_date.date() > p.date_to
            and not p.is_refund_payslip)
        if not late_slips:
            return
        declared_sheets = self.env['l10n_be.274_xx'].sudo().search([
            ('company_id', 'in', late_slips.company_id.root_id.ids),
            ('state', 'in', ['ready', 'done']),
            ('date_start', '<=', max(late_slips.mapped('date_from'))),
            ('date_end', '>=', min(late_slips.mapped('date_to'))),
        ])
        for payslip in late_slips:
            pay_period_declared = any(
                sheet.company_id == payslip.company_id.root_id
                and sheet.date_start <= payslip.date_from and payslip.date_to <= sheet.date_end
                for sheet in declared_sheets)
            if payslip.l10n_be_arrear_salary or pay_period_declared:
                payslip.l10n_be_fiscal_date = payslip.done_date.date()

    def _l10n_be_apply_correction_fiscal_period(self):
        """Bring a correction back to the period it corrects when it lowers the declared amounts.

        A correction is paid now, so like any late remuneration it is declared now. An amount
        that goes down is the exception: declaring it now would mean a negative amount, which is
        refused, so the correction and its refund stay attached to the period they correct.
        """
        for correction in self.filtered(lambda p: p.is_correction_payslip and p.origin_payslip_id):
            origin = correction.origin_payslip_id
            lowers_declaration = (
                float_compare(correction.gross_wage, origin.gross_wage, 2) < 0
                or float_compare(correction.l10n_be_withholding_taxes, origin.l10n_be_withholding_taxes, 2) < 0
            )
            refunds = origin.related_payslip_ids.filtered('is_refund_payslip')
            if lowers_declaration:
                (correction | refunds).l10n_be_fiscal_date = correction.date_to
            else:
                refunds.l10n_be_fiscal_date = correction.l10n_be_fiscal_date
            # A reversal and the correction replacing it are one operation, so both halves of the
            # delta must land in the same declaration: the reversal takes the attachment its
            # counterpart resolved, which it could not resolve itself for lack of a delta.
            attachment = {line.code: line.l10n_be_follow_pay_period for line in correction.line_ids}
            for line in refunds.line_ids:
                if line.code in attachment:
                    line.l10n_be_follow_pay_period = attachment[line.code]

    def _get_l10n_be_arrear_average_tax_rate(self):
        """
        Compute the average withholding tax rate for the arrear salary year.
        average_rate = total withholding tax paid / total taxable salary in the arrear year.
        """
        self.ensure_one()
        arrear_year = self.date_from.year
        year_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', date(arrear_year, 1, 1)),
            ('date_to', '<=', date(arrear_year, 12, 31)),
            ('l10n_be_arrear_salary', '=', False),
            ('company_id', '=', self.company_id.id),
        ])
        if not year_payslips:
            return 0.0
        line_values = year_payslips._get_line_values(['PPTOTAL', 'GROSS'], compute_sum=True)
        total_tax = line_values['PPTOTAL']['sum']['total']
        total_gross = line_values['GROSS']['sum']['total']
        if not total_gross:
            return 0.0
        return total_tax / total_gross

    @api.constrains('l10n_be_arrear_salary')
    def _check_l10n_be_arrear_salary(self):
        if self.l10n_be_arrear_salary and self.create_date.year <= self.date_from.year:
            raise ValidationError(self.env._("Arrear salary must be for a prior year."))

    def _l10n_be_get_december_holiday_regularization(self, get_explanation=False):
        """
        compute the regularization for december:
        'what the employee should receive' - 'what was already paid'
        """
        self.ensure_one()
        if (self.struct_id.code == 'BEMONTHLY' and self.l10n_be_is_december) or self.struct_id.code == 'BEHOLN1':
            simple_holiday_due, double_holiday_due = self._l10n_be_get_holiday_pay_due()
            simple_holiday_n, double_holiday_n = self._l10n_be_get_holiday_pay_n()

            simple_december_pay = max(0, simple_holiday_due - simple_holiday_n)
            total_double_december_pay = max(0, double_holiday_due - double_holiday_n)
            explanation_info = {'explanation': self.env._(
                "Result = Max(0, Simple Holiday Due (%(simple_holiday_due)s €) - Simple Holiday Already Paid (%(simple_holiday_n)s €))",
                simple_holiday_due=float_round(simple_holiday_due, precision_digits=2),
                simple_holiday_n=float_round(simple_holiday_n, precision_digits=2)
            )}
            result = {
                'simple': simple_december_pay,
                'double': total_double_december_pay,
            }
            return (result, explanation_info) if get_explanation else result

        return ({}, {}) if get_explanation else {}

    def _l10n_be_get_remuneration_n1(self):
        """
        Remuneration of the previous year:
        gross salary of year N-1 + fictive gross for assimilated periods of absence.

        13th month salary:
        - for 'Departure Holiday Attests': included in the remuneration
        - for 'December Settlement': NOT included in the remuneration
        """
        self.ensure_one()
        if not self.employee_id or (not self.l10n_be_is_december and self.struct_id.code != 'BEHOLN1'):
            return 0
        struct_codes = ['BEMONTHLY']
        if self.struct_id.code == 'BEHOLN1':
            struct_codes.append('BETHIRTEEN')
        payslips_n1 = self.employee_id._get_payslips_for_year(
            self.date_from.year - 1,
            struct_codes
        )
        salary_codes = self._get_salary_wage_line_codes()
        line_values = payslips_n1._get_line_values(salary_codes, compute_sum=True)
        net_n1 = sum(line_values[code]['sum']['total'] for code in salary_codes)
        fictitious_remuneration_n1 = self.employee_id._get_fictitious_remuneration_previous_year(self.date_from, payslips=payslips_n1)
        remuneration_n1 = net_n1 + fictitious_remuneration_n1
        return remuneration_n1

    def _l10n_be_get_holiday_pay_due(self):
        """
        compute Simple Holiday and Double Holiday which the employee should receive.
        Calculation is based on the remuneration of the previous year
        """
        self.ensure_one()
        remuneration_n1 = self._l10n_be_get_remuneration_n1()
        simple_holiday_due = remuneration_n1 * 0.0767
        current_year = self.date_from.replace(month=1, day=1)
        dp_date = current_year.replace(month=self._l10n_be_get_theoretical_double_holiday_pay_month())
        double_holiday_due_based_on_main_holiday_month = self._l10n_be_get_paid_double_holiday(
            base_month=dp_date) * 0.92
        double_holiday_due = max(remuneration_n1 * 0.0767, double_holiday_due_based_on_main_holiday_month)
        return simple_holiday_due, double_holiday_due

    def _l10n_be_get_holiday_pay_n(self):
        """
        Compute Simple Holiday and Double Holiday already paid in this year
        """
        self.ensure_one()
        current_year = self.date_from.replace(month=1, day=1)
        structure_monthly_pay = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        structure_double_holiday = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday')
        payslips_n = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', current_year),
            ('date_to', '<=', self.date_to),
            ('state', 'in', ['validated', 'paid']),
            ('struct_id', 'in', (structure_monthly_pay + structure_double_holiday).ids)])
        double_payslip = payslips_n.filtered(lambda p: p.struct_id == structure_double_holiday)
        monthly_payslips = payslips_n - double_payslip

        simple_holiday_n = monthly_payslips._get_worked_days_line_values(
            ['016.00'], ['amount'], True)['016.00']['sum']['amount']
        simple_holiday_n += monthly_payslips._get_line_values(
            ['SIMPLE_DECEMBER'], ['amount'], compute_sum=True)['SIMPLE_DECEMBER']['sum']['amount']

        double_holiday_n = payslips_n._get_line_values(
            ['DH_BASIC'], compute_sum=True)['DH_BASIC']['sum']['total']

        return simple_holiday_n, double_holiday_n

    def _get_unused_legal_leave_at_year_end(self, leave_code, employee, cutoff):
        year_end = cutoff.replace(month=12, day=31)
        leave_type = self.env['hr.work.entry.type'].search([('code', '=', leave_code)], limit=1)
        if leave_type:
            all_leaves_data = leave_type.get_allocation_data(employee, year_end)
            employee_data = all_leaves_data.get(employee, [])
            for name, vals, *_rest in employee_data:
                if name == leave_type.name:
                    return vals.get('virtual_remaining_leaves', 0.0)
        return 0.0

    def _l10n_be_get_legal_leave_days_per_month(self):
        self.ensure_one()
        current_year = self.date_from.replace(month=1, day=1)
        next_year = current_year + relativedelta(years=1)
        monthly_pay = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        payslips_n = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', current_year),
            ('date_to', '<', next_year),
            ('state', 'in', ['validated', 'paid']),
            ('struct_id', '=', monthly_pay.id)])
        return {
            date_to.month: sum(
                slips._get_worked_days_line_values(['016.00'], ['number_of_days'], True)['016.00']['sum']['number_of_days']
                for slips in grouped_slips
            )
            for date_to, grouped_slips in payslips_n.grouped('date_to').items()
        }

    def _l10n_be_get_theoretical_double_holiday_pay_month(self):
        """
        The method returns a month with the maximum days of vacation.
        If there are more than one maximum, returns a months after which is impossible to take a vacation longer than maximum
        (according to the documentation)
        """
        self.ensure_one()
        payslip_month = self.date_to.month
        holidays_dict = self._l10n_be_get_legal_leave_days_per_month()
        if not holidays_dict or not any(holidays_dict.values()):
            return payslip_month

        days_off_left = self._get_unused_legal_leave_at_year_end("016.00", self.employee_id, self.date_from)
        total_taken = sum(holidays_dict.values())
        total_allowance = total_taken + days_off_left
        if days_off_left > total_allowance / 2:
            return payslip_month

        max_value = max(holidays_dict.values())
        remaining_balance = total_allowance
        for month in sorted(holidays_dict.keys()):
            remaining_balance -= holidays_dict[month]
            if holidays_dict[month] == max_value and remaining_balance <= max_value:
                return month
        return payslip_month

    def _l10n_be_get_termination_yearly_salary(self):
        self.ensure_one()
        current_quarter_start = date_utils.get_quarter(self.date_from)[0]
        previous_quarter_end = current_quarter_start - relativedelta(days=1)
        previous_quarter_start = date_utils.get_quarter(previous_quarter_end)[0]

        loop_guard = 0
        max_quarters_lookback = 40  # at most 10 years lookback
        while loop_guard < max_quarters_lookback:
            payslips_previous_quarter = self.env['hr.payslip'].search([
                ('employee_id', '=', self.employee_id.id),
                ('date_from', '>=', previous_quarter_start),
                ('date_to', '<=', previous_quarter_end),
                ('state', 'in', ['validated', 'paid']),
                ('struct_id.code', '=', "BEMONTHLY")
            ])

            eligible_worked_days = payslips_previous_quarter.worked_days_line_ids.filtered(lambda wd: wd.work_entry_type_id.dmfa_code in ['1', '101']) if payslips_previous_quarter else False
            if eligible_worked_days:
                quarter_basis = payslips_previous_quarter._get_line_values(['SALARY'], compute_sum=True)['SALARY']['sum']['total']
                if quarter_basis > 0:
                    if self.version_id.work_time_rate == 1:
                        total_worked_days = sum(eligible_worked_days.mapped('number_of_days'))
                        day_basis = quarter_basis / total_worked_days
                    else:
                        total_worked_hours = sum(eligible_worked_days.mapped('number_of_hours'))
                        day_basis = quarter_basis / total_worked_hours * self.version_id._get_reference_calendar().hours_per_week / 5
                    return day_basis * 260
            previous_quarter_end = previous_quarter_start - relativedelta(days=1)
            previous_quarter_start = date_utils.get_quarter(previous_quarter_end)[0]
            loop_guard += 1
        return 0

    def _l10n_be_get_economic_unemployment_compensation(self, localdict):
        """Compute the economic unemployment compensation for the employee/worker.

        Joint Committee Rules:
            CP200:
                No predefined amount; it's set manually. (handeled by a property_input EUC_CP200)
            CP302:
                - Seniority < 6 months: 2€ per day.
                - Seniority >= 6 months:
                    - Total temporary unemployment days <= 110: max(2€, 0.5187 * daily unemployment hours).
                    - Total temporary unemployment days > 110: 2€ per day.
            Default (Other Joint Committees):
                2€ per day.
        """
        self.ensure_one()

        payslip_input = self._get_input_line_amount('EUC_CP200')
        employee = self.employee_id
        worked_days = self.worked_days_line_ids
        company_seniority = relativedelta(self.date_from, employee.first_contract_date)
        company_seniority = company_seniority.years * 12 + company_seniority.months
        joint_committee_code = self.l10n_be_joint_committee_id.egov3_code or "200"
        daily_compensation = self._rule_parameter("economic_unemployment_daily_compensation")
        special_codes = ["152.00", "156.50", "151.00"]
        days = 0
        days_special = 0

        for line in worked_days.filtered(lambda l: l.work_entry_type_id.l10n_be_economic_unemployment):
            if line.work_entry_type_id.code in special_codes:
                days_special += line.number_of_days
            else:
                days += line.number_of_days

        result_qty = days + days_special
        result = daily_compensation
        if joint_committee_code == "302" and company_seniority >= 6:
            previous_unemployment_days = 0
            previous_payslips_of_year = localdict['l10n_be_year_payslips_by_payslip'][self].filtered_domain([
                ('date_to', '<=', self.date_from),
                ('state', 'in', ['paid', 'validated']),
            ])

            for previous_worked_days in previous_payslips_of_year.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id.l10n_be_economic_unemployment):
                previous_unemployment_days += previous_worked_days.number_of_days

            if previous_unemployment_days <= 110:
                hourly_compensation = self._rule_parameter("cp302_temp_unemployment_bonus")
                result = 0
                result_qty = 1
                cap_remaining_days = 110 - previous_unemployment_days

                unemployment_entries = [
                    we for we in localdict['work_entries']
                    if we["work_entry_type_id"].l10n_be_economic_unemployment
                ]

                entries_by_date = defaultdict(list)
                for entry in unemployment_entries:
                    entries_by_date[entry["date"]].append(entry)

                for daily_entries in entries_by_date.values():
                    if cap_remaining_days <= 0:
                        break
                    cap_remaining_days -= 1

                    if any(we["work_entry_type_id"].code in special_codes for we in daily_entries):
                        continue

                    daily_hours = sum(we["duration"] for we in daily_entries)
                    result += max(daily_compensation, daily_hours * hourly_compensation)
                    days -= 1

                result += (days_special + days) * daily_compensation
        elif joint_committee_code == "200":
            result = payslip_input

        return (result_qty, result)

    def _get_termination_fees_contribution_basis(self, base_amount):
        self.ensure_one()

        days_after_2014 = (self.employee_id.l10n_be_notice_period_start - max(date(2014, 1, 1), self.employee_id.l10n_be_first_contract_date)).days
        total_days = (self.employee_id.l10n_be_notice_period_start - self.employee_id.l10n_be_first_contract_date).days
        if self.version_id.is_worker():
            base_amount *= 1.08
        return base_amount * days_after_2014 / total_days

    def _get_termination_fees_minimum_yearly_salary(self):
        return self._rule_parameter('l10n_be_termination_contribution_type')[0][0]

    def _get_termination_fees_contribution_type(self, yearly_salary):
        self.ensure_one()
        contribution_type_brackets = self._rule_parameter('l10n_be_termination_contribution_type')
        for yearly_salary_threshold, contribution_type in reversed(contribution_type_brackets):
            if yearly_salary >= yearly_salary_threshold:
                return contribution_type
        return '1'

    def _get_pension_fund_contribution_type(self, quarter_payslips=None):
        self.ensure_one()
        employer_category = self.payroll_config_id.l10n_be_employer_category_id.dmfa_code

        if not quarter_payslips:
            quarter_payslips = self.env['hr.payslip'].search([
                ('employee_id', '=', self.employee_id.id),
                ('date_from', '>=', date_utils.get_quarter(self.date_from)[0]),
                ('date_to', '<=', date_utils.get_quarter(self.date_from)[1]),
                ('state', 'in', ['validated', 'paid']),
                ('struct_id.code', 'in', ['BEMONTHLY', 'BETERM', 'BETHIRTEEN', 'BEHOLN', 'BEHOLN1'])
            ])

        occupation_fraction = self._calculate_dmfa_occupation_fraction(quarter_payslips)
        contribution_type = 0
        if employer_category == '320':
            if occupation_fraction >= 80:
                contribution_type = 1
            elif occupation_fraction >= 50:
                contribution_type = 2
            elif occupation_fraction >= 33:
                contribution_type = 3
        return contribution_type, occupation_fraction

    def _get_onss_global_rates(self):
        self.ensure_one()
        contribution_type = '0'
        if self.version_id.is_worker():
            contribution_type = '1'

        # Source: https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/instructions/special_contributions/students.html
        if self.version_id.is_student():
            worker_code = '840' if self.version_id.is_worker() else '841'
            rates = self._get_onss_rates(worker_code)
        else:
            rates = self._get_onss_rates(contribution_type=contribution_type)
        return rates

    def _l10n_be_has_mrt_without_valid_worked_days(self):
        mrts = self.employee_id.resource_calendar_id.l10n_be_reorganisation_measure_ids
        credit_work_entry_types = self.env['hr.work.entry.type'].search([
            '|',
                ("l10n_be_is_time_credit", "=", True),
                ("code", "in", "122.04")
        ])
        worked_days_codes = self.worked_days_line_ids.mapped("code")
        measure_refs = ['l10n_be_reorganisation_measure_009_3', 'l10n_be_reorganisation_measure_009_4', 'l10n_be_reorganisation_measure_005_5']
        if any(self.env.ref(f'l10n_be_hr_payroll.{measure_ref}') in mrts for measure_ref in measure_refs):
            return all(leave.code not in worked_days_codes for leave in credit_work_entry_types)

    def action_l10n_be_edit_time_off(self):
        self.ensure_one()
        return {
            'name': self.env._('Time Off Dashboard'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave',
            'view_mode': 'calendar',
            'views': [[self.env.ref('hr_holidays.hr_leave_employee_view_dashboard_month').id, 'calendar']],
            'domain': [('employee_id', 'in', self.employee_id.ids)],
            'context': {
                'default_employee_id': self.employee_id.id,
                'initial_date': self.date_from,
                'employee_id': [self.employee_id.id]
            },
        }

    def _get_category_options_data(self, work_entries=None):
        """
        Compute category option hours from work entry vals, grouping by category and day, then capping daily hours for
        specific categories (Sunday/holiday premium, temporary unemployment) based on their max amount and hourly rate parameters.

        :return: dict mapping category code to total (capped) hours for the payslip period.
        """
        if self.struct_id.country_id.code != 'BE':
            return super()._get_category_options_data(work_entries=work_entries)

        category_options = defaultdict(float)
        if not work_entries:
            return category_options

        category_options_params_by_code = {
            'PREMIUM_PAY_SUN': [self._rule_parameter('cp_200_premium_pay_sunday_max'), self._rule_parameter('cp_200_premium_pay_sunday_hourly_rate')],
            'PREMIUM_PAY_HOLIDAY': [self._rule_parameter('cp_200_premium_pay_holiday_max'), self._rule_parameter('cp_200_premium_pay_holiday_hourly_rate')],
            'TEMP_UNEMP': [self._rule_parameter('cp_200_temporary_unemployment_max'), self._rule_parameter('cp_200_temporary_unemployment_hourly_rate')],
        }

        # {category_code: {days: hours}}
        # A category option implies its ancestors: hours carrying a child option (e.g. a custom
        # premium pay) are also credited to each parent category code, once per work entry.
        hours_per_day_per_category_option = defaultdict(lambda: defaultdict(float))
        for work_entry_vals in work_entries:
            for code in work_entry_vals['category_options_ids']._get_codes_with_ancestors():
                hours_per_day_per_category_option[code][work_entry_vals['date']] += work_entry_vals['duration']

        for code, dates in hours_per_day_per_category_option.items():
            if code not in category_options_params_by_code:
                category_options[code] = sum(dates.values())
                continue
            max_amount_per_day, hourly_rate = category_options_params_by_code[code]
            max_hours_per_day = max_amount_per_day / hourly_rate if hourly_rate else 0
            for _date, hours in dates.items():
                category_options[code] += min(hours, max_hours_per_day)

        return category_options

    def _get_flxwage_amounts(self):
        """Split the flexi gross into the eGov FLXWAGE remuneration (0001001000) and
        bonus (0002001000) buckets.
        Lines are bucketed by their DmfA remuneration code (``1`` = remuneration,
        ``2`` = prime/bonus), the same field DMFA reporting uses. ``SALARY`` (code 1)
        is the ONSS gross and already contains the code-2 lines and the flexi-pécule;
        on a dedicated bonus slip there is no ``SALARY`` line, so ``remuneration_base``
        falls back to 0. eGov declares the flexi holiday pay (``FLEXI_PECULE``) with the
        pay it was computed on, so the single pécule line is split pro rata between the
        two bases.
        """
        self.ensure_one()
        lines = self.line_ids
        salary = sum(lines.filtered(lambda l: l.salary_rule_id.l10n_be_remuneration_code == '1').mapped('total'))
        bonus_base = sum(lines.filtered(lambda l: l.salary_rule_id.l10n_be_remuneration_code == '2').mapped('total'))
        pecule = sum(lines.filtered(lambda l: l.salary_rule_id.code == 'FLEXI_PECULE').mapped('total'))
        remuneration_base = max(salary - bonus_base - pecule, 0.0)
        base = remuneration_base + bonus_base
        if not base:
            return 0.0, 0.0
        remuneration = remuneration_base + pecule * remuneration_base / base
        bonus = bonus_base + pecule * bonus_base / base
        return remuneration, bonus

    def _create_flxwage_declarations(self):
        payslips = self or self.search(self.env.context.get('active_domain', []))
        flexi_payslips = payslips.filtered(lambda p:
            p.l10n_be_needs_flxwage_declaration and p.state in ('validated', 'paid') and not p.l10n_be_flexi_declaration_id)
        return self.env['l10n.be.flexi.at.work'].create([{'payslip_id': payslip.id} for payslip in flexi_payslips])

    def action_create_flxwage_declaration(self):
        payslips = self or self.search(self.env.context.get('active_domain', []))
        flexi_payslips = payslips.filtered(lambda p: p.l10n_be_needs_flxwage_declaration and p.state in ('validated', 'paid'))
        flexi_payslips_to_create = flexi_payslips.filtered(lambda p: not p.l10n_be_flexi_declaration_id)
        if not flexi_payslips_to_create and flexi_payslips:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': self.env._("All selected payslips already have a Flexi@Work declaration."),
                },
            }

        flexis = self.env['l10n.be.flexi.at.work'].create([{'payslip_id': payslip.id} for payslip in flexi_payslips_to_create])
        if not flexis:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': self.env._("No Flexi@Work declarations were created."),
                },
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._("%(count)s Flexi@Work declaration(s) created successfully.", count=len(flexis)),
            },
        }

    def action_create_and_show_flxwage_declaration(self):
        action = self.action_create_flxwage_declaration()
        if 'params' in action and not 'next' in action['params']:
            flexis = self.l10n_be_flexi_declaration_id
            if len(flexis) == 1:
                action['params']['next'] = {
                    'type': 'ir.actions.act_window',
                    'res_model': 'l10n.be.flexi.at.work',
                    'res_id': flexis.id,
                    'view_mode': 'form',
                    'views': [[False, 'form']],
                }
            elif flexis:
                action['params']['next'] = {
                    'type': 'ir.actions.act_window',
                    'res_model': 'l10n.be.flexi.at.work',
                    'view_mode': 'tree,form',
                    'domain': [('payslip_id', 'in', self.ids)],
                }
        return action

    def action_create_flxwage_declaration_and_reload(self):
        action = self.action_create_flxwage_declaration()
        if 'params' in action and action['params']['type'] == 'success' and not 'next' in action['params']:
            action['params']['next'] = {'type': 'ir.actions.client', 'tag': 'reload'}
        return action

    def action_show_flxwage_declaration(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.be.flexi.at.work',
            'res_id': self.l10n_be_flexi_declaration_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
        }

    def action_postpone_paid_time_off(self, paid_time_off_to_postpone_n1=0, paid_time_off_to_postpone_n2=0):
        self.ensure_one()

        existing_amounts = {
            code: sum(self.input_line_ids.filtered(lambda line: line.code == code).mapped('amount'))
            for code in ('PPTO1', 'PPTO2')
        }

        if paid_time_off_to_postpone_n1 > 0:
            self._set_input_value('PPTO1', existing_amounts['PPTO1'] + paid_time_off_to_postpone_n1)

        if paid_time_off_to_postpone_n2 > 0:
            self._set_input_value('PPTO2', existing_amounts['PPTO2'] + paid_time_off_to_postpone_n2)

    def _get_net_to_recover_amount(self, localdict):
        self.ensure_one()

        categories = localdict['categories']
        current_net = categories['REMUNERATION_BASE']

        if current_net < 0:
            return abs(current_net)

        past_payslips = localdict['l10n_be_year_payslips_by_payslip'][self].filtered_domain([
            ('date_to', '<', self.date_to),
            ('state', 'in', ['paid', 'validated']),
        ])

        line_values = past_payslips._get_line_values(['NET_TO_RECOVER'], compute_sum=True)
        accumulated_debt = line_values['NET_TO_RECOVER']['sum']['total']

        if current_net > 0 and accumulated_debt > 0:
            return -min(current_net, accumulated_debt)

        return 0.0

    def _get_cp200_sectorial_bonus_compensation(self):
        self.ensure_one()
        benefit = self.env.ref('l10n_be_hr_payroll.l10n_be_sectorial_bonus_comp', raise_if_not_found=False)
        if not benefit or not benefit.active:
            return 0.0
        return self.version_id.l10n_be_sectorial_bonus_compensatory_amount

    def _get_starterjob_deduction_rate(self):
        self.ensure_one()
        if self.version_id.l10n_be_is_starterjob and not self.env.context.get('without_starterjob'):
            last_day_of_the_month = date.today() + relativedelta(day=31)
            age = self.employee_id._get_age(last_day_of_the_month)
            if age >= 18 and age <= 20:
                return self._rule_parameter('starterjob_gross_reduction').get(age)
        return 0

    def _l10n_be_generate_termination_documents(self, payslip_run=None):
        for payslip in self.filtered(lambda p: p.struct_id.code == 'BEMONTHLY' and p.employee_id.departure_id
                and not p.employee_id.departure_id.l10n_be_termination_documents_generated
                and p.employee_id.departure_id.departure_date and p.date_to >= p.employee_id.departure_id.departure_date):
            departure = payslip.employee_id.departure_id
            generated_payslips = self.browse()
            if departure.l10n_be_notice_respect != 'with':
                generated_payslips += departure._generate_termination_payslip()
            generated_payslips += departure._generate_termination_holidays()
            if departure.l10n_be_thirteen_month_eligible:
                generated_payslips += departure._generate_termination_thirteen_month()
            if payslip_run:
                generated_payslips.payslip_run_id = payslip_run.id
            payslip.employee_id.action_report_employment_certificate()
            departure.l10n_be_termination_documents_generated = True

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "No double holiday pay, so no simple holiday pay":
            return self.env._("No double holiday pay, so no simple holiday pay")
        if text == "Result = Gross Reference Remuneration (%(result)s €) * 7.67%%":
            return self.env._("Result = Gross Reference Remuneration (%(result)s €) * 7.67%%", **kwargs)
        return super()._get_payroll_translation(text, **kwargs)

    def _get_l10n_be_mobility_amounts(self):
        monthly_slips = self.filtered(
            lambda slip:
            slip.struct_id.code == 'BEMONTHLY'
            and slip.state == 'draft'
            and slip.employee_id
            and slip.date_from
            and slip.country_code == 'BE'
            and (slip.version_id.l10n_be_mobility_budget or slip.l10n_be_is_december or slip._is_last_monthly_payslip())
        )
        if not monthly_slips:
            return {}

        # 1. Compute the prorated yearly mobility budget
        employees_by_year = defaultdict(lambda: self.env['hr.employee'])
        for slip in monthly_slips:
            employees_by_year[slip.date_from.year] |= slip.employee_id

        prorated_budgets = {}
        for year, employees in employees_by_year.items():
            amounts = employees._get_l10n_be_mobility_budget_amount_prorated(
                reference_date=date(year, 12, 31),
                year=year,
            )
            for employee_id, amount in amounts.items():
                prorated_budgets[employee_id, year] = amount

        # Keep December/last payslips without MB only if the employee was entitled to a mobility budget earlier in the year.
        monthly_slips = monthly_slips.filtered(lambda s:
            s.version_id.l10n_be_mobility_budget or
            ((s.l10n_be_is_december or s._is_last_monthly_payslip()) and prorated_budgets.get((s.employee_id.id, s.date_from.year), 0.0) > 0)
        )

        # 2. Compute already paid mobility amounts.
        # For the yearly amount, include all validated and done payslips of the same year.
        # For the monthly amount, only consider the current month (normally, this only includes expenses from l10n_be_hr_payroll_expense).
        employees_by_year = defaultdict(lambda: self.env['hr.employee'])

        for slip in monthly_slips:
            employees_by_year[slip.date_from.year] |= slip.employee_id

        paid_amounts_by_year = {}
        for year, employees in employees_by_year.items():
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)
            yearly_paid, monthly_paid = employees._get_l10n_be_paid_mobility_amounts(date_start=year_start, date_end=year_end)
            paid_amounts_by_year[year] = (yearly_paid, monthly_paid)

        # 3.  Build mobility input values for each payslip.
        values_by_slip = {}
        for slip in monthly_slips:
            employee_id = slip.employee_id.id
            year = slip.date_from.year
            month = slip.date_from.month
            prorated_yearly_budget = prorated_budgets.get((employee_id, year), 0.0)

            yearly_paid, monthly_paid = paid_amounts_by_year[year]
            already_paid_year = yearly_paid.get((employee_id, year), 0.0)
            already_paid_month = monthly_paid.get((employee_id, year, month), 0.0)
            values_by_slip[slip] = {
                'MOBILITY_PAID_MONTH': already_paid_month,
                'MOBILITY_PAID_YEAR': already_paid_year,
                'MOBILITY_REMAINING': round(max(0.0, prorated_yearly_budget - already_paid_year), 2),
            }

        return values_by_slip

    def _get_l10n_be_mobility_budget_termination_fee_amount(self):
        self.ensure_one()
        if self.struct_id.code == 'BETERM':
            version = self.version_id
            termination_duration_weeks = version.l10n_be_notice_duration_week_after_2014
            if version.l10n_be_notice_respect == 'partial':
                termination_duration_weeks -= version.l10n_be_notice_duration
            termination_duration_months = termination_duration_weeks / 13.0 * 3.0
            return version.l10n_be_mobility_budget_amount_monthly, termination_duration_months
        return 0, 0

    def _is_last_monthly_payslip(self):
        self.ensure_one()
        departure_date = self.employee_id.departure_date
        return departure_date and self.date_from <= departure_date <= self.date_to

    def _l10n_be_show_mobility_budget_rules(self):
        self.ensure_one()
        return self.version_id.l10n_be_mobility_budget or self.l10n_be_is_december or self._is_last_monthly_payslip()

    def _get_special_wage_moderation_contribution(self):
        """
        Formule: (Partie_A + Partie_B) / 2
            - Partie A = (Salaire de ref. indexé modéré - [4000 * (1 + chiffre d'index) * fraction de prestation]) * chiffre d'index limité à 2%
            - Partie B = Partie A * taux ONSS global (employeur + modération salariale)
        Source: https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/instructions/special_contributions/pennyindex_wagemoderationcontribution.html
        """
        self.ensure_one()
        version = self.version_id
        rates = self._get_onss_global_rates()
        onss_pat_global_rate = rates['employer_rate'] + rates['salary_moderation_rate']
        reference_salary = version._l10n_be_get_monthly_wage(int(self.date_from.year))
        rule_parameter = self.env["hr.rule.parameter"]._get_parameter_from_code(
                    "l10n_be_legal_index", date=date(self.date_from.year, 1, 1), raise_if_not_found=False,
                ).get(version.l10n_be_egov3_code, False)
        if not rule_parameter:
            return 0
        rate, cap = rule_parameter
        attendance_rate = self._get_attendance_rate()
        part_A = (reference_salary - (cap * (1 + rate) * attendance_rate)) * min(rate, 0.02)
        part_B = part_A * onss_pat_global_rate / 100
        return (part_A + part_B) / 2

    def _get_attendance_rate(self):
        self.ensure_one()
        # DMFA prestation codes 1, 3, 4, 5, 20
        PRESTATION_DMFA_CODES = {'1', '3', '4', '5', '20'}
        wd_lines = self.worked_days_line_ids.filtered(lambda wd: wd.code != 'OUT')
        prestation_lines = wd_lines.filtered(lambda wd: wd.work_entry_type_id.dmfa_code in PRESTATION_DMFA_CODES)
        is_part_time = self.version_id.work_time_rate < 1.0
        if is_part_time:
            # attendance_rate = H / U  (hours with prestation codes / total theoretical monthly hours)
            H = sum(prestation_lines.mapped('number_of_hours'))
            U = sum(wd_lines.mapped('number_of_hours'))
            attendance_rate = H / U if U else 0
        else:
            # attendance_rate = J / D  (days with prestation codes / total theoretical monthly days)
            J = sum(prestation_lines.mapped('number_of_days'))
            D = sum(wd_lines.mapped('number_of_days'))
            attendance_rate = J / D if D else 0
        return attendance_rate

    def action_open_employee_calendar(self):
        """Encoding worked time needs the wider list of time types, absences only is not enough.
        The regular time off gantt keeps the employee facing one."""
        action = super().action_open_employee_calendar()
        if self.struct_id.country_id.code != 'BE':
            return action
        gantt = self.env.ref('hr_payroll.hr_leave_gantt_view_payroll_encoding')
        action['views'] = [
            (gantt.id, view_type) if view_type == 'gantt' else (view_id, view_type)
            for view_id, view_type in action['views']
        ]
        return action

    def _l10n_be_get_meal_vouchers_yearly_estimated_quantity(self):
        self.ensure_one()
        days_per_week = self.version_id.resource_calendar_id.days_per_week
        pto_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_legal_leave')
        extra_legal_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_extra_legal')
        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('work_entry_type_id', 'in', (pto_work_entry_type + extra_legal_work_entry_type).ids),
            ('date_from', '>=', self.date_from.replace(month=1, day=1)),
            '|',
            ('date_to', '<=', self.date_from.replace(month=12, day=31)),
            ('date_to', '=', False),
        ])
        number_of_days_off = sum(allocations.mapped('number_of_days'))
        return (days_per_week * 52) - 10 - number_of_days_off

    @api.model
    def _l10n_be_find_withholding_tax_rates(self, x, rates):
        low_bound, high_bound = rates[0][0], rates[-1][1]
        x = min(max(low_bound, x), high_bound)
        for low, high, rate in rates:
            if low <= x <= high:
                return rate / 100.0
