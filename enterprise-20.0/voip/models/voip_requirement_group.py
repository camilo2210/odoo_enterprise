import logging

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI
from odoo.addons.voip.models.voip_did_number import DID_NUMBER_TYPES

_logger = logging.getLogger(__name__)

_REQUIREMENT_GROUP_STATUS_MAP = {
    "unapproved": "unapproved",
    "pending-approval": "pending_approval",
    "approved": "approved",
    "declined": "declined",
    "expired": "expired",
    "no-longer-eligible": "no_longer_eligible",
}


class VoipRequirementGroup(models.Model):
    """Reusable set of provider requirements for a country and DID number type."""

    _name = "voip.requirement.group"
    _description = "VoIP Requirement Group"
    _order = "create_date desc"

    telnyx_requirement_group_id = fields.Char(
        readonly=True,
        index=True,
        required=True,
    )
    country_id = fields.Many2one("res.country", required=True, readonly=True)
    did_number_type = fields.Selection(
        DID_NUMBER_TYPES,
        required=True,
        readonly=True,
    )
    status = fields.Selection(
        [
            ("unapproved", "Unapproved"),
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("declined", "Declined"),
            ("expired", "Expired"),
            ("no_longer_eligible", "No Longer Eligible"),
        ],
        default="unapproved",
        readonly=True,
        help="Current phone_service approval status of the requirement group.",
    )

    requirement_ids = fields.Many2many("voip.requirement", string="Requirements", required=True)
    did_number_ids = fields.One2many("voip.did.number", "requirement_group_id")
    filtered_requirement_ids = fields.Many2many(
        "voip.requirement",
        string="Requirements for DID Number",
        compute="_compute_filtered_requirement_ids",
        help="Requirements filtered for the specific DID number from context",
    )
    shared_pending_count = fields.Integer(
        compute="_compute_shared_pending_count",
        help="Not-yet-active DIDs sharing this group, whose pending orders a resubmission affects.",
    )

    _unique_telnyx_id = models.Constraint(
        "UNIQUE(telnyx_requirement_group_id)",
        "Telnyx requirement group ID must be unique!",
    )

    @api.depends_context("did_number_id")
    @api.depends("requirement_ids")
    def _compute_filtered_requirement_ids(self):
        did_number_id = self.env.context.get("did_number_id")
        filter_function = (
            (lambda r: r.field_type != "action" or r.did_number_id.id == did_number_id)
            if did_number_id
            else (lambda r: r.field_type != "action")
        )
        for group in self:
            group.filtered_requirement_ids = group.requirement_ids.filtered(filter_function)

    @api.depends("did_number_ids.state")
    def _compute_shared_pending_count(self):
        for group in self:
            group.shared_pending_count = len(
                group.did_number_ids.filtered(lambda did: did.state in ("ordering", "pending"))
            )

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        if "country_id" not in defaults or "did_number_type" not in defaults:
            return defaults
        country = self.env["res.country"].browse(defaults["country_id"])
        # TODO: Synchronous phone_service HTTP call on form open; may stall if phone_service is unreachable.
        requirement_group_data, requirements_data = PhoneServiceAPI(self.env).create_requirement_group(
            country_code=country.code,
            phone_number_type=defaults["did_number_type"],
        )

        if not requirement_group_data:
            return defaults

        defaults["telnyx_requirement_group_id"] = requirement_group_data.get("id")
        requirements = requirements_data.get("requirement_types", [])
        if not requirements:
            return defaults

        non_action_requirements = [req for req in requirements if req.get("type") != "action"]
        telnyx_requirement_ids = [req.get("id") for req in non_action_requirements]
        # Action requirements are DID-specific, so only reusable requirement
        # templates are shared across groups.
        existing_requirements = self.env["voip.requirement"].search(
            [
                ("telnyx_requirement_id", "in", telnyx_requirement_ids),
                ("did_number_id", "=", False),
            ],
        )
        existing_by_telnyx_id = {req.telnyx_requirement_id: req for req in existing_requirements}

        requirement_commands = []
        for req in requirements:
            telnyx_id = req.get("id")
            field_type = req.get("type")
            existing = existing_by_telnyx_id.get(telnyx_id) if field_type != "action" else None
            if existing:
                requirement_commands.append(Command.link(existing.id))
            else:
                requirement_commands.append(
                    Command.create({
                        "telnyx_requirement_id": telnyx_id,
                        "name": req.get("name"),
                        "description": req.get("description", ""),
                        "field_type": field_type,
                        "example": req.get("example", ""),
                    }),
                )
        defaults["requirement_ids"] = requirement_commands
        return defaults

    def action_fulfill_requirements(self):
        phone_service_api = PhoneServiceAPI(self.env)
        did_number_id = self.env.context.get("did_number_id")
        number_request = self.env["voip.did.number.request"].browse(
            self.env.context.get("number_request_id"),
        ).exists()
        requirement_statuses = (
            self.env["voip.did.number"].browse(did_number_id).requirement_statuses or {}
            if did_number_id
            else {}
        )
        for group in self:
            requirements_to_fulfill = []
            # Track requirements whose document was uploaded in this call so we
            # can clear telnyx_document_id if the PATCH fails (upstream deletes
            # unlinked documents after 30 minutes).
            freshly_uploaded_reqs = []
            upload_errors = {}  # {error_message: [req_name, ...]}
            for req in group.requirement_ids:
                if requirement_statuses.get(req.telnyx_requirement_id) == "approved":
                    continue
                # Action requirements are fulfilled through a separate identity
                # verification URL flow and are therefore not submitted here.
                if req.field_type == "textual" and req.text_value:
                    requirements_to_fulfill.append(
                        {
                            "requirement_id": req.telnyx_requirement_id,
                            "field_value": req.text_value,
                        },
                    )
                elif req.field_type == "document" and req.document_file:
                    if not req.telnyx_document_id:
                        try:
                            result = phone_service_api.upload_document(
                                content=req.document_file,
                                filename=req.document_file.filename or "document.pdf",
                            )
                        except UserError as e:
                            upload_errors.setdefault(e.args[0], []).append(req.name)
                            continue
                        req.telnyx_document_id = result.get("id")
                        freshly_uploaded_reqs.append(req)
                    requirements_to_fulfill.append(
                        {
                            "requirement_id": req.telnyx_requirement_id,
                            "field_value": req.telnyx_document_id,
                        },
                    )
                elif req.field_type == "address" and req.address_is_filled:
                    if not req.telnyx_address_id:
                        address_data = req._get_address_api_body()
                        try:
                            result = phone_service_api.create_address(address_data)
                        except UserError as e:
                            upload_errors.setdefault(e.args[0], []).append(req.name)
                            continue
                        req.telnyx_address_id = result.get("id")
                    requirements_to_fulfill.append(
                        {
                            "requirement_id": req.telnyx_requirement_id,
                            "field_value": req.telnyx_address_id,
                        },
                    )
            if upload_errors:
                raise UserError("\n\n".join(
                    msg + "\n" + "\n".join(f"• {name}" for name in names)
                    for msg, names in upload_errors.items()
                ))
            if requirements_to_fulfill:
                # Use a success flag + finally so the cleanup runs regardless of
                # the exception type, without needing to catch-and-reraise.
                fulfill_succeeded = False
                number_request_params = (
                    {"request_uuid": number_request.request_uuid} if number_request else {}
                )
                try:
                    phone_service_api.fulfill_requirement_group(
                        requirement_group_id=group.telnyx_requirement_group_id,
                        requirements=requirements_to_fulfill,
                        **number_request_params,
                    )
                    fulfill_succeeded = True
                finally:
                    if not fulfill_succeeded:
                        for req in freshly_uploaded_reqs:
                            req.telnyx_document_id = False
        if did_number_id:
            self.env["voip.did.number"].browse(did_number_id).update_requirement_group()
        message = (
            self.env._("Requirements updated successfully.")
            if did_number_id
            else self.env._("Requirements submitted successfully.")
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    @api.model
    def get_compatible_group(self, country_id, did_number_type):
        return self.search(
            [
                ("country_id", "=", country_id),
                ("did_number_type", "=", did_number_type),
                ("status", "!=", "no_longer_eligible"),
            ],
            limit=1,
        )

    @api.model
    def _handle_status_event(self, payload):
        telnyx_id = payload["requirement_group_id"]
        telnyx_status = payload["status"]
        new_status = _REQUIREMENT_GROUP_STATUS_MAP.get(telnyx_status)
        if not telnyx_id or not new_status:
            _logger.warning(
                "Ignoring requirement_group_status with telnyx_id=%r status=%r",
                telnyx_id, telnyx_status,
            )
            return
        group = self.search(
            [("telnyx_requirement_group_id", "=", telnyx_id)], limit=1,
        )
        if not group:
            return
        group.status = new_status
        group._post_status_change_to_dids(new_status, payload.get("error"))
        for did in group.did_number_ids:
            did._fetch_and_post_sub_order_comments()

    def _post_status_change_to_dids(self, new_status, error):
        """Post a chatter notification about the requirement-group status change
        on every DID currently tied to this group."""
        self.ensure_one()
        if new_status == "approved":
            body = self.env._(
                "Regulatory requirements approved by the provider — orders using this group will activate automatically.",
            )
        elif new_status == "declined":
            body = self.env._(
                "Regulatory requirements were declined: %(error)s. Please review the requirements and resubmit.",
                error=error or self.env._("no error provided"),
            )
        elif new_status == "expired":
            body = self.env._(
                "Regulatory requirements have expired. Please resubmit to keep ordering numbers under this group.",
            )
        elif new_status == "no_longer_eligible":
            body = self.env._(
                "Regulatory requirements are no longer eligible (provider policy change). A new group must be created.",
            )
        else:
            label = dict(self._fields["status"].selection)[new_status]
            body = self.env._(
                "Requirement group status updated: %(status)s.", status=label,
            )
        self.did_number_ids.post_notification(body)
