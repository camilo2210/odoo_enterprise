from odoo import models, api


class ReportAccountReport_Invoice(models.AbstractModel):
    _name = 'report.l10n_mx_edi.report_mx_cancel_ack'
    _description = 'Acknowledgement of CFDI cancellation request'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['l10n_mx_edi.document'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'l10n_mx_edi.document',
            'docs': docs,
        }
