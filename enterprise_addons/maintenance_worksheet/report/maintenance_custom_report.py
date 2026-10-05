# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ReportMaintenance_WorksheetMaintenance_Worksheet(models.AbstractModel):
    _name = 'report.maintenance_worksheet.maintenance_worksheet'
    _description = 'Maintenance Request Worksheet Custom Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['maintenance.request'].browse(docids).sudo()
        return {
            'doc_model': 'maintenance.request',
            'doc_ids': docids,
            'docs': docs,
        }
