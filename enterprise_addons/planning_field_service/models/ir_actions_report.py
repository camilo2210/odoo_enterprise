from odoo import models
from odoo.exceptions import ValidationError


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        if self._get_report(report_ref).report_name == 'planning_field_service.worksheet_custom':
            interventions = self.env['planning.slot'].browse(res_ids).filtered(lambda slot: slot._is_intervention_report_available())
            if interventions:
                return super()._render_qweb_pdf(report_ref, res_ids=interventions.ids, data=data)
            else:
                raise ValidationError(
                    self.env._('The field service report is unavailable for the selected interventions as they do not contain any timesheets, products, or worksheets.')
                )
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
