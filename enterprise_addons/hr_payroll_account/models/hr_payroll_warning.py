from odoo import models


class HrPayrollWarning(models.Model):
    _inherit = 'hr.payroll.warning'

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "No Journal on Structure":
            return self.env._("No Journal on Structure")
        if text == "Structure":
            return self.env._("Structure")
        return super()._get_payroll_translation(text, **kwargs)
