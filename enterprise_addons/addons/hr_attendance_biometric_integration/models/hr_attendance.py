# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    in_mode = fields.Selection(selection_add=[("biometric", "Biometric")])
    out_mode = fields.Selection(selection_add=[("biometric", "Biometric")])
    biometric_check_in_event_id = fields.Many2one(
        "hr.attendance.biometric.event",
        string="Biometric Check-In Event",
        readonly=True,
        ondelete="restrict",
    )
    biometric_check_out_event_id = fields.Many2one(
        "hr.attendance.biometric.event",
        string="Biometric Check-Out Event",
        readonly=True,
        ondelete="restrict",
    )

    @api.ondelete(at_uninstall=True)
    def _unlink_related_biometric_events(self):
        linked_events = self.mapped("biometric_check_in_event_id") | self.mapped("biometric_check_out_event_id")
        if not linked_events:
            return

        self.write({
            "biometric_check_in_event_id": False,
            "biometric_check_out_event_id": False,
        })
        linked_events.with_context(biometric_event_force_unlink=True).unlink()
