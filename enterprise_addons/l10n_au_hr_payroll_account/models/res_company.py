# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_au_hr_super_responsible_id = fields.Many2one(
        "hr.employee",
        string="HR Super Sender",
        help="Person responsible for sending superannuation contributions to super funds on behalf of employees.")

    l10n_au_stp_responsible_id = fields.Many2one(
        "hr.employee", string="STP Responsible", help="Employee responsible for sending STP data to the ATO.")

    @api.constrains('l10n_au_hr_super_responsible_id', 'l10n_au_stp_responsible_id')
    def _check_payroll_responsible_fields(self):
        for company in self:
            if company.l10n_au_hr_super_responsible_id and not company.l10n_au_hr_super_responsible_id.user_id.exists():
                raise ValidationError(_("The HR Super Sender must be linked to a user."))
            if company.l10n_au_stp_responsible_id and not company.l10n_au_stp_responsible_id.user_id.exists():
                raise ValidationError(_("The STP Responsible must be linked to a user."))

    def _get_ytd_template_vals(self, employee_id, income_stream_type, struct_id, start_date):
        """Return the list of YTD value dicts for a single employee based on the template."""

        ytd_vals = [
            {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "requires_inputs": True,
                "rule_id": self.env["hr.salary.rule"].search(
                    [("struct_ids", "in", [struct_id]), ("code", "=", "BASIC")], limit=1
                ).id,
                "start_date": start_date,
                "l10n_au_payslip_ytd_input_ids": [
                    (0, 0, {"res_id": self.env.ref("hr_work_entry.au_work_entry_type_attendance").id, "res_model": "hr.work.entry.type", "ytd_amount": 0}),
                    (0, 0, {"res_id": self.env.ref("hr_work_entry.au_work_entry_type_overtime").id, "res_model": "hr.work.entry.type", "ytd_amount": 0}),
                    (0, 0, {"res_id": self.env.ref("hr_work_entry.l10n_au_work_entry_type_public_holiday_week_day").id, "res_model": "hr.work.entry.type", "ytd_amount": 0}),
                    (0, 0, {"res_id": self.env.ref("hr_work_entry.l10n_au_work_entry_type_annual_leave").id, "res_model": "hr.work.entry.type", "ytd_amount": 0}),
                    (0, 0, {"res_id": self.env.ref("hr_work_entry.l10n_au_work_entry_type_parental").id, "res_model": "hr.work.entry.type", "ytd_amount": 0}),
                    (0, 0, {"res_id": self.env.ref("hr_work_entry.l10n_au_work_entry_type_compensation").id, "res_model": "hr.work.entry.type", "ytd_amount": 0}),
                    (0, 0, {"res_id": self.env.ref("hr_work_entry.l10n_au_work_entry_type_defence").id, "res_model": "hr.work.entry.type", "ytd_amount": 0}),
                ],
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "requires_inputs": True,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_extra_pay_structure_1").id,
                "start_date": start_date,
                "l10n_au_payslip_ytd_input_ids": [
                    (0, 0, {"res_id": input_type.id, "res_model": "hr.salary.rule"})
                    for input_type in self.env["hr.salary.rule"].search([("code", "=like", "EXTRA.INPUT%")])
                ],
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "requires_inputs": True,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_salary_sacrifice_other_structure_1").id,
                "start_date": start_date,
                "l10n_au_payslip_ytd_input_ids": [
                    (0, 0, {"name": "Salary Sacrifice: Other Benefits"}),
                    (0, 0, {"name": "Salary Sacrificed Workplace Giving"}),
                ],
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_workplace_giving_structure_1").id,
                "start_date": start_date,
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "requires_inputs": True,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_allowance_structure_1").id,
                "start_date": start_date,
                "l10n_au_payslip_ytd_input_ids": [
                    (0, 0, {"res_id": input_type.id, "res_model": "hr.salary.rule"})
                    for input_type in self.env["hr.salary.rule"].search([
                        ("l10n_au_payment_type", "=", "allowance"),
                        ("l10n_au_paygw_treatment", "in", ("regular", "special")),
                    ])
                ],
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_return_to_work_structure_1").id,
                "start_date": start_date,
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "requires_inputs": True,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_non_tax_allowance_structure_1").id,
                "start_date": start_date,
                "l10n_au_payslip_ytd_input_ids": [
                    (0, 0, {"res_id": input_type.id, "res_model": "hr.salary.rule"})
                    for input_type in self.env["hr.salary.rule"].search([
                        ("l10n_au_payment_type", "=", "allowance"),
                        ("l10n_au_paygw_treatment", "in", ("no_paygw", "special")),
                    ])
                ],
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "requires_inputs": True,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_back_payments_structure_1").id,
                "start_date": start_date,
                "l10n_au_payslip_ytd_input_ids": [
                    (0, 0, {"res_id": input_type.id, "res_model": "hr.salary.rule"})
                    for input_type in self.env["hr.salary.rule"].search([("code", "=", "BACKPAY.INPUT")])
                ],
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_withholding_net_structure_1").id,
                "start_date": start_date,
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "requires_inputs": True,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_child_support_structure_1").id,
                "start_date": start_date,
                "l10n_au_payslip_ytd_input_ids": [
                    (0, 0, {"name": "Child Support Deduction"}),
                ] + [
                    (0, 0, {"res_id": input_type.id, "res_model": "hr.salary.rule"})
                    for input_type in self.env["hr.salary.rule"].search([("code", "=like", "CHILD_SUPPORT_GARNISHEE%")])
                ],
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_super_contribution_structure_1").id,
                "start_date": start_date,
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "requires_inputs": True,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_salary_sacrifice_structure_1").id,
                "start_date": start_date,
                "l10n_au_payslip_ytd_input_ids": [
                    (0, 0, {"name": "Salary Sacrifice: Superannuation"}),
                    (0, 0, {"name": "Extra Negotiated Super (RESC)"}),
                    (0, 0, {"name": "Extra Compusory Super (Non RESC)"}),
                ],
            }, {
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "requires_inputs": True,
                "rule_id": self.env.ref("l10n_au_hr_payroll.l10n_au_reportable_fringe_benefits_structure_1").id,
                "start_date": start_date,
                "l10n_au_payslip_ytd_input_ids": [
                    (0, 0, {"res_id": input_type.id, "res_model": "hr.salary.rule"})
                    for input_type in self.env["hr.salary.rule"].search([("code", "=like", "FBT%")])
                ],
            },
        ]
        # Deduction rules (hr_payroll.DED category)
        # Exclude the default rules from the template
        to_exclude = (
            self.env.ref("l10n_au_hr_payroll.l10n_au_hr_payroll_structure_au_regular_deduction_salary_rule") +
            self.env.ref("l10n_au_hr_payroll.l10n_au_hr_payroll_structure_au_regular_attachment_of_salary_rule") +
            self.env.ref("l10n_au_hr_payroll.l10n_au_hr_payroll_structure_au_regular_assignment_of_salary_rule") +
            self.env.ref("l10n_au_hr_payroll.l10n_au_hr_payroll_structure_au_regular_child_support")
        )
        deduction_rules = self.env["hr.salary.rule"].search(
            [
                ("struct_ids", "in", [struct_id]),
                ("category_ids", "in", self.env.ref("hr_payroll.DED").ids),
                ("id", "not in", to_exclude.ids),
            ],
        )
        for rule in deduction_rules:
            ytd_vals.append({
                "employee_id": employee_id,
                "l10n_au_income_stream_type": income_stream_type,
                "struct_id": struct_id,
                "rule_id": rule.id,
                "start_date": start_date,
            })
        return ytd_vals

    def _create_ytd_values(self, prev_pay_transfer_employees, start_date):
        values = []
        for employee_transfer in prev_pay_transfer_employees:
            if not employee_transfer.employee_id.version_ids:
                raise UserError(_("The contract for employee %(employee)s might be archived or deleted. "
                    "Please unarchive it first to proceed.", employee=employee_transfer.employee_id.name))

            default_struct_id = employee_transfer.employee_id.structure_type_id.default_struct_id.id
            if not default_struct_id:
                raise UserError(_("Unable to generate YTD Opening balance for %s. "
                    "Please set the correct pay structure or unset the Import YTD field.", (employee_transfer.employee_id.name)))

            values += self._get_ytd_template_vals(
                employee_transfer.employee_id.id,
                employee_transfer.l10n_au_income_stream_type,
                default_struct_id,
                start_date,
            )
        return self.env["l10n_au.payslip.ytd"].create(values)

    def _regenerate_ytd_values(self, employees, start_date):
        """Create any YTD records missing from the template for employees with existing YTD records."""
        PayslipYTD = self.env["l10n_au.payslip.ytd"]
        start_date = PayslipYTD._get_start_date(start_date)

        existing = PayslipYTD.search_read(
            [("employee_id", "in", employees.ids), ("start_date", "=", start_date)],
            ["employee_id", "l10n_au_income_stream_type", "struct_id", "rule_id"],
            load=False,
        )
        if not existing:
            return PayslipYTD

        combos = defaultdict(set)
        for rec in existing:
            key = (rec["employee_id"], rec["l10n_au_income_stream_type"], rec["struct_id"])
            combos[key].add(rec["rule_id"])

        to_create_vals = []
        for (employee_id, income_stream_type, struct_id), existing_rule_ids in combos.items():
            template_vals = self._get_ytd_template_vals(employee_id, income_stream_type, struct_id, start_date)
            for val in template_vals:
                if val.get("rule_id") and val["rule_id"] not in existing_rule_ids:
                    to_create_vals.append(val)

        return PayslipYTD.with_context(allow_regenerate=True).create(to_create_vals) if to_create_vals else PayslipYTD
