# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.tools.float_utils import float_compare


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    l10n_be_joint_committee_id = fields.Many2one(related='version_id.l10n_be_joint_committee_id')
    l10n_be_reorganisation_measure_ids = fields.Many2many(related='version_id.resource_calendar_id.l10n_be_reorganisation_measure_ids')
    l10n_be_replacement_amount = fields.Float(string="Replacement Amount", compute="_compute_replacement_amount")
    l10n_be_credit_time_proration_rate = fields.Float(string="Credit Time Proration Rate", compute="_compute_l10n_be_credit_time_proration_rate")

    def _l10n_be_skip_amount_computation(self):
        self.ensure_one()
        return self.payslip_id.state != 'draft' \
                or self.payslip_id.edited \
                or self.payslip_id.wage_type != 'monthly' \
                or self.payslip_id.struct_id.country_id.code != 'BE' \
                or not self.is_paid

    def _l10n_be_get_024_00_amount(self, wage):
        # For training time off: The maximum reimbursement is fixed by a threshold that you can
        # find at https://www.leforem.be/entreprises/aides-financieres-conge-education-paye.html
        # In that case we have to adapt the wage.
        self.ensure_one()
        wage_to_deduct = 0
        max_hours_per_week = self.version_id.reference_calendar_id.hours_per_week \
                                or self.version_id.resource_calendar_id.hours_per_week
        training_ratio = 3 / (13 * max_hours_per_week) if max_hours_per_week else 0
        training_hours = sum(self.payslip_id.worked_days_line_ids.filtered(
            lambda wd: wd.work_entry_type_id.code == '024.00'
        ).mapped('number_of_hours'))
        training_threshold = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
            'training_time_off_threshold', self.payslip_id.date_to, raise_if_not_found=False)
        if wage > training_threshold:
            hourly_wage_to_deduct = (wage - training_threshold) * training_ratio
            wage_to_deduct = training_hours * hourly_wage_to_deduct
        if wage_to_deduct:
            return min(wage, training_threshold) * training_ratio * training_hours
        else:
            hours_per_week = self.version_id.resource_calendar_id.hours_per_week
            return wage * 3 / (13 * hours_per_week) * training_hours if hours_per_week else 0

    def _l10n_be_get_072_00_amount(self, wage):
        self.ensure_one()
        hours_per_week = self.version_id.resource_calendar_id.hours_per_week
        sick_hours = sum(self.payslip_id.worked_days_line_ids.filtered(
            lambda wd: wd.work_entry_type_id.code == '072.00'
        ).mapped('number_of_hours'))
        ratio = 3 / (13 * hours_per_week) * sick_hours if hours_per_week else 0
        if self.version_id.is_employee():
            fte_amount = 0.2693 * min(3464.43, wage) + 0.8693 * max(0, wage - 3464.43)
        elif self.version_id.is_worker():
            fte_amount = 0.2588 * min(3464.43, wage) + 0.8588 * max(0, wage - 3464.43)
        else:
            fte_amount = 0
        return fte_amount * ratio

    def _l10n_be_get_017_49_amount(self, wage):
        self.ensure_one()
        days_per_week = self.version_id.resource_calendar_id.days_per_week
        monthly_cap = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
            'l10n_be_political_leave_monthly_cap', raise_if_not_found=False,
        )
        daily_cap = monthly_cap * 3 / (13 * days_per_week)
        daily_wage = wage * 3 / (13 * days_per_week)
        return min(daily_wage, daily_cap) * self.number_of_days

    def _l10n_be_has_enough_paid_hours(self):
        # We usually deduct the unpaid hours using the hourly formula. This is the fairest
        # way to deduct 1 day, because we will deduct the same amount in a short month (February)
        # than in a long month (March)
        # But in the case of the long month with not enough paid hours, this could lead
        # to a basic salary = 0, which is in that case unfair. Switch to another method in which
        # we compute the amount from the paid hours using the hourly formula
        self.ensure_one()
        excluded_work_entry_codes = ['000.00', '147.00', '147.05', '147.07', '147.04', '147.08', '147.13']

        worked_days_line_ids = self.payslip_id.worked_days_line_ids
        paid_hours = sum(wd.number_of_hours for wd in worked_days_line_ids if wd.is_paid and wd.code not in excluded_work_entry_codes)
        unpaid_hours = sum(wd.number_of_hours for wd in worked_days_line_ids if not wd.is_paid or wd.code in excluded_work_entry_codes)

        return paid_hours >= unpaid_hours

    def _l10n_be_get_paid_work_days(self):
        self.ensure_one()
        payslip = self.payslip_id
        worked_days_line_ids = payslip.worked_days_line_ids
        excluded_work_entry_codes = [
            '000.00', '147.00', '147.05', '024.00', '142.20',
            '122.00', '147.07', '147.04', '147.08', '147.13'
        ]
        paid_worked_days = worked_days_line_ids.filtered(
                    lambda wd: wd.is_paid and wd.code not in excluded_work_entry_codes
                ).sorted(key=lambda wd: (wd.code, -wd.number_of_hours))
        if not paid_worked_days:
            # In case there is only european time off for instance
            paid_worked_days = worked_days_line_ids.filtered(
                lambda wd: wd.is_paid and wd.code not in ['147.00', '147.05', '147.07', '147.04', '147.08', '147.13']
            ).sorted(key=lambda wd: (wd.code, -wd.number_of_hours))
        return paid_worked_days

    def _l10n_be_get_amount_ratio(self, number_of_hours, out_ratio):
        self.ensure_one()
        hours_per_week = self.version_id.resource_calendar_id.hours_per_week
        ratio = 3 / (13 * hours_per_week) * number_of_hours if hours_per_week else 0 # (3 months = 13 weeks)
        if out_ratio != None:
            ratio = out_ratio - ratio
        return ratio

    def _l10n_be_get_workday_amount(self, wage, nb_hour=None, out_ratio=None, inverse=False):
        self.ensure_one()
        number_of_hours = nb_hour if nb_hour != None else self.number_of_hours
        ratio = self._l10n_be_get_amount_ratio(number_of_hours, out_ratio)
        return ratio * wage if not inverse else (1-ratio) * wage

    def _l10n_be_get_out_ratio(self):
        self.ensure_one()
        out_worked_day = self.payslip_id.worked_days_line_ids.filtered(
            lambda wd: wd.code == '000.00' and wd.version_id.contract_date_start == self.version_id.contract_date_start
        )
        if out_worked_day:
            out_hours = sum(out_worked_day.mapped('number_of_hours'))
            out_hours_per_week = self.payslip_id._get_out_of_contract_calendar(self.version_id).hours_per_week
            return 1 - 3 / (13 * out_hours_per_week) * out_hours if out_hours_per_week else 1
        return 1

    @api.depends('version_id.l10n_be_time_credit', 'version_id.resource_calendar_id', 'payslip_id.date_from', 'payslip_id.date_to')
    def _compute_l10n_be_credit_time_proration_rate(self):
        proration_rates = {}
        for worked_day in self:
            calendar = worked_day.version_id.resource_calendar_id
            date_from = worked_day.payslip_id.date_from
            date_to = worked_day.payslip_id.date_to

            if worked_day.version_id.l10n_be_time_credit:
                key = (calendar.id, date_from, date_to)
                if key not in proration_rates:
                    proration_rates[key] = calendar._l10n_be_get_time_credit_proration(date_from, date_to)
                worked_day.l10n_be_credit_time_proration_rate = proration_rates[key]
            else:
                worked_day.l10n_be_credit_time_proration_rate = 1.0

    def _compute_amount(self):
        computed_by_super = self.env['hr.payslip.worked_days']
        unpaid_fte = {
            payslip.id: sum(
                wd.fte for wd in self
                if wd.payslip_id == payslip and not wd.is_paid
                and not wd.work_entry_type_id.l10n_be_is_time_credit and wd.code != '000.00'
            )
            for payslip in self.payslip_id
        }

        for worked_day in self:

            wage = worked_day.version_id._get_contract_wage() * worked_day.l10n_be_credit_time_proration_rate if worked_day.version_id else 0

            if worked_day._l10n_be_skip_amount_computation():
                computed_by_super += worked_day
                continue
            if worked_day.work_entry_type_id.l10n_be_is_time_credit or worked_day.code == '000.00':
                worked_day.amount = 0
                continue
            if not worked_day._l10n_be_has_enough_paid_hours():
                worked_day.amount = worked_day._l10n_be_get_workday_amount(wage)
                continue
            if worked_day.code == '024.00':
                worked_day.amount = worked_day._l10n_be_get_024_00_amount(wage)
                continue
            if worked_day.code == '072.00':
                worked_day.amount = worked_day._l10n_be_get_072_00_amount(wage)
                continue
            if worked_day.code == '017.49':
                worked_day.amount = worked_day._l10n_be_get_017_49_amount(wage)
                continue

            ####################################################################################
            #  Example:
            #  Note: (3/13/38) * wage : hourly wage, if 13th months and 38 hours/week calendar
            #
            #  CODE     :   number_of_hours    :    Amount
            #  002.00  :      130 hours       : (1 - 3/13/38 * (15 + 30)) * wage
            #  PAID     :      30 hours        : 3/13/38 * (15 + 30)) * wage
            #  UNPAID   :      15 hours        : 0
            #
            #  TOTAL PAID : 002.00 + PAID + UNPAID = (1 - 3/13/38 * 15 ) * wage
            ####################################################################################
            paid_worked_days = worked_day._l10n_be_get_paid_work_days()
            main_worked_day = paid_worked_days[0].code if paid_worked_days else False
            amount_rate = worked_day.work_entry_type_id.amount_rate

            if worked_day.code != main_worked_day:
                worked_day.amount = min(wage, worked_day._l10n_be_get_workday_amount(wage)) * amount_rate
                continue

            # If out of contract, we use the hourly formula to deduct the real wage
            out_ratio = worked_day._l10n_be_get_out_ratio()

            # 002.00 (Generally)
            worked_days_line_ids = worked_day.payslip_id.worked_days_line_ids

            if not float_compare(unpaid_fte[worked_day.payslip_id.id], 0.5, 2):
                # should be strictly proportional to the number of hours for this worked days line
                total_hours = sum(
                    wd.number_of_hours for wd in worked_days_line_ids
                    if not wd.work_entry_type_id.l10n_be_is_time_credit and wd.code != '000.00'
                )
                worked_day.amount = amount_rate * wage * worked_day.number_of_hours / total_hours
                continue

            work100_wds = worked_days_line_ids.filtered(lambda wd: wd.code == main_worked_day)
            number_of_other_hours = sum(
                wd.number_of_hours
                for wd in worked_days_line_ids
                if wd.code not in [main_worked_day, '000.00', '202.00']
                and not wd.work_entry_type_id.l10n_be_is_time_credit
                and not wd.work_entry_type_id.is_extra_hours
                and not wd.work_entry_type_id.l10n_be_economic_unemployment
            )

            if len(work100_wds) == 1:
                worked_day.amount = max(
                    0, worked_day._l10n_be_get_workday_amount(wage, number_of_other_hours, out_ratio)
                ) * amount_rate
                continue

            # Case with half days mixed with full days
            # If only presence -> Compute the full days from the hourly formula
            if len(set(worked_days_line_ids.mapped('code'))) == 1 and len(set(worked_days_line_ids.mapped('category_options_ids'))) < 1:
                wage = worked_day._l10n_be_get_workday_amount(wage, number_of_other_hours, out_ratio)
                if float_compare(worked_day.number_of_hours, max(work100_wds.mapped('number_of_hours')), 2): # lowest lines
                    number_of_hours = sum((work100_wds - worked_day).mapped('number_of_hours'))
                    worked_day.amount = worked_day._l10n_be_get_workday_amount(wage, number_of_hours, inverse=True) * amount_rate
                else:  # biggest line
                    worked_day.amount = worked_day._l10n_be_get_workday_amount(wage) * amount_rate
            # Mix of presence/absences - Compute the half days from the hourly formula
            else:
                if float_compare(worked_day.number_of_hours, max(work100_wds.mapped('number_of_hours')), 2): # lowest lines
                    worked_day.amount = worked_day._l10n_be_get_workday_amount(wage) * amount_rate
                else:  # biggest line
                    total_wage = worked_day._l10n_be_get_workday_amount(wage, number_of_other_hours, out_ratio)
                    number_of_hours = sum((work100_wds - worked_day).mapped('number_of_hours'))
                    worked_day.amount = (total_wage - worked_day._l10n_be_get_workday_amount(wage, number_of_hours)) * amount_rate

        super(HrPayslipWorkedDays, computed_by_super)._compute_amount()

    @api.depends('code', 'is_paid', 'amount', 'number_of_hours', 'version_id', 'l10n_be_credit_time_proration_rate')
    def _compute_replacement_amount(self):
        for worked_day in self:
            if worked_day.payslip_id.country_code != 'BE':
                worked_day.l10n_be_replacement_amount = 0
                continue

            worked_day_category_codes = worked_day.work_entry_type_id.category_ids.mapped('code')
            if worked_day.amount or worked_day.code == '000.00' or 'UNASSIMILATED' in worked_day_category_codes:
                worked_day.l10n_be_replacement_amount = 0
            elif worked_day.version_id.l10n_be_time_credit and worked_day.work_entry_type_id.l10n_be_is_time_credit:
                worked_day.l10n_be_replacement_amount = worked_day.version_id._get_contract_wage() * (1.0 - worked_day.l10n_be_credit_time_proration_rate)
            else:
                wage = worked_day.version_id._get_contract_wage() * worked_day.l10n_be_credit_time_proration_rate if worked_day.version_id else 0
                worked_day.l10n_be_replacement_amount = worked_day._l10n_be_get_workday_amount(wage)

    def _get_default_name(self):
        self.ensure_one()
        if self.payslip_id.struct_id.country_id.code != 'BE':
            return super()._get_default_name()
        name = self.work_entry_type_id.name or ''
        if self.category_options_ids:
            options = ', '.join(self.category_options_ids.mapped('name'))
            name += self.env._(' (%s)', options)
        return name
