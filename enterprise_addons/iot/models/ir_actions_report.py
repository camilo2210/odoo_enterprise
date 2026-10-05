# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    @api.model
    def get_print_jobs(self, report_name: str, docids: list[int], data) -> list:
        """IoT Boxes will print any job rendered in this method, no matter
        the type of the report.

        We then don't render again the ZPL reports as they already are by the
        parent method.
        """
        jobs = super().get_print_jobs(report_name, docids, data)
        report = self._get_report(report_name)
        iot_printer_ids = report.printer_ids.filtered(lambda p: p.type == "iot")
        if report.report_type == "qweb-text" and ".zpl" in report.name.lower() or not iot_printer_ids:
            # ZPL reports are already in the jobs list
            return jobs

        report_data = self._render(report_name, docids, data)[0]
        if report_data:  # if the report is shipping labels/docs, report is empty
            jobs.append({"type": "iot", "report": base64.b64encode(report_data).decode()})
        return jobs

    def get_select_printer_wizard(self, cached: dict | None = None):
        res = super().get_select_printer_wizard(cached)

        res["context"]["printer_ids"] = self.printer_ids.mapped(lambda p: {
            "id": p.id,
            "ip_address": p.ip_address,
            "name": p.name,
            "type": p.type,
            "iot_id": p.iot_device_id.iot_id.id if p.iot_device_id else None,
            "identifier": p.iot_device_id.identifier if p.iot_device_id else None,
        })
        res["context"]["report_name"] = self.name  # to allow hiding duplex option depending on report
        cached = cached or {}
        self.env["select.printers.wizard"].browse(res["res_id"]).write({
            "duplex": cached.get("duplex", True),
        })
        return res
