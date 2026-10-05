# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import UserError


class HrPayslipCorrectionWizard(models.TransientModel):
    _inherit = "hr.payslip.correction.wizard"

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code == "CH":
            raise UserError(self.env._(
                'This feature is not available for payslips in Switzerland. '
                'If you wish to correct amounts please cancel the payslip or report corrections to the next month.'))
        return super().default_get(fields)
