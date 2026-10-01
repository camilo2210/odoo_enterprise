from odoo import models


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_payment_report(self, export_format='sepa'):
        action = super().action_payment_report()
        default_export_format = None
        if self.company_id.country_code == 'CH':
            default_export_format = 'iso20022_ch'
        elif self.company_id.currency_id.name == 'EUR':
            default_export_format = export_format

        if default_export_format:
            action.update({
                'context': {
                    **action['context'],
                    'default_export_format': default_export_format,
                },
            })
        return action
