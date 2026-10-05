import logging
from datetime import timedelta

from .phone_service_api import PhoneServiceAPI, PhoneServiceError
from .voip_did_number import DID_NUMBER_TYPES
from markupsafe import Markup

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import split_every

_logger = logging.getLogger(__name__)

NUMBER_REQUEST_STATES = [
    ("pending", "Pending"),
    ("processing", "Processing"),
    ("exception", "Action Required"),
    ("hold", "On Hold"),
    ("ordered", "Ordered"),
    ("failed", "Failed"),
]
NUMBER_REQUESTS_PER_SYNC = 50
TERMINAL_COMMENT_SYNC_GRACE = timedelta(days=1)


class VoipDidNumberRequest(models.Model):
    _name = "voip.did.number.request"
    _description = "VoIP DID Number Request"
    _inherit = ["mail.thread"]
    _rec_name = "provider_order_id"
    _order = "create_date desc"

    request_uuid = fields.Char(required=True, readonly=True, copy=False, index=True)
    provider_order_id = fields.Char(
        string="Request Reference", readonly=True, copy=False, index=True,
    )
    state = fields.Selection(
        NUMBER_REQUEST_STATES,
        required=True,
        readonly=True,
        tracking=True,
    )
    country_id = fields.Many2one("res.country", required=True, readonly=True)
    did_number_type = fields.Selection(
        DID_NUMBER_TYPES, string="Number Type", required=True, readonly=True,
    )
    quantity = fields.Integer(required=True, readonly=True)
    area_code = fields.Char(readonly=True)
    requirement_group_id = fields.Many2one(
        "voip.requirement.group", readonly=True, ondelete="set null",
    )
    requested_by_id = fields.Many2one(
        "res.users", string="Requested By", required=True, readonly=True,
    )
    number_ids = fields.One2many(
        "voip.did.number", "number_request_id", string="Phone Numbers", readonly=True,
    )
    candidate_numbers = fields.Text(string="Proposed Phone Numbers", readonly=True)
    provider_synced_comment_ids = fields.Json(readonly=True, default=list)
    new_comment = fields.Text(string="Message", copy=False)

    _request_uuid_unique = models.UniqueIndex("(request_uuid)")
    _provider_order_id_unique = models.UniqueIndex("(provider_order_id)")

    def _phone_service_create_params(self):
        self.ensure_one()
        return {
            "request_uuid": self.request_uuid,
            "country_code": self.country_id.code,
            "phone_number_type": self.did_number_type,
            "quantity": self.quantity,
            "area_code": self.area_code or None,
            "requirement_group_id": (
                self.requirement_group_id.telnyx_requirement_group_id or None
            ),
        }

    def _submit_to_phone_service(self):
        self.ensure_one()
        if self.provider_order_id:
            return
        result = PhoneServiceAPI(self.env).create_advanced_order(
            **self._phone_service_create_params(),
        )
        if not result.get("id") or result.get("status") not in dict(NUMBER_REQUEST_STATES):
            raise PhoneServiceError(
                self.env._(
                    "The Odoo Phone Service returned an invalid number request. Please try again later.",
                ),
                error_key="service_temporarily_unavailable",
            )
        self.write({
            "provider_order_id": result["id"],
            "state": result["status"],
        })

    @api.model
    def _cron_sync_number_requests(self, batch_size=NUMBER_REQUESTS_PER_SYNC):
        terminal_cutoff = fields.Datetime.now() - TERMINAL_COMMENT_SYNC_GRACE
        number_requests = self.search([
            "|",
            ("state", "not in", ("ordered", "failed")),
            ("write_date", ">=", terminal_cutoff),
        ])
        # An ordered request can still have no DID when its number-status
        # events were missed. Keep that recovery path open until the adopted
        # numbers have arrived, without polling every completed request forever.
        ordered_requests = self.search([
            ("state", "=", "ordered"),
            ("write_date", "<", terminal_cutoff),
        ])
        number_requests |= ordered_requests.filtered(
            lambda request: (
                set((request.candidate_numbers or "").splitlines())
                - set(request.number_ids.mapped("did_number"))
                or (not request.candidate_numbers and not request.number_ids)
            ),
        )
        for number_request in number_requests.filtered(
            lambda item: not item.provider_order_id and item.state != "failed",
        ):
            try:
                with self.env.cr.savepoint():
                    number_request._submit_to_phone_service()
            except PhoneServiceError as error:
                if error.error_key not in (
                    "authentication_failed",
                    "service_temporarily_unavailable",
                ):
                    number_request.write({"state": "failed"})
                    number_request.message_post(
                        body=str(error),
                        partner_ids=number_request.requested_by_id.partner_id.ids,
                        notify_skip_followers=True,
                    )
                    continue
                _logger.warning(
                    "Could not submit number request %s; it will be retried.",
                    number_request.request_uuid,
                    exc_info=True,
                )
            except UserError:
                _logger.warning(
                    "Could not submit number request %s; it will be retried.",
                    number_request.request_uuid,
                    exc_info=True,
                )
        submitted = number_requests.filtered("provider_order_id")
        for batch in split_every(batch_size, submitted.ids, self.browse):
            try:
                statuses = PhoneServiceAPI(self.env).get_number_request_statuses(
                    batch.mapped("request_uuid"),
                )
            except UserError:
                _logger.warning("Could not synchronize number requests; they will be retried.", exc_info=True)
                continue
            for number_request in batch:
                payload = statuses.get(number_request.request_uuid)
                if not isinstance(payload, dict):
                    continue
                with self.env.cr.savepoint():
                    self._handle_status_event(payload)
                    self._handle_comment_event(payload)
                    number_statuses = payload.get("number_statuses", [])
                    if not isinstance(number_statuses, list):
                        _logger.warning("Ignoring invalid advanced order number statuses")
                        number_statuses = []
                    for number_payload in number_statuses:
                        if isinstance(number_payload, dict):
                            self.env["voip.did.number"]._handle_status_event(number_payload)

    @api.model
    def _handle_status_event(self, payload):
        request_uuid = payload.get("request_uuid")
        state = payload.get("status")
        if not request_uuid or state not in dict(NUMBER_REQUEST_STATES):
            _logger.warning(
                "Ignoring invalid advanced order status event (request_uuid=%s, status=%r)",
                bool(request_uuid), state,
            )
            return
        order = self.with_user(SUPERUSER_ID).search([("request_uuid", "=", request_uuid)], limit=1)
        if not order:
            return
        order._sync_candidate_numbers(payload)
        if order.state == state:
            return
        order.state = state
        notification = {
            "exception": self.env._(
                "More information is required for this number request. Review and reply within five business days to avoid automatic cancellation.",
            ),
            "hold": self.env._(
                "Your decision is needed for this number request. Review any proposed numbers and reply within five business days to avoid automatic cancellation.",
            ),
            "ordered": self.env._(
                "This number request has been processed. Phone numbers will appear here as their individual orders complete.",
            ),
            "failed": self.env._(
                "This number request could not be fulfilled. Review the latest message below for details.",
            ),
        }.get(state)
        if notification:
            order.message_post(
                body=notification,
                partner_ids=order.requested_by_id.partner_id.ids,
                notify_skip_followers=True,
            )

    @api.model
    def _handle_comment_event(self, payload):
        request_uuid = payload.get("request_uuid")
        comments = payload.get("comments")
        if not request_uuid or not isinstance(comments, list):
            _logger.warning(
                "Ignoring invalid advanced order comment event (request_uuid=%s, comments=%r)",
                bool(request_uuid), comments,
            )
            return
        order = self.with_user(SUPERUSER_ID).search([("request_uuid", "=", request_uuid)], limit=1)
        if order:
            order._sync_candidate_numbers(payload)
            order._sync_comments(comments)

    def _sync_candidate_numbers(self, payload):
        self.ensure_one()
        candidates = payload.get("candidate_numbers")
        if candidates is None:
            return
        if not isinstance(candidates, list):
            _logger.warning(
                "Ignoring invalid advanced order candidate numbers (%r)",
                candidates,
            )
            return
        normalized = list(dict.fromkeys(
            candidate.strip()
            for candidate in candidates
            if isinstance(candidate, str) and candidate.strip()
        ))
        value = "\n".join(normalized)
        if value != (self.candidate_numbers or ""):
            self.candidate_numbers = value or False

    def _sync_comments(self, comments):
        self.ensure_one()
        synced_ids = self.provider_synced_comment_ids or []
        new_ids = list(synced_ids)
        valid_comments = (comment for comment in comments if isinstance(comment, dict))
        for comment in sorted(valid_comments, key=lambda item: item.get("created_at") or ""):
            comment_id = comment.get("id")
            body = comment.get("body")
            if not comment_id or not isinstance(body, str) or not body.strip() or comment_id in new_ids:
                continue
            created_at = comment.get("created_at") or ""
            message_body = Markup(
                "<p>%s</p><p class='text-muted small'>%s</p>",
            ) % (body, created_at)
            self.message_post(
                body=message_body,
                partner_ids=self.requested_by_id.partner_id.ids,
                notify_skip_followers=True,
            )
            new_ids.append(comment_id)
        if new_ids != synced_ids:
            self.provider_synced_comment_ids = new_ids

    def action_send_comment(self):
        self.ensure_one()
        body = (self.new_comment or "").strip()
        if not body:
            raise UserError(self.env._("Write a message before sending it."))
        comment = PhoneServiceAPI(self.env).create_advanced_order_comment(
            self.request_uuid, body,
        )
        self.message_post(body=body)
        if comment.get("id") and comment["id"] not in (self.provider_synced_comment_ids or []):
            self.provider_synced_comment_ids = [
                *(self.provider_synced_comment_ids or []), comment["id"],
            ]
        self.new_comment = False

    def action_open_requirements(self):
        self.ensure_one()
        if not self.requirement_group_id:
            return False
        return {
            "name": self.env._("Review Requirements"),
            "type": "ir.actions.act_window",
            "res_model": "voip.requirement.group",
            "res_id": self.requirement_group_id.id,
            "view_mode": "form",
            "view_id": self.env.ref("voip.view_requirement_group_submit_form").id,
            "target": "new",
            "context": {"number_request_id": self.id},
        }
