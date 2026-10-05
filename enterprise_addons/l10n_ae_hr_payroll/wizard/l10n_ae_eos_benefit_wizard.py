# Part of Odoo. See LICENSE file for full copyright and licensing details.

from io import BytesIO
import xlsxwriter


from odoo import api, fields, models
from odoo.tools import BinaryBytes
from odoo.tools.misc import format_date
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class L10nAeEosBenefitWizard(models.TransientModel):
    _name = 'l10n.ae.eos.benefit.wizard'
    _description = 'EOS Benefit Wizard'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "AE":
            raise UserError(self.env._('This feature seems to be as exclusive as the Burj Khalifa. You must be logged in to a UAE company to use it.'))
        return super().default_get(fields)

    date_to = fields.Date(default=lambda s: fields.Date.today() + relativedelta(day=31))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, required=True)
    employee_ids = fields.Many2many('hr.employee', string='Employees', domain="[('company_id', '=', company_id)]")
    eosb_filename_xlsx = fields.Char()
    eosb_xlsx = fields.Binary('End of Service Benefit Spreadsheet', readonly=True, attachment=False)
    state_xlsx = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')
    issues = fields.Boolean(string="Issues", compute="_compute_issues")

    def _get_report_data(self):
        report_data = []

        # Populate employee_ids if none is selected
        if not self.employee_ids:
            self.employee_ids = self.env['hr.employee'].search([('company_id', '=', self.company_id.id)])

        # Report computation
        for employee in self.employee_ids:
            eosb_amount = employee.version_id._l10n_ae_get_eos_compensation(at_date=self.date_to)
            report_data.append(
                {
                    'employee_name': employee.name,
                    'employee_id': employee.id,
                    'first_contract_date': min(employee._get_first_versions().mapped('date_start') or [False]),
                    'selected_end_date': self.date_to,
                    'eosb_amount': eosb_amount,
                }
            )

        return report_data

    @api.depends('employee_ids', 'date_to')
    def _compute_issues(self):
        for record in self:
            record.issues = any(employee.version_id.departure_date and employee.version_id.departure_date < record.date_to for employee in record.employee_ids)

    def export_report_xlsx(self):
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        eos_worksheet = workbook.add_worksheet(self.env._('EOS Benefit'))

        # styling
        style_header = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center', 'bottom': 1})
        style_normal = workbook.add_format({'align': 'center'})
        style_date = workbook.add_format({'num_format': 'yyyy-mm-dd', 'align': 'center'})
        currency = self.company_id.currency_id
        if currency.position == 'before':
            style_monetary = workbook.add_format({'num_format': self.env._('"%(symbol)s" ###,###,##0.00', symbol=currency.symbol), 'align': 'center'})
        else:
            style_monetary = workbook.add_format({'num_format': self.env._('###,###,##0.00 "%(symbol)s"', symbol=currency.symbol), 'align': 'center'})
        column_width = 40

        eos_headers = ['Employee Name', 'Employee ID', 'First Contract Date', 'Selected End Date', 'EOSB Amount']
        report_data = self._get_report_data()

        current_line = 0
        for i, header in enumerate(eos_headers):
            eos_worksheet.write(current_line, i, header, style_header)
            eos_worksheet.set_column(i, i, column_width)
        current_line += 1

        for line in report_data:
            eos_worksheet.write(current_line, 0, line['employee_name'], style_normal)
            eos_worksheet.write(current_line, 1, line['employee_id'], style_normal)
            eos_worksheet.write(current_line, 2, line['first_contract_date'], style_date)
            eos_worksheet.write(current_line, 3, line['selected_end_date'], style_date)
            eos_worksheet.write(current_line, 4, line['eosb_amount'], style_monetary)
            current_line += 1

        workbook.close()
        base64_xlsx = BinaryBytes(output.getvalue())
        filename = self.env._('EOSB report as per %(date_to)s', date_to=format_date(self.env, self.date_to))
        self.eosb_filename_xlsx = filename
        self.eosb_xlsx = base64_xlsx
        self.state_xlsx = 'done'

        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('EOS Benefits'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
