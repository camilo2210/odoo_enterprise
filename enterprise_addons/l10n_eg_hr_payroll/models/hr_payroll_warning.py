from odoo import models


class HrPayrollWarning(models.Model):
    _inherit = 'hr.payroll.warning'

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "Employee":
            return self.env._("Employee")
        if text == "Missing field '%(field_label)s' to print ETA-form2.":
            return self.env._("Missing field '%(field_label)s' to print ETA-form2.", **kwargs)
        return super()._get_payroll_translation(text, **kwargs)
