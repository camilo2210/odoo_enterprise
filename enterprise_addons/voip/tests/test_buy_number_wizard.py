from datetime import date
from unittest.mock import Mock, PropertyMock, patch

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, common, tagged
from odoo.tests.common import new_test_user
from odoo.tools import BinaryBytes, mute_logger
from odoo.tools.safe_eval import expr_eval

from odoo.addons.iap.models.iap_account import IapAccount
from odoo.addons.voip.models.pbx_service import PBXService
from odoo.addons.voip.models.phone_service_api import (
    PHONE_SERVICE_NAME,
    PhoneServiceError,
    PhoneServiceAPI,
)
from odoo.addons.voip.models.voip_did_number import DID_NUMBER_TYPES
from odoo.addons.voip.tests.common_voip import (
    calls_for,
    capture_pbx_calls,
    forbid_phone_service_http,
    mock_pbx_layer,
    pbx_router,
    tts_sound_values,
)

NUMBER_REQUEST_LOGGER = "odoo.addons.voip.models.voip_did_number_request"

VOIP_DID_NUMBER_LOGGER = "odoo.addons.voip.models.voip_did_number"
VOIP_DID_NUMBER_SEARCH_WIZARD_LOGGER = "odoo.addons.voip.wizards.voip_did_number_search_wizard"
VOIP_REQUIREMENT_LOGGER = "odoo.addons.voip.models.voip_requirement"


def _mock_phone_service(route, params, retry_registration=True):
    """Default mock that returns empty success for any phone_service route."""
    if route.startswith("/api/phone_service/1/pbx/"):
        return pbx_router(route, params)
    return {"success": True, "data": {}}


def _mock_search_available_phone_numbers(country_code="BE", has_requirements=False):
    """Return a _call_phone_service mock that handles search + requirements check."""
    def side_effect(route, params, retry_registration=True):
        if "search_available_phone_numbers" in route:
            return {
                "success": True,
                "data": [
                    {
                        "phone_number": "+3287000001",
                        "phone_number_type": "local",
                        # Telnyx returns these unordered: state before rate center.
                        "region_information": [
                            {"region_type": "state", "region_name": "BRU"},
                            {"region_type": "country_code", "region_name": "BE"},
                            {"region_type": "location", "region_name": "Brussels"},
                            {"region_type": "rate_center", "region_name": "Brussels"},
                        ],
                        "monthly_credits": 2,
                    },
                    {
                        "phone_number": "+3287000002",
                        "phone_number_type": "local",
                        "region_information": [{"region_name": "Antwerp"}],
                        "monthly_credits": 3,
                    },
                ],
            }
        if "requirements" in route:
            total = 1 if has_requirements else 0
            return {"success": True, "data": [], "meta": {"total_results": total}}
        return {"success": True, "data": {}}
    return side_effect


def _mock_batch_order(params):
    """Build the per-number order response from the batch request params."""
    return {
        "success": True,
        "data": {
            item["phone_number"]: {"status": "ordering", "monthly_credits": 2.0}
            for item in params["phone_numbers"]
        },
    }


def _mock_order_success(route, params, retry_registration=True):
    """Mock that handles the order + sync flow for a successful purchase."""
    if route == "/api/phone_service/1/order_phone_numbers":
        return _mock_batch_order(params)
    if "/get_phone_number_comments" in route:
        return {"success": True, "data": []}
    if route.startswith("/api/phone_service/1/pbx/"):
        return pbx_router(route, params)
    return {"success": True, "data": {}}


def _mock_order_pending_with_requirements(route, params, retry_registration=True):
    """Mock for orders that go to ordering state (async, with requirements)."""
    if route == "/api/phone_service/1/order_phone_numbers":
        return _mock_batch_order(params)
    if "/get_phone_number_comments" in route:
        return {"success": True, "data": []}
    if route.startswith("/api/phone_service/1/pbx/"):
        return pbx_router(route, params)
    return {"success": True, "data": {}}


