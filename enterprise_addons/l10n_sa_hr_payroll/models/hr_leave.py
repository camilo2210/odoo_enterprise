from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError, AccessError


class HrLeave(models.Model):
    _inherit = "hr.leave"

    company_country_code = fields.Char(
        related="company_id.country_id.code",
        string="Company Country Code",
        depends=["company_id.country_id"],
    )
    l10n_sa_work_entry_type_change_warning = fields.Char(compute='_compute_l10n_sa_work_entry_type_change_warning')

    @api.depends('work_entry_type_id', 'date_from', 'date_to', 'employee_id')
    def _compute_l10n_sa_work_entry_type_change_warning(self):
        l10n_sa_concerned_leaves = self.filtered(
            lambda leave: leave.company_id.country_code == 'SA' and leave.employee_id and leave.date_from
                and leave.date_to and leave.work_entry_type_id.code in ['013.00', 'SASICKLEAVE75', 'SASICKLEAVE0']
        )
        for leave in l10n_sa_concerned_leaves:
            leave_split = leave._get_l10n_sa_sick_leave_split()
            leave.l10n_sa_work_entry_type_change_warning = self._get_work_entry_type_change_warning(leave_split)

        (self - l10n_sa_concerned_leaves).l10n_sa_work_entry_type_change_warning = ""

    def _get_l10n_sa_sick_leave_split(self):
        """
        This method computes the sick leave split for SA:
        - The first 30 days are fully paid
        - The following 60 days are 75% paid
        - The following days are unpaid
        Note: The counter for sick leave starts from the first sick leave the employee took and ends after 1 year from that date,
        and the next cycle starts in the next time the employee takes a sick leave,
        so we need 2 counters if the leave lays between 2 sick leave counting years.
        Returns an *ordered* list of tuples where the key is the work entry type and the value the number of days
        """
        self.ensure_one()
        sick_work_entry_type_codes = ["013.00", "SASICKLEAVE75", "SASICKLEAVE0"]
        sick_work_entry_types = self.env["hr.work.entry.type"].search(
            [("code", "in", sick_work_entry_type_codes), ("country_id.code", "=", "SA")]
        )
        paid_100_work_entry_type = sick_work_entry_types.filtered(lambda w: w.code == "013.00")
        paid_75_work_entry_type = sick_work_entry_types.filtered(lambda w: w.code == "SASICKLEAVE75")
        unpaid_work_entry_type = sick_work_entry_types.filtered(lambda w: w.code == "SASICKLEAVE0")
        previous_sick_leaves = self.env["hr.leave"].search(
            [
                ('employee_id', '=', self.employee_id.id),
                ('date_from', '<', self.date_from),
                ('work_entry_type_id', 'in', sick_work_entry_types.ids),
                ('state', '=', 'validate'),
            ],
            order="date_from asc",
        )

        year_counter = previous_sick_leaves[0].date_from if previous_sick_leaves else self.date_from
        for leave in previous_sick_leaves:
            next_year_counter = year_counter + relativedelta(years=1)
            if leave.date_to >= next_year_counter:
                if leave.date_from <= next_year_counter:
                    year_counter = next_year_counter
                else:
                    year_counter = leave.date_from
        next_year_counter = year_counter + relativedelta(years=1)

        first_year_days = self.number_of_days
        if self.date_to >= next_year_counter:
            domain = [('count_as', '=', 'absence'),
                      ('company_id', 'in', self.env.companies.ids + self.env.context.get('allowed_company_ids', [])),
                      '|', ('holiday_id', '=', False), ('holiday_id', '!=', self.id)]
            first_year_days = self.employee_id._get_work_days_data_batch(
                self.date_from,
                next_year_counter,
                compute_leaves=not self.work_entry_type_id.include_public_holidays_in_duration,
                domain=domain,
                calendar=self.resource_calendar_id
            )[self.employee_id.id]['days']

        result = []
        first_year_sick_leave_100_days = sum(
            previous_sick_leaves.filtered(
                lambda l: l.date_from >= year_counter and l.date_to < next_year_counter and l.work_entry_type_id.code == '013.00'
            ).mapped('number_of_days')
        )
        first_year_sick_leave_75_days = sum(
            previous_sick_leaves.filtered(
                lambda l: l.date_from >= year_counter and l.date_to < next_year_counter and l.work_entry_type_id.code == 'SASICKLEAVE75'
            ).mapped('number_of_days')
        )
        remaining_sick_leave_100_balance = max(0, 30 - first_year_sick_leave_100_days)
        remaining_sick_leave_75_balance = max(0, 60 - first_year_sick_leave_75_days)

        paid_100_days = min(first_year_days, remaining_sick_leave_100_balance)
        if paid_100_days:
            result.append((paid_100_work_entry_type, paid_100_days))
        paid_75_days = min(first_year_days - paid_100_days, remaining_sick_leave_75_balance)
        if paid_75_days:
            result.append((paid_75_work_entry_type, paid_75_days))
        unpaid_days = first_year_days - paid_100_days - paid_75_days
        if unpaid_days:
            result.append((unpaid_work_entry_type, unpaid_days))

        # if the leave spans two sick leave counting years
        if self.date_to >= next_year_counter:
            second_year_days = self.number_of_days - first_year_days
            second_year_paid_100_days = min(second_year_days, 30)
            if second_year_paid_100_days:
                result.append((paid_100_work_entry_type, second_year_paid_100_days))
            second_year_paid_75_days = min(second_year_days - second_year_paid_100_days, 60)
            if second_year_paid_75_days:
                result.append((paid_75_work_entry_type, second_year_paid_75_days))
            second_year_unpaid_days = second_year_days - second_year_paid_100_days - second_year_paid_75_days
            if second_year_unpaid_days:
                result.append((unpaid_work_entry_type, second_year_unpaid_days))

        return result

    def _action_validate(self, check_state=True):
        all_l10n_sa_concerned_leaves = self.filtered(
            lambda leave: leave.company_id.country_code == 'SA' and leave.work_entry_type_id.code in ['013.00', 'SASICKLEAVE75', 'SASICKLEAVE0']
        ).sorted('request_date_from')
        l10n_sa_concerned_leaves_by_employee = all_l10n_sa_concerned_leaves.grouped('employee_id')
        sick_work_entry_type_100 = self.env["hr.work.entry.type"].search(
            [("code", "=", "013.00"), ("country_id.code", "=", "SA")]
        )
        use_worked_days = sick_work_entry_type_100.count_days_as == 'working'

        res = True
        for _, l10n_sa_concerned_leaves in l10n_sa_concerned_leaves_by_employee.items():
            for l10n_sa_concerned_leave in l10n_sa_concerned_leaves:
                leave_split = l10n_sa_concerned_leave._get_l10n_sa_sick_leave_split()
                new_leaves = l10n_sa_concerned_leave._create_leaves_from_split(leave_split, use_worked_days=use_worked_days)
                res &= super(HrLeave, new_leaves)._action_validate(check_state=check_state)

        non_sa_leaves = self - all_l10n_sa_concerned_leaves
        res &= super(HrLeave, non_sa_leaves)._action_validate(check_state=check_state)

        return res

    def action_create_sa_leave_advance_pay(self):
        self.ensure_one()

        if self.env.company.country_id.code != "SA":
            raise UserError(
                self.env._(
                    "You must log in to a Saudi Arabian company to use this action."
                )
            )

        if self.work_entry_type_id != self.env.company.l10n_sa_annual_work_entry_type_id:
            raise UserError(
                self.env._(
                    "The leave type in the leave request must match the company's Annual Leave Time-off Type."
                )
            )

        if self.state != "validate":
            raise UserError(
                self.env._("The leave must be validated to perform this action.")
            )

        # The user must be at least a Payroll Assistant and a time off officer to perform this action.
        # but since the time off officer is implied by the payroll assistant, we only check for the payroll assistant role.
        if not self.env.user.has_group("hr_payroll.group_hr_payroll_user"):
            raise AccessError(
                self.env._(
                    "To perform this action, you must be at least a Payroll Assistant."
                )
            )
        sa_struct_id = self.env.ref(
            "l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure",
            raise_if_not_found=False,
        )
        return {
            "name": self.env._("Advance leave pay"),
            "res_model": "hr.leave.advance.pay",
            "view_mode": "form",
            "type": "ir.actions.act_window",
            "context": {
                "hr_leave_id": self.id,
                "default_struct_id": sa_struct_id.id if sa_struct_id else False,
            },
            "target": "new",
        }
