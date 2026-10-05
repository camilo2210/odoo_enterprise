from odoo import models


class HrPayrollWarning(models.Model):
    _inherit = 'hr.payroll.warning'

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "Contract":
            return self.env._("Contract")
        if text == "Employee":
            return self.env._("Employee")
        if text == "Missing Employer Unique Id in payroll settings.":
            return self.env._("Missing Employer Unique Id in payroll settings.")
        if text == "Missing Routing ID for the employee bank account.":
            return self.env._("Missing Routing ID for the employee bank account.")
        if text == "Missing salaries bank account in payroll settings.":
            return self.env._("Missing salaries bank account in payroll settings.")
        if text == "Missing unique Identification No. for the current employee.":
            return self.env._("Missing unique Identification No. for the current employee.")
        return super()._get_payroll_translation(text, **kwargs)
