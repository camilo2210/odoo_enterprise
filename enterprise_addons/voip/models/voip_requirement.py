import logging
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.voip.models.phone_service_api import (
    _invalid_address_lines,
    PhoneServiceAPI,
)

_logger = logging.getLogger(__name__)

ADDRESS_DATA_FIELDS = frozenset({
    "address_first_name", "address_last_name", "address_business_name",
    "address_street", "address_extended", "address_city", "address_state",
    "address_postal_code", "address_country_id", "address_phone",
})


class VoipRequirement(models.Model):
    """A regulatory requirement that must be fulfilled before ordering phone
    numbers in certain countries.  Requirements are fetched from phone_service
    during the phone-number purchase flow and come in four flavours:

    * **textual** - free-text value (e.g. tax ID),
    * **document** - file upload (e.g. proof of address),
    * **address** - validated postal address,
    * **action** - identity-verification link generated upstream.

    Requirements are grouped via :class:`voip.requirement.group` and shared
    across phone numbers of the same country / number-type combination so the
    user only has to fill them in once.
    """

    _name = "voip.requirement"
    _description = "VoIP Regulatory Requirement"

    requirement_group_ids = fields.Many2many("voip.requirement.group", required=True)
    telnyx_requirement_id = fields.Char(required=True)
    name = fields.Char(required=True)
    description = fields.Text()
    field_type = fields.Selection(
        [
            ("textual", "Text"),
            ("document", "Document"),
            ("address", "Address"),
            ("action", "Action"),
        ],
        string="Type",
        required=True,
    )
    example = fields.Text()

    # Values for TEXTUAL requirements
    text_value = fields.Char()

    # Values for DOCUMENT requirements
    document_file = fields.Binary(help="Upload document")
    telnyx_document_id = fields.Char(readonly=True)

    # Values for ADDRESS requirements
    address_first_name = fields.Char(string="First Name")
    address_last_name = fields.Char(string="Last Name")
    address_business_name = fields.Char(string="Business Name")
    address_street = fields.Char(string="Street Address")
    address_extended = fields.Char(string="Apt/Suite/Floor", help="Additional address info")
    address_city = fields.Char(string="City")
    address_state = fields.Char(string="State/Province")
    address_postal_code = fields.Char(string="Postal Code")
    address_country_id = fields.Many2one("res.country", string="Country")
    address_phone = fields.Char(string="Phone Number", help="Contact phone for this address")
    telnyx_address_id = fields.Char(readonly=True)

    # Values for ACTION requirements (identity verification)
    action_first_name = fields.Char()
    action_last_name = fields.Char()
    action_verification_url = fields.Char(readonly=True)
    did_number_id = fields.Many2one(
        "voip.did.number",
        readonly=True,
        help="For action requirements, the specific DID number this verification is for",
    )

    address_is_filled = fields.Boolean(
        string="Address Filled",
        compute="_compute_address_is_filled",
        help="Whether required address fields are filled",
    )
    is_fulfilled = fields.Boolean(
        string="Fulfilled",
        compute="_compute_is_fulfilled",
        help="Whether this requirement has been fulfilled based on its type",
    )
    review_status = fields.Selection(
        [
            ("required", "Required"),
            ("provided", "Provided"),
            ("not_submitted", "Not Submitted"),
            ("under_review", "Under Review"),
            ("rejected", "Rejected"),
            ("approved", "Approved"),
        ],
        compute="_compute_review_status",
    )

    def _check_address_name(self, first_name, last_name, business_name):
        if not ((first_name and last_name) or business_name):
            raise ValidationError(self.env._("Address should include either First and Last Name or Business Name."))

    def _check_address_phone(self, phone):
        if phone and not re.match(r'^\+\d{7,15}$', phone):
            raise ValidationError(self.env._("The phone number must be in international format (e.g. +32485200345)."))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("skip_validation"):
            return super().create(vals_list)
        for vals in vals_list:
            if vals.get("field_type") == "address":
                self._check_address_name(
                    vals.get("address_first_name"), vals.get("address_last_name"), vals.get("address_business_name"),
                )
                self._check_address_phone(vals.get("address_phone"))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("skip_validation") or not self:
            return super().write(vals)
        # Validation involves per-record API calls and may mutate vals (e.g.
        # resetting telnyx_address_id), so bulk writes are not supported.
        self.ensure_one()
        did_number_id = self.env.context.get("did_number_id")
        if did_number_id:
            statuses = self.env["voip.did.number"].browse(did_number_id).requirement_statuses or {}
            if statuses.get(self.telnyx_requirement_id) == "approved":
                raise UserError(self.env._("This requirement is already approved for this phone number."))
        if self.field_type == "address" and vals.keys() & ADDRESS_DATA_FIELDS:
            self._check_address_name(
                vals.get("address_first_name", self.address_first_name),
                vals.get("address_last_name", self.address_last_name),
                vals.get("address_business_name", self.address_business_name),
            )
            self._check_address_phone(vals.get("address_phone", self.address_phone))
            address_data = self._get_address_validation_body(vals)
            result = PhoneServiceAPI(self.env).validate_address(address_data)
            if not result.get("valid"):
                lines = _invalid_address_lines(self.env, result.get("invalid_address_fields") or [])
                raise ValidationError(
                    "\n".join(lines)
                    or self.env._("The address could not be validated by the provider.")
                )
            if "telnyx_address_id" not in vals:
                vals["telnyx_address_id"] = False
        elif self.field_type == "document" and "telnyx_document_id" not in vals:
            vals["telnyx_document_id"] = False
        res = super().write(vals)
        if self.field_type == "action" and self.is_fulfilled and not self.action_verification_url:
            self.generate_verification_url()
        return res

    @api.depends(
        "address_street",
        "address_city",
        "address_country_id",
        "address_first_name",
        "address_last_name",
        "address_business_name",
    )
    def _compute_address_is_filled(self):
        for req in self:
            has_name = (req.address_first_name and req.address_last_name) or req.address_business_name
            has_address = req.address_street and req.address_city and req.address_country_id
            req.address_is_filled = bool(has_name and has_address)

    @api.depends(
        "field_type",
        "text_value",
        "document_file",
        "address_is_filled",
        "action_first_name",
        "action_last_name",
    )
    def _compute_is_fulfilled(self):
        for req in self:
            if req.field_type == "textual":
                req.is_fulfilled = bool(req.text_value)
            elif req.field_type == "document":
                req.is_fulfilled = bool(req.document_file)
            elif req.field_type == "address":
                req.is_fulfilled = req.address_is_filled
            elif req.field_type == "action":
                req.is_fulfilled = bool(req.action_first_name and req.action_last_name)
            else:
                req.is_fulfilled = False

    @api.depends_context("did_number_id")
    @api.depends("is_fulfilled", "telnyx_requirement_id")
    def _compute_review_status(self):
        did_number_id = self.env.context.get("did_number_id")
        statuses = (
            self.env["voip.did.number"].browse(did_number_id).requirement_statuses or {}
            if did_number_id
            else {}
        )
        for requirement in self:
            if not did_number_id:
                requirement.review_status = "provided" if requirement.is_fulfilled else "required"
            else:
                requirement.review_status = statuses.get(requirement.telnyx_requirement_id) or (
                    "under_review" if requirement.is_fulfilled else "not_submitted"
                )

    def _get_address_validation_body(self, vals):
        """Return the address payload for the phone_service validate_address API."""
        self.ensure_one()
        country_code = (
            self.env["res.country"].browse(vals.get("address_country_id")).code
            if "address_country_id" in vals
            else self.address_country_id.code
        )
        data = {
            "street_address": vals.get("address_street", self.address_street),
            "locality": vals.get("address_city", self.address_city),
            "country_code": country_code,
            "administrative_area": vals.get("address_state", self.address_state),
            "postal_code": vals.get("address_postal_code", self.address_postal_code),
        }
        if vals.get("address_extended", self.address_extended):
            data["extended_address"] = vals.get("address_extended", self.address_extended)
        return data

    def _get_address_api_body(self):
        """Return the full address payload for the phone_service create_address API."""
        self.ensure_one()
        data = {
            "street_address": self.address_street,
            "locality": self.address_city,
            "country_code": self.address_country_id.code,
            "administrative_area": self.address_state,
            "postal_code": self.address_postal_code,
        }
        if self.address_first_name:
            data["first_name"] = self.address_first_name
        if self.address_last_name:
            data["last_name"] = self.address_last_name
        if self.address_business_name:
            data["business_name"] = self.address_business_name
        if self.address_extended:
            data["extended_address"] = self.address_extended
        if self.address_phone:
            self._check_address_phone(self.address_phone)
            data["phone_number"] = self.address_phone
        return data

    def generate_verification_url(self):
        self.ensure_one()
        if self.field_type != "action":
            return False
        if not self.action_first_name or not self.action_last_name:
            raise UserError(self.env._("Please provide first and last name for identity verification."))
        if not self.telnyx_requirement_id:
            raise UserError(self.env._("Could not find requirement id for URL generation."))
        phone_number = self.did_number_id
        if not phone_number:
            did_number_id = self.env.context.get("did_number_id")
            if did_number_id:
                phone_number = self.env["voip.did.number"].browse(did_number_id)
        if not phone_number:
            raise UserError(self.env._("Cannot generate verification URL without a DID number order."))

        result = PhoneServiceAPI(self.env).generate_requirement_verification_url(
            requirement_id=self.telnyx_requirement_id,
            phone_number=phone_number.did_number,
            first_name=self.action_first_name,
            last_name=self.action_last_name,
        )
        requirement_action = result.get("requirement_action", {})
        verification_url = requirement_action.get("value")
        if not verification_url:
            _logger.warning(
                "generate_verification_url: no verification URL returned for requirement %s (DID %s)",
                self.telnyx_requirement_id, phone_number.did_number,
            )
            raise UserError(self.env._(
                "The phone service did not return an identity verification link. Please try again."
            ))
        self.with_context(skip_validation=True).write({"action_verification_url": verification_url})
        return True

    def action_open_verification_url(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.action_verification_url,
            "target": "new",
        }
