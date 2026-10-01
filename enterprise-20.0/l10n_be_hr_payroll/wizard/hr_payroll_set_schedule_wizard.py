from odoo import models


class HrPayrollSetScheduleWizard(models.TransientModel):
    _inherit = 'hr.payroll.set.schedule.wizard'

    def action_save(self):
        res = super().action_save()
        if self.env.company.current_payroll_config_id.l10n_be_employer_category_id.dmfa_code:
            self.env['l10n.be.onss.rates.import.wizard']._fetch_onss_rates_since(self.first_payrun_date.year, (self.first_payrun_date.month - 1) // 3 + 1)
        return res
