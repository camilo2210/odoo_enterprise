from odoo import Command
from odoo.tests import common, tagged
from odoo.tests.common import new_test_user


@tagged("voip", "call_artifacts")
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestVoipAccessRights(common.TransactionCase):
    def _create_user_in_company(self, company, name, login, groups="base.group_user"):
        return new_test_user(
            self.env,
            login=login,
            groups=groups,
            company_id=company.id,
            name=name,
        )

    def test_officer_crud_access_to_company_calls(self):
        """
        Officers have full CRUD access to calls where call.user_id.company_id is their company.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        officer_user = self._create_user_in_company(company_a, "Officer", "officer", groups="voip.group_voip_officer")
        call_owner = self._create_user_in_company(company_a, "Taha Hussein", "tahaaaaaaaaaaaa")
        company_call = (
            self.env["voip.call"]
            .with_user(officer_user)
            .create({"user_id": call_owner.id, "phone_number": "123456789"})
        )

        self.assertTrue(company_call.with_user(officer_user).has_access("read"))
        self.assertTrue(company_call.with_user(officer_user).has_access("write"))
        self.assertTrue(company_call.with_user(officer_user).has_access("unlink"))
        self.assertTrue(company_call.with_user(officer_user).has_access("create"))

    def test_officer_restricted_access_to_other_company_calls(self):
        """
        Officers cannot perform CRUD on calls where user_id.company_id is not their company.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})
        officer_user = self._create_user_in_company(company_a, "Officer", "officer", groups="voip.group_voip_officer")
        other_company_user = self._create_user_in_company(company_b, "Tamer Elgyar", "fssssssssssss")
        other_company_call = self.env["voip.call"].create({"user_id": other_company_user.id, "phone_number": "987654321"})

        self.assertFalse(other_company_call.with_user(officer_user).has_access("read"))
        self.assertFalse(other_company_call.with_user(officer_user).has_access("write"))
        self.assertFalse(other_company_call.with_user(officer_user).has_access("unlink"))
        self.assertFalse(other_company_call.with_user(officer_user).has_access("create"))

    def test_admin_full_access_to_own_company_calls(self):
        """
        Admins have full CRUD access to calls where user_id.company_id is their company.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        admin_user = self._create_user_in_company(company_a, "Admin", "voip_admin", groups="voip.group_voip_admin")
        call_owner = self._create_user_in_company(company_a, "Jr Elaraby", "omar_gamal")
        company_call = (
            self.env["voip.call"]
            .with_user(admin_user)
            .create({"user_id": call_owner.id, "phone_number": "123456789"})
        )

        self.assertTrue(company_call.with_user(admin_user).has_access("create"))
        self.assertTrue(company_call.with_user(admin_user).has_access("read"))
        self.assertTrue(company_call.with_user(admin_user).has_access("write"))
        self.assertTrue(company_call.with_user(admin_user).has_access("unlink"))

    def test_admin_no_access_to_other_company_calls(self):
        """
        Admins do not have any access to calls where call.user_id.company_id is not their company.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})
        admin_user = self._create_user_in_company(company_a, "Admin", "voip_admin", groups="voip.group_voip_admin")
        other_company_user = self._create_user_in_company(company_b, "Nagiub Sawiris", "nagiub_mahfouz")
        other_company_call = self.env["voip.call"].create({"user_id": other_company_user.id, "phone_number": "987654321"})

        self.assertFalse(other_company_call.with_user(admin_user).has_access("create"))
        self.assertFalse(other_company_call.with_user(admin_user).has_access("read"))
        self.assertFalse(other_company_call.with_user(admin_user).has_access("write"))
        self.assertFalse(other_company_call.with_user(admin_user).has_access("unlink"))

    def test_regular_user_crud_on_their_own_calls(self):
        """
        Regular users can only perform read on their own call records.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        regular_user = self._create_user_in_company(company_a, "Regular", "regular")
        call_made_by_self = self.env["voip.call"].create({"user_id": regular_user.id, "phone_number": "987654321"})

        self.assertFalse(call_made_by_self.with_user(regular_user).has_access("create"))
        self.assertTrue(call_made_by_self.with_user(regular_user).has_access("read"))
        self.assertFalse(call_made_by_self.with_user(regular_user).has_access("write"))
        self.assertFalse(call_made_by_self.with_user(regular_user).has_access("unlink"))

    def test_regular_user_no_crud_on_others_calls(self):
        """
        Regular users cannot perform CRUD on other users' call records.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        regular_user = self._create_user_in_company(company_a, "Regular", "regular")
        other_user = self._create_user_in_company(company_a, "Wario", "waaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        call_made_by_other = self.env["voip.call"].create({"user_id": other_user.id, "phone_number": "+246 532 4846"})

        self.assertFalse(call_made_by_other.with_user(regular_user).has_access("create"))
        self.assertFalse(call_made_by_other.with_user(regular_user).has_access("read"))
        self.assertFalse(call_made_by_other.with_user(regular_user).has_access("write"))
        self.assertFalse(call_made_by_other.with_user(regular_user).has_access("unlink"))

    def test_regular_user_access_to_providers(self):
        """
        Regular users can only read provider records of their companies, not create, write, or unlink.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})
        regular_user = self._create_user_in_company(company_a, "Regular", "regular")
        provider_a = self.env["voip.provider"].create({"name": "Provider A", "company_id": company_a.id})
        provider_b = self.env["voip.provider"].create({"name": "Provider B", "company_id": company_b.id})

        self.assertFalse(provider_a.with_user(regular_user).has_access("create"))
        self.assertTrue(provider_a.with_user(regular_user).has_access("read"))
        self.assertFalse(provider_a.with_user(regular_user).has_access("write"))
        self.assertFalse(provider_a.with_user(regular_user).has_access("unlink"))
        self.assertFalse(provider_b.with_user(regular_user).has_access("create"))
        self.assertFalse(provider_b.with_user(regular_user).has_access("read"))
        self.assertFalse(provider_b.with_user(regular_user).has_access("write"))
        self.assertFalse(provider_b.with_user(regular_user).has_access("unlink"))

    def test_admin_access_to_providers(self):
        """
        Admins have full CRUD access to providers of their companies, but no access to other companies' providers.
        """
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})
        admin_user = self._create_user_in_company(company_a, "Admin", "voip_admin", groups="voip.group_voip_admin")
        provider_a = self.env["voip.provider"].create({"name": "Provider A", "company_id": company_a.id})
        provider_b = self.env["voip.provider"].create({"name": "Provider B", "company_id": company_b.id})

        self.assertTrue(provider_a.with_user(admin_user).has_access("create"))
        self.assertTrue(provider_a.with_user(admin_user).has_access("read"))
        self.assertTrue(provider_a.with_user(admin_user).has_access("write"))
        self.assertTrue(provider_a.with_user(admin_user).has_access("unlink"))
        self.assertFalse(provider_b.with_user(admin_user).has_access("create"))
        self.assertFalse(provider_b.with_user(admin_user).has_access("read"))
        self.assertFalse(provider_b.with_user(admin_user).has_access("write"))
        self.assertFalse(provider_b.with_user(admin_user).has_access("unlink"))

    def test_admin_access_follows_allowed_companies(self):
        company_a = self.env["res.company"].create({"name": "Allowed Company A"})
        company_b = self.env["res.company"].create({"name": "Allowed Company B"})
        admin_user = self._create_user_in_company(
            company_a,
            "Multi-company Admin",
            "multi_company_voip_admin",
            groups="voip.group_voip_admin",
        )
        admin_user.company_ids = [Command.link(company_b.id)]
        call_owner = self._create_user_in_company(company_b, "Company B User", "company_b_user")
        provider = self.env["voip.provider"].create({
            "name": "Company B Provider",
            "company_id": company_b.id,
        })
        call = self.env["voip.call"].create({
            "user_id": call_owner.id,
            "phone_number": "123456789",
        })

        self.assertTrue(provider.with_user(admin_user).has_access("read"))
        self.assertTrue(call.with_user(admin_user).has_access("read"))

    def test_pbx_configuration_models_are_admin_only(self):
        regular_user = new_test_user(self.env, login="pbx_config_regular")
        officer = new_test_user(
            self.env,
            login="pbx_config_officer",
            groups="voip.group_voip_officer",
        )
        admin = new_test_user(
            self.env,
            login="pbx_config_admin",
            groups="voip.group_voip_admin",
        )
        model_names = (
            "voip.sound",
            "voip.call.flow",
            "voip.call.group",
            "voip.did.number.request",
            "voip.did.number",
            "voip.extension",
            "voip.ivr",
            "voip.music.on.hold",
            "voip.music.on.hold.track",
            "voip.queue",
            "voip.time.condition",
            "voip.voicemail",
        )

        for model_name in model_names:
            with self.subTest(model=model_name):
                model = self.env[model_name]
                for operation in ("create", "read", "write", "unlink"):
                    self.assertFalse(model.with_user(regular_user).has_access(operation))
                    self.assertFalse(model.with_user(officer).has_access(operation))
                    self.assertTrue(model.with_user(admin).has_access(operation))

    def test_regular_user_read_access_to_own_mail_call_artifacts(self):
        """Verify that regular users can read artifacts of their own calls but not others'"""
        company_a = self.env["res.company"].create({"name": "Company A"})
        regular_user = self._create_user_in_company(company_a, "Regular", "regular")
        other_user = self._create_user_in_company(company_a, "Other", "other")

        own_call = self.env["voip.call"].create({"user_id": regular_user.id, "phone_number": "123"})
        other_call = self.env["voip.call"].create({"user_id": other_user.id, "phone_number": "456"})

        own_artifact = self.env["mail.call.artifact"].create({
            "voip_call_id": own_call.id,
            "start_ms": 0,
            "end_ms": 1000,
        })
        other_artifact = self.env["mail.call.artifact"].create({
            "voip_call_id": other_call.id,
            "start_ms": 0,
            "end_ms": 1000,
        })

        # Own artifact: read access
        self.assertTrue(own_artifact.with_user(regular_user).has_access("read"))
        # No other CRUD access
        self.assertFalse(own_artifact.with_user(regular_user).has_access("create"))
        self.assertFalse(own_artifact.with_user(regular_user).has_access("write"))
        self.assertFalse(own_artifact.with_user(regular_user).has_access("unlink"))

        # Other's artifact: no read access
        self.assertFalse(other_artifact.with_user(regular_user).has_access("read"))

    def test_officer_read_access_to_company_artifacts(self):
        """Verify that officers can read artifacts of calls where the call's user is in their company"""
        company_a = self.env["res.company"].create({"name": "Company A"})
        company_b = self.env["res.company"].create({"name": "Company B"})

        officer = self._create_user_in_company(company_a, "Officer", "officer", groups="voip.group_voip_officer")
        user_a = self._create_user_in_company(company_a, "User A", "user_a")
        user_b = self._create_user_in_company(company_b, "User B", "user_b")

        call_a = self.env["voip.call"].create({"user_id": user_a.id, "phone_number": "123"})
        call_b = self.env["voip.call"].create({"user_id": user_b.id, "phone_number": "456"})

        artifact_a = self.env["mail.call.artifact"].create({
            "voip_call_id": call_a.id,
            "start_ms": 0,
            "end_ms": 1000,
        })
        artifact_b = self.env["mail.call.artifact"].create({
            "voip_call_id": call_b.id,
            "start_ms": 0,
            "end_ms": 1000,
        })

        # Officer can read artifacts from their own company
        self.assertTrue(artifact_a.with_user(officer).has_access("read"))

        # Officer CANNOT read artifacts from another company
        self.assertFalse(artifact_b.with_user(officer).has_access("read"))
