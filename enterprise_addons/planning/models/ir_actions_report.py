# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def create_action(self):
        """Prevent adding the planning report to the print menu.

        The planning report requires specific data preparation that is only done
        through the custom Print action in calendar/Gantt views.
        """
        if any(report.report_name == "planning.slot_report" for report in self):
            raise UserError(
                self.env._(
                    "The Planning report cannot be added to the print menu. "
                    "Please use the Print action available in the Planning calendar and Gantt views."
                )
            )
        return super().create_action()

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Validate that the planning report is called with required data.

        The planning report requires pre-processed data (weeks, grouped slots, etc.)
        that is only prepared by the action_print_plannings() method called from
        the custom Print action in calendar/Gantt views. If called without this data
        (e.g., from the standard Print menu for users who already added it), raise an error.
        """
        report = self._get_report(report_ref)
        if report.report_name == "planning.slot_report" and not self.env.context.get("allow_printing_planning_report"):
            raise UserError(
                self.env._(
                    "The Planning report cannot be printed from here. "
                    "Please use the Print action available in the Planning calendar and Gantt views."
                )
            )
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