@tagged("voip")
class TestBuyNumberWizardBase(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = new_test_user(
            cls.env,
            login="voip_test_admin",
            groups="voip.group_voip_admin",
            country_id=cls.env.ref("base.be").id,
        )
        cls.regular_user = new_test_user(
            cls.env,
            login="voip_test_user",
            groups="base.group_user",
        )
        cls.country_be = cls.env.ref("base.be")
        did_numbers = cls.env["voip.did.number"].search([]).with_context(voip_skip_pbx_sync=True)
        did_numbers.write({"state": "released"})
        did_numbers.unlink()
        cls.env["voip.requirement.group"].search([]).unlink()

    def setUp(self):
        super().setUp()
        forbid_phone_service_http(self)
        mock_pbx_layer(self)
        patchers = [
            patch.object(
                PBXService,
                "voip_provider",
                new_callable=PropertyMock,
                return_value=self.env.ref("voip.odoo_provider"),
            ),
            patch.object(
                IapAccount,
                "get_credits",
                lambda self, service_name: 10_000.0,
            ),
            patch.object(
                PhoneServiceAPI,
                "get_all_country_coverage",
                side_effect=lambda: {"BE": ["toll_free", "local", "mobile"]},
            ),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        # ormcache survives across TransactionCase cases (only the cursor rolls
        # back), so clear it or cached coverage from a prior test would leak.
        self.env.transaction.invalidate_ormcache()

    def _create_wizard(self, user=None, **kwargs):
        vals = {
            "country_id": self.country_be.id,
            "did_number_type": "local",
            **kwargs,
        }
        return (
            self.env["voip.did.number.search.wizard"]
            .with_user(user or self.admin_user)
            .create(vals)
        )


@tagged("voip")
class TestPhoneNumberRequest(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.requester = new_test_user(
            cls.env,
            login="phone_number_requester",
            email="requester@example.com",
            groups="base.group_user",
        )
        cls.active_admin = new_test_user(
            cls.env,
            login="phone_number_request_admin",
            email="phone-admin@example.com",
            groups="voip.group_voip_admin",
        )
        cls.inactive_admin = new_test_user(
            cls.env,
            login="inactive_phone_number_request_admin",
            email="inactive-phone-admin@example.com",
            groups="voip.group_voip_admin",
        )
        cls.inactive_admin.active = False

    def test_request_emails_active_voip_admins(self):
        request = self.env["voip.did.number.request.wizard"].with_user(self.requester).create({
            "body_html": "We need a customer support number.",
        })
        expected_users = self.env.ref("voip.group_voip_admin").all_user_ids
        existing_mails = self.env["mail.mail"].search([])

        with patch.object(self.env.registry["mail.mail"], "send", autospec=True) as send:
            action = request.action_send_request()

        mails = self.env["mail.mail"].search([("id", "not in", existing_mails.ids)])
        self.assertEqual(len(mails), len(expected_users))
        self.assertEqual(set(mails.recipient_ids.ids), set(expected_users.partner_id.ids))
        self.assertIn(self.active_admin.partner_id, mails.recipient_ids)
        self.assertNotIn(self.inactive_admin.partner_id, mails.recipient_ids)
        self.assertTrue(all(mail.subject == "Phone number request" for mail in mails))
        self.assertTrue(all("We need a customer support number." in mail.body_html for mail in mails))
        self.assertTrue(all("action-voip.action_voip_did_number\"" in mail.body_html for mail in mails))
        self.assertTrue(all("action_voip_did_number_search_wizard" not in mail.body_html for mail in mails))
        self.assertEqual(send.call_count, len(expected_users))
        self.assertEqual(action["tag"], "display_notification")

    def test_request_email_without_comment(self):
        """The request template omits the comment section when it is empty."""
        request = self.env["voip.did.number.request.wizard"].with_user(self.requester).create({})
        existing_mails = self.env["mail.mail"].search([])

        with patch.object(self.env.registry["mail.mail"], "send", autospec=True):
            request.action_send_request()

        mails = self.env["mail.mail"].search([("id", "not in", existing_mails.ids)])
        self.assertTrue(mails)
        self.assertTrue(all("They added the following comment:" not in mail.body_html for mail in mails))


@tagged("voip")
class TestBuyNumberWizardSearch(TestBuyNumberWizardBase):

    def test_empty_search_can_submit_advanced_order_without_buying_number(self):
        def empty_search(route, params, retry_registration=True):
            if "search_available_phone_numbers" in route:
                return {"success": True, "data": []}
            if "requirements" in route:
                return {"success": True, "data": [], "meta": {"total_results": 0}}
            return {"success": True, "data": {}}

        wizard = self._create_wizard(starts_with="2")
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=empty_search):
            wizard.action_search()
        self.assertFalse(wizard.result_line_ids)

        wizard.action_open_number_request()
        self.assertEqual(wizard.step, "number_request")

        with (
            patch.object(PhoneServiceAPI, "create_advanced_order") as create_advanced_order,
            patch("odoo.addons.base.models.ir_cron.IrCron._trigger") as trigger,
        ):
            action = wizard.action_submit_number_request()

        create_advanced_order.assert_not_called()
        trigger.assert_called_once()
        number_request = self.env["voip.did.number.request"].search([
            ("request_uuid", "=", wizard.number_request_uuid),
        ])
        self.assertEqual(len(number_request), 1)
        self.assertFalse(number_request.provider_order_id)
        self.assertEqual(number_request.state, "pending")
        self.assertEqual(number_request.country_id, self.country_be)
        self.assertEqual(number_request.did_number_type, "local")
        self.assertEqual(number_request.quantity, 1)
        self.assertEqual(number_request.area_code, "2")
        self.assertEqual(number_request.requested_by_id, self.admin_user)
        self.assertFalse(self.env["voip.did.number"].search([
            ("did_number", "=like", "+32%"),
        ]))
        self.assertEqual(action, {
            "type": "ir.actions.act_window",
            "res_model": "voip.did.number.request",
            "res_id": number_request.id,
            "views": [(self.env.ref("voip.voip_did_number_request_form_view").id, "form")],
            "target": "current",
        })

    def test_number_request_survives_lost_phone_service_response(self):
        wizard = self._create_wizard(
            starts_with="2",
            number_request=True,
            step="number_request",
        )

        with patch.object(
            PhoneServiceAPI,
            "create_advanced_order",
            side_effect=PhoneServiceError(
                "Could not reach the Odoo Phone Service.",
                error_key="service_temporarily_unavailable",
            ),
        ) as create_advanced_order:
            action = wizard.action_submit_number_request()

        create_advanced_order.assert_not_called()
        number_request = self.env["voip.did.number.request"].search([
            ("request_uuid", "=", wizard.number_request_uuid),
        ])
        self.assertEqual(len(number_request), 1)
        self.assertFalse(number_request.provider_order_id)
        self.assertEqual(number_request.state, "pending")
        self.assertEqual(action["res_id"], number_request.id)

        with (
            patch.object(
                PhoneServiceAPI,
                "create_advanced_order",
                side_effect=PhoneServiceError(
                    "Could not reach the Odoo Phone Service.",
                    error_key="service_temporarily_unavailable",
                ),
            ) as create_advanced_order,
            mute_logger(NUMBER_REQUEST_LOGGER),
        ):
            self.env["voip.did.number.request"]._cron_sync_number_requests()
        create_advanced_order.assert_called_once()
        self.assertEqual(number_request.state, "pending")

    def test_country_defaults_to_main_company_country(self):
        company = self.env["res.company"].create({
            "name": "VoIP Number Purchase Company",
            "country_id": self.country_be.id,
        })
        self.admin_user.write({
            "company_ids": [(4, company.id)],
            "company_id": company.id,
        })

        defaults = (
            self.env["voip.did.number.search.wizard"]
            .with_user(self.admin_user)
            .default_get(["country_id"])
        )

        self.assertEqual(defaults["country_id"], self.country_be.id)

    def test_search_returns_results(self):
        wizard = self._create_wizard()
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_search_available_phone_numbers()):
            wizard.action_search()
        self.assertEqual(wizard.step, "search")
        self.assertEqual(len(wizard.result_line_ids), 2)
        self.assertEqual(wizard.result_line_ids[0].phone_number, "+3287000001")
        self.assertEqual(wizard.result_line_ids[1].phone_number, "+3287000002")

    def test_search_result_location_is_narrowest_first_without_duplicates(self):
        wizard = self._create_wizard()
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_search_available_phone_numbers()):
            wizard.action_search()
        self.assertEqual(wizard.result_line_ids[0].location, "Brussels, BRU, BE")
        self.assertEqual(wizard.result_line_ids[1].location, "Antwerp")

    def test_search_error_stored_on_wizard(self):
        wizard = self._create_wizard()

        def raise_error(route, params, retry_registration=True):
            if "search_available_phone_numbers" in route:
                raise UserError("Service temporarily unavailable")
            return {"success": True, "data": [], "meta": {"total_results": 0}}
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=raise_error):
            wizard.action_search()
        self.assertEqual(wizard.step, "search")
        self.assertTrue(wizard.search_error)
        self.assertEqual(len(wizard.result_line_ids), 0)

    def test_invalid_subscription_search_error_asks_for_activation(self):
        wizard = self._create_wizard()

        with patch.object(
            PhoneServiceAPI,
            "search_available_phone_numbers",
            side_effect=PhoneServiceError(
                "Your Odoo subscription does not allow this operation.",
                error_key="invalid_subscription",
            ),
        ):
            wizard.action_search()

        self.assertEqual(
            wizard.search_error,
            "You must activate your database to buy a phone number.",
        )

    def test_search_requires_admin(self):
        wizard = self._create_wizard(user=self.admin_user)
        wizard_as_regular = wizard.with_user(self.regular_user)
        with self.assertRaises(UserError):
            with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_phone_service):
                wizard_as_regular.action_search()

    def test_search_stamps_has_requirements(self):
        wizard = self._create_wizard()
        with patch.object(
            PhoneServiceAPI, "_call_phone_service",
            side_effect=_mock_search_available_phone_numbers(has_requirements=True),
        ):
            wizard.action_search()
        self.assertTrue(wizard.has_requirements)

    def test_has_requirements_is_false_without_results(self):
        wizard = self._create_wizard()
        self.assertFalse(wizard.has_requirements)
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_search_available_phone_numbers()):
            wizard.action_search()
        self.assertFalse(wizard.has_requirements)

    def test_changing_search_criteria_clears_stale_results(self):
        wizard = self._create_wizard()
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_search_available_phone_numbers()):
            wizard.action_search()
        self.assertEqual(len(wizard.result_line_ids), 2)

        with Form(wizard) as form:
            form.starts_with = "32"

        self.assertFalse(wizard.has_searched)
        self.assertEqual(len(wizard.result_line_ids), 0)
        self.assertFalse(wizard.search_error)

    def test_consecutive_block_clears_ends_with(self):
        """A consecutive-block search and an 'ends with' filter are mutually
        exclusive; raising 'consecutive' above 1 must drop a previously typed
        'ends with' instead of leaving both set (an impossible search)."""
        wizard = self._create_wizard()
        with Form(wizard) as form:
            form.ends_with = "00"
            form.consecutive = 12
        self.assertEqual(wizard.consecutive, 12)
        self.assertFalse(wizard.ends_with)

    def test_emptying_consecutive_normalizes_to_one(self):
        """Erasing the consecutive input must settle on the neutral value 1, not
        revert to its previous value nor fall to 0 (which the >= 1 constraint
        rejects) — otherwise the field deadlocks against 'ends with'."""
        wizard = self._create_wizard(consecutive=12)
        with Form(wizard) as form:
            form.consecutive = 0
            form.ends_with = "00"
        self.assertEqual(wizard.consecutive, 1)
        self.assertEqual(wizard.ends_with, "00")

    def test_consecutive_field_stays_editable(self):
        """'consecutive' must never become readonly: it is the escape hatch out
        of the mutually-exclusive state, so it cannot be locked by 'ends with'."""
        arch = self.env.ref("voip.voip_did_number_search_wizard_form").arch_db
        root = etree.fromstring(arch)
        consecutive = root.xpath("//field[@name='consecutive']")[0]
        self.assertNotIn("readonly", consecutive.attrib)

    def test_search_view_uses_direct_pay_for_results_without_requirements(self):
        arch = self.env.ref("voip.voip_did_number_search_wizard_form").arch_db
        root = etree.fromstring(arch)

        result_fields = root.xpath("//field[@name='result_line_ids']")
        self.assertTrue(result_fields)
        self.assertFalse(result_fields[0].xpath("ancestor::div[contains(@class, 'flex-lg-row')]"))
        self.assertTrue(result_fields[0].xpath("ancestor::page[@string='Available Phone Numbers']"))
        selected_field = result_fields[0].xpath("list/field[@name='selected']")[0]
        self.assertEqual(selected_field.get("string"), "")

        search_pay_buttons = root.xpath("//footer/button[@name='action_purchase' and contains(@invisible, 'show_pay')]")
        self.assertTrue(search_pay_buttons)
        self.assertIn("selected_count", search_pay_buttons[0].get("invisible"))

        requirement_buttons = root.xpath("//footer/button[@name='action_confirm_groups']")
        self.assertTrue(requirement_buttons)
        self.assertIn("pay_label", etree.tostring(requirement_buttons[0], encoding="unicode"))
        requirement_notes = root.xpath("//footer//span[contains(@invisible, \"step != 'assign_groups'\")]")
        self.assertTrue(any(
            "credits/month" in etree.tostring(note, encoding="unicode")
            for note in requirement_notes
        ))

    def test_search_footer_keeps_greyed_twin_and_prorate_note(self):
        """Each terminal action keeps an active button plus a greyed twin (a
        button's `disabled` can't be data-driven), and the prorated Pay button
        is clarified as a first-month charge."""
        arch = self.env.ref("voip.voip_did_number_search_wizard_form").arch_db
        root = etree.fromstring(arch)
        for name in ("action_next", "action_purchase"):
            active = root.xpath(f"//footer/button[@name='{name}' and contains(@invisible, 'not selected_count')]")
            greyed = root.xpath(
                f"//footer/button[@name='{name}' and @disabled='disabled' and contains(@invisible, 'or selected_count')]",
            )
            self.assertTrue(active, f"active {name} button missing")
            self.assertTrue(greyed, f"greyed {name} twin missing")

        note = root.xpath("//footer//span[contains(text(), 'for the remainder of this month')]")
        self.assertTrue(note)
        self.assertIn("show_pay", note[0].get("invisible"))

    def test_buy_credits_button_has_contextual_emphasis(self):
        arch = self.env.ref("voip.voip_did_number_search_wizard_form").arch_db
        root = etree.fromstring(arch)

        buy_credits_buttons = root.xpath("//footer/button[@name='action_buy_credits']")
        self.assertEqual(len(buy_credits_buttons), 2)
        self.assertEqual(
            {button.get("class") for button in buy_credits_buttons},
            {"btn-primary", "btn-secondary"},
        )
        primary_button = next(button for button in buy_credits_buttons if button.get("class") == "btn-primary")
        secondary_button = next(button for button in buy_credits_buttons if button.get("class") == "btn-secondary")
        self.assertIn("not result_line_ids", primary_button.get("invisible"))
        self.assertIn("result_line_ids", secondary_button.get("invisible"))
        self.assertIn("search_error", secondary_button.get("invisible"))
        for button in buy_credits_buttons:
            self.assertIn("not has_searched", button.get("invisible"))
            self.assertIn("not needs_credits", button.get("invisible"))

    def test_search_has_contextual_emphasis_and_empty_results_offer_number_request(self):
        root = etree.fromstring(self.env.ref("voip.voip_did_number_search_wizard_form").arch_db)

        search_buttons = root.xpath("//footer/button[@name='action_search']")
        self.assertEqual(len(search_buttons), 2)
        self.assertEqual(
            {button.get("class") for button in search_buttons},
            {"btn-primary", "btn-secondary"},
        )
        primary_button = next(button for button in search_buttons if button.get("class") == "btn-primary")
        secondary_button = next(button for button in search_buttons if button.get("class") == "btn-secondary")
        self.assertIn("has_searched and not search_error", primary_button.get("invisible"))
        self.assertIn("not has_searched", secondary_button.get("invisible"))
        self.assertIn("search_error", secondary_button.get("invisible"))
        self.assertIn("result_line_ids and not needs_credits", secondary_button.get("invisible"))

        request_buttons = root.xpath("//footer/button[@name='action_open_number_request']")
        self.assertEqual(len(request_buttons), 1)
        self.assertEqual(request_buttons[0].get("string"), "Request Numbers")
        self.assertIn("not has_searched", request_buttons[0].get("invisible"))
        self.assertIn("result_line_ids", request_buttons[0].get("invisible"))
        self.assertFalse(root.xpath("//sheet//button[@name='action_open_number_request']"))

    def test_search_footer_has_one_contextual_primary_action(self):
        root = etree.fromstring(self.env.ref("voip.voip_did_number_search_wizard_form").arch_db)
        base_state = {
            "step": "search",
            "has_available_types": True,
            "has_searched": False,
            "search_error": False,
            "result_line_ids": [],
            "needs_credits": False,
            "show_continue": False,
            "show_pay": False,
            "selected_count": 0,
            "number_request": False,
        }
        scenarios = [
            ("initial", {}, "action_search"),
            ("search error", {"has_searched": True, "search_error": "Unavailable"}, "action_search"),
            ("empty result", {"has_searched": True}, "action_open_number_request"),
            (
                "empty result without credit",
                {"has_searched": True, "needs_credits": True},
                "action_open_number_request",
            ),
            (
                "unaffordable results",
                {"has_searched": True, "result_line_ids": [1], "needs_credits": True},
                "action_buy_credits",
            ),
            (
                "affordable results",
                {"has_searched": True, "result_line_ids": [1], "show_pay": True},
                "action_purchase",
            ),
        ]
        for scenario, values, expected_action in scenarios:
            state = base_state | values
            visible_buttons = [
                button
                for button in root.xpath("//footer/button")
                if not expr_eval(button.get("invisible", "False"), state)
            ]
            visible_primary_actions = [
                button.get("name")
                for button in visible_buttons
                if "btn-primary" in button.get("class", "")
            ]
            self.assertEqual(visible_primary_actions, [expected_action], scenario)
            self.assertIn("btn-primary", visible_buttons[0].get("class", ""), scenario)

    def test_buy_number_views_use_material_icons(self):
        expected = {
            "voip.voip_did_number_search_wizard_form": [
                ("refresh", None),
                ("open_in_new", None),
                ("open_in_new", None),
            ],
            "voip.view_requirement_list": [
                ("edit", "oi-filled text-danger"),
                ("check", "text-success"),
                ("schedule", "text-warning"),
                ("close", "text-danger"),
                ("check", "text-success"),
                ("link", None),
            ],
            "voip.view_requirement_group_submit_form": [("upload", None), ("upload", None)],
            "voip.voip_did_number_form_view": [
                ("description", "oi-filled"),
                ("description", "oi-filled"),
                ("close", None),
                ("open_in_new", None),
            ],
        }
        for xml_id, icons in expected.items():
            root = etree.fromstring(self.env.ref(xml_id).arch_db)
            actual = [
                (button.get("icon"), button.get("icon_class"))
                for button in root.xpath("//button[@icon]")
            ]
            self.assertEqual(actual, icons)

        requirement_root = etree.fromstring(self.env.ref("voip.view_requirement_list").arch_db)
        status_buttons = requirement_root.xpath("//button[@icon and not(@name)]")
        self.assertTrue(status_buttons)
        self.assertTrue(all(button.get("type") == "button" for button in status_buttons))
        self.assertTrue(all(button.get("title") for button in status_buttons))

    def test_advanced_order_form_focuses_on_the_current_action(self):
        root = etree.fromstring(self.env.ref("voip.voip_did_number_request_form_view").arch_db)

        statusbar = root.xpath("//field[@name='state' and @widget='statusbar']")[0]
        self.assertEqual(statusbar.get("statusbar_visible"), "pending,processing")
        self.assertFalse(root.xpath("//div[contains(@class, 'oe_title')]"))
        self.assertTrue(root.xpath(
            "//field[@name='provider_order_id']",
        ))
        requirement_group = root.xpath("//field[@name='requirement_group_id']")[0]
        self.assertEqual(requirement_group.get("invisible"), "True")
        self.assertTrue(root.xpath("//button[@name='action_open_requirements']"))
        detail_groups = root.xpath("//group[@string='Request Details']/group")
        self.assertEqual(
            [field.get("name") for field in detail_groups[0].xpath("./field")],
            ["country_id", "did_number_type", "quantity", "area_code"],
        )
        self.assertEqual(
            [field.get("name") for field in detail_groups[1].xpath("./field")],
            ["create_date", "requested_by_id", "provider_order_id"],
        )
        requested_on = detail_groups[1].xpath("./field[@name='create_date']")[0]
        self.assertEqual(requested_on.get("string"), "Requested On")

        contact_carrier = root.xpath("//group[@string=\"Contact Odoo's Phone Carrier\"]")[0]
        contact_carrier_text = " ".join(contact_carrier.itertext())
        self.assertIn("communicate with Odoo's phone carrier", contact_carrier_text)
        self.assertIn("eventually confirm your order", contact_carrier_text)
        self.assertIn("recorded in the chatter", contact_carrier_text)
        self.assertNotIn("activity history", contact_carrier_text)

        comment_field = root.xpath("//field[@name='new_comment']")[0]
        self.assertEqual(comment_field.get("widget"), "voip_number_request_comment")
        self.assertEqual(
            comment_field.get("placeholder"),
            "I have updated the proof of address with a more recent bill...",
        )

        send_buttons = root.xpath("//button[@name='action_send_comment']")
        self.assertEqual(len(send_buttons), 2)
        self.assertTrue(all(button.get("string") == "Send Message" for button in send_buttons))
        self.assertTrue(all(not button.get("icon") for button in send_buttons))
        enabled_button = next(button for button in send_buttons if not button.get("disabled"))
        disabled_button = next(button for button in send_buttons if button.get("disabled"))
        self.assertEqual(enabled_button.get("invisible"), "not new_comment")
        self.assertEqual(disabled_button.get("invisible"), "new_comment")

        user_facing_text = " ".join(root.itertext()) + " " + " ".join(
            value
            for node in root.iter()
            for attribute in ("string", "help", "placeholder", "title")
            if (value := node.get(attribute))
        )
        self.assertNotIn("Telnyx", user_facing_text)

    def test_did_requirement_actions_follow_review_state(self):
        did_root = etree.fromstring(self.env.ref("voip.voip_did_number_form_view").arch_db)
        update_buttons = did_root.xpath("//header/button[@string='Update Requirements']")
        self.assertEqual(len(update_buttons), 2)
        self.assertEqual({button.get("class") for button in update_buttons}, {"btn-primary", "btn-secondary"})
        self.assertTrue(all("state == 'pending'" in button.get("invisible") for button in update_buttons))

        release_button = did_root.xpath("//header/button[@name='action_release_number']")[0]
        self.assertNotIn("failure", release_button.get("invisible"))
        failure_alert = did_root.xpath("//div[contains(@class, 'alert-danger') and contains(@invisible, \"state != 'failure'\")]")[0]
        failure_text = " ".join(failure_alert.itertext())
        self.assertNotIn("log below", failure_text)
        self.assertNotIn("Release Number", failure_text)

        group_root = etree.fromstring(self.env.ref("voip.view_requirement_group_submit_form").arch_db)
        self.assertFalse(group_root.xpath("//field[@name='status']"))


