# Part of Odoo. See LICENSE file for full copyright and licensing details.

from io import BytesIO
import xlsxwriter


from odoo import api, fields, models
from odoo.tools import BinaryBytes
from odoo.exceptions import UserError


class L10nSaGOSIWageUpdate(models.TransientModel):
    _name = 'l10n.sa.gosi.wage.update'
    _description = 'GOSI wage update'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "SA":
            raise UserError(self.env._('This feature seems to be as exclusive as the Clock Tower. You must be logged in to a Saudi company to use it.'))
        return super().default_get(fields)

    line_ids = fields.One2many(
    'l10n.sa.gosi.wage.update.line', 'sheet_id',
    compute='_compute_line_ids', store=True, readonly=False)
    gosi_filename_xlsx = fields.Char()
    gosi_xlsx = fields.Binary('GOSI wage update Sheet', readonly=True, attachment=False)
    state_xlsx = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')

    def _compute_line_ids(self):
        for sheet in self:
            employees = self.env['hr.employee'].search([
                ('company_id', '=', self.env.company.id),
                ('activity_ids.technical_usage', '=', 'l10n_sa_gosi_wage_update'),
            ])
            result = [(5, 0, 0)]
            for employee in employees:
                result.append((0, 0, {
                    'employee_id': employee.id,
                    'sheet_id': sheet.id,
                }))
            sheet.line_ids = result

    def export_report_xlsx(self):
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        gosi_worksheet = workbook.add_worksheet(self.env._('GOSI wage update'))

        # styling
        style_header = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center', 'bottom': 1})
        style_normal = workbook.add_format({'align': 'center'})
        currency = self.line_ids.currency_id
        if currency.position == 'before':
            style_monetary = workbook.add_format({'num_format': self.env._('"%(symbol)s" ###,###,##0.00', symbol=currency.symbol), 'align': 'center'})
        else:
            style_monetary = workbook.add_format({'num_format': self.env._('###,###,##0.00 "%(symbol)s"', symbol=currency.symbol), 'align': 'center'})
        column_width = 40

        gosi_wage_headers = ['Contributor', 'Identification Number', 'Basic Wage', 'Housing', 'Other Allowances']
        report_data = self.line_ids

        current_line = 0
        for i, header in enumerate(gosi_wage_headers):
            gosi_worksheet.write(current_line, i, header, style_header)
            gosi_worksheet.set_column(i, i, column_width)
        current_line += 1

        for line in report_data:
            gosi_worksheet.write(current_line, 0, line['employee_name'], style_normal)
            gosi_worksheet.write(current_line, 1, line['identification_number'], style_normal)
            gosi_worksheet.write(current_line, 2, line['wage'], style_monetary)
            gosi_worksheet.write(current_line, 3, line['housing'], style_monetary)
            gosi_worksheet.write(current_line, 4, line['other_allowance'], style_monetary)
            current_line += 1

        workbook.close()
        base64_xlsx = BinaryBytes(output.getvalue())
        filename = self.env._('GOSI wage update report')
        self.gosi_filename_xlsx = filename
        self.gosi_xlsx = base64_xlsx
        self.state_xlsx = 'done'

        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('GOSI wage update'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }


class L10nSaGOSIWageUpdateLine(models.TransientModel):
    _name = 'l10n.sa.gosi.wage.update.line'
    _description = 'GOSI wage update lines'

    sheet_id = fields.Many2one('l10n.sa.gosi.wage.update')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id, required=True)
    employee_id = fields.Many2one('hr.employee')
    employee_name = fields.Char(string="Contributor", related='employee_id.name')
    identification_number = fields.Char(string="ID number", related='employee_id.l10n_sa_employee_code')
    wage = fields.Monetary(related="employee_id.wage", string="Basic Wage")
    housing = fields.Monetary(related="employee_id.l10n_sa_housing_allowance", string="Housing")
    other_allowance = fields.Monetary(related="employee_id.l10n_sa_other_allowances", string="Other Allowances")
