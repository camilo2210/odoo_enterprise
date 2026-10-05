from odoo import models


class HrPayrollWarning(models.Model):
    _inherit = "hr.payroll.warning"

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "This time off will be split into:\n%(lines)s":
            return self.env._("This time off will be split into:\n%(lines)s", **kwargs)
        if text == "This time off will be entirely replaced with %(code)s - %(name)s":
            return self.env._("This time off will be entirely replaced with %(code)s - %(name)s", **kwargs)
        if text == "- %(code)s - %(name)s: %(nbr_days)s days":
            return self.env._("- %(code)s - %(name)s: %(nbr_days)s days", **kwargs)
        return super()._get_payroll_translation(text, **kwargs)
