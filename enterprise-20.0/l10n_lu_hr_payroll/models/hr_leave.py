from dateutil.relativedelta import relativedelta
from odoo import models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    def _issues_dependencies(self):
        return super()._issues_dependencies() + ["work_entry_type_id", "date_from", "date_to", "employee_id"]

    def _get_l10n_lu_sick_leave_split(self):

        self.ensure_one()
        leave_duration = self._get_calendar_days()
        sick_work_entry_type_codes = ["013.00", "SL_CNS"]
        sick_work_entry_types = self.env["hr.work.entry.type"].search(
            [("code", "in", sick_work_entry_type_codes), ("country_id.code", "=", "LU")]
        )
        prev_sick_leaves_sum = 0
        sick_leaves = self.env["hr.leave"].search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("date_from", ">=", (self.date_from.replace(day=1) + relativedelta(months=-18))),
                ("work_entry_type_id", "in", sick_work_entry_types.ids),
                ("state", "=", "validate"),
            ],
            order="date_from asc",
        )
        sick_leaves += self
        prev_sick_leave = False
        paid_sick_work_entry_type = sick_work_entry_types.filtered(
            lambda w: w.code == "013.00"
        )
        unpaid_sick_work_entry_type = sick_work_entry_types.filtered(
            lambda w: w.code == "SL_CNS"
        )
        cns_starting_date = False
        result = []
        # After 77 consecutive sick days, any sick leave becomes unpaid by Employer, to be paid by CNS (starting from the following month).
        for leave in sick_leaves:
            leave_duration = leave._get_calendar_days()
            if not prev_sick_leave:
                prev_sick_leaves_sum += leave_duration
                prev_sick_leave = leave

            else:
                duration_between_leaves = self._get_calendar_days_between_leaves(
                    prev_sick_leave, leave
                )
                if duration_between_leaves != 0:
                    prev_sick_leaves_sum = 0

                prev_sick_leaves_sum += leave_duration

            if prev_sick_leaves_sum >= 77:
                sick_leaves_to_date = prev_sick_leaves_sum - leave_duration
                if sick_leaves_to_date < 77 and not cns_starting_date:

                    start_of_next_month = (leave.date_from + relativedelta(days=77 - sick_leaves_to_date)).replace(day=1) + relativedelta(months=1)
                    cns_starting_date = start_of_next_month
                if (
                    leave.date_to >= cns_starting_date and leave.date_from < cns_starting_date
                    and leave.work_entry_type_id.code == "013.00"
                ):
                    remaining_paid_sick_days = max(
                        0, (cns_starting_date - leave.date_from).days
                    )
                    paid_days = min(leave_duration, remaining_paid_sick_days)
                    if paid_days:
                        result.append((paid_sick_work_entry_type, paid_days))
                    unpaid_days = leave_duration - paid_days
                    if unpaid_days:
                        result.append((unpaid_sick_work_entry_type, unpaid_days))
                elif (
                    leave.date_from > cns_starting_date and duration_between_leaves == 0
                    and leave.work_entry_type_id.code == "013.00"
                ):
                    result.append(
                        (unpaid_sick_work_entry_type, leave._get_calendar_days())
                    )
            prev_sick_leave = leave
        return result

    def _action_validate(self, check_state=True):
        all_l10n_lu_concerned_leaves = self.filtered(
            lambda leave: (
                leave.company_id.country_code == "LU"
                and leave.work_entry_type_id.code in ["013.00"]
            )
        ).sorted("request_date_from")

        l10n_lu_concerned_leaves_by_employee = all_l10n_lu_concerned_leaves.grouped(
            "employee_id"
        )
        res = True
        for _, l10n_lu_concerned_leaves in l10n_lu_concerned_leaves_by_employee.items():
            for l10n_lu_concerned_leave in l10n_lu_concerned_leaves:
                leave_split = l10n_lu_concerned_leave._get_l10n_lu_sick_leave_split()
                new_leaves = l10n_lu_concerned_leave._create_leaves_from_split(leave_split)
                res &= super(HrLeave, new_leaves)._action_validate(check_state=check_state)

        non_lu_leaves = self - all_l10n_lu_concerned_leaves
        res &= super(HrLeave, non_lu_leaves)._action_validate(check_state=check_state)

        return res
