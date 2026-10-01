from odoo import models


class HrPayrollWarning(models.Model):
    _inherit = 'hr.payroll.warning'

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "Payroll CFDIs must be issued no later than %(deadline)s.":
            return self.env._("Payroll CFDIs must be issued no later than %(deadline)s.", **kwargs)
        return super()._get_payroll_translation(text, **kwargs)