@tagged("voip")
class TestBuyNumberWizardNoRequirements(TestBuyNumberWizardBase):

    def _search_and_select(self, wizard, select_count=1):
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_search_available_phone_numbers()):
            wizard.action_search()
        for line in wizard.result_line_ids[:select_count]:
            line.selected = True

    def test_happy_path_single_number(self):
        wizard = self._create_wizard()
        self._search_and_select(wizard, select_count=1)
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_order_success):
            result = wizard.action_purchase()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "success")
        self.assertEqual(result["params"]["message"], "Number +3287000001 is pending validation.")
        did = self.env["voip.did.number"].search([("did_number", "=", "+3287000001")])
        self.assertTrue(did)
        self.assertEqual(did.state, "ordering")

    def test_happy_path_multiple_numbers(self):
        wizard = self._create_wizard()
        self._search_and_select(wizard, select_count=2)
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_order_success):
            result = wizard.action_purchase()
        self.assertEqual(result["params"]["message"], "2 numbers are pending validation.")
        dids = self.env["voip.did.number"].search([
            ("did_number", "in", ["+3287000001", "+3287000002"]),
        ])
        self.assertEqual(len(dids), 2)
        for did in dids:
            self.assertEqual(did.state, "ordering")

    def test_partial_order_response_surfaces_usererror(self):
        """If the order response omits a requested number, surface a clear
        UserError (caught by action_purchase) instead of a raw KeyError."""
        wizard = self._create_wizard()
        self._search_and_select(wizard, select_count=2)

        def partial_order(route, params, retry_registration=True):
            if route == "/api/phone_service/1/order_phone_numbers":
                # Shop confirms only the first number; the second is omitted.
                return {"success": True, "data": {
                    "+3287000001": {"status": "ordering", "monthly_credits": 2.0},
                }}
            return {"success": True, "data": {}}

        with (
            patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=partial_order),
            mute_logger(VOIP_DID_NUMBER_LOGGER), self.assertRaisesRegex(UserError, r"\+3287000002"),
        ):
            wizard.action_purchase()

    def test_action_next_requires_selection(self):
        wizard = self._create_wizard()
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_search_available_phone_numbers()):
            wizard.action_search()
        with self.assertRaises(UserError, msg="Please select at least one"):
            wizard.action_next()

    def test_confirm_step_is_removed(self):
        step_values = dict(self.env["voip.did.number.search.wizard"]._fields["step"].selection)
        self.assertNotIn("confirm", step_values)

    def test_purchase_closes_wizard(self):
        wizard = self._create_wizard()
        self._search_and_select(wizard, select_count=2)

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_order_success):
            result = wizard.action_purchase()

        self.assertEqual(result["params"]["next"], {"type": "ir.actions.act_window_close"})

    def test_purchase_assigns_first_number_to_buyer_without_number(self):
        wizard = self._create_wizard(user=self.admin_user)
        self._search_and_select(wizard, select_count=2)

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_order_success):
            wizard.action_purchase()

        dids = self.env["voip.did.number"].search([
            ("did_number", "in", ["+3287000001", "+3287000002"]),
        ], order="did_number")
        self.assertEqual(dids[0].user_id, self.admin_user)
        self.assertEqual(dids[0].destination_ref, self.admin_user)
        self.assertFalse(dids[1].user_id)
        self.assertEqual(dids[0].state, "ordering")
        self.assertTrue(self.admin_user.voip_pbx_user_id)
        self.assertTrue(self.admin_user.voip_pbx_line_id)
        self.assertTrue(self.admin_user.res_users_settings_id.voip_username)
        self.assertTrue(self.admin_user.res_users_settings_id.voip_secret)

    def test_purchase_requires_admin(self):
        wizard = self._create_wizard()
        self._search_and_select(wizard)
        wizard_as_regular = wizard.with_user(self.regular_user)
        with self.assertRaises(UserError):
            with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_order_success):
                wizard_as_regular.action_purchase()

    def _buy_number(self, phone_number="+3287000001"):
        wizard = self._create_wizard()
        self._search_and_select(wizard, select_count=1)
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_order_success):
            wizard.action_purchase()
        return self.env["voip.did.number"].search([("did_number", "=", phone_number)])

    def test_rebuy_released_number_reuses_row(self):
        """Buying a number you previously released must not trip
        UNIQUE(did_number): the released row is reused, keeping its history."""
        did = self._buy_number()
        self.assertEqual(did.state, "ordering")
        released_id = did.id
        did.with_context(voip_skip_pbx_sync=True).write({
            "state": "released",
            "requirement_statuses": {"req_old": "approved"},
        })

        reused = self._buy_number()

        self.assertEqual(reused.id, released_id, "the released row should be reused, not duplicated")
        self.assertEqual(reused.state, "ordering")
        self.assertFalse(reused.requirement_statuses, "a new order must not inherit old review verdicts")

    def test_rebuy_failed_number_reuses_row(self):
        """A failed order leaves a 'failure' row; re-buying must reuse it too."""
        did = self._buy_number()
        released_id = did.id
        did.with_context(voip_skip_pbx_sync=True).write({"state": "failure"})

        reused = self._buy_number()

        self.assertEqual(reused.id, released_id, "the failure row should be reused, not duplicated")
        self.assertEqual(reused.state, "ordering")

    def test_rebuy_clears_stale_action_requirements(self):
        """Reuse must not inherit the prior order's per-DID action requirements:
        the buy wizard re-creates them, so a surviving row would be a duplicate.
        The group's shared (non-action) template must survive."""
        did = self._buy_number()
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_phone_service):
            group = self.env["voip.requirement.group"].with_context(
                skip_validation=True,
                default_country_id=self.country_be.id,
                default_did_number_type="local",
            ).create({"telnyx_requirement_group_id": "rg_reuse_stale"})
        stale_req = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "telnyx_requirement_id": "req_stale_action",
            "name": "Old Identity Verification",
            "field_type": "action",
            "did_number_id": did.id,
            "requirement_group_ids": [(4, group.id)],
        })
        # A shared template (no did_number_id) must survive the reuse.
        template_req = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "telnyx_requirement_id": "req_template_action",
            "name": "Identity Verification Template",
            "field_type": "action",
            "requirement_group_ids": [(4, group.id)],
        })
        did.with_context(voip_skip_pbx_sync=True).write({"state": "released"})

        reused = self._buy_number()

        self.assertEqual(reused.id, did.id)
        self.assertEqual(reused.state, "ordering")
        self.assertFalse(stale_req.exists(), "the prior order's action requirement must be removed")
        self.assertTrue(template_req.exists(), "the shared action template must not be removed")

    def test_rebuy_mixed_batch_reuses_and_creates(self):
        """A single purchase mixing a reused released number and a brand-new one
        must return both, correctly paired (the reuse/create split must not drop
        or mis-pair a number)."""
        first = self._buy_number("+3287000001")
        reused_id = first.id
        first.with_context(voip_skip_pbx_sync=True).write({"state": "released"})

        wizard = self._create_wizard()
        self._search_and_select(wizard, select_count=2)
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_order_success):
            wizard.action_purchase()

        dids = self.env["voip.did.number"].search([
            ("did_number", "in", ["+3287000001", "+3287000002"]),
        ])
        self.assertEqual(len(dids), 2, "one reused + one created, no duplicate")
        self.assertEqual(
            dids.filtered(lambda d: d.did_number == "+3287000001").id, reused_id,
            "the released number must reuse its row",
        )
        self.assertEqual(set(dids.mapped("state")), {"ordering"})

    def test_shared_pending_count_counts_only_not_yet_active(self):
        """The submit-form warning counts pending DIDs sharing the reusable values.

        Only the current DID is resubmitted; active/suspended/released/failure
        numbers are irrelevant to this warning.
        """
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_phone_service):
            group = self.env["voip.requirement.group"].with_context(
                skip_validation=True,
                default_country_id=self.country_be.id,
                default_did_number_type="local",
            ).create({"telnyx_requirement_group_id": "rg_shared_count"})
        for number, state in {
            "+3287000010": "ordering",
            "+3287000011": "pending",
            "+3287000012": "active",
            "+3287000013": "suspended",
            "+3287000014": "released",
            "+3287000015": "failure",
        }.items():
            self.env["voip.did.number"].with_context(voip_skip_pbx_sync=True).create({
                "did_number": number,
                "did_number_type": "local",
                "country_id": self.country_be.id,
                "requirement_group_id": group.id,
                "state": state,
            })
        self.assertEqual(group.shared_pending_count, 2)


