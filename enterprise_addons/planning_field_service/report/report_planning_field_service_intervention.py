# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import api, models


class ReportPlanning_Field_ServiceIntervention(models.AbstractModel):
    _name = 'report.planning_field_service.worksheet_custom'
    _description = 'Field Service Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['planning.slot'].sudo().browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'planning.slot',
            'docs': docs,
        }
