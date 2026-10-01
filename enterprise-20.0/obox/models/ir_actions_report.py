import base64

from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    @api.model
    def get_print_jobs(self, report_name: str, docids: list[int], data) -> list:
        jobs = super().get_print_jobs(report_name, docids, data)
        report = self._get_report(report_name)
        obox_printer_ids = report.printer_ids.filtered(lambda p: p.type == "obox")
        if not obox_printer_ids:
            return jobs

        report_data = self._render(report_name, docids, data)[0]
        if report_data:  # if the report is shipping labels/docs, report is empty
            jobs.append({"type": "obox", "report": base64.b64encode(report_data).decode()})
        return jobs
