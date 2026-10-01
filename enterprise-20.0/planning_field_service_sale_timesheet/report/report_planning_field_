# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import api, models


class ReportPlanning_Field_ServiceIntervention(models.AbstractModel):
    _inherit = 'report.planning_field_service.worksheet_custom'

    @api.model
    def _get_report_values(self, docids, data=None):
        report_values = super()._get_report_values(docids, data=data)
        report_values['allow_material'] = self.env['res.groups']._is_feature_enabled('planning.group_field_service_allow_material')
        return report_values
