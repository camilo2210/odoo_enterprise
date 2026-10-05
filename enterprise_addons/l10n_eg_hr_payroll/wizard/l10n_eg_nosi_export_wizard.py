# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io

import xlsxwriter
from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nEgNosiExportWizard(models.AbstractModel):
    _name = 'l10n.eg.nosi.export.wizard'
    _description = 'Egypt NOSI Forms Export Wizard'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "EG":
            raise UserError(self.env._('You must be logged in to an Egyptian company to use this feature.'))
        return super().default_get(fields)

    employee_ids = fields.Many2many(
        'hr.employee',
        string='Employees',
        required=True,
        domain="[('company_id', '=', company_id)]",
        context={'active_test': False},
        help='Select employees to generate NOSI forms for.')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company)

    def _generate_xlsx_report(self, sheet_name, headers, data_rows, column_format_specs=None):
        """
        Generic method to generate an XLSX file in memory and return its binary content.
        """
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet(sheet_name)

        header_format = workbook.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "bg_color": "#D3D3D3", "border": 1,
        })
        default_cell_format = workbook.add_format({"border": 1})

        column_formats = []
        if column_format_specs:
            for spec in column_format_specs:
                column_formats.append(workbook.add_format(spec) if spec else default_cell_format)

        for col_num, header in enumerate(headers):
            sheet.write(0, col_num, header, header_format)
            sheet.set_column(col_num, col_num, len(header) + 5)

        for row_num, row_data in enumerate(data_rows, 1):
            for col_num, cell_data in enumerate(row_data):
                cell_format = default_cell_format
                if col_num < len(column_formats):
                    cell_format = column_formats[col_num]
                sheet.write(row_num, col_num, cell_data, cell_format)

        workbook.close()
        output.seek(0)
        return output.read()

    def _validate_employee_data_nosi(self, employees, company_fields, employee_fields):
        """
        Generic validation method to check for missing mandatory fields.
        """
        employees_with_missing_data = []
        missing_fields_set = set()
        for employee in employees:
            found_missing_field = False
            for field, label in company_fields.items():
                if not employee.company_id[field]:
                    missing_fields_set.add(label)
                    found_missing_field = True
            for field, label in employee_fields.items():
                value = employee[field]
                if (not value) and not (isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0):
                    missing_fields_set.add(label)
                    found_missing_field = True
            if found_missing_field:
                employees_with_missing_data.append(employee.name)

        if employees_with_missing_data:
            employee_names = ", ".join(sorted(employees_with_missing_data))
            field_names = ", ".join(sorted(missing_fields_set))
            raise UserError(
                self.env._(
                    "Cannot complete export. Employees %(employees)s have at least one of the "
                    "following fields missing: %(fields)s",
                    employees=employee_names,
                    fields=field_names,
                ))

    def _export_nosi_form_generic(
        self, form_name, file_name, company_mandatory_fields, employee_mandatory_fields,
        headers, data_mapper_func, column_formats=None, extra_validation_func=None):
        """
        Generic orchestrator for exporting NOSI forms.
        """
        employees = self.employee_ids
        if not employees:
            raise UserError(self.env._("Please select at least one employee"))

        if extra_validation_func:
            extra_validation_func(employees)

        self._validate_employee_data_nosi(employees, company_mandatory_fields, employee_mandatory_fields)

        report_data = [data_mapper_func(emp) for emp in employees]

        xlsx_data = self._generate_xlsx_report(form_name, headers, report_data, column_formats)

        attachment = self.env["ir.attachment"].create({
            "name": file_name,
            "raw": xlsx_data,
            "res_model": "ir.ui.view",
            "res_id": 0,
            "type": "binary",
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "new",
        }

    def action_generate_report(self):
        """Generate the NOSI form."""
        raise NotImplementedError()
