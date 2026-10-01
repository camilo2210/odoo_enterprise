# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    iso20022_uetr = fields.Char(
        string='UETR',
        help='Unique end-to-end transaction reference',
    )

    def _get_iso20022_communication(self, bank_account):
        """ Communication displayed to the payee on their bank statement (RmtInf/Ustrd). """
        self.ensure_one()
        return str(self.id)

    def action_payslip_payment_report(self, export_format='sepa'):
        action = super().action_payslip_payment_report()
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
