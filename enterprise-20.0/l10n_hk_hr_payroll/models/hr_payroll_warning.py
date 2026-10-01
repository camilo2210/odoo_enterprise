from odoo import models


class HrPayrollWarning(models.Model):
    _inherit = 'hr.payroll.warning'

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "Rental":
            return self.env._("Rental")
        if text == "The employee rental's 'Valid Up To' date is missing or expired.":
            return self.env._("The employee rental's 'Valid Up To' date is missing or expired.")
        return super()._get_payroll_translation(text, **kwargs)
