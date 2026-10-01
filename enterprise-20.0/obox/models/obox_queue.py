import json
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_UNIQUE_ACTION_TYPES = ["restart", "disconnect", "discover_devices", "remote_debug"]


class OboxQueue(models.TransientModel):
    _name = "obox.queue"
    _order = "id desc"
    _transient_max_hours = (
        48.0  # Actions for the Obox may be considered obsolete after this time
    )
    _description = """
        Queue is just a model to store actions to be performed by the Obox
        devices. The devices will fetch the next action to perform using
        the get_next_action method, which will return the action and mark
        it as processed in an atomic way to avoid conflicts.
    """

    name = fields.Char(string="Name", compute="_compute_name")
    uuid = fields.Char(
        string="UUID",
        required=True,
        readonly=True,
        default=lambda self: str(uuid4()),
        copy=False,
    )
    obox_id = fields.Many2one(
        "obox.obox", help="Obox id", readonly=True, ondelete="cascade",
    )
    obox_serial_number = fields.Char(
        string="Obox Serial Number",
        related="obox_id.serial_number",
        readonly=True,
    )
    payload_length = fields.Integer(
        string="Payload Length",
        compute="_compute_payload_length",
        readonly=True,
    )
    action_type = fields.Selection(
        [
            ("restart", "Restart"),
            ("test", "Test"),
            ("disconnect", "Disconnect"),
            ("action", "Action"),
            ("discover_devices", "Discover Devices"),
            ("remote_debug", "Remote Debug"),
        ],
        default="action",
        string="Request type",
        readonly=True,
        index=True,
    )
    payload = fields.Json(string="Payload", readonly=True)
    result = fields.Char(string="Result", readonly=True)

    # Action state fields
    retry = fields.Integer(string="Retry", default=0, readonly=True)
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
        ],
        default="pending",
        readonly=True,
        index=True,
    )

    def _compute_name(self):
        for record in self:
            record.name = f"Queued Job {record.id}"

    @api.model
    def _get_unique_action_types(self):
        return _UNIQUE_ACTION_TYPES

    @api.constrains("action_type")
    def _check_action_type(self):
        relevant = [
            (record.obox_id.id, record.action_type)
            for record in self
            if record.action_type in self._get_unique_action_types()
        ]

        if not relevant:
            return

        obox_ids = list({p[0] for p in relevant})
        action_types = list({p[1] for p in relevant})
        pending = self.env["obox.queue"].search([
            ("action_type", "in", action_types),
            ("obox_id", "in", obox_ids),
            ("status", "!=", "done"),  # pending or processing
            ("id", "not in", self.ids),
        ])

        pending_pairs = {
            (record.obox_id.id, record.action_type) for record in pending
        }
        conflicts = pending_pairs.intersection(relevant)
        if conflicts:
            raise UserError(
                _("Only one pending action of this type is allowed per device."),
            )

    @api.depends("payload")
    def _compute_payload_length(self):
        for record in self:
            record.payload_length = (
                len(json.dumps(record.payload)) if record.payload else 0
            )

    @api.model_create_multi
    def create(self, vals_list):
        actions = super().create(vals_list)
        # Avoid sending websocket actions with demo data creation
        if any(not action.obox_id for action in actions):
            devices = self.env["obox.obox"].search([])
            devices.dispatch_new_action()
        else:
            actions.obox_id.dispatch_new_action()
        return actions

    @api.model
    def get_next_actions(self, obox):
        """
        SKIP LOCKED will skip rows that are currently being processed by
        another worker, allowing concurrent processing without conflicts.
        This is a common pattern for implementing job queues in PostgreSQL.

        Everything is done in the same transaction to ensure that once
        actions are fetched for processing, they are immediately deleted,
        preventing other workers from fetching the same actions.

        Returns:
            List of action dicts with keys: uuid, payload, action_type
        """
        obox_id = obox.id if obox else None
        self.env.cr.execute(
            """
            SELECT uuid, payload
              FROM obox_queue
             WHERE (obox_id = %s OR obox_id IS NULL)
               AND status = 'pending'
          ORDER BY create_date ASC
               FOR UPDATE SKIP LOCKED
        """,
            (obox_id,),
        )

        rows = self.env.cr.fetchall()
        if not rows:
            return []

        action_uuids = [row[0] for row in rows]
        self.env.cr.execute(
            "UPDATE obox_queue SET status = 'processing' WHERE uuid = ANY(%s)",
            (action_uuids,),
        )

        return [
            {
                "uuid": row[0],
                "payload": row[1],
            }
            for row in rows
        ]

    def handle_obox_response(self, result):
        # Testing purpose, we should not send a notification for every
        # action result in a real implementation
        self.ensure_one()

        if result:
            result = json.dumps(result) if isinstance(result, dict) else str(result)
            self.result = (result)
            self.status = "done"

            match self.action_type:
                case "disconnect":
                    self.obox_id.unlink()
                case "discover_devices":
                    count = self.obox_id._sync_devices(json.loads(self.result))
                    self.create_uid._bus_send("simple_notification", {
                        "type": "success",
                        "message": self.env._("%s devices found", count),
                    })
                    self.obox_id._send_obox_updated_notification()
                case "remote_debug":
                    if "enabled" in result:
                        self.create_uid._bus_send("obox.remote_debug_notification", {
                            "type": "success",
                            "message": self.env._("Remote debug is enabled"),
                        })
                        self.obox_id.write({"remote_debug_enabled": True})
                    elif "disabled" in result:
                        self.create_uid._bus_send("obox.remote_debug_notification", {
                            "type": "success",
                            "message": self.env._("Remote debug is disabled"),
                        })
                        self.obox_id.write({"remote_debug_enabled": False})
                    elif "token" in result:
                        self.create_uid._bus_send("obox.remote_debug_notification", {
                            "type": "danger",
                            "message": self.env._("Token is invalid"),
                        })
                    else:
                        self.create_uid._bus_send("obox.remote_debug_notification", {
                            "type": "danger",
                            "message": self.env._("Failed to toggle remote debug"),
                        })
        else:
            self.status = "pending"
            self.retry += 1
