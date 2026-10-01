from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrEmployeeType(models.Model):
    _inherit = 'hr.employee.type'
    _description = 'Employee Type'

    payroll_closing_date = fields.Selection(selection=lambda self: self.env.company._selection_payroll_closing_date(), string="Closing Date")
    payroll_auto_post = fields.Boolean(string="Auto Post", default=False, help="If checked, the payslips will be automatically created and validated when the closing date is reached.")

    @api.constrains('payroll_closing_date', 'payroll_auto_post')
    def _check_payroll_closing_date(self):
        for record in self:
            if record.payroll_auto_post and not record.payroll_closing_date:
                raise ValidationError(self.env._("The closing date must be set if auto post is enabled."))
