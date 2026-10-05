from collections import defaultdict

from lxml import etree

from odoo import api, fields, models
from odoo.tools.xml_utils import cleanup_xml_node


L10N_TR_ACCRUAL_REASON_SELECTION = [
    ("A", "Submitted within legal period"),
    ("B", "Submitted outside legal period"),
    ("C", "Additional Article 5 of Unemployment Insurance Law No. 4447"),
    ("D", "Change of document and/or law type"),
    ("E", "Force majeure"),
    ("F", "Retroactive wage differences due to collective labor agreement (by employer decision)"),
    ("G", "Retroactive wage differences due to Supreme Arbitration Board decision"),
    ("H", "Retroactive wage differences due to court decision enforcing collective labor agreement"),
    ("I", "Retroactive wage differences for uninsured or union-excluded employees (public/private)"),
    ("J", "Salaries paid late due to Ministry of Finance visa delay"),
    ("K", "Wages paid by employer during medical leave under collective agreement"),
    ("L", "Reinstatement decision by labor court or arbitrator"),
    ("M", "Payment to reinstated personnel due to administrative court decision"),
    ("N", "Retroactive wage payment to public workers by court or administrative decision"),
    ("O", "Inflation or other retroactive payments to workers transitioning from 4B to 4A status"),
    ("P", "Non-wage payments made when no contract exists or contract is suspended"),
    ("R", "Findings identified by SGK audits or workplace records"),
    ("S", "Investigations/audits by public inspectors"),
    ("T", "Documents or information provided by public institutions or banks"),
    ("U", "Official entry by SGK user (ex officio record)"),
]


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = "hr.payroll.payment.report.wizard"

    def _get_export_format_selection(self):
        selection = super()._get_export_format_selection()
        if 'TR' in self.env.companies.country_id.mapped('code'):
            selection.extend([
                ('muhsgk', '1003B (MPHB)'),
            ])
        return selection

    def _get_default_export_format(self):
        default = super()._get_default_export_format()
        if 'TR' in self.env.companies.country_id.mapped('code'):
            default = 'muhsgk'
        return default

    l10n_tr_accrual_reason = fields.Selection(
        selection=L10N_TR_ACCRUAL_REASON_SELECTION,
        string="Accrual Reason",
        default="A",
        help="The reason this payslip is created.",
    )

    def _get_slip_lines_totals(self):
        parameters_to_agg = ["l10n_tr_tax_exempt", "l10n_tr_stamp_tax_exempt"]

        totals_per_codes = self.env["hr.payslip.line"]._read_group(
            [("slip_id", "in", self.payslip_ids.ids)],
            ["slip_id.state", "slip_id.l10n_tr_payment_type_code", "code"],
            ["total:sum"],
        )

        allowance_totals_per_slip = dict(self.env['hr.payslip.line']._read_group(
            [
                ('slip_id', 'in', self.payslip_ids.ids),
                ('salary_rule_id.category_ids', 'in', self.env.ref("hr_payroll.ALW").id),
            ],
            ['slip_id'],
            ['total:sum'],
        ))

        res = {
            "totals_per_payment_code": defaultdict(lambda: defaultdict(lambda: 0)),
            "totals_per_code": defaultdict(lambda: 0),
            "unpaid_days": defaultdict(lambda: 0),
            "remote_days": defaultdict(lambda: 0),
            "allowance": allowance_totals_per_slip,
        }

        for d in totals_per_codes:
            state = d[0]
            payment_type_code = d[1]
            code = d[2]
            res["totals_per_code"][code] += d[3]

            if code == "NET" and state != "paid":
                res["totals_per_code"]["accrued_amount"] += d[3]

            if payment_type_code:
                res["totals_per_payment_code"][payment_type_code][code] += d[3]

        for payslip in self.payslip_ids:
            res["totals_per_payment_code"][payslip.l10n_tr_payment_type_code]["_count"] += 1
            for line in payslip.worked_days_line_ids:
                if not line.is_paid:
                    res["unpaid_days"][payslip] += line.number_of_days
                if line.work_entry_type_id in payslip.struct_id.l10n_tr_remote_work_entry_type_ids:
                    res["remote_days"][payslip] += line.number_of_days

            for parameter in parameters_to_agg:
                value = (
                    self.env["hr.rule.parameter"]._get_parameter_from_code(
                        parameter, payslip.date_from, raise_if_not_found=False,
                    )
                    or 0
                )
                res["totals_per_code"][parameter] += value
                if payslip.l10n_tr_payment_type_code:
                    res["totals_per_payment_code"][payslip.l10n_tr_payment_type_code][parameter] += value

        return res

    @api.model
    def _get_muhsgk2_partner_vals(self, employee):
        trade_registry_category = self.env.ref("l10n_tr_nilvera_einvoice.res_partner_category_ticaretsicilno", raise_if_not_found=False)
        trade_registry_number = employee.work_contact_id.category_id.filtered(lambda c: c.parent_id.id == trade_registry_category.id)[:1].name if trade_registry_category else False
        return {
            "last_name": employee.l10n_tr_last_name,
            "first_name": employee.l10n_tr_first_name,
            "id_number": employee.identification_id,
            "trade_registry_number": trade_registry_number,
            "email": employee.work_email,
            "area_code": employee.private_state_id.code and employee.private_state_id.code.zfill(3),
            "phone_number": employee.work_phone,
        }

    def _get_muhsgk2_general_vals(self):
        date_start = self.payslip_run_id.date_start or self.payslip_ids[:1].date_from
        tax_office_code = ("l10n_tr_tax_office_id" in self.company_id._fields and self.company_id.l10n_tr_tax_office_id.code) or "055254"
        return {
                "administrative": {
                    "tax_office_code": tax_office_code,
                    "period": {
                        "type": "aylik",
                        "year": date_start and date_start.strftime("%Y"),
                        "month": date_start and date_start.strftime("%-m"),
                    },
                },
                "tax_payer": self._get_muhsgk2_partner_vals(
                    self.company_id.l10n_tr_tax_reponsible_id,
                ),
            }

    def _get_tax_base_declarations(self, totals):
        return [
            {
                "type_code": payment_type.zfill(3),
                "gross_amount": abs(aggs.get("GROSS", 0)),
                "withholding_amount": abs(aggs.get("BTNET", 0)),
            }
            for payment_type, aggs in totals["totals_per_payment_code"].items()
        ]

    def _get_working_employees(self, totals):
        return [
            {
                "employee_code": str(idx).zfill(3),
                "total_employees": aggs["_count"],
                "income_tax_base": abs(aggs.get("CURTAXABLE", 0)),
                "income_tax_withholding": abs(aggs.get("BTNET", 0)),
                "au_exempted_it": abs(aggs.get("l10n_tr_tax_exempt", 0)),
                "au_exempted_st": abs(aggs.get("l10n_tr_stamp_tax_exempt", 0)),
                "stamp_tax_withholding": abs(aggs.get("STAX", 0)),
            }
            for idx, (_payment_type, aggs) in enumerate(totals["totals_per_payment_code"].items())
        ]

    def _get_sgk_declarations(self, totals):
        res = []
        payslip_lines_values = self.payslip_ids._get_line_values(["BASIC", "CURTAXABLE", "BTAXNET", "BTNET", "STAX"])
        for payslip in self.payslip_ids:
            employee = payslip.employee_id

            today = fields.Date.today()
            entry_date = employee._get_first_version_date()
            entry_month = entry_day = False
            if entry_date and entry_date.year == today.year and entry_date.month == today.month:
                entry_month = entry_date.strftime('%m')
                entry_day = entry_date.strftime('%d')

            departure_date = employee.current_version_id.departure_date
            departure_month = departure_day = False
            if departure_date and departure_date.year == today.year and departure_date.month == today.month:
                departure_month = departure_date.strftime('%m')
                departure_day = departure_date.strftime('%d')

            res.append(
                {
                    "document_nature": payslip.l10n_tr_document_nature,
                    "document_type": employee.l10n_tr_document_type,
                    "law": employee.l10n_tr_social_security_law,
                    "new_branch_code": payslip.company_id.l10n_tr_new_unit_code,
                    "old_branch_code": payslip.company_id.l10n_tr_old_unit_code,
                    "workplace_sequence_number": (payslip.company_id.l10n_tr_sgk_workspace_registration_no or "")[:7],
                    "workplace_city_code": employee.private_state_id.code and employee.private_state_id.code.zfill(3),
                    "workplace_agent_sequence_number": payslip.company_id.l10n_tr_sgk_intermediary_code,
                    "insured_registry": employee.l10n_tr_social_insurance_number,
                    "id_number": employee.identification_id,
                    "first_name": employee.l10n_tr_first_name,
                    "last_name": employee.l10n_tr_last_name,
                    "days_worked": 30 - totals["unpaid_days"].get(payslip, 0),
                    "remote_work_days": totals["remote_days"].get(payslip, 0),
                    "earned_wage": abs(payslip_lines_values["BASIC"][payslip.id]["total"]),
                    "bonus_premium": abs(totals["allowance"].get(payslip, 0)),
                    "entry_day": entry_day,
                    "entry_month": entry_month,
                    "exit_day": departure_day,
                    "exit_month": departure_month,
                    "exit_reason": employee.current_version_id.departure_reason_id.name,
                    "occupation_code": employee.l10n_tr_occupational_code,
                    "worked_during_report": 2,
                    "accrual_reason": self.l10n_tr_accrual_reason,
                    "service_month": payslip.date_from.strftime("%m"),
                    "service_year": payslip.date_from.strftime("%Y"),
                    "related_period_tax_base": abs(
                        payslip_lines_values["CURTAXABLE"][payslip.id]["total"],
                    ),
                    "tax_discount": abs(payslip_lines_values["BTAXNET"][payslip.id]["total"]),
                    "tax_withholding": abs(payslip_lines_values["BTNET"][payslip.id]["total"]),
                    "au_exempted_it": abs(
                        self.env["hr.rule.parameter"]._get_parameter_from_code(
                            "l10n_tr_tax_exempt", payslip.date_from, raise_if_not_found=False,
                        )
                        or 0,
                    ),
                    "au_exempted_st": abs(
                        self.env["hr.rule.parameter"]._get_parameter_from_code(
                            "l10n_tr_stamp_tax_exempt", payslip.date_from, raise_if_not_found=False,
                        )
                        or 0,
                    ),
                    "stamp_tax_withholding": abs(payslip_lines_values["STAX"][payslip.id]["total"]),
                },
            )
        return res

    def _get_muhsgk2_special_vals(self, totals):
        return {
                "branch_number": self.company_id.id
                if self.company_id.parent_id
                else "000",
                "declaration_exists": "1",
                "tax_base_declarations": self._get_tax_base_declarations(totals),
                "total_gross_amount": abs(totals["totals_per_code"].get("GROSS", 0)),
                "total_withholding_amount": abs(totals["totals_per_code"].get("BTNET", 0)),
                "amount_after_exemption": abs(totals["totals_per_code"].get("BTNET", 0)),
                "working_employees": self._get_working_employees(totals),
                "tax_base": abs(totals["totals_per_code"].get("CURTAXABLE", 0)),
                "accrued_amount": abs(totals["totals_per_code"].get("accrued_amount", 0)),
                "offset": 0,
                "payable": abs(totals["totals_per_code"].get("accrued_amount", 0)),
                "refundable": 0,
                "payable_stamp_tax": abs(totals["totals_per_code"].get("STAX", 0)),
                "sgk_employee_info": self._get_sgk_declarations(totals),
            }

    def _generate_muhsgk_file(self):
        totals = self._get_slip_lines_totals()
        return {
            "general": self._get_muhsgk2_general_vals(),
            "special": self._get_muhsgk2_special_vals(totals),
        }

    def generate_payment_report(self):
        super().generate_payment_report()
        if self.export_format == "muhsgk":
            xml_str = self.env['ir.qweb']._render(
                self.env.ref('l10n_tr_hr_payroll.muhsgk_v2').id,
                self._generate_muhsgk_file(),
            )
            root = cleanup_xml_node(xml_str, remove_blank_text=True)
            payment_report = etree.tostring(root, pretty_print=True, encoding='ISO-8859-9', xml_declaration=True)
            date_start = self.payslip_run_id.date_start or self.payslip_ids[:1].date_from
            self._write_file(payment_report, ".xml", f"1003B (MPHB) - {date_start.strftime('%m-%Y')}")
