from odoo import models


class HrPayrollWarning(models.Model):
    _inherit = 'hr.payroll.warning'

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "Employee":
            return self.env._("Employee")
        if text == "No birthdate":
            return self.env._("No birthdate")
        return super()._get_payroll_translation(text, **kwargs)
