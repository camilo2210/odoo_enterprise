from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.voip.tests.common_voip import mock_pbx_layer


@tagged("voip", "post_install", "-at_install")
class TestVoipRequirement(TransactionCase):
    def setUp(self):
        super().setUp()
        mock_pbx_layer(self)
        self.country_be = self.env.ref("base.be")
        self.group = self.env["voip.requirement.group"].with_context(
            skip_validation=True,
            default_country_id=self.country_be.id,
            default_did_number_type="local",
        ).create({
            "telnyx_requirement_group_id": "rg_test_requirement",
            "status": "unapproved",
        })

    def _create_address_requirement(self, **values):
        return self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, self.group.id)],
            "telnyx_requirement_id": "req_address",
            "name": "Address",
            "field_type": "address",
            **values,
        })

    def test_create_address_requires_a_name(self):
        with self.assertRaisesRegex(ValidationError, "First and Last Name or Business Name"):
            self.env["voip.requirement"].create({
                "requirement_group_ids": [(4, self.group.id)],
                "telnyx_requirement_id": "req_address_noname",
                "name": "Address",
                "field_type": "address",
                "address_street": "Rue de la Loi 16",
            })

    def test_create_address_rejects_a_badly_formatted_phone(self):
        with self.assertRaisesRegex(ValidationError, "international format"):
            self.env["voip.requirement"].create({
                "requirement_group_ids": [(4, self.group.id)],
                "telnyx_requirement_id": "req_address_badphone",
                "name": "Address",
                "field_type": "address",
                "address_first_name": "Jane",
                "address_last_name": "Doe",
                "address_phone": "0032485200345",
            })

    def test_create_address_accepts_a_valid_international_phone(self):
        requirement = self.env["voip.requirement"].create({
            "requirement_group_ids": [(4, self.group.id)],
            "telnyx_requirement_id": "req_address_goodphone",
            "name": "Address",
            "field_type": "address",
            "address_first_name": "Jane",
            "address_last_name": "Doe",
            "address_phone": "+32485200345",
        })
        self.assertEqual(requirement.address_phone, "+32485200345")

    def test_compute_address_is_filled(self):
        requirement = self._create_address_requirement()
        self.assertFalse(requirement.address_is_filled)

        requirement.write({
            "address_first_name": "Jane",
            "address_last_name": "Doe",
            "address_street": "Rue de la Loi 16",
            "address_city": "Brussels",
            "address_country_id": self.country_be.id,
        })

        self.assertTrue(requirement.address_is_filled)

    def test_compute_is_fulfilled_for_address_and_action_types(self):
        address_requirement = self._create_address_requirement()
        self.assertFalse(address_requirement.is_fulfilled)
        address_requirement.write({
            "address_first_name": "Jane",
            "address_last_name": "Doe",
            "address_street": "Rue de la Loi 16",
            "address_city": "Brussels",
            "address_country_id": self.country_be.id,
        })
        self.assertTrue(address_requirement.is_fulfilled)

        action_requirement = self.env["voip.requirement"].with_context(
            skip_validation=True,
        ).create({
            "requirement_group_ids": [(4, self.group.id)],
            "telnyx_requirement_id": "req_action",
            "name": "Identity check",
            "field_type": "action",
        })
        self.assertFalse(action_requirement.is_fulfilled)
        action_requirement.write({"action_first_name": "Jane", "action_last_name": "Doe"})
        self.assertTrue(action_requirement.is_fulfilled)

    def test_get_address_api_body_includes_optional_fields_when_set(self):
        requirement = self._create_address_requirement(
            address_first_name="Jane",
            address_last_name="Doe",
            address_business_name="Acme",
            address_street="Rue de la Loi 16",
            address_extended="Floor 3",
            address_city="Brussels",
            address_country_id=self.country_be.id,
            address_phone="+32485200345",
        )

        body = requirement._get_address_api_body()

        self.assertEqual(body["street_address"], "Rue de la Loi 16")
        self.assertEqual(body["country_code"], self.country_be.code)
        self.assertEqual(body["first_name"], "Jane")
        self.assertEqual(body["last_name"], "Doe")
        self.assertEqual(body["business_name"], "Acme")
        self.assertEqual(body["extended_address"], "Floor 3")
        self.assertEqual(body["phone_number"], "+32485200345")

    def test_get_address_api_body_omits_unset_optional_fields(self):
        requirement = self._create_address_requirement(address_street="Rue de la Loi 16")

        body = requirement._get_address_api_body()

        self.assertNotIn("first_name", body)
        self.assertNotIn("last_name", body)
        self.assertNotIn("business_name", body)
        self.assertNotIn("extended_address", body)
        self.assertNotIn("phone_number", body)

    def test_generate_verification_url_is_a_noop_for_non_action_types(self):
        requirement = self._create_address_requirement()

        self.assertFalse(requirement.generate_verification_url())

    def test_generate_verification_url_requires_action_names(self):
        requirement = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, self.group.id)],
            "telnyx_requirement_id": "req_action_noname",
            "name": "Identity check",
            "field_type": "action",
        })

        with self.assertRaisesRegex(UserError, "first and last name"):
            requirement.generate_verification_url()

    def test_generate_verification_url_requires_a_telnyx_requirement_id(self):
        requirement = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, self.group.id)],
            "telnyx_requirement_id": "",
            "name": "Identity check",
            "field_type": "action",
            "action_first_name": "Jane",
            "action_last_name": "Doe",
        })

        with self.assertRaisesRegex(UserError, "Could not find requirement id"):
            requirement.generate_verification_url()

    def test_generate_verification_url_requires_a_did_number(self):
        requirement = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, self.group.id)],
            "telnyx_requirement_id": "req_action_nodid",
            "name": "Identity check",
            "field_type": "action",
            "action_first_name": "Jane",
            "action_last_name": "Doe",
        })

        with self.assertRaisesRegex(UserError, "without a DID number order"):
            requirement.generate_verification_url()

    def test_action_open_verification_url_returns_an_url_action(self):
        requirement = self.env["voip.requirement"].with_context(skip_validation=True).create({
            "requirement_group_ids": [(4, self.group.id)],
            "telnyx_requirement_id": "req_action_url",
            "name": "Identity check",
            "field_type": "action",
            "action_verification_url": "https://verify.example.com/xyz",
        })

        action = requirement.action_open_verification_url()

        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertEqual(action["url"], "https://verify.example.com/xyz")