@tagged("voip")
class TestBuyNumberWizardCreditDisplay(TestBuyNumberWizardBase):
    """Credit amounts always render with two decimals across the buy flow
    (pay button, balance/prorated labels, per-line price) instead of
    trimming trailing zeros."""

    def test_format_credits_always_shows_two_decimals(self):
        wizard_model = self.env["voip.did.number.search.wizard"]
        self.assertEqual(wizard_model._format_credits(1.2), "1.20")
        self.assertEqual(wizard_model._format_credits(0.8712), "0.87")
        self.assertEqual(wizard_model._format_credits(0), "0.00")

    def test_pay_label_bare_when_nothing_selected(self):
        wizard = self.env["voip.did.number.search.wizard"].new({
            "country_id": self.country_be.id,
            "did_number_type": "local",
        })
        self.assertEqual(wizard.pay_label, "Pay")

    def test_pay_label_shows_two_decimal_credits(self):
        wizard = self.env["voip.did.number.search.wizard"].new({
            "country_id": self.country_be.id,
            "did_number_type": "local",
        })
        wizard.selected_count = 1
        wizard.selected_prorated_total = 0.8712
        self.assertEqual(wizard.pay_label, "Pay 0.87 Credits")

    def test_pay_label_on_requirements_step_submits_and_pays(self):
        wizard = self.env["voip.did.number.search.wizard"].new({
            "country_id": self.country_be.id,
            "did_number_type": "local",
            "step": "assign_groups",
        })
        wizard.selected_count = 1
        wizard.selected_prorated_total = 0.8712
        self.assertEqual(wizard.pay_label, "Submit & Pay 0.87 Credits")

    def test_price_display_drops_per_minute_cost(self):
        line = self.env["voip.did.number.search.result.line"].new({"monthly_cost": 1.2})
        self.assertEqual(line.price_display, "1.20 credits/month")


