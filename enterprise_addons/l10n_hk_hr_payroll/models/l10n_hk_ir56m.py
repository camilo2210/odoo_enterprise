# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import format_date


class L10nHkIr56m(models.Model):
    _name = "l10n_hk.ir56m"
    _inherit = ["l10n_hk.ird"]
    _description = "IR56M Sheet"
    _order = "start_period"

    # ------------------
    # Fields declaration
    # ------------------

    year_of_employer_return = fields.Char("Year of Employer's Return", compute="_compute_year_of_employer_return", store=True, readonly=False)

    @api.depends("submission_date")
    def _compute_year_of_employer_return(self):
        for sheet in self:
            sheet.year_of_employer_return = str(sheet.submission_date.year) if sheet.submission_date else str(date.today().year)

    @api.depends("year_of_employer_return", "start_month", "end_month")
    def _compute_period(self):
        for sheet in self:
            sheet.start_period = date(int(sheet.year_of_employer_return) - 1, int(sheet.start_month), 1)
            sheet.end_period = date(int(sheet.year_of_employer_return), int(sheet.end_month), 1) + relativedelta(day=31)

    def _compute_separate_original_from_adjustments(self):
        self.separate_original_from_adjustments = True

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends("start_period", "end_period")
    def _compute_display_name(self):
        lang_code = self.env.user.lang or "en_US"
        for sheet in self:
            if sheet.start_period and sheet.end_period:
                sheet.display_name = sheet.env._(
                    "From %(start_period)s to %(end_period)s",
                    start_period=format_date(self.env, sheet.start_period, date_format="MMMM y", lang_code=lang_code),
                    end_period=format_date(self.env, sheet.end_period, date_format="MMMM y", lang_code=lang_code),
                )
            else:
                sheet.display_name = sheet.env._("IR56M Sheet")

    # ----------------
    # Business methods
    # ----------------

    def _validate_employee_personal_info(self, employees):
        individuals = employees.filtered(lambda e: not e.work_contact_id.is_company)
        return super()._validate_employee_identification(individuals)

    def _validate_employee_identification(self, employees):
        individuals = employees.filtered(lambda e: not e.work_contact_id.is_company)
        return super()._validate_employee_identification(individuals)

    def _get_report_version_domain(self):
        """Filters to ONLY include Freelancers / Contractors who meet the income thresholds."""
        self.ensure_one()
        contractor_type = self.env.ref("l10n_hk_hr_payroll.l10n_hk_contract_type_contractor")
        non_employee_type = self.env.ref("l10n_hk_hr_payroll.l10n_hk_contract_type_non_employee")

        payslips = self.env['hr.payslip'].search([
            ("state", "in", ["validated", "paid"]),
            ("company_id", "=", self.company_id.id),
            ("date_to", ">=", self.start_period),
            ("date_to", "<=", self.end_period),
            ("version_id.employee_type_id", "in", [
                non_employee_type.id,
                contractor_type.id,
            ]),
        ])

        if not payslips:
            return Domain.FALSE

        valid_version_ids = []
        for version, version_payslips in payslips.grouped('version_id').items():
            threshold = (200000 if version.employee_type_id == contractor_type else 25000)
            if sum(version_payslips.mapped('net_wage')) >= threshold:
                valid_version_ids.append(version.id)

        return Domain([
            ('company_id', '=', self.company_id.id),
            ('contract_date_start', '!=', False),
            ('contract_date_start', '<=', self.end_period),
            '|',
            ('contract_date_end', '=', False),
            ('contract_date_end', '>', self.end_period),
            ('id', 'in', valid_version_ids),
        ])

    def _get_rendering_data(self, employees):
        self.ensure_one()

        if employees_error := self._check_employees(employees):
            return {"error": employees_error}

        report_info = self._get_report_info_data()

        try:
            payslip_info = self._get_employees_payslip_data(employees)
        except UserError as e:
            return {"error": str(e)}

        all_payslips = payslip_info["all_payslips"]

        employee_payslips = defaultdict(lambda: self.env["hr.payslip"])
        for payslip in all_payslips.sorted("employee_id"):
            employee_payslips[payslip.employee_id] |= payslip

        all_lines_values = all_payslips._get_line_values(set(all_payslips.line_ids.mapped('code')), compute_sum=True)

        employee_declarations = self.line_ids.grouped('employee_id')
        employees_data = []
        for sequence, employee in enumerate(employee_payslips, start=900001):  # IR56M spec starts at 900001
            payslips = employee_payslips[employee]
            mapped_periods = {}
            for code in all_lines_values:
                active_slips = [p for p in payslips if all_lines_values.get(code, {}).get(p.id, {}).get("total", 0.0) > 0]
                if active_slips:
                    min_date = min(p.date_from for p in active_slips)
                    max_date = max(p.date_to for p in active_slips)
                    mapped_periods[code] = f"{min_date.strftime('%d/%m/%Y')} - {max_date.strftime('%d/%m/%Y')}"
                else:
                    mapped_periods[code] = ""

            is_company = employee.work_contact_id.is_company
            payslip_start = min(payslips.mapped('date_from'))
            payslip_end = max(payslips.mapped('date_to'))
            other_lines = payslips.mapped('line_ids').filtered(lambda l: l.code == 'OTHER' and l.total > 0)
            other_names = list(set(other_lines.mapped('name')))

            _, categories_totals = payslips._l10n_hk_aggregate_totals(all_lines_values)
            amt_withheld = self._format_ird_amount(categories_totals["WITHHELD_DED"])
            sheet_values = {
                **self._get_employee_data(employee),
                **self._get_employee_spouse_data(employee),
                "SheetNo": sequence,
                'TypeOfForm': employee_declarations.get(employee).l10n_hk_hr_payroll_type_of_form,
                "RTN_ASS_YR": self.year_of_employer_return,
                "StartDateOfEmp": payslip_start,
                "EndDateOfEmp": payslip_end,
                "TotalIncome": self._format_ird_amount(categories_totals["FEE"]),
                "ComRecNameEng": "",
                "ComRecNameChi": "",
                "ComRecBRN": "",
                "PeriodOfType1": mapped_periods.get("SUBCON_FEE"),
                "PeriodOfType2": mapped_periods.get("COMMISSION"),
                "PeriodOfType3": mapped_periods.get("WRITER_FEE"),
                "PeriodOfArtistFee": mapped_periods.get("ARTIST_FEE"),
                "PeriodOfCopyright": mapped_periods.get("ROYALTIES"),
                "PeriodOfConsultFee": mapped_periods.get("CONSULT_FEE"),
                "PeriodOfServiceFee": mapped_periods.get("SERVICE_FEE"),
                "AmtOfType1": self._format_ird_amount(categories_totals["FEE_SUBCON"]),
                "AmtOfType2": self._format_ird_amount(categories_totals["FEE_COMMISSION"]),
                "AmtOfType3": self._format_ird_amount(categories_totals["FEE_WRITER"]),
                "AmtOfArtistFee": self._format_ird_amount(categories_totals["FEE_ARTIST"]),
                "AmtOfCopyright": self._format_ird_amount(categories_totals["FEE_ROYALTY"]),
                "AmtOfConsultFee": self._format_ird_amount(categories_totals["FEE_CONSULT"]),
                "AmtOfServiceFee": self._format_ird_amount(categories_totals["FEE_SERVICE"]),
                "NatureOtherInc": other_names[0] if len(other_names) == 1 else ("Others" if other_names else ""),
                "AmtOfOtherInc": self._format_ird_amount(categories_totals["FEE_OTHER"]) if other_lines else "",
                "Remarks": "",
                "IndOfSumWithheld": 1 if amt_withheld > 0 else 0,
                "AmtOfSumWithheld": amt_withheld or 0,
            }

            if is_company:
                sheet_values.update({
                    "ComRecNameEng": employee.work_contact_id.name or "",
                    "ComRecNameChi": employee.l10n_hk_name_in_chinese or "",
                    "ComRecBRN": employee.work_contact_id._get_additional_identifier('HK_BRN') or employee.work_contact_id.vat or "",
                    "HKID": "",
                    "Surname": "",
                    "GivenName": "",
                    "NameInChinese": "",
                    "Sex": "",
                    "MaritalStatus": "",
                    "SpouseName": "",
                    "SpouseHKID": "",
                    "SpousePpNum": "",
                })

            employees_data.append(sheet_values)

        total_data = {
            "NoRecordBatch": f"{len(employees_data):05}",
            "TotIncomeBatch": self._format_ird_amount(sum(ed['TotalIncome'] for ed in employees_data)),
        }

        return {"data": report_info, "employees_data": employees_data, "total_data": total_data}

    def _get_xml_report_xsd_schemas(self, type_of_form):
        self.ensure_one()
        return {
            "O": self._get_xml_resource("ir56m_annual.xsd"),
            "ARS": self._get_xml_resource("ir56m_additional_replacement_supplementary.xsd"),
        }.get(type_of_form)

    def _get_xml_report_filename(self, file_number=False):
        self.ensure_one()
        company_name = self.company_id.name.replace(" ", "_")
        if file_number:
            return f"{company_name}_IR56M_{self.year_of_employer_return}_{self.type_of_form}_{file_number}.xml"
        return f"{company_name}_IR56M_{self.year_of_employer_return}_{self.type_of_form}.xml"

    def _get_xml_report_template(self):
        self.ensure_one()
        return "l10n_hk_hr_payroll.ir56m_xml_report"

    def _get_pdf_report(self):
        return self.env.ref("l10n_hk_hr_payroll.action_report_employee_ir56m", raise_if_not_found=False)

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        employee_name = employee.name.replace(" ", "_")
        return self.env._("%(employee_name)s_IR56M_%(start_year)s", employee_name=employee_name, start_year=self.start_year)

    def _post_process_rendering_data_pdf(self, rendering_data):
        result = {}
        for sheet_values in rendering_data['employees_data']:
            result[sheet_values['employee']] = {**sheet_values, **rendering_data['data']}
        return result
