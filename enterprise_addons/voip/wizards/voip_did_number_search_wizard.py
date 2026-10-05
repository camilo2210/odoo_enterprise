import logging
import uuid
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, formatLang

from odoo.addons.voip.models.phone_service_api import (
    MAX_PHONE_NUMBERS_PER_REQUEST,
    PHONE_SERVICE_NAME,
    get_buy_credits_action,
    PhoneServiceError,
    PhoneServiceAPI,
)
from odoo.addons.voip.models.voip_did_number import DID_NUMBER_TYPES

_logger = logging.getLogger(__name__)

# Telnyx returns region_information unordered; render it narrowest-first ("GRIMSBY, ON, CA").
REGION_DISPLAY_ORDER = ("rate_center", "location", "state", "country_code")


def format_location(region_information):
    ranked = sorted(
        region_information,
        key=lambda region: (
            REGION_DISPLAY_ORDER.index(region["region_type"])
            if region.get("region_type") in REGION_DISPLAY_ORDER
            else len(REGION_DISPLAY_ORDER)
        ),
    )
    return ", ".join(dict.fromkeys(region["region_name"] for region in ranked if region.get("region_name")))


class VoipNumberSearchWizard(models.TransientModel):
    _name = "voip.did.number.search.wizard"
    _description = "DID Number Search Wizard"

    step = fields.Selection(
        [
            ("search", "Search"),
            ("number_request", "Number request"),
            ("assign_groups", "Regulatory requirements"),
        ],
        default="search",
        required=True,
    )
    country_id = fields.Many2one(
        "res.country",
        default=lambda self: self._default_country_id(),
        required=True,
        help="Country prefix of the phone number",
    )
    did_number_type = fields.Selection(
        DID_NUMBER_TYPES,
        string="Type",
        compute="_compute_did_number_type",
        store=True,
        readonly=False,
        help="""Local: Number contains digits corresponding to a geographic area.
        Mobile: Number is formatted like a mobile number.
        National: Number doesn't contain digits corresponding to a geographic area.
        Toll-Free: Special number where call receiver pays for the communication cost.
        """,
    )
    available_did_number_type_codes = fields.Json(
        compute="_compute_coverage",
        store=True,
        help="Sellable number types the selected country covers, in canonical order.",
    )
    has_available_types = fields.Boolean(compute="_compute_coverage", store=True)
    country_id_domain = fields.Char(compute="_compute_country_id_domain")
    starts_with = fields.Char(
        help="Search for numbers starting with specific digits after the country prefix (e.g., area code)",
    )
    ends_with = fields.Char(string="Ends with", help="Search for numbers ending with specific digits")
    consecutive = fields.Integer(
        string="Consecutive numbers",
        default=1,
        help="Find consecutive numbers (e.g., 5 for a block of 5 sequential numbers)",
    )
    iap_balance = fields.Float(default=lambda self: self._fetch_iap_balance(), digits=(16, 4))
    search_error = fields.Char()
    has_searched = fields.Boolean()
    number_request = fields.Boolean()
    number_request_quantity = fields.Integer(default=1, string="Quantity")
    number_request_uuid = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True)

    result_line_ids = fields.One2many("voip.did.number.search.result.line", "wizard_id")
    selected_line_ids = fields.One2many(
        "voip.did.number.search.result.line",
        compute="_compute_selected_line_ids",
    )
    selected_count = fields.Integer(compute="_compute_selected_line_ids")
    requirement_group_id = fields.Many2one("voip.requirement.group")
    requirement_ids = fields.Many2many(
        "voip.requirement",
        compute="_compute_requirement_ids",
        string="Fill in the required information",
        help="Requirements of the matching requirement group (template records for filling).",
    )
    selected_total_credits = fields.Float(
        string="Recurring Monthly Credits",
        compute="_compute_selected_line_ids",
        help="Recurring monthly cost in credits for the selected numbers",
    )
    selected_prorated_total = fields.Float(
        string="First Month (prorated)",
        compute="_compute_selected_line_ids",
        help="Prorated first-month credits charged now for the selected numbers",
    )
    needs_credits = fields.Boolean(
        compute="_compute_needs_credits",
        help="Whether the user must buy credits before purchasing.",
    )

    has_requirements = fields.Boolean()
    show_continue = fields.Boolean(
        compute="_compute_terminal_action",
        help="Search returned affordable results whose numbers still need regulatory info, so the footer offers Continue.",
    )
    show_pay = fields.Boolean(
        compute="_compute_terminal_action",
        help="Search returned affordable results ready to buy directly, so the footer offers Pay.",
    )

    pay_label = fields.Char(compute="_compute_pay_label")
    iap_balance_label = fields.Char(compute="_compute_credit_labels")
    selected_total_credits_label = fields.Char(compute="_compute_credit_labels")
    selected_prorated_total_label = fields.Char(compute="_compute_credit_labels")

    @api.depends("iap_balance", "selected_total_credits", "selected_prorated_total")
    def _compute_credit_labels(self):
        for wizard in self:
            wizard.iap_balance_label = wizard._format_credits(wizard.iap_balance)
            wizard.selected_total_credits_label = wizard._format_credits(wizard.selected_total_credits)
            wizard.selected_prorated_total_label = wizard._format_credits(wizard.selected_prorated_total)

    @api.depends("selected_count", "selected_prorated_total", "step")
    def _compute_pay_label(self):
        # Built as a single translatable sentence so the amount keeps its place
        # across languages, instead of stitching "Pay" + value + "credits" in the
        # view (which would split into separate, un-orderable translation terms).
        for wizard in self:
            if not wizard.selected_count:
                wizard.pay_label = self.env._("Pay")
            elif wizard.step == "assign_groups":
                wizard.pay_label = self.env._(
                    "Submit & Pay %(credits)s Credits",
                    credits=wizard._format_credits(wizard.selected_prorated_total),
                )
            else:
                wizard.pay_label = self.env._(
                    "Pay %(credits)s Credits",
                    credits=wizard._format_credits(wizard.selected_prorated_total),
                )

    @api.onchange("country_id", "did_number_type", "starts_with", "ends_with", "consecutive")
    def _onchange_search_criteria(self):
        for wizard in self:
            if wizard.step == "search":
                wizard._clear_search_results()

    @api.onchange("consecutive")
    def _onchange_consecutive(self):
        if not self.consecutive:
            self.consecutive = 1
        elif self.consecutive > 1:
            self.ends_with = False

    def _clear_search_results(self):
        self.result_line_ids = [Command.clear()]
        self.search_error = False
        self.has_searched = False

    @api.constrains("consecutive")
    def _check_consecutive(self):
        for wizard in self:
            if wizard.consecutive < 1:
                raise ValidationError(self.env._("Consecutive numbers must be at least 1."))

    @api.depends("requirement_group_id.requirement_ids")
    def _compute_requirement_ids(self):
        for wizard in self:
            wizard.requirement_ids = wizard.requirement_group_id.requirement_ids.filtered(
                lambda r: r.field_type != "action",
            )

    @api.depends("result_line_ids", "result_line_ids.selected")
    def _compute_selected_line_ids(self):
        factor = self._proration_factor()
        for wizard in self:
            wizard.selected_line_ids = wizard.result_line_ids.filtered("selected")
            wizard.selected_count = len(wizard.selected_line_ids)
            wizard.selected_total_credits = sum(line.monthly_cost for line in wizard.selected_line_ids)
            wizard.selected_prorated_total = float_round(
                wizard.selected_total_credits * factor, precision_digits=4,
            )

    @api.depends("selected_count", "selected_prorated_total", "iap_balance")
    def _compute_needs_credits(self):
        for wizard in self:
            wizard.needs_credits = bool(
                wizard.iap_balance == 0
                or (wizard.selected_count and wizard.selected_prorated_total > wizard.iap_balance),
            )

    @api.depends("step", "result_line_ids", "needs_credits", "has_requirements")
    def _compute_terminal_action(self):
        for wizard in self:
            # Continue/Pay only apply on the search step, once it has returned
            # results the user can afford; has_requirements then picks which of
            # the two the footer offers (Continue → regulatory step, Pay → buy).
            ready = wizard.step == "search" and bool(wizard.result_line_ids) and not wizard.needs_credits
            wizard.show_continue = ready and wizard.has_requirements
            wizard.show_pay = ready and not wizard.has_requirements

    @api.model
    def _proration_factor(self):
        """Fraction of the current month remaining (matches the iap server's
        _compute_prorated_total): a uniform calendar factor for all numbers."""
        today = fields.Date.today()
        first_of_month = today.replace(day=1)
        days_in_month = ((first_of_month + timedelta(days=32)).replace(day=1) - first_of_month).days
        return (days_in_month - today.day + 1) / days_in_month

    @api.depends("country_id")
    def _compute_coverage(self):
        for wizard in self:
            codes = wizard._coverage_type_codes()
            wizard.available_did_number_type_codes = codes
            wizard.has_available_types = bool(codes)

    @api.depends("country_id")
    def _compute_country_id_domain(self):
        sellable = {code for code, _label in DID_NUMBER_TYPES}
        for wizard in self:
            try:
                coverage = wizard._coverage_map()
            except UserError:
                wizard.country_id_domain = "[]"
                continue
            covered = [code for code, types in coverage.items() if sellable.intersection(types)]
            wizard.country_id_domain = repr([("code", "in", covered)])

    @api.depends("available_did_number_type_codes")
    def _compute_did_number_type(self):
        # separate from _compute_coverage. In Odoo, passing any one
        # computed field to create() makes the ORM skip the compute for *every*
        # field that shares that method. If this field shared _compute_coverage,
        # creating a wizard with a did_number_type would leave
        # available_did_number_type_codes empty. Split, both still compute.
        for wizard in self:
            codes = wizard.available_did_number_type_codes or []
            if wizard.did_number_type not in codes:
                wizard.did_number_type = codes[0] if codes else False

    @api.model
    def _default_country_id(self):
        # Pre-fill the company country only when Telnyx actually covers it;
        # on coverage outage degrade open (keep the default), matching the
        # domain/type fallbacks below.
        company_country = self.env.company.country_id
        if not company_country:
            return company_country
        sellable = {code for code, _label in DID_NUMBER_TYPES}
        try:
            coverage = self._coverage_map()
        except UserError:
            return company_country
        if sellable.intersection(coverage.get(company_country.code) or []):
            return company_country
        return self.env["res.country"]

    def _coverage_type_codes(self):
        """Sellable types the country covers, in canonical order. Falls back to
        the full sellable list (logged) when coverage is unreachable, and
        offers every sellable type when no country is picked yet."""
        self.ensure_one()
        sellable = [code for code, _label in DID_NUMBER_TYPES]
        if not self.country_id:
            # No country picked yet: offer every sellable type so the Type
            # field is always visible; the country pick narrows it down.
            return sellable
        try:
            coverage = self._coverage_map()
        except UserError as error:
            _logger.warning(
                "voip: country coverage unavailable for %s, offering all types: %s",
                self.country_id.code, error,
            )
            return sellable
        covered = set(coverage.get(self.country_id.code) or [])
        return [code for code in sellable if code in covered]

    def _coverage_map(self):
        return self._get_coverage_map(fields.Date.today())

    @api.ormcache("day")
    def _get_coverage_map(self, day):
        # Coverage is static and global, so fetch every country in one broker
        # round-trip and serve each lookup from memory. `day`
        # (fields.Date.today()) only exists to key the cache with a daily TTL,
        # since there's no invalidation code.
        return PhoneServiceAPI(self.env).get_all_country_coverage()

    def _fetch_iap_balance(self):
        balance = self.env["iap.account"].get_credits(PHONE_SERVICE_NAME)
        return 0 if balance == -1 else max(balance, 0)

    def _build_search_filters(self):
        self.ensure_one()
        filters = {
            "filter[limit]": 10,
            "filter[features]": ["voice"],
            "filter[exclude_held_numbers]": True,
            "filter[best_effort]": False,
        }
        if self.starts_with:
            filters["filter[phone_number][starts_with]"] = self.starts_with
        if self.ends_with:
            filters["filter[phone_number][ends_with]"] = self.ends_with
        if self.consecutive > 1:
            filters["filter[consecutive]"] = self.consecutive
        filters["filter[phone_number_type]"] = self.did_number_type
        if self.did_number_type == "toll_free":
            filters["filter[quickship]"] = True
        return filters

    def action_search(self):
        self.ensure_one()
        if not self.env.user.has_group("voip.group_voip_admin"):
            raise UserError(self.env._("You don't have permission to search phone numbers."))
        phone_service_api = PhoneServiceAPI(self.env)
        search_filters = self._build_search_filters()
        self.result_line_ids.unlink()
        self.search_error = False
        self.has_searched = True
        self.has_requirements = False
        self.requirement_group_id = False
        result_lines = []
        try:
            results = phone_service_api.search_available_phone_numbers(
                country_code=self.country_id.code,
                filters=search_filters,
            )
        except UserError as error:
            # CHECK: can we have a case where the error is invalid_subscription but the database is actually activated?
            self.search_error = (
                self.env._("You must activate your database to buy a phone number.")
                if isinstance(error, PhoneServiceError) and error.error_key == "invalid_subscription"
                else str(error)
            )
        else:
            for result in results:
                result_lines.append(
                    {
                        "wizard_id": self.id,
                        "phone_number": result.get("phone_number"),
                        "location": format_location(result.get("region_information", [])),
                        "did_number_type": result.get("phone_number_type"),
                        "monthly_cost": result.get("monthly_credits", 0),
                        "selected": False,
                    },
                )

            _, meta = phone_service_api.get_requirements(
                country_code=self.country_id.code,
                phone_number_type=self.did_number_type,
            )
            self.has_requirements = bool(meta.get("total_results"))

        if result_lines:
            self.env["voip.did.number.search.result.line"].create(result_lines)
        self.step = "search"
        return self._return_wizard_action()

    def action_next(self):
        """Move from number selection to regulatory requirements when needed."""
        self.ensure_one()
        if not self.selected_line_ids:
            raise UserError(self.env._("Please select at least one phone number."))
        if self.has_requirements:
            self._assign_requirement_group()
            self.step = "assign_groups"
            return self._return_wizard_action()
        return self.action_purchase()

    def action_open_number_request(self):
        self.ensure_one()
        if not self.env.user.has_group("voip.group_voip_admin"):
            raise UserError(self.env._("You don't have permission to request phone numbers."))
        if not self.has_searched or self.result_line_ids or self.search_error:
            raise UserError(self.env._("Number requests are available only when a search finds no numbers."))
        self.number_request = True
        self.step = "number_request"
        return self._return_wizard_action()

    def _validate_number_request(self):
        self.ensure_one()
        if not self.env.user.has_group("voip.group_voip_admin"):
            raise UserError(self.env._("You don't have permission to request phone numbers."))
        if not 1 <= self.number_request_quantity <= MAX_PHONE_NUMBERS_PER_REQUEST:
            raise UserError(self.env._(
                "You can request between 1 and %(max)s numbers.",
                max=MAX_PHONE_NUMBERS_PER_REQUEST,
            ))
        if self.starts_with and (not self.starts_with.isdigit() or len(self.starts_with) > 3):
            raise UserError(self.env._("Number requests support a numeric prefix of at most 3 digits."))
        if self.did_number_type == "toll_free" and self.country_id.code in ("CA", "US"):
            raise UserError(self.env._(
                "Number requests are not available for toll-free numbers in Canada or the United States.",
            ))

    def action_submit_number_request(self):
        self._validate_number_request()
        if self.has_requirements:
            group = self.env["voip.requirement.group"].get_compatible_group(
                self.country_id.id, self.did_number_type,
            )
            if not group or group.requirement_ids.filtered(
                lambda requirement: requirement.field_type != "action" and not requirement.is_fulfilled,
            ):
                self._assign_requirement_group()
                self.step = "assign_groups"
                return self._return_wizard_action()
            self.requirement_group_id = group
            if group.status not in ("pending_approval", "approved"):
                group.action_fulfill_requirements()
        return self._place_number_request()

    def _assign_requirement_group(self):
        group = self.env["voip.requirement.group"].get_compatible_group(
            self.country_id.id, self.did_number_type,
        )
        if not group:
            group = (
                self.env["voip.requirement.group"]
                .with_context(
                    skip_validation=True,
                    default_country_id=self.country_id.id,
                    default_did_number_type=self.did_number_type,
                )
                .create({})
            )
        self.requirement_group_id = group

    def action_confirm_groups(self):
        self.ensure_one()
        unfulfilled = self.requirement_ids.filtered(lambda r: not r.is_fulfilled)
        if unfulfilled:
            raise UserError(
                self.env._(
                    "Please complete all requirements before submitting:\n%(requirements)s",
                    requirements="\n".join(f"• {r.name}" for r in unfulfilled),
                ),
            )
        if self.number_request:
            self._validate_number_request()
        else:
            self._validate_purchase()
        self.requirement_group_id.action_fulfill_requirements()
        return {
            "type": "ir.actions.client",
            "tag": "voip.purchase_after_requirements",
            "params": {
                "wizard_id": self.id,
            },
        }

    def action_back(self):
        self.ensure_one()
        if self.step == "assign_groups" and self.number_request:
            self.step = "number_request"
        else:
            self.number_request = False
            self.step = "search"
        return self._return_wizard_action()

    def _validate_purchase(self):
        self.ensure_one()
        if not self.env.user.has_group("voip.group_voip_admin"):
            raise UserError(self.env._("You don't have permission to purchase phone numbers."))
        if not self.selected_line_ids:
            raise UserError(self.env._("No phone numbers selected."))
        if len(self.selected_line_ids) > MAX_PHONE_NUMBERS_PER_REQUEST:
            raise UserError(self.env._(
                "You can order at most %(max)s numbers at once.", max=MAX_PHONE_NUMBERS_PER_REQUEST,
            ))
        if self.selected_prorated_total > self.iap_balance:
            raise UserError(self.env._(
                "Not enough credits to buy all %(count)s selected numbers: this requires"
                " %(needed).2f credits (first month, prorated) but only %(balance).2f are available.",
                count=len(self.selected_line_ids),
                needed=self.selected_prorated_total,
                balance=self.iap_balance,
            ))

    def action_purchase(self):
        if self.number_request:
            return self._place_number_request()
        self._validate_purchase()
        phone_numbers_to_be_purchased = [
            {
                "did_number": line.phone_number,
                "country_id": self.country_id.id,
                "did_number_type": line.did_number_type,
                "location": line.location,
                "requirement_group_id": self.requirement_group_id.id,
                "state": "ordering",
            }
            for line in self.selected_line_ids
        ]
        phone_numbers_records = self.env["voip.did.number"]._create_or_reuse_for_order(
            phone_numbers_to_be_purchased,
        )
        try:
            phone_numbers_records.order_from_phone_service()
        except UserError as e:
            raise UserError(self.env._(
                "Could not place the order for %(count)d number(s): %(error)s",
                count=len(phone_numbers_records),
                error=str(e),
            )) from e

        self._assign_first_number_to_buyer(phone_numbers_records)

        if len(phone_numbers_to_be_purchased) == 1:
            message = self.env._(
                "Number %(phone_number)s is pending validation.",
                phone_number=phone_numbers_to_be_purchased[0].get("did_number"),
            )
        else:
            message = self.env._(
                "%(count)d numbers are pending validation.",
                count=len(phone_numbers_to_be_purchased),
            )
        next_action = {"type": "ir.actions.act_window_close"}
        has_action_reqs = any(phone_numbers_records.mapped("has_pending_action_requirement"))
        if has_action_reqs:
            message += " " + self.env._(
                "Identity verification required: open the number and submit the requirements.",
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": message,
                "type": "warning" if has_action_reqs else "success",
                "sticky": has_action_reqs,
                "next": next_action,
            },
        }

    def _place_number_request(self):
        self._validate_number_request()
        number_request = self.env["voip.did.number.request"].search([
            ("request_uuid", "=", self.number_request_uuid),
        ], limit=1)
        if not number_request:
            number_request = self.env["voip.did.number.request"].create({
                "request_uuid": self.number_request_uuid,
                "state": "pending",
                "country_id": self.country_id.id,
                "did_number_type": self.did_number_type,
                "quantity": self.number_request_quantity,
                "area_code": self.starts_with,
                "requirement_group_id": self.requirement_group_id.id,
                "requested_by_id": self.env.user.id,
            })
            number_request.message_subscribe(partner_ids=self.env.user.partner_id.ids)
        self.env.ref("voip.ir_cron_voip_sync_number_requests").sudo()._trigger()
        return {
            "type": "ir.actions.act_window",
            "res_model": "voip.did.number.request",
            "res_id": number_request.id,
            "views": [(self.env.ref("voip.voip_did_number_request_form_view").id, "form")],
            "target": "current",
        }

    def _assign_first_number_to_buyer(self, phone_numbers):
        self.ensure_one()
        buyer = self.env.user
        existing_number = self.env["voip.did.number"].sudo().search([
            ("user_id", "=", buyer.id),
            ("state", "!=", "released"),
        ], limit=1)
        if existing_number:
            return
        first_number = phone_numbers.sorted("id")[:1]
        if first_number:
            first_number.with_context(voip_skip_pbx_sync=True).destination_ref = buyer
            buyer.with_context(voip_skip_pbx_sync=True)._select_odoo_voip_provider()
            first_number._sync_pbx_after_status_update(buyer)

    def _return_wizard_action(self):
        step_titles = {
            "search": self.env._("Buy a Phone Number"),
            "number_request": self.env._("Request Phone Numbers"),
            "assign_groups": self.env._("Some documents are required for regulatory purposes"),
        }
        action = {
            "type": "ir.actions.act_window",
            "name": step_titles.get(self.step, self.env._("Purchase Phone Number")),
            "res_model": "voip.did.number.search.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": {"dialog_size": "large"},
        }
        return action

    def action_buy_credits(self):
        return get_buy_credits_action(self.env)

    def action_refresh_balance(self):
        self.iap_balance = self._fetch_iap_balance()
        return self._return_wizard_action()

    def _format_credits(self, value):
        # Buy-flow display rule: always two decimals ("1.20", "0.87").
        # Display-only: comparisons/charges keep the 4-decimal floats (the IAP
        # server computes the real charge itself).
        return formatLang(self.env, value, digits=2)