@tagged("voip")
class TestBuyNumberWizardWithRequirements(TestBuyNumberWizardBase):

    def _mock_requirement_group_creation(self, route, params, retry_registration=True):
        if "/get_requirements" in route:
            return {
                "success": True,
                "data": [
                    {
                        "requirement_types": [
                            {
                                "id": "test_req_textual",
                                "name": "End User Name",
                                "description": "Full name",
                                "type": "textual",
                                "example": "John Doe",
                            },
                            {
                                "id": "test_req_document",
                                "name": "Proof of Identity",
                                "description": "Government ID",
                                "type": "document",
                                "example": "Passport",
                            },
                            {
                                "id": "test_req_action",
                                "name": "Identity Verification",
                                "description": "Third-party verification",
                                "type": "action",
                                "example": "Verification link",
                            },
                        ],
                    },
                ],
                "meta": {"total_results": 1},
            }
        if route.endswith("/create_requirement_group"):
            return {"success": True, "data": {"id": "test_rg_001"}}
        return {"success": True, "data": {}}

    def _search_select_and_proceed(self, wizard):
        with patch.object(
            PhoneServiceAPI, "_call_phone_service",
            side_effect=_mock_search_available_phone_numbers(has_requirements=True),
        ):
            wizard.action_search()
        wizard.result_line_ids[0].selected = True
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=self._mock_requirement_group_creation):
            wizard.action_next()

    def test_advanced_order_collects_missing_requirements_before_submission(self):
        def empty_search_with_requirements(route, params, retry_registration=True):
            if "search_available_phone_numbers" in route:
                return {"success": True, "data": []}
            if "requirements" in route:
                return {"success": True, "data": [], "meta": {"total_results": 1}}
            return {"success": True, "data": {}}

        wizard = self._create_wizard(starts_with="2")
        with patch.object(
            PhoneServiceAPI,
            "_call_phone_service",
            side_effect=empty_search_with_requirements,
        ):
            wizard.action_search()
        wizard.action_open_number_request()

        with patch.object(
            PhoneServiceAPI,
            "_call_phone_service",
            side_effect=self._mock_requirement_group_creation,
        ):
            action = wizard.action_submit_number_request()

        self.assertEqual(action["res_id"], wizard.id)
        self.assertEqual(wizard.step, "assign_groups")
        self.assertTrue(wizard.number_request)
        self.assertEqual(
            wizard.requirement_group_id.telnyx_requirement_group_id,
            "test_rg_001",
        )
        self.assertTrue(wizard.requirement_ids)
        wizard.action_back()
        self.assertEqual(wizard.step, "number_request")

        with patch.object(PhoneServiceAPI, "create_advanced_order") as create_advanced_order:
            action = wizard.action_submit_number_request()
        create_advanced_order.assert_not_called()
        self.assertEqual(action["res_id"], wizard.id)
        self.assertEqual(wizard.step, "assign_groups")

    def test_advanced_order_submits_completed_group_after_back(self):
        group = self.env["voip.requirement.group"].with_context(skip_validation=True).create({
            "telnyx_requirement_group_id": "test_rg_completed_advanced",
            "country_id": self.country_be.id,
            "did_number_type": "local",
        })
        self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, group.id)],
            "telnyx_requirement_id": "test_req_textual",
            "name": "End User Name",
            "field_type": "textual",
            "text_value": "Test User",
        })
        wizard = self._create_wizard(
            number_request=True,
            has_requirements=True,
            requirement_group_id=group.id,
            step="assign_groups",
        )
        wizard.action_back()

        with (
            patch.object(PhoneServiceAPI, "fulfill_requirement_group") as fulfill,
            patch.object(
                PhoneServiceAPI,
                "create_advanced_order",
                return_value={"id": "advanced_123", "status": "pending"},
            ) as create_advanced_order,
            patch("odoo.addons.base.models.ir_cron.IrCron._trigger") as trigger,
        ):
            wizard.action_submit_number_request()

        fulfill.assert_called_once_with(
            requirement_group_id="test_rg_completed_advanced",
            requirements=[{
                "requirement_id": "test_req_textual",
                "field_value": "Test User",
            }],
        )
        create_advanced_order.assert_not_called()
        trigger.assert_called_once()
        number_request = self.env["voip.did.number.request"].search([
            ("request_uuid", "=", wizard.number_request_uuid),
        ])
        self.assertEqual(number_request.state, "pending")

    def test_requirements_step_shown_when_needed(self):
        wizard = self._create_wizard()
        self._search_select_and_proceed(wizard)
        self.assertEqual(wizard.step, "assign_groups")
        self.assertTrue(wizard.requirement_ids)

    def test_confirm_groups_requires_fulfilled_requirements(self):
        wizard = self._create_wizard()
        self._search_select_and_proceed(wizard)
        with self.assertRaises(UserError, msg="Please complete all requirements"):
            wizard.action_confirm_groups()

    def test_confirm_groups_validates_purchase_before_submitting_requirements(self):
        group = self.env["voip.requirement.group"].with_context(skip_validation=True).create({
            "telnyx_requirement_group_id": "test_rg_prevalidation",
            "country_id": self.country_be.id,
            "did_number_type": "local",
        })
        wizard = self._create_wizard(
            step="assign_groups",
            requirement_group_id=group.id,
            iap_balance=0,
        )
        self.env["voip.did.number.search.result.line"].create({
            "wizard_id": wizard.id,
            "phone_number": "+3287000098",
            "did_number_type": "local",
            "monthly_cost": 2,
            "selected": True,
        })

        with (
            patch.object(
                self.env.registry["voip.requirement.group"],
                "action_fulfill_requirements",
                autospec=True,
            ) as fulfill_requirements,
            self.assertRaisesRegex(UserError, "Not enough credits"),
        ):
            wizard.action_confirm_groups()

        fulfill_requirements.assert_not_called()

    def test_confirm_groups_purchases_in_a_followup_request(self):
        group = self.env["voip.requirement.group"].with_context(skip_validation=True).create({
            "telnyx_requirement_group_id": "test_rg_purchase_boundary",
            "country_id": self.country_be.id,
            "did_number_type": "local",
        })
        wizard = self._create_wizard(
            step="assign_groups",
            requirement_group_id=group.id,
            iap_balance=500,
        )
        self.env["voip.did.number.search.result.line"].create({
            "wizard_id": wizard.id,
            "phone_number": "+3287000097",
            "did_number_type": "local",
            "monthly_cost": 2,
            "selected": True,
        })

        with (
            patch.object(
                self.env.registry["voip.requirement.group"],
                "action_fulfill_requirements",
                autospec=True,
            ) as fulfill_requirements,
            patch.object(
                self.env.registry["voip.did.number.search.wizard"],
                "action_purchase",
                autospec=True,
            ) as purchase,
        ):
            action = wizard.action_confirm_groups()

        fulfill_requirements.assert_called_once()
        purchase.assert_not_called()
        self.assertEqual(action["tag"], "voip.purchase_after_requirements")
        self.assertEqual(action["params"]["wizard_id"], wizard.id)

    def test_document_upload_and_ttl_cleanup(self):
        wizard = self._create_wizard()
        self._search_select_and_proceed(wizard)
        doc_req = wizard.requirement_ids.filtered(lambda r: r.field_type == "document")
        self.assertTrue(doc_req)
        doc_req.with_context(skip_validation=True).write({
            "document_file": BinaryBytes(b"fake-pdf-content", filename="test_id.pdf"),
        })
        text_req = wizard.requirement_ids.filtered(lambda r: r.field_type == "textual")
        text_req.with_context(skip_validation=True).write({"text_value": "Test User"})
        self.assertTrue(all(
            r.is_fulfilled for r in wizard.requirement_ids
            if r.field_type in ("textual", "document")
        ))

        uploaded_payload = {}

        def fulfill_fails(route, params, retry_registration=True):
            if "/upload_document" in route:
                uploaded_payload.update(params["payload"])
                return {"success": True, "data": {"id": "uploaded_doc_123"}}
            if route.endswith("/fulfill_requirement_group"):
                raise UserError("phone_service PATCH failed")
            return {"success": True, "data": {}}

        group = wizard.requirement_group_id
        with self.assertRaises(UserError):
            with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=fulfill_fails):
                group.action_fulfill_requirements()
        self.assertFalse(
            doc_req.telnyx_document_id,
            "telnyx_document_id must be cleared after failed fulfill so next retry re-uploads",
        )
        self.assertEqual(
            uploaded_payload["file_content_base64"],
            BinaryBytes(b"fake-pdf-content").to_base64(),
        )

    def test_document_reuse_skips_upload(self):
        wizard = self._create_wizard()
        self._search_select_and_proceed(wizard)
        doc_req = wizard.requirement_ids.filtered(lambda r: r.field_type == "document")
        doc_req.with_context(skip_validation=True).write({
            "document_file": BinaryBytes(b"fake-pdf", filename="id.pdf"),
            "telnyx_document_id": "already_uploaded_doc",
        })
        text_req = wizard.requirement_ids.filtered(lambda r: r.field_type == "textual")
        text_req.with_context(skip_validation=True).write({"text_value": "Test"})

        upload_called = []

        def track_uploads(route, params, retry_registration=True):
            if "/upload_document" in route:
                upload_called.append(True)
                return {"success": True, "data": {"id": "should_not_be_called"}}
            return {"success": True, "data": {}}

        group = wizard.requirement_group_id
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=track_uploads):
            group.action_fulfill_requirements()
        self.assertFalse(upload_called, "Should not re-upload when telnyx_document_id exists")

    def test_single_group_for_all_selected_lines(self):
        wizard = self._create_wizard()
        with patch.object(
            PhoneServiceAPI, "_call_phone_service",
            side_effect=_mock_search_available_phone_numbers(has_requirements=True),
        ):
            wizard.action_search()
        for line in wizard.result_line_ids:
            line.selected = True
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=self._mock_requirement_group_creation):
            wizard.action_next()
        self.assertTrue(wizard.requirement_group_id)
        self.assertEqual(wizard.requirement_group_id.telnyx_requirement_group_id, "test_rg_001")
        self.assertTrue(wizard.requirement_ids)

    def test_back_from_assign_groups_to_results(self):
        wizard = self._create_wizard()
        self._search_select_and_proceed(wizard)
        self.assertEqual(wizard.step, "assign_groups")
        wizard.action_back()
        self.assertEqual(wizard.step, "search")

    def test_second_search_resets_requirements_state(self):
        wizard = self._create_wizard()
        with patch.object(PhoneServiceAPI, "_call_phone_service",
                          side_effect=_mock_search_available_phone_numbers(has_requirements=True)):
            wizard.action_search()
        self.assertTrue(wizard.has_requirements)
        for line in wizard.result_line_ids:
            line.selected = True
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=self._mock_requirement_group_creation):
            wizard.action_next()
        self.assertTrue(wizard.requirement_group_id)
        wizard.action_back()
        with patch.object(PhoneServiceAPI, "_call_phone_service",
                          side_effect=_mock_search_available_phone_numbers(has_requirements=False)):
            wizard.action_search()
        self.assertFalse(wizard.has_requirements)
        self.assertFalse(wizard.requirement_group_id)

    def test_reuse_existing_requirement_group(self):
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_phone_service):
            existing_group = self.env["voip.requirement.group"].with_context(
                skip_validation=True,
                default_country_id=self.country_be.id,
                default_did_number_type="local",
            ).create({"telnyx_requirement_group_id": "rg_preexisting_be_local"})
        group_count_before = self.env["voip.requirement.group"].search_count([
            ("country_id", "=", self.country_be.id),
            ("did_number_type", "=", "local"),
        ])
        wizard = self._create_wizard()
        with patch.object(
            PhoneServiceAPI, "_call_phone_service",
            side_effect=_mock_search_available_phone_numbers(has_requirements=True),
        ):
            wizard.action_search()
        wizard.result_line_ids[0].selected = True
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=self._mock_requirement_group_creation):
            wizard.action_next()
        self.assertEqual(wizard.requirement_group_id, existing_group)
        group_count_after = self.env["voip.requirement.group"].search_count([
            ("country_id", "=", self.country_be.id),
            ("did_number_type", "=", "local"),
        ])
        self.assertEqual(group_count_after, group_count_before)

    def test_no_longer_eligible_requirement_group_is_replaced(self):
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_phone_service):
            obsolete_group = self.env["voip.requirement.group"].with_context(
                skip_validation=True,
                default_country_id=self.country_be.id,
                default_did_number_type="local",
            ).create({
                "telnyx_requirement_group_id": "rg_no_longer_eligible",
                "status": "no_longer_eligible",
            })
        group_count_before = self.env["voip.requirement.group"].search_count([
            ("country_id", "=", self.country_be.id),
            ("did_number_type", "=", "local"),
        ])
        wizard = self._create_wizard()
        with patch.object(
            PhoneServiceAPI, "_call_phone_service",
            side_effect=_mock_search_available_phone_numbers(has_requirements=True),
        ):
            wizard.action_search()
        wizard.result_line_ids[0].selected = True

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=self._mock_requirement_group_creation):
            wizard.action_next()

        self.assertNotEqual(wizard.requirement_group_id, obsolete_group)
        self.assertEqual(wizard.requirement_group_id.telnyx_requirement_group_id, "test_rg_001")
        group_count_after = self.env["voip.requirement.group"].search_count([
            ("country_id", "=", self.country_be.id),
            ("did_number_type", "=", "local"),
        ])
        self.assertEqual(group_count_after, group_count_before + 1)


@tagged("voip")
class TestBuyNumberWizardActionRequirement(TestBuyNumberWizardBase):

    def test_action_requirement_created_per_did_on_purchase(self):
        wizard = self._create_wizard()
        with patch.object(
            PhoneServiceAPI, "_call_phone_service",
            side_effect=_mock_search_available_phone_numbers(has_requirements=True),
        ):
            wizard.action_search()
        wizard.result_line_ids[0].selected = True

        def mock_group_and_reqs(route, params, retry_registration=True):
            if "/get_requirements" in route:
                return {
                    "success": True,
                    "data": [
                        {
                            "requirement_types": [
                                {"id": "req_action_test", "name": "Verify", "type": "action", "description": "Verify", "example": ""},
                            ],
                        },
                    ],
                    "meta": {"total_results": 1},
                }
            if route.endswith("/create_requirement_group"):
                return {"success": True, "data": {"id": "rg_action_test"}}
            return {"success": True, "data": {}}

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=mock_group_and_reqs):
            wizard.action_next()
        self.assertEqual(wizard.step, "assign_groups")
        wizard.requirement_ids.with_context(skip_validation=True).write({
            "action_first_name": "Ada",
            "action_last_name": "Lovelace",
        })

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=mock_group_and_reqs):
            followup_action = wizard.action_confirm_groups()
        self.assertEqual(followup_action["tag"], "voip.purchase_after_requirements")

        def order(route, params, retry_registration=True):
            if route == "/api/phone_service/1/order_phone_numbers":
                return _mock_batch_order(params)
            if "/get_phone_number_comments" in route:
                return {"success": True, "data": []}
            if route.startswith("/api/phone_service/1/pbx/"):
                return pbx_router(route, params)
            return {"success": True, "data": {}}

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=order):
            result = wizard.action_purchase()
        self.assertEqual(result["params"]["type"], "warning")
        self.assertIn("Identity verification", result["params"]["message"])
        self.assertTrue(result["params"]["sticky"])

        did = self.env["voip.did.number"].search([("did_number", "=", "+3287000001")])
        self.assertTrue(did.has_pending_action_requirement)

    def test_has_pending_action_requirement_false_after_url_generated(self):
        with patch.object(PhoneServiceAPI, "_call_phone_service", return_value={"success": True, "data": {"id": "mock_telnyx_id"}}):
            did = self.env["voip.did.number"].create({
                "did_number": "+3299999999",
                "did_number_type": "local",
                "state": "pending",
                "country_id": self.country_be.id,
            })
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_phone_service):
            group = self.env["voip.requirement.group"].with_context(
                skip_validation=True,
                default_country_id=self.country_be.id,
                default_did_number_type="local",
            ).create({"telnyx_requirement_group_id": "rg_test_pending"})
        did.requirement_group_id = group
        action_req = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "telnyx_requirement_id": "req_action_pending",
            "name": "Identity Verification",
            "field_type": "action",
            "did_number_id": did.id,
            "requirement_group_ids": [(4, group.id)],
        })
        self.assertTrue(did.has_pending_action_requirement)
        action_req.with_context(skip_validation=True).write({
            "action_verification_url": "https://example.com/verify",
        })
        self.assertFalse(did.has_pending_action_requirement)


