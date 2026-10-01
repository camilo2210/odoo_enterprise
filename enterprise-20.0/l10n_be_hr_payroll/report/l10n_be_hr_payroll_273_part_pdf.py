from odoo import api, models


class ReportL10n_Be_Hr_Payroll_273Part(models.AbstractModel):
    _name = 'report.l10n_be_hr_payroll.273_part'
    _description = 'Get 273 Part report as PDF.'

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': self.env['l10n_be.273_xx'],
            'data': data,
            'docs': self.env['l10n_be.273_xx'].browse(self.env.context.get('active_id')),
        }
