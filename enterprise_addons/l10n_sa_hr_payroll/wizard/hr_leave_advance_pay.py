from odoo import fields, models
from odoo.exceptions import UserError


class HrLeaveAdvancePay(models.TransientModel):
    _name = "hr.leave.advance.pay"
    _description = "Leave Advance Pay"

    struct_id = fields.Many2one(
        comodel_name="hr.payroll.structure", required=True, string="Pay Structure"
    )

    def action_populate_payslip(self):
        self.ensure_one()
        if self.struct_id and "LEAVEADVPAY" not in self.struct_id.rule_ids.mapped(
            "code"
        ):
            raise UserError(
                self.env._(
                    "The selected salary structure does not have a dedicated salary rule for the leave advance pay. "
                    "Please create a salary rule using the following code: LEAVEADVPAY"
                )
            )
        leave_id = self.env["hr.leave"].browse(self.env.context["hr_leave_id"])
        employee_id = leave_id.employee_id
        start_dt = leave_id.date_from.replace(day=1)
        next_month_start_dt = start_dt.replace(month=(start_dt.month + 1) % 12)
        version_id = employee_id._get_version(start_dt)
        payslip_id = self.env["hr.payslip"].search(
            [
                ("date_from", "=", start_dt),
                ("employee_id", "=", employee_id.id),
                ("struct_id", "=", self.struct_id.id),
                ("version_id", "=", version_id.id),
                ("state", "!=", "cancel"),
            ]
        )
        if len(payslip_id) > 1:
            raise UserError(
                self.env._(
                    "There are duplicated payslips having the same version and salary structure. \
                    The action can only be used if there is \
                    at most one payslip created for the same period."
                )
            )

        advance_pay_value = employee_id._get_work_days_data_batch(
            next_month_start_dt, leave_id.date_to,
                compute_leaves=not leave_id.work_entry_type_id.include_public_holidays_in_duration,
                domain=[('count_as', '=', 'absence'),
                        ('company_id', 'in', self.env.companies.ids + self.env.context.get('allowed_company_ids', [])),
                        '|', ('holiday_id', '=', False), ('holiday_id', '!=', leave_id.id)],
                calendar=leave_id.resource_calendar_id,
        )[employee_id.id]['days']
        if payslip_id:
            if payslip_id.state != "draft":
                raise UserError(
                    self.env._(
                        "A validated payslip already exists for the current period: %(payslip)s",
                        payslip=payslip_id.name,
                    )
                )
            payslip_id._set_input_value("LEAVEADVPAY", advance_pay_value)
            return {
                "type": "ir.actions.act_window",
                "res_model": "hr.payslip",
                "views": [[False, "form"]],
                "view_mode": "form",
                "res_id": payslip_id.id,
            }
        else:
            payslip_id = self.env["hr.payslip"].create(
                {
                    "name": "payslip name",
                    "employee_id": employee_id.id,
                    "struct_id": self.struct_id.id,
                    "date_from": start_dt,
                }
            )
            payslip_id._compute_name()
            payslip_id._set_input_value("LEAVEADVPAY", advance_pay_value)
            payslip_id.message_post(
                body=self.env._(
                    "This payslip was generated from %(leave)s",
                    leave=leave_id._get_html_link(title=leave_id.name),
                )
            )
            return {
                "type": "ir.actions.act_window",
                "res_model": "hr.payslip",
                "views": [[False, "form"]],
                "view_mode": "form",
                "res_id": payslip_id.id,
            }
