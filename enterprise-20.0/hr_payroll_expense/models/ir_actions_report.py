from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _hr_expense_get_payment_mode_name_map(self):
        # EXTENDS hr_expense

        res = super()._hr_expense_get_payment_mode_name_map()
        res['payslip_account'] = self.env._("Employee")  # To merge it with the employee one
        return res
