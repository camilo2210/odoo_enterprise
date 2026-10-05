import logging
from collections import defaultdict
from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from requests.exceptions import RequestException

from odoo import api, fields, models
from odoo.exceptions import AccessError, RedirectWarning, UserError
from odoo.tools.urls import urljoin

from odoo.addons.hr_attendance_zkteco.models.utils import _get_records_from_server, _notification

_logger = logging.getLogger(__name__)

PUNCH_STATE_TO_TYPE = {"0": "check_in", "1": "check_out"}


class ZktecoTransactions(models.Model):
    _name = "zkteco.transactions"
    _description = "ZKTeco Transactions"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "employee_id, punch_datetime asc"
    _rec_name = "zkteco_transaction_id"

    punch_datetime = fields.Datetime(string="Punch Time", required=True)
    punch_type = fields.Selection([("check_in", "Check-In"), ("check_out", "Check-Out")], string="Type", tracking=True)

    zkteco_transaction_id = fields.Char(required=True)
    employee_id = fields.Many2one("hr.employee")
    terminal_id = fields.Many2one("zkteco.terminal")
    attendance_id = fields.Many2one("hr.attendance", readonly=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)

    is_processed = fields.Boolean()
    manual_punch_type = fields.Boolean()
    unmatched_checkout = fields.Boolean(readonly=True)
    attendance_unlinked = fields.Boolean(readonly=True)
    processing_note = fields.Text(compute="_compute_processing_note", store=True)

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (self.env.company.zkteco_initial_sync_done,)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        if not self.env.company.zkteco_initial_sync_done:
            raise RedirectWarning(
                message=self.env._(
                    "ZKTeco BioTime is not set up for %s yet. Configure the BioTime credentials in Settings to start syncing.",
                    self.env.company.name,
                ),
                action=self.env.ref("base_setup.action_general_configuration").id,
                button_text=self.env._("Go to Settings"),
            )
        return super()._get_view(view_id, view_type, **options)

    @api.depends("employee_id", "punch_type", "unmatched_checkout", "attendance_unlinked")
    def _compute_processing_note(self):
        for record in self:
            notes = []
            if not record.employee_id:
                notes.append(self.env._("Employee is not linked, make sure to set the Zkteco ID on the related employees."))
            if not record.punch_type:
                notes.append(self.env._("This transaction uses an unsupported type. Please select a valid one."))
            if record.unmatched_checkout:
                notes.append(self.env._("No matching Check-in transaction was found."))
            if record.attendance_unlinked:
                notes.append(self.env._("This transaction was previously linked to an attendance record that no longer exists."))

            record.processing_note = "\n".join(notes) or False

    @api.ondelete(at_uninstall=False)
    def _unlink_except_processed_with_attendance(self):
        if any(record.is_processed and record.attendance_id for record in self):
            raise UserError(
                self.env._(
                    "You cannot delete a processed transaction that is linked to an attendance record. "
                    "Delete the attendance record first."
                )
            )

    @api.model
    def _zkteco_configured_domain(self):
        return [
            ("zkteco_server_url", "!=", False),
            ("zkteco_email", "!=", False),
            ("zkteco_password", "!=", False),
            ("zkteco_company", "!=", False),
        ]

    @api.model
    def _cron_fetch_transactions(self):
        companies = self.env["res.company"].search(self._zkteco_configured_domain())
        if not companies:
            _logger.debug("No companies with ZKTeco BioTime configured. Skipping transaction fetch.")
            return

        self._fetch_transactions_for_companies(companies)

    def action_fetch_transactions(self):
        if not self.env.user.has_groups("base.group_system,hr_attendance.group_hr_attendance_manager"):
            raise AccessError(self.env._("Only attendance managers can fetch transactions from the ZKTeco BioTime server."))

        company = self.env.company
        if not company.filtered_domain(self._zkteco_configured_domain()):
            raise UserError(self.env._("ZKTeco BioTime is not configured for %s.", company.name))

        self._fetch_transactions_for_companies(company, raise_on_error=True)

        return _notification(
            self.env._("Transactions have been fetched from the BioTime server."),
            title=self.env._("Fetch Complete"),
        )

    @api.model
    def _fetch_transactions_for_companies(self, companies, raise_on_error=False):
        existing_transactions_by_company = self._get_existing_transaction_ids_by_company()
        terminals_by_company = self._get_terminal_ids_by_company()
        employees_by_zkteco_id_by_company = self._get_employees_by_zkteco_id_by_company()

        for company in companies:
            try:
                session = company.sudo()._get_zkteco_session()
            except (RequestException, UserError) as e:
                if raise_on_error:
                    raise UserError(self.env._("Could not connect to the ZKTeco BioTime server: %s", e)) from None
                _logger.warning("Skipping ZKTeco sync for company %s: %s", company.name, e)
                continue

            try:
                self._fetch_and_create_transactions(
                    company,
                    session,
                    existing_transactions_by_company.get(company, set()),
                    terminals_by_company.get(company, self.env["zkteco.terminal"]),
                    employees_by_zkteco_id_by_company.get(company, {}),
                )
            except RequestException as e:
                if raise_on_error:
                    raise UserError(self.env._("Failed to fetch transactions from BioTime server: %s", e)) from None
                _logger.warning("ZKTeco transaction fetch failed for company %s: %s", company.name, e)

    @api.model
    def _fetch_and_create_transactions(self, company, session, existing_transaction_ids, terminals, employees_by_zkteco_id):
        """Fetch transactions from the BioTime server and create transaction records."""
        start_time = fields.Datetime.now() - timedelta(days=company.zkteco_transaction_fetch_days)

        transactions = []

        params = {"start_time": start_time.strftime("%Y-%m-%d %H:%M:%S")}
        for transaction in _get_records_from_server(session, "/iclock/api/transactions/", params=params):
            transaction_id = str(transaction["id"])
            if transaction_id in existing_transaction_ids:
                continue

            vals = self._parse_transaction_vals(transaction, employees_by_zkteco_id, terminals)
            vals["company_id"] = company.id

            transactions.append(vals)
            existing_transaction_ids.add(transaction_id)

        self.create(transactions)
        _logger.info("Created %d transaction records from ZKTeco BioTime server", len(transactions))

    def _get_existing_transaction_ids_by_company(self):
        return {
            company: set(records.mapped("zkteco_transaction_id"))
            for company, records in self._read_group([], ["company_id"], ["id:recordset"])
        }

    def _get_terminal_ids_by_company(self):
        return dict(self.env["zkteco.terminal"]._read_group([], ["company_id"], ["id:recordset"]))

    def _get_employees_by_zkteco_id_by_company(self):
        groups = self.env["hr.employee"]._read_group(
            [("zkteco_emp_id", "!=", False)],
            ["company_id", "zkteco_emp_id"],
            ["id:recordset"],
        )
        result = defaultdict(dict)
        for company, zkteco_emp_id, employees in groups:
            result[company][zkteco_emp_id] = employees
        return result

    def action_refetch_transaction(self):
        if not self.env.user.has_groups("base.group_system,hr_attendance.group_hr_attendance_manager"):
            raise AccessError(self.env._("Only attendance managers can re-fetch transactions from the ZKTeco BioTime server."))

        if any(record.attendance_id for record in self):
            raise UserError(
                self.env._(
                    "You cannot re-fetch a transaction that is linked to an attendance record. "
                    "Delete the attendance record first."
                )
            )

        sessions_by_company = {}
        unreachable_companies = self.env["res.company"]
        for company in self.company_id:
            try:
                sessions_by_company[company] = company.sudo()._get_zkteco_session()
            except (RequestException, UserError) as e:
                unreachable_companies |= company
                _logger.warning("Could not open a ZKTeco BioTime session for company %s: %s", company.name, e)

        terminals_by_company = self._get_terminal_ids_by_company()
        employees_by_zkteco_id_by_company = self._get_employees_by_zkteco_id_by_company()

        refetched_count = 0
        for record in self:
            company = record.company_id
            session = sessions_by_company.get(company)
            if not session:
                continue

            try:
                response = session.get(
                    urljoin(session.base_url, f"/iclock/api/transactions/{record.zkteco_transaction_id}/"),
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except RequestException as e:
                _logger.warning("Failed to re-fetch transaction %s from the BioTime server: %s", record.zkteco_transaction_id, e)
                continue

            vals = self._parse_transaction_vals(
                data,
                employees_by_zkteco_id_by_company.get(company, {}),
                terminals_by_company.get(company, self.env["zkteco.terminal"]),
            )

            record.write(
                {
                    **vals,
                    "is_processed": False,
                    "attendance_unlinked": False,
                    "unmatched_checkout": False,
                }
            )
            refetched_count += 1

        failed_count = len(self) - refetched_count
        if not failed_count:
            return _notification(
                self.env._("Re-fetched %d transaction(s) from the BioTime server.", refetched_count),
                title=self.env._("Re-fetched"),
            )

        if unreachable_companies:
            message = self.env._(
                "Re-fetched %(refetched)d transaction(s). %(failed)d could not be re-fetched; "
                "the BioTime server could not be reached for: %(companies)s.",
                refetched=refetched_count,
                failed=failed_count,
                companies=", ".join(unreachable_companies.mapped("name")),
            )
        else:
            message = self.env._(
                "Re-fetched %(refetched)d transaction(s). %(failed)d could not be re-fetched from the BioTime server.",
                refetched=refetched_count,
                failed=failed_count,
            )

        return _notification(message, title=self.env._("Re-fetched"), notification_type="warning")

    def _parse_transaction_vals(self, data, employees_by_zkteco_id, terminals):
        zkteco_emp_id = data["emp_code"]
        terminal_sn = data["terminal_sn"]
        punch_state = data["punch_state"]
        transaction_id = str(data["id"])

        employee = employees_by_zkteco_id.get(zkteco_emp_id, False)
        terminal = terminals.filtered(lambda t: t.terminal_sn == terminal_sn)
        punch_type = PUNCH_STATE_TO_TYPE.get(punch_state)

        punch_datetime = fields.Datetime.from_string(data["punch_time"])
        if employee and (tz := employee._get_tz()):
            punch_datetime = punch_datetime.replace(tzinfo=ZoneInfo(tz)).astimezone(UTC).replace(tzinfo=None)

        return {
            "employee_id": employee and employee.id,
            "terminal_id": terminal and terminal.id,
            "punch_datetime": punch_datetime,
            "punch_type": punch_type,
            "manual_punch_type": not punch_type,
            "zkteco_transaction_id": transaction_id,
        }

    def _mark_processed(self, attendance):
        self.write(
            {
                "attendance_id": attendance.id,
                "is_processed": True,
                "unmatched_checkout": False,
                "attendance_unlinked": False,
            }
        )

    def action_process_attendances(self):
        transactions = self.filtered(lambda r: not r.is_processed).sorted(key=lambda r: (r.employee_id.id, r.punch_datetime))
        open_att_by_employee = self._get_open_attendances_by_employee(transactions)

        # {"vals": attendance value, "checkin_tx": zk transaction entry, "checkout_tx": zk transaction entry}
        attendance_entries = []
        check_in_queue = defaultdict(list)

        for record in transactions:
            employee = record.employee_id
            if not employee or not record.punch_type:
                continue

            if record.punch_type == "check_in":
                entry = {
                    "vals": {
                        "employee_id": employee.id,
                        "check_in": record.punch_datetime,
                        "zkteco_checkin_id": record.zkteco_transaction_id,
                        "zkteco_checkin_transaction_id": record.id,
                        "terminal_id": record.terminal_id.id,
                        "in_mode": "biotime",
                    },
                    "checkin_tx": record,
                    "checkout_tx": None,
                }
                attendance_entries.append(entry)
                check_in_queue[employee.id].append(entry)
            elif record.punch_type == "check_out":
                self._match_checkout(record, open_att_by_employee.get(employee.id, []), check_in_queue[employee.id])

        created_attendances = self.env["hr.attendance"].create([entry["vals"] for entry in attendance_entries])
        for attendance, entry in zip(created_attendances, attendance_entries):
            entry["checkin_tx"]._mark_processed(attendance)
            if entry["checkout_tx"]:
                entry["checkout_tx"]._mark_processed(attendance)

        processed = transactions.filtered("is_processed")
        unmatched = transactions.filtered("unmatched_checkout")

        message = self.env._("Processed %(processed_count)d transactions.", processed_count=len(processed))
        if unmatched:
            message += " " + self.env._("%(orphan_count)d non matched check-out transactions found.", orphan_count=len(unmatched))

        return _notification(
            message,
            title=self.env._("Processing Complete"),
            notification_type="warning" if unmatched else "success",
        )

    def _get_open_attendances_by_employee(self, transactions):
        result = {}
        for company, records in transactions.grouped("company_id").items():
            for employee, atts in self.env["hr.attendance"]._read_group(
                domain=[
                    ("employee_id", "in", records.employee_id.ids),
                    ("check_in", ">=", fields.Datetime.now() - timedelta(days=company.zkteco_checkout_lookback_days)),
                    ("check_out", "=", False),
                ],
                groupby=["employee_id"],
                aggregates=["id:recordset"],
            ):
                result[employee.id] = list(atts.sorted("check_in", reverse=True))
        return result

    def _match_checkout(self, record, open_atts, check_in_queue):
        """Pair a check-out transaction with its check-in, in this order:

        1. an open attendance already in hr.attendance (closest earlier check-in);
        2. a check-in queued earlier in this employee's batch (not yet in DB);
        3. otherwise flag the record for HR review.
        """
        checkout_vals = {
            "check_out": record.punch_datetime,
            "zkteco_checkout_id": record.zkteco_transaction_id,
            "zkteco_checkout_transaction_id": record.id,
            "out_mode": "biotime",
        }
        matched_att = next((att for att in open_atts if att.check_in <= record.punch_datetime), None)

        if matched_att:
            matched_att.write(checkout_vals)
            open_atts.remove(matched_att)
            record._mark_processed(matched_att)
        elif check_in_queue:
            entry = check_in_queue.pop(0)
            entry["checkout_tx"] = record
            entry["vals"].update(checkout_vals)
        else:
            record._schedule_missing_checkin_activity()
            record.unmatched_checkout = True

    def _schedule_missing_checkin_activity(self):
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=self.employee_id.parent_id.user_id.id or self.env.uid,
            summary=self.env._("Missing Check-In Record"),
            note=self.env._(
                "Employee %(employee_name)s has a check-out at %(check_out)s without a check-in.",
                employee_name=self.employee_id.name,
                check_out=self.punch_datetime,
            ),
        )
