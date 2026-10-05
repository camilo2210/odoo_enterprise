# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes
from odoo.tools.misc import format_date


class L10nEgNosiForm2Wizard(models.TransientModel):
    _name = 'l10n.eg.nosi.form2.wizard'
    _description = 'Egypt NOSI Form 2 Wizard'
    _inherit = 'l10n.eg.nosi.export.wizard'

    def action_generate_report(self):
        self.ensure_one()
        employees = self.employee_ids
        company = self.company_id

        # validation of mandatory fields company and employees,
        self._validate_company_and_employee_data()

        # generate xlsx report
        output = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
        style_bold = workbook.add_format({'bold': True, 'align': 'center'})
        style_normal = workbook.add_format({'align': 'center'})

        # company details
        company_header_data_map = {
            self.env._('NOSI Registration'): company.l10n_eg_nosi_code,
            self.env._('Company Name'): company.name,
            self.env._('Company VAT ID'): company.vat,
            self.env._('Company Address'): company.partner_id._display_address().replace('\n', ', '),
        }
        worksheet.merge_range(0, 0, 0, len(company_header_data_map) - 1, self.env._('Company Details'), style_highlight)
        for col, data in enumerate(company_header_data_map.items()):
            header = data[0]
            value = data[1]
            worksheet.write(1, col, header, style_bold)
            worksheet.write(2, col, value, style_normal)
            worksheet.set_column(col, col, 30)

        # employee headers
        employee_header = [
            self.env._('Insurance Number'),
            self.env._('Name'),
            self.env._('ID/National Number'),
            self.env._('Joining Date'),
            self.env._('NOSI Contribution Amount'),
            self.env._('Total Salary'),
        ]
        worksheet.merge_range(4, 0, 4, len(employee_header) - 1, self.env._('Employees Details'), style_highlight)
        for col, header in enumerate(employee_header):
            worksheet.write(5, col, header, style_bold)
            worksheet.set_column(col, col, 30)

        def _get_employee_row_datas(employee):
            return [
                employee.l10n_eg_ssn, employee.name, employee.identification_id,
                format_date(self.env, employee.contract_date_start),
                employee.l10n_eg_social_insurance_reference,
                employee.current_version_id._get_contract_wage(),
            ]

        for row, employee in enumerate(employees, start=6):
            for col, data in enumerate(_get_employee_row_datas(employee)):
                worksheet.write(row, col, data, style_normal)

        workbook.close()
        xlsx_data = output.getvalue()
        attachment = self.env['ir.attachment'].create({
            'name': 'Nosi_form_2.xlsx',
            'raw': BinaryBytes(xlsx_data),
            'res_model': 'ir.ui.view',
            'res_id': 0,
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def _validate_company_and_employee_data(self):
        def get_missing_fields(record, required_fields):
            missing = []
            fields = record._fields
            for field_name in required_fields:
                if not record[field_name]:
                    label = fields[field_name].string
                    missing.append(label)
            return missing

        error_message = []
        company_missing_fields = get_missing_fields(self.env.company, ['vat', 'l10n_eg_nosi_code'])
        if company_missing_fields:
            error_message.append(
                self.env._('Cannot create NOSI form-2 company missing:\n- %(fields)s',
                    fields='\n- '.join(company_missing_fields)
                )
            )
        for emp in self.employee_ids:
            employee_missing_fields = get_missing_fields(
                emp,
                ['l10n_eg_ssn', 'identification_id', 'contract_date_start', 'wage', 'l10n_eg_social_insurance_reference']
            )
            if employee_missing_fields:
                error_message.append(
                    self.env._('Cannot create NOSI form-2 for %(name)s. Missing:\n- %(fields)s',
                        name=emp.name,
                        fields='\n- '.join(employee_missing_fields)
                    )
                )
        if error_message:
            raise UserError('\n\n'.join(error_message))
