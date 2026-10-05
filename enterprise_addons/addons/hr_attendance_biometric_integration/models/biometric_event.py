# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from odoo.exceptions import UserError, ValidationError

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class BiometricEvent(models.Model):
    _name = "hr.attendance.biometric.event"
    _inherit = ["mail.thread"]
    _description = "Biometric Attendance Event"
    _rec_name = "punch_reference"
    _order = "create_date, id"

    company_id = fields.Many2one("res.company", required=True)
    provider = fields.Selection(selection=[], required=True)
    punch_reference = fields.Char("Punch Reference", readonly=True)
    employee_code = fields.Char(index=True)
    employee_id = fields.Many2one("hr.employee", compute="_compute_employee_id", store=True, index='btree_not_null')
    punch_datetime = fields.Datetime(required=True, index=True)
    device_id = fields.Char(index=True)
    attendance_id = fields.Many2one("hr.attendance", readonly=True, ondelete="set null", index=True)
    state = fields.Selection([
        ("processed", "Processed"),
        ("error", "Error")], index=True, tracking=True,
    )
    warning_note = fields.Text(readonly=True, copy=False)

    _unique_punch_reference = models.Constraint(
        "unique(company_id, provider, punch_reference)",
        "The biometric event already exists for this company and provider.",
    )

    @api.ondelete(at_uninstall=True)
    def _unlink_except_processed_or_error(self):
        if self.env.context.get("biometric_event_force_unlink"):
            return
        events = self.filtered(lambda event: event.state in ("processed"))
        if events:
            raise UserError(self.env._(
                "You cannot delete biometric events that have already been processed"
            ))

    @api.depends("employee_code", "company_id")
    def _compute_employee_id(self):
        employees = self.env['hr.employee'].search([
            ("barcode", "in", self.mapped('employee_code'))
        ])
        employee_by_barcode = {employee.barcode: employee for employee in employees}

        for event in self:
            event.employee_id = employee_by_barcode.get(event.employee_code)

    @api.model
    def _parse_local_datetime(self, company, raw_datetime):
        local_dt = datetime.fromisoformat(raw_datetime.strip())

        if local_dt.tzinfo is not None:
            return local_dt.astimezone(UTC).replace(tzinfo=None)

        tz = ZoneInfo(company.tz or "UTC")
        return local_dt.replace(tzinfo=tz).astimezone(UTC).replace(tzinfo=None)

    @api.model
    def _get_or_create_events(self, vals_list):
        if not vals_list:
            return []

        vals_by_key = {}
        for vals in vals_list:
            vals_by_key.setdefault(vals["punch_reference"], vals)

        punch_references = list(vals_by_key.keys())
        domain = [
            ("company_id", "=", vals_list[0]["company_id"]),
            ("provider", "=", vals_list[0]["provider"]),
            ("punch_reference", "in", punch_references),
        ]

        existing_records = self.search(domain)
        existing_keys = set(existing_records.mapped("punch_reference"))

        to_create = [vals for key, vals in vals_by_key.items() if key not in existing_keys]
        created_records = self.create(to_create) if to_create else self.browse()

        if created_records:
            created_records._process_events()

        records_by_key = {
            record.punch_reference: record
            for record in existing_records + created_records
        }
        created_keys = {vals["punch_reference"] for vals in to_create}

        return [
            (records_by_key.get(vals["punch_reference"]), vals["punch_reference"] in created_keys)
            for vals in vals_list
        ]

    def _process_events(self):
        for event in self.sorted(lambda event: (event.punch_datetime)):
            try:
                event._process_one_event()
            except Exception as exc:
                _logger.exception("Failed to process biometric event %s", event.id)
                event.write({
                    "state": "error",
                    "warning_note": str(exc),
                })

    def action_process_attendances(self):
        events = self.filtered(lambda event: event.state == "error")
        if not events:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': self.env._('There is no transaction found to processed.'),
                    'type': 'warning',
                    'sticky': False
                }
            }

        events._process_events()
        return True

    def _process_one_event(self):
        self.ensure_one()
        company = self.company_id
        Attendance = self.env["hr.attendance"].with_company(company).sudo()

        employee = self.employee_id
        if not employee:
            raise ValidationError(self.env._("Employee not found"))

        last_punch = employee.biometric_last_punch_datetime
        if last_punch and self.punch_datetime < last_punch:
            raise ValidationError(
                self.env._(
                    "This event was received with a datetime "
                    "earlier than the last processed biometric punch.\n\n"
                    "Last processed punch: %(punch)s\n"
                    "Current Datetime: %(datetime)s"
                ) % {
                    "punch": last_punch,
                    "datetime": self.punch_datetime,
                })

        open_attendance = Attendance.search([
            ("employee_id", "=", employee.id),
            ("check_out", "=", False),
        ], order="check_in desc, id desc", limit=1)

        if open_attendance:
            gap = self.punch_datetime - open_attendance.check_in
            if gap < timedelta(0):
                raise ValidationError(
                    self.env._(
                        "This event was received with a datetime earlier than "
                        "the open attendance check-in.\n\n"
                        "Last processed punch: %(punch)s\n"
                        "Current Datetime: %(datetime)s"
                    ) % {
                        "punch": last_punch,
                        "datetime": self.punch_datetime,
                    })

            open_attendance.write({
                "check_out": self.punch_datetime,
                "out_mode": "biometric",
                "biometric_check_out_event_id": self.id,
            })
            self.write({
                "attendance_id": open_attendance.id,
                "state": "processed",
            })
            employee.biometric_last_punch_datetime = self.punch_datetime
            return

        attendance = Attendance.create({
            "employee_id": employee.id,
            "check_in": self.punch_datetime,
            "in_mode": "biometric",
            "biometric_check_in_event_id": self.id,
        })
        self.write({
            "attendance_id": attendance.id,
            "state": "processed",
        })
        employee.biometric_last_punch_datetime = self.punch_datetime
