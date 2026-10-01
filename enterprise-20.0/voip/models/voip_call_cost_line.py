import logging
from datetime import timedelta

from psycopg2.errors import UniqueViolation

from odoo import api, fields, models

from odoo.addons.voip.models.utils import digits, same_number

_logger = logging.getLogger(__name__)

CALL_MATCH_LOOKBACK = timedelta(minutes=5)
CALL_MATCH_FORWARD = timedelta(minutes=15)
ORPHAN_REMATCH_HORIZON = timedelta(hours=2)


class VoipCallCostLine(models.Model):
    """Billing entry received from the provider for one call.

    Each `call_cost` webhook is recorded as one line, keyed by `event_id` to
    stay idempotent across retries; the `voip.call` aggregate `cost` is the sum
    of its lines. The provider (Telnyx, over the Wazo SIP trunk) exposes no call
    identifier shared with the PBX, so the line is linked to its call by the
    dialed/caller number and the call's time window, both carried in
    `payload`.
    """

    _name = "voip.call.cost.line"
    _description = "VoIP Call Cost Line"
    _order = "occurred_at"

    event_id = fields.Char(required=True)
    occurred_at = fields.Datetime(required=True)
    credits = fields.Float(required=True)
    payload = fields.Json()

    call_id = fields.Many2one(
        comodel_name="voip.call",
        ondelete="cascade",
        index="btree_not_null",
        readonly=True,
    )

    _check_unique_event_id = models.UniqueIndex(
        "(event_id)", message="Event ID must be unique"
    )

    @api.model
    def _handle_call_cost_event(self, event_id, payload, occurred_at):
        credits = float(payload.get("total_cost") or 0.0)
        if not credits:
            return
        try:
            with self.env.cr.savepoint():
                self.sudo().create({
                    "event_id": event_id,
                    "occurred_at": occurred_at,
                    "credits": credits,
                    "payload": payload,
                })
        except UniqueViolation:
            _logger.info("Ignoring duplicate phone_service event: %s", event_id)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._link_call()
        return lines

    def _link_call(self):
        for line in self:
            line.call_id = line._match_call()

    @api.model
    def _cron_link_orphan_cost_lines(self):
        """Re-match lines whose call did not yet exist (or fell just outside the
        window) when they were first recorded."""
        horizon = fields.Datetime.now() - ORPHAN_REMATCH_HORIZON
        self.search([
            ("call_id", "=", False),
            ("occurred_at", ">=", horizon),
        ])._link_call()

    def _match_call(self):
        self.ensure_one()
        payload = self.payload or {}
        direction = payload.get("direction")
        if direction not in ("incoming", "outgoing") or not self.occurred_at:
            return self.env["voip.call"]
        number = payload.get("to") if direction == "outgoing" else payload.get("from")
        if not digits(number):
            return self.env["voip.call"]
        billed = int(payload.get("billed_duration_secs") or 0)
        candidates = self.env["voip.call"].sudo().search([
            ("direction", "=", direction),
            ("create_date", ">=", self.occurred_at - timedelta(seconds=billed) - CALL_MATCH_LOOKBACK),
            ("create_date", "<=", self.occurred_at + CALL_MATCH_FORWARD),
        ])
        matches = candidates.filtered(lambda c: same_number(c.phone_number, number))
        if len(matches) <= 1:
            return matches
        best = min(matches, key=self._timing_distance)
        _logger.warning(
            "call_cost %s matches %s calls to %s in window; attaching to closest call %s",
            self.event_id, len(matches), number, best.id,
        )
        return best

    def _timing_distance(self, call):
        """Seconds between a candidate call's end and when this cost was emitted;
        used to pick between several calls to the same number."""
        call_end = call.end_date or call.effective_start_date or call.create_date
        return abs((call_end - self.occurred_at).total_seconds())
