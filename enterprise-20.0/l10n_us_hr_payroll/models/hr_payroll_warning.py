from odoo import models


class HrPayrollWarning(models.Model):
    _inherit = 'hr.payroll.warning'

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "The payment date has not been set. The payslip close date (%(date)s) will be used as the reference date for tax calculations, YTD calculations and applicable tax parameters. If you set a payment date later, please recompute the payslip to update the calculations.":
            return self.env._("The payment date has not been set. The payslip close date (%(date)s) will be used as the reference date for tax calculations, YTD calculations and applicable tax parameters. If you set a payment date later, please recompute the payslip to update the calculations.", **kwargs)
        return super()._get_payroll_translation(text, **kwargs)