@tagged("voip")
class TestDidNumberTypeConstant(common.TransactionCase):
    def test_models_share_canonical_type_order(self):
        """All number-type selections share one canonical order, so the buy
        wizard's 'first covered' default is deterministic."""
        expected = ["mobile", "local", "national", "toll_free"]
        for model in ("voip.did.number", "voip.requirement.group", "voip.did.number.search.result.line"):
            codes = [code for code, _label in self.env[model]._fields["did_number_type"].selection]
            self.assertEqual(codes, expected, f"{model} drifted from the canonical order")

    def test_wizard_sellable_types_exclude_shared_cost_and_all(self):
        wizard_codes = [
            code for code, _label
            in self.env["voip.did.number.search.wizard"]._fields["did_number_type"].selection
        ]
        self.assertEqual(wizard_codes, ["mobile", "local", "national", "toll_free"])
        self.assertNotIn("compatible_requirement_group_ids", self.env["voip.did.number.search.result.line"]._fields)
        self.assertNotIn("has_requirements", self.env["voip.did.number.search.result.line"]._fields)


@tagged("voip")
class TestBuyNumberOrderConfirmation(common.TransactionCase):
    """order_from_phone_service applies the state the phone_service response
    confirms for each number. Verifies the batch path lands every DID in
    'active' when the server confirms all of them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_be = cls.env.ref("base.be")
        dids = cls.env["voip.did.number"].search([]).with_context(voip_skip_pbx_sync=True)
        dids.write({"state": "released"})
        dids.unlink()

    def setUp(self):
        super().setUp()
        forbid_phone_service_http(self)

    def test_order_batch_lands_in_active(self):
        dids = self.env["voip.did.number"].create([
            {"did_number": "+3287000030", "did_number_type": "local",
             "state": "ordering", "country_id": self.country_be.id},
            {"did_number": "+3287000031", "did_number_type": "local",
             "state": "ordering", "country_id": self.country_be.id},
        ])

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "data": {
                "+3287000030": {"status": "active", "monthly_credits": 1.0},
                "+3287000031": {"status": "active", "monthly_credits": 1.0},
            },
        }
        with patch(
            "odoo.addons.voip.models.phone_service_api.requests.post",
            return_value=response,
        ):
            dids.order_from_phone_service()
        dids.invalidate_recordset()

        self.assertEqual(dids[0].state, "active")
        self.assertEqual(dids[1].state, "active")


@tagged("voip")
class TestBuyNumberWizardErrorWrap(TestBuyNumberWizardBase):
    """Verifies that ``action_purchase`` wraps a make_order failure in a
    UserError that mentions how many numbers were attempted, so the user
    knows the whole batch — not just one number — failed."""

    def test_action_purchase_wraps_iap_error_with_count(self):
        wizard = self._create_wizard()
        with patch.object(
            PhoneServiceAPI, "_call_phone_service",
            side_effect=_mock_search_available_phone_numbers(),
        ):
            wizard.action_search()
        # Select two numbers so the count in the wrap message is non-trivial.
        for line in wizard.result_line_ids[:2]:
            line.selected = True

        def fail_on_order(route, params, retry_registration=True):
            if route == "/api/phone_service/1/order_phone_numbers":
                raise UserError("Insufficient IAP credits.")
            return {"success": True, "data": {}}

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=fail_on_order):
            with self.assertRaisesRegex(UserError, r"Could not place the order for 2 number.*Insufficient IAP credits"):
                wizard.action_purchase()


@tagged("voip")
class TestVoipRequirementValidation(TestBuyNumberWizardBase):
    """voip.requirement error-surfacing on degraded phone_service responses."""

    def _make_group(self, ref):
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_phone_service):
            return self.env["voip.requirement.group"].with_context(
                skip_validation=True,
                default_country_id=self.country_be.id,
                default_did_number_type="local",
            ).create({"telnyx_requirement_group_id": ref})

    def test_address_validation_blank_errors_yields_message(self):
        """A provider rejection with no itemized errors must still produce a
        readable message instead of a blank ValidationError dialog."""
        group = self._make_group("rg_addr")
        addr_req = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "telnyx_requirement_id": "req_addr",
            "name": "Address",
            "field_type": "address",
            "requirement_group_ids": [(4, group.id)],
        })

        def invalid_no_errors(route, params, retry_registration=True):
            if "/validate_address" in route:
                return {"success": True, "data": {"valid": False, "errors": []}}
            return {"success": True, "data": {}}

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=invalid_no_errors):
            with self.assertRaisesRegex(ValidationError, r"could not be validated"):
                addr_req.with_context(skip_validation=False).write({
                    "address_first_name": "Ada",
                    "address_last_name": "Lovelace",
                    "address_street": "1 Rue Centrale",
                    "address_city": "Brussels",
                    "address_country_id": self.country_be.id,
                })

    def test_address_validation_invalid_fields_yield_itemized_message(self):
        group = self._make_group("rg_addr_fields")
        addr_req = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "telnyx_requirement_id": "req_addr_fields",
            "name": "Address",
            "field_type": "address",
            "requirement_group_ids": [(4, group.id)],
        })

        def invalid_fields(route, params, retry_registration=True):
            if "/validate_address" in route:
                return {"success": True, "data": {
                    "valid": False,
                    "invalid_address_fields": ["postal_code", "street_address"],
                }}
            return {"success": True, "data": {}}

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=invalid_fields):
            with self.assertRaisesRegex(
                ValidationError,
                r"(?s)The postal code is invalid.*The street address is invalid",
            ):
                addr_req.with_context(skip_validation=False).write({
                    "address_first_name": "Ada",
                    "address_last_name": "Lovelace",
                    "address_street": "1 Rue Centrale",
                    "address_city": "Brussels",
                    "address_country_id": self.country_be.id,
                })

    def test_generate_verification_url_raises_when_provider_returns_no_url(self):
        """An empty verification response must surface a clear error instead of
        silently writing a blank URL and reporting success."""
        with patch.object(PhoneServiceAPI, "_call_phone_service", return_value={"success": True, "data": {"id": "mock_telnyx_id"}}):
            did = self.env["voip.did.number"].create({
                "did_number": "+3299999997",
                "did_number_type": "local",
                "state": "pending",
                "country_id": self.country_be.id,
            })
        group = self._make_group("rg_no_url")
        action_req = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "telnyx_requirement_id": "req_action_no_url",
            "name": "Identity Verification",
            "field_type": "action",
            "action_first_name": "Ada",
            "action_last_name": "Lovelace",
            "did_number_id": did.id,
            "requirement_group_ids": [(4, group.id)],
        })

        def empty_url(route, params, retry_registration=True):
            if "/generate_requirement_verification_url" in route:
                return {"success": True, "data": {"requirement_action": {}}}
            return {"success": True, "data": {}}

        with (
            patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=empty_url),
            mute_logger(VOIP_REQUIREMENT_LOGGER), self.assertRaises(UserError),
        ):
            action_req.generate_verification_url()
        self.assertFalse(action_req.action_verification_url)

    def test_address_validation_missing_valid_key_is_handled(self):
        """A success response missing the 'valid' key must surface a clean
        ValidationError, not a raw KeyError."""
        group = self._make_group("rg_addr_no_valid")
        addr_req = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "telnyx_requirement_id": "req_addr_no_valid",
            "name": "Address",
            "field_type": "address",
            "requirement_group_ids": [(4, group.id)],
        })

        def no_valid_key(route, params, retry_registration=True):
            if "/validate_address" in route:
                return {"success": True, "data": {}}
            return {"success": True, "data": {}}

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=no_valid_key):
            with self.assertRaises(ValidationError):
                addr_req.with_context(skip_validation=False).write({
                    "address_first_name": "Ada",
                    "address_last_name": "Lovelace",
                    "address_street": "1 Rue Centrale",
                    "address_city": "Brussels",
                    "address_country_id": self.country_be.id,
                })

    def test_create_requirement_group_handles_empty_data_with_positive_count(self):
        """total_results>0 with an empty data list must not IndexError on form open."""
        api = PhoneServiceAPI(self.env)

        def divergent(route, params, retry_registration=True):
            if "/get_requirements" in route:
                return {"success": True, "data": [], "meta": {"total_results": 1}}
            if route.endswith("/create_requirement_group"):
                return {"success": True, "data": {"id": "rg_x"}}
            return {"success": True, "data": {}}

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=divergent):
            _data, requirements = api.create_requirement_group("BE", "local")
        self.assertEqual(requirements, {})


@tagged("voip")
class TestBuyNumberRelease(TestBuyNumberWizardBase):
    def _assigned_number(self, number="+3287000099"):
        user = new_test_user(
            self.env,
            login=f"voip_assigned_{number[-4:]}",
            groups="base.group_user",
            country_id=self.country_be.id,
        )
        user.with_context(voip_skip_pbx_sync=True).write({
            "voip_pbx_user_id": 10,
            "voip_pbx_line_id": 20,
        })
        provider = self.env.ref("voip.odoo_provider")
        settings = self.env["res.users.settings"]._find_or_create_for_user(user)
        settings.write({
            "voip_provider_id": provider.id,
            "voip_username": "old_user",
            "voip_secret": "old_secret",
        })
        did = self.env["voip.did.number"].with_context(install_mode=True).create({
            "did_number": number,
            "did_number_type": "local",
            "state": "active",
            "country_id": self.country_be.id,
            "destination_ref": f"res.users,{user.id}",
            "pbx_incall_id": 50,
            "pbx_incall_extension_id": 60,
        })
        return did, user, settings

    def test_release_number(self):
        with patch.object(PhoneServiceAPI, "_call_phone_service", return_value={"success": True, "data": {"id": "mock_id"}}):
            did = self.env["voip.did.number"].create({
                "did_number": "+3288888888",
                "did_number_type": "local",
                "state": "active",
                "country_id": self.country_be.id,
            })
        with patch.object(PhoneServiceAPI, "_call_phone_service", return_value={"success": True, "data": {}}):
            did.action_release_number()
        self.assertEqual(did.state, "released")
        self.assertFalse(did.user_id)

    def test_state_change_posts_status_changed_subtype(self):
        did, user, _settings = self._assigned_number("+3287000123")
        did._subscribe_status_followers()
        self.env.cr.precommit.run()

        did.write({"state": "suspended"})
        self.env.cr.precommit.run()

        state_subtype = self.env.ref("voip.mt_did_number_state")
        self.assertEqual(did.message_ids[:1].subtype_id, state_subtype)
        self.assertTrue(state_subtype.default, "followers must auto-subscribe to status changes")
        follower = did.message_follower_ids.filtered(lambda f: f.partner_id == user.partner_id)
        self.assertIn(state_subtype, follower.subtype_ids)

    def test_assign_active_number_creates_user_and_incall_route(self):
        did = self.env["voip.did.number"].with_context(install_mode=True).create({
            "did_number": "+3287000100",
            "did_number_type": "local",
            "state": "active",
            "country_id": self.country_be.id,
        })
        user = new_test_user(
            self.env,
            login="voip_assign_number_user",
            groups="base.group_user",
            country_id=self.country_be.id,
        )
        provider = self.env.ref("voip.odoo_provider")

        did.write({"destination_ref": f"res.users,{user.id}"})

        self.assertEqual(did.user_id, user)
        self.assertEqual(did.destination_ref, user)
        self.assertEqual(did.pbx_incall_id, 50)
        self.assertEqual(did.pbx_incall_extension_id, 60)
        self.assertEqual(user.res_users_settings_id.voip_provider_id, provider)

    def test_active_number_routes_to_all_supported_destinations(self):
        contact = self.env["res.partner"].create({
            "name": "DID external destination",
            "phone": "+32472222222",
            "country_id": self.country_be.id,
        })
        user = new_test_user(
            self.env,
            login="voip_did_destination_user",
            groups="base.group_user",
        )
        user.with_context(voip_skip_pbx_sync=True).voip_pbx_user_id = 211
        call_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "DID group destination",
            "pbx_group_id": 212,
            "pbx_group_uuid": "did-group-uuid",
        })
        extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "number": "9213",
            "destination_ref": f"voip.call.group,{call_group.id}",
            "pbx_extension_id": 213,
        })
        queue = self.env["voip.queue"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "DID queue destination",
            "pbx_queue_id": 214,
        })
        audio_message = self.env["voip.sound"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "DID audio destination",
            **tts_sound_values("Welcome."),
        })
        ivr = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "DID menu destination",
            "menu_sound_id": audio_message.id,
            "pbx_ivr_id": 215,
        })
        voicemail = self.env["voip.voicemail"].with_context(
            voip_skip_pbx_sync=True,
        ).create({
            "name": "DID mailbox destination",
            "pbx_voicemail_id": 216,
        })
        call_flow = self.env["voip.call.flow"].create({
            "name": "DID Call Flow destination",
            "graph_data": {
                "nodes": [
                    {
                        "id": "start",
                        "type": "start",
                        "outputs": [{
                            "id": "next",
                            "direction": "output",
                            "provides": "flow",
                            "maxConnections": 1,
                        }],
                    },
                    {
                        "id": "extension",
                        "type": "extension",
                        "input": {
                            "id": "input",
                            "direction": "input",
                            "accepts": ["flow"],
                        },
                        "outputs": [],
                        "record": {
                            "resModel": "voip.extension",
                            "resId": extension.id,
                        },
                    },
                ],
                "connections": [{
                    "sourceNodeId": "start",
                    "sourcePortId": "next",
                    "targetNodeId": "extension",
                    "targetPortId": "input",
                }],
            },
        })
        scenarios = (
            (extension, {"type": "extension", "exten": "9213"}),
            (call_flow, {"type": "extension", "exten": "9213"}),
            (call_group, {"type": "group", "group_id": 212}),
            (ivr, {"type": "ivr", "ivr_id": 215}),
            (queue, {"type": "queue", "queue_id": 214}),
            (
                audio_message,
                {
                    "type": "sound",
                    "filename": audio_message._get_pbx_sound_filename(),
                },
            ),
            (user, {"type": "user", "user_id": 211}),
            (contact, {"type": "outcall", "exten": "32472222222"}),
            (voicemail, {"type": "voicemail", "voicemail_id": 216}),
        )

        for index, (destination, expected_payload) in enumerate(scenarios):
            with self.subTest(destination=destination._name):
                did = self.env["voip.did.number"].with_context(
                    voip_skip_pbx_sync=True,
                ).create({
                    "did_number": f"+32870002{index:02}",
                    "did_number_type": "local",
                    "state": "active",
                    "country_id": self.country_be.id,
                    "destination_ref": f"{destination._name},{destination.id}",
                })
                calls, patcher = capture_pbx_calls()
                with patcher:
                    did.with_context(voip_skip_pbx_sync=False)._sync_pbx_incall()

                self.assertEqual(
                    calls_for(calls, "sync_incall")[-1]["params"]["destination"],
                    expected_payload,
                )

    def test_unassign_number_deletes_incall_route_and_resets_caller_id(self):
        # Unassigning keeps the credentials so the PBX user identity can be reused.
        did, _user, settings = self._assigned_number("+3287000101")
        sip_credentials = (settings.voip_username, settings.voip_secret)

        did.write({"destination_ref": False})

        self.assertFalse(did.user_id)
        self.assertFalse(did.destination_ref)
        self.assertFalse(did.pbx_incall_id)
        self.assertFalse(did.pbx_incall_extension_id)
        self.assertEqual(settings.voip_provider_id, self.env.ref("voip.odoo_provider"))
        self.assertEqual(
            (settings.voip_username, settings.voip_secret),
            sip_credentials,
        )

    def test_release_assigned_number_deletes_incall_route_and_resets_caller_id(self):
        did, _user, settings = self._assigned_number("+3287000102")

        with patch.object(PhoneServiceAPI, "_call_phone_service", return_value={"success": True, "data": {}}):
            did.action_release_number()

        self.assertEqual(did.state, "released")
        self.assertFalse(did.user_id)
        self.assertFalse(did.destination_ref)
        self.assertFalse(did.pbx_incall_id)
        self.assertFalse(did.pbx_incall_extension_id)
        self.assertEqual(settings.voip_provider_id, self.env.ref("voip.odoo_provider"))

    def test_removing_destination_unroutes_number(self):
        did, _user, _settings = self._assigned_number("+3287000104")
        call_group = self.env["voip.call.group"].with_context(
            voip_skip_pbx_sync=True,
        ).create({"name": "Temporary Destination"})
        did.with_context(voip_skip_pbx_sync=True).destination_ref = call_group

        call_group.with_context(voip_skip_pbx_sync=False).unlink()

        self.assertFalse(did.destination_ref)
        self.assertFalse(did.pbx_incall_id)
        self.assertFalse(did.pbx_incall_extension_id)


@tagged("voip")
class TestBuyNumberWizardCreditGate(TestBuyNumberWizardBase):
    def _search_and_select(self, wizard, select_count=1):
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=_mock_search_available_phone_numbers()):
            wizard.action_search()
        for line in wizard.result_line_ids[:select_count]:
            line.selected = True

    def test_purchase_blocked_when_credits_insufficient(self):
        wizard = self._create_wizard()
        self._search_and_select(wizard)
        # An empty account overrides the funded balance from the base setUp.
        with patch.object(IapAccount, "get_credits", lambda self, service_name: 0.0):
            wizard.action_refresh_balance()
            self.assertEqual(wizard.iap_balance, 0)
            with self.assertRaisesRegex(UserError, "Not enough credits"):
                wizard.action_purchase()

    def test_needs_credits_matrix(self):
        wizard = self._create_wizard()
        # Funded balance (per setUp), nothing selected.
        self.assertFalse(wizard.needs_credits)

        # Selection affordable: prorated cost is a few credits, well under the funded balance.
        self._search_and_select(wizard)
        self.assertGreater(wizard.selected_prorated_total, 0)
        self.assertLess(wizard.selected_prorated_total, wizard.iap_balance)
        self.assertFalse(wizard.needs_credits)

        # Selection unaffordable: drop the balance below the prorated cost.
        wizard.iap_balance = wizard.selected_prorated_total / 2
        self.assertTrue(wizard.needs_credits)

        # Zero balance, nothing selected.
        wizard.iap_balance = 0
        wizard.result_line_ids.selected = False
        self.assertTrue(wizard.needs_credits)

    def test_terminal_buttons_gate_on_results_and_affordability(self):
        wizard = self._create_wizard()
        # No search yet: no results, so no terminal Pay/Continue buttons.
        self.assertFalse(wizard.show_pay or wizard.show_continue)

        # Search returns affordable results: the terminal buttons apply.
        self._search_and_select(wizard)
        self.assertFalse(wizard.needs_credits)
        self.assertTrue(wizard.show_pay or wizard.show_continue)

        # Out of credits: route to Buy Credits instead of Pay/Continue.
        wizard.iap_balance = 0
        self.assertTrue(wizard.needs_credits)
        self.assertFalse(wizard.show_pay or wizard.show_continue)

    def test_action_buy_credits_opens_iap_store_in_new_tab(self):
        action = self._create_wizard().action_buy_credits()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertEqual(action["target"], "new")
        self.assertIn(f"service_name={PHONE_SERVICE_NAME}", action["url"])

    def test_refresh_balance_repolls_and_keeps_wizard_open(self):
        wizard = self._create_wizard()
        self._search_and_select(wizard)
        with patch.object(IapAccount, "get_credits", lambda self, service_name: 0.0):
            wizard.action_refresh_balance()
            self.assertEqual(wizard.iap_balance, 0)
        with patch.object(IapAccount, "get_credits", lambda self, service_name: 42.0):
            action = wizard.action_refresh_balance()
            self.assertEqual(wizard.iap_balance, 42)
        self.assertEqual(action["res_model"], "voip.did.number.search.wizard")
        self.assertEqual(action["res_id"], wizard.id)
        self.assertEqual(wizard.result_line_ids[0].selected, True, "selection survives the refresh")

    def test_delete_released_number_deletes_stale_incall_route(self):
        did = self.env["voip.did.number"].with_context(install_mode=True).create({
            "did_number": "+3287000103",
            "did_number_type": "local",
            "state": "released",
            "country_id": self.country_be.id,
            "pbx_incall_id": 50,
            "pbx_incall_extension_id": 60,
        })

        did.unlink()

        self.assertFalse(self.env["voip.did.number"].search([("did_number", "=", "+3287000103")]))

    def test_cannot_delete_active_number(self):
        with patch.object(PhoneServiceAPI, "_call_phone_service", return_value={"success": True, "data": {"id": "mock_id"}}):
            did = self.env["voip.did.number"].create({
                "did_number": "+3277777777",
                "did_number_type": "local",
                "state": "active",
                "country_id": self.country_be.id,
            })
        with self.assertRaises(UserError, msg="must release"):
            did.unlink()

    def test_can_delete_released_number(self):
        with patch.object(PhoneServiceAPI, "_call_phone_service", return_value={"success": True, "data": {"id": "mock_id"}}):
            did = self.env["voip.did.number"].create({
                "did_number": "+3266666666",
                "did_number_type": "local",
                "state": "released",
                "country_id": self.country_be.id,
            })
        did.unlink()
        self.assertFalse(self.env["voip.did.number"].search([("did_number", "=", "+3266666666")]))


@tagged("voip")
class TestBuyNumberWizardCoverage(TestBuyNumberWizardBase):
    def _wizard_with_coverage(self, types):
        with patch.object(
            PhoneServiceAPI, "get_all_country_coverage",
            side_effect=lambda: {"BE": types},
        ):
            wizard = self.env["voip.did.number.search.wizard"].with_user(self.admin_user).create({
                "country_id": self.country_be.id,
            })
            wizard.flush_recordset()  # stored computes are lazy; flush while mock is active
            return wizard

    def test_whitelist_dedupes_strips_shared_cost_and_uses_canonical_order(self):
        wizard = self._wizard_with_coverage(["toll_free", "local", "local", "shared_cost", "mobile"])
        self.assertEqual(wizard.available_did_number_type_codes, ["mobile", "local", "toll_free"])
        self.assertTrue(wizard.has_available_types)

    def test_default_is_first_covered_in_canonical_order(self):
        wizard = self._wizard_with_coverage(["toll_free", "local", "mobile"])
        self.assertEqual(wizard.did_number_type, "mobile")

    def test_explicit_type_survives_create_and_siblings_still_compute(self):
        """An explicit did_number_type on create must be kept AND the whitelist
        siblings must still be computed. (Regression guard for the split compute.)"""
        with patch.object(
            PhoneServiceAPI, "get_all_country_coverage",
            side_effect=lambda: {"BE": ["toll_free", "local", "mobile"]},
        ):
            wizard = self.env["voip.did.number.search.wizard"].with_user(self.admin_user).create({
                "country_id": self.country_be.id,
                "did_number_type": "local",
            })
        self.assertEqual(wizard.did_number_type, "local")
        self.assertEqual(wizard.available_did_number_type_codes, ["mobile", "local", "toll_free"])
        self.assertTrue(wizard.has_available_types)

    def test_empty_coverage_disables_search(self):
        wizard = self._wizard_with_coverage([])
        self.assertFalse(wizard.has_available_types)
        # Json field coerces [] to False server-side (convert_to_cache: `if not value: return None`)
        self.assertFalse(wizard.available_did_number_type_codes)

    def test_only_shared_cost_is_treated_as_empty(self):
        wizard = self._wizard_with_coverage(["shared_cost"])
        self.assertFalse(wizard.has_available_types)

    def test_coverage_failure_falls_back_to_full_sellable_list(self):
        def boom():
            raise UserError("phone_service unreachable")

        with (
            patch.object(PhoneServiceAPI, "get_all_country_coverage", side_effect=boom),
            mute_logger(VOIP_DID_NUMBER_SEARCH_WIZARD_LOGGER),
        ):
            wizard = self.env["voip.did.number.search.wizard"].with_user(self.admin_user).create({
                "country_id": self.country_be.id,
            })
            wizard.flush_recordset()  # stored computes are lazy; flush while mock is active
        self.assertEqual(wizard.available_did_number_type_codes, ["mobile", "local", "national", "toll_free"])
        self.assertTrue(wizard.has_available_types)

    def test_view_filters_type_dropdown_and_gates_search_on_coverage(self):
        arch = self.env.ref("voip.voip_did_number_search_wizard_form").arch_db
        root = etree.fromstring(arch)
        type_field = root.xpath("//field[@name='did_number_type'][@widget='filterable_selection']")[0]
        self.assertIn("available_did_number_type_codes", type_field.get("options"))
        # Hidden when no types -> the filterable_selection widget never mounts on
        # an empty (False-coerced) Json whitelist, so it can't crash on .includes.
        self.assertIn("has_available_types", type_field.get("invisible") or "")
        search_buttons = root.xpath("//footer/button[@name='action_search']")
        self.assertTrue(search_buttons)
        self.assertIn("has_available_types", search_buttons[0].get("invisible"))

    def test_empty_coverage_alert_invisible_conditions(self):
        arch = self.env.ref("voip.voip_did_number_search_wizard_form").arch_db
        root = etree.fromstring(arch)
        alert_divs = root.xpath("//div[contains(@class, 'alert-warning')][contains(text(), 'No supported number types')]")
        self.assertEqual(len(alert_divs), 1)
        invisible = alert_divs[0].get("invisible", "")
        self.assertIn("not country_id", invisible)
        self.assertIn("has_available_types", invisible)

    def test_coverage_map_cached_per_day(self):
        """The full coverage map is fetched once per day, then served from
        ormcache; a new day misses and re-fetches."""
        Wizard = self.env["voip.did.number.search.wizard"]
        with patch.object(
            PhoneServiceAPI, "get_all_country_coverage",
            side_effect=lambda: {"BE": ["local", "mobile"], "US": ["local"]},
        ) as mocked:
            Wizard._get_coverage_map(date(2026, 1, 1))
            Wizard._get_coverage_map(date(2026, 1, 1))  # same day -> cache hit
            self.assertEqual(mocked.call_count, 1)
            Wizard._get_coverage_map(date(2026, 1, 2))  # new day -> miss
            self.assertEqual(mocked.call_count, 2)

    def test_country_domain_covers_only_countries_with_sellable_types(self):
        """country_id is restricted to countries whose coverage intersects the
        sellable types; no-type and unsellable-only countries are excluded."""
        with patch.object(
            PhoneServiceAPI, "get_all_country_coverage",
            side_effect=lambda: {
                "BE": ["local", "mobile"],  # sellable -> covered
                "AF": [],                   # no types -> excluded
                "XX": ["shared_cost"],      # only unsellable -> excluded
            },
        ):
            wizard = self.env["voip.did.number.search.wizard"].with_user(self.admin_user).create({
                "country_id": self.country_be.id,
            })
            self.assertEqual(wizard.country_id_domain, repr([("code", "in", ["BE"])]))

    def test_country_domain_falls_back_to_all_on_broker_error(self):
        def boom():
            raise UserError("phone_service unreachable")

        with (
            patch.object(PhoneServiceAPI, "get_all_country_coverage", side_effect=boom),
            mute_logger(VOIP_DID_NUMBER_SEARCH_WIZARD_LOGGER),
        ):
            wizard = self.env["voip.did.number.search.wizard"].with_user(self.admin_user).create({
                "country_id": self.country_be.id,
            })
            self.assertEqual(wizard.country_id_domain, "[]")  # empty domain -> every country

    def test_view_country_field_uses_coverage_domain(self):
        arch = self.env.ref("voip.voip_did_number_search_wizard_form").arch_db
        root = etree.fromstring(arch)
        country_field = root.xpath("//field[@name='country_id']")[0]
        self.assertEqual(country_field.get("domain"), "country_id_domain")

    def test_no_country_offers_all_types(self):
        """With no country picked yet, the Type field must still be usable:
        offer every sellable type instead of an empty (hidden) whitelist.
        Uses .new() (an in-memory record) since country_id is a required,
        NOT-NULL-backed field and can't be persisted as False."""
        wizard = self.env["voip.did.number.search.wizard"].new({"country_id": False})
        self.assertEqual(
            wizard.available_did_number_type_codes,
            [code for code, _label in DID_NUMBER_TYPES],
        )
        self.assertTrue(wizard.has_available_types)

    def test_default_country_skipped_when_not_covered(self):
        """Company country US, coverage map only contains BE: pre-filling US
        would put the user straight into a country Telnyx doesn't sell in."""
        self.env.company.country_id = self.env.ref("base.us")
        defaults = self.env["voip.did.number.search.wizard"].default_get(["country_id"])
        self.assertFalse(defaults.get("country_id"))

    def test_default_country_kept_when_covered(self):
        self.env.company.country_id = self.env.ref("base.be")
        defaults = self.env["voip.did.number.search.wizard"].default_get(["country_id"])
        self.assertEqual(defaults.get("country_id"), self.env.ref("base.be").id)

    def test_default_country_falls_back_on_coverage_failure(self):
        """On a coverage-fetch outage the default degrades open: keep the
        company country rather than leaving the field blank."""
        self.env.company.country_id = self.env.ref("base.us")

        def boom():
            raise UserError("phone_service unreachable")

        with patch.object(PhoneServiceAPI, "get_all_country_coverage", side_effect=boom):
            # Base setUp's BE-only coverage was already cached; bust it so
            # this call actually reaches (and fails on) the mock above.
            self.env.transaction.invalidate_ormcache()
            defaults = self.env["voip.did.number.search.wizard"].default_get(["country_id"])
        self.assertEqual(defaults.get("country_id"), self.env.ref("base.us").id)


@tagged("voip")
class TestCountryCoverageApi(common.TransactionCase):
    def setUp(self):
        super().setUp()
        forbid_phone_service_http(self)

    def test_get_all_country_coverage_rekeys_by_iso_code(self):
        api = PhoneServiceAPI(self.env)

        def mock(route, params, retry_registration=True):
            if "/get_country_coverage" in route:
                return {"success": True, "data": {
                    "Egypt": {"code": "EG", "phone_number_type": ["local", "toll_free"]},
                    "Belgium": {"code": "BE", "phone_number_type": ["mobile", "local"]},
                }}
            return {"success": True, "data": {}}

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=mock):
            coverage = api.get_all_country_coverage()
        self.assertEqual(coverage, {"EG": ["local", "toll_free"], "BE": ["mobile", "local"]})

    def test_get_all_country_coverage_empty_when_no_data(self):
        api = PhoneServiceAPI(self.env)
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=lambda *a, **k: {"success": True, "data": {}}):
            self.assertEqual(api.get_all_country_coverage(), {})
