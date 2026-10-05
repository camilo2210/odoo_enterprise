from unittest.mock import call, patch

from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import Form, common, tagged
from odoo.tests.common import new_test_user

from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI
from odoo.addons.voip.tests.common_voip import pbx_router, mock_pbx_layer


@tagged("voip", "post_install", "-at_install")
class TestVoipUserConfig(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        did_numbers = cls.env["voip.did.number"].search([]).with_context(voip_skip_pbx_sync=True)
        did_numbers.write({"state": "released"})
        did_numbers.unlink()

    def setUp(self):
        super().setUp()
        mock_pbx_layer(self)

    def test_voip_user_config_access_rights(self):
        """
        Tests that users cannot read VoIP configuration of other users.
        """
        user_data_1 = {"login": "i_love_voip", "name": "Handsome VoIP User 😎"}
        voip_user = self.env["res.users"].create(user_data_1).sudo(False)
        settings = voip_user.env["res.users.settings"]._find_or_create_for_user(voip_user)
        settings.write({"voip_secret": "Top Secret 🤫"})
        user_data_2 = {"login": "i_hate_voip", "name": "Evil Password Stealer 👺"}
        evil_password_stealer = self.env["res.users"].create(user_data_2).sudo(False)
        self.env.invalidate_all()

        self.assertFalse(voip_user.with_user(evil_password_stealer).voip_secret)

    def test_update_voip_user_config_from_user_form(self):
        """
        Asserts that changes made to the VoIP Config in the res.users forms are reflected in res.users.settings.
        """
        form = Form(self.env["res.users"], view="base.view_users_form")
        form.name = "钟离"
        form.login = "摩拉克斯"
        form.voip_provider_id = self.env.ref("voip.default_voip_provider")
        form.external_device_number = "110"
        user = form.save()
        settings = user.res_users_settings_id
        self.assertEqual(settings.how_to_call_on_mobile, "ask")
        self.assertEqual(settings.external_device_number, "110")

        form = Form(user, view="base.view_users_form")
        form.how_to_call_on_mobile = "voip"
        form.external_device_number = "911"
        form.save()
        self.assertEqual(settings.how_to_call_on_mobile, "voip")
        self.assertEqual(settings.external_device_number, "911")

    def test_provider_change_does_not_sync_pbx_routing(self):
        user = new_test_user(self.env, login="provider_change_user", name="Provider Change")
        user.with_context(voip_skip_pbx_sync=True).write({"voip_pbx_user_id": 999})
        settings = user.res_users_settings_id
        settings.with_context(voip_skip_pbx_sync=True).write({
            "voip_provider_id": self.env.ref("voip.odoo_provider").id,
            "voip_no_answer_timeout": 20,
        })
        provider = self.env["voip.provider"].create({
            "name": "External Provider",
            "mode": "prod",
            "pbx_ip": "sip.example.com",
            "ws_server": "wss://sip.example.com",
        })
        pbx_routes = []

        def capture(route, params, **kw):
            pbx_routes.append(route)
            return pbx_router(route, params)

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=capture):
            user.voip_provider_id = provider
            user.voip_provider_id = False
            settings.write({"voip_provider_id": self.env.ref("voip.odoo_provider").id})
            settings.write({"voip_provider_id": False})

        self.assertNotIn("/api/phone_service/1/pbx/update_user_routing", pbx_routes)

    def test_provider_domain_is_restricted_only_for_non_admins(self):
        admin = new_test_user(self.env, login="domain_admin", groups="base.group_user,voip.group_voip_admin")
        regular = new_test_user(self.env, login="domain_regular", groups="base.group_user")

        for model_name, view_xmlid in [
            ("res.users", "base.view_users_form"),
            ("res.users", "base.view_users_form_simple_modif"),
            ("res.users.settings", "mail.res_users_settings_view_form"),
        ]:
            view_id = self.env.ref(view_xmlid).id
            admin_arch = self.env[model_name].with_user(admin).get_view(view_id)["arch"]
            regular_arch = self.env[model_name].with_user(regular).get_view(view_id)["arch"]
            self.assertNotIn("[('mode', '=', 'prod')]", admin_arch, view_xmlid)
            self.assertIn("[('mode', '=', 'prod')]", regular_arch, view_xmlid)

    def test_only_voip_admins_can_select_demo_providers(self):
        demo_provider = self.env["voip.provider"].create({
            "name": "Restricted Demo Provider",
            "mode": "demo",
        })
        production_provider = self.env["voip.provider"].create({
            "name": "Allowed Production Provider",
            "mode": "prod",
        })
        regular = new_test_user(self.env, login="provider_regular", groups="base.group_user")
        voip_admin = new_test_user(
            self.env,
            login="provider_voip_admin",
            groups="base.group_user,voip.group_voip_admin",
        )

        regular.with_user(regular).voip_provider_id = production_provider
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            regular.with_user(regular).voip_provider_id = demo_provider
        voip_admin.with_user(voip_admin).voip_provider_id = demo_provider

        self.assertEqual(regular.voip_provider_id, production_provider)
        self.assertEqual(voip_admin.voip_provider_id, demo_provider)

    def test_provider_change_refreshes_live_voip_config(self):
        voip_admin = new_test_user(
            self.env,
            login="provider_refresh_admin",
            groups="base.group_user,voip.group_voip_admin",
        )
        odoo_provider = self.env.ref("voip.odoo_provider")
        demo_provider = self.env["voip.provider"].create({
            "name": "Live Demo Provider",
            "mode": "demo",
        })
        voip_admin.with_context(voip_skip_pbx_sync=True).voip_provider_id = odoo_provider

        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            voip_admin.with_user(voip_admin).voip_provider_id = demo_provider

        self.assertEqual(
            [bus_call for bus_call in bus_send.call_args_list if bus_call.args[1] == "voip.config/updated"],
            [call(voip_admin, "voip.config/updated", {})],
        )

        settings = voip_admin.res_users_settings_id.with_user(voip_admin)
        settings.with_context(
            voip_skip_config_bus=True,
            voip_skip_pbx_sync=True,
        ).voip_provider_id = odoo_provider
        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            settings.voip_provider_id = demo_provider

        self.assertEqual(
            [bus_call for bus_call in bus_send.call_args_list if bus_call.args[1] == "voip.config/updated"],
            [call(voip_admin, "voip.config/updated", {})],
        )

    def test_did_changes_refresh_live_voip_config(self):
        user = new_test_user(self.env, login="did_config_refresh")
        did = self.env["voip.did.number"].with_context(install_mode=True).create({
            "did_number": "+3287000050",
            "did_number_type": "local",
            "state": "pending",
        })

        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            did.with_context(voip_skip_pbx_sync=True).destination_ref = user

        bus_send.assert_called_once()
        self.assertEqual(bus_send.call_args.args[0], user)
        self.assertEqual(bus_send.call_args.args[1], "voip.config/updated")

        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            did.with_context(voip_skip_pbx_sync=True).state = "active"

        bus_send.assert_called_once()
        self.assertEqual(bus_send.call_args.args[0], user)
        self.assertEqual(bus_send.call_args.args[1], "voip.config/updated")

    def test_main_number_change_refreshes_all_internal_users(self):
        internal_user = new_test_user(self.env, login="main_config_refresh")
        create_did = self.env["voip.did.number"].with_context(install_mode=True).create
        create_did({
            "did_number": "+3287000051",
            "did_number_type": "local",
            "state": "active",
            "is_default_outgoing_number": True,
        })
        new_main = create_did({
            "did_number": "+3287000052",
            "did_number_type": "local",
            "state": "active",
        })

        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            new_main.with_context(voip_skip_pbx_sync=True).action_set_as_main_number()

        bus_send.assert_called_once()
        self.assertIn(internal_user, bus_send.call_args.args[0])
        self.assertEqual(bus_send.call_args.args[1], "voip.config/updated")

    def test_extension_changes_refresh_affected_users(self):
        first_user = new_test_user(self.env, login="first_extension_refresh")
        second_user = new_test_user(self.env, login="second_extension_refresh")
        extensions = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True)
        self.assertFalse(first_user.routing_extension_id)
        self.assertFalse(first_user.res_users_settings_id.pbx_extension_number)
        self.assertFalse(first_user.pbx_extension_number)

        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            extension = extensions.create({
                "number": "1090",
                "destination_ref": f"res.users,{first_user.id}",
            })

        bus_send.assert_called_once()
        self.assertEqual(bus_send.call_args.args[0], first_user)
        self.assertEqual(first_user.routing_extension_id, extension)
        self.assertEqual(first_user.routing_extension_number, "1090")
        self.assertTrue(first_user.has_routing_extension)
        self.assertEqual(first_user.res_users_settings_id.pbx_extension_number, "1090")
        self.assertEqual(first_user.pbx_extension_number, "1090")
        self.assertFalse(second_user.routing_extension_id)
        self.assertFalse(second_user.res_users_settings_id.pbx_extension_number)
        self.assertFalse(second_user.pbx_extension_number)

        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            extension.destination_ref = second_user

        bus_send.assert_called_once()
        self.assertEqual(bus_send.call_args.args[0], first_user | second_user)
        self.assertFalse(first_user.routing_extension_id)
        self.assertFalse(first_user.routing_extension_number)
        self.assertFalse(first_user.has_routing_extension)
        self.assertFalse(first_user.res_users_settings_id.pbx_extension_number)
        self.assertFalse(first_user.pbx_extension_number)
        self.assertEqual(second_user.routing_extension_id, extension)
        self.assertEqual(second_user.res_users_settings_id.pbx_extension_number, "1090")
        self.assertEqual(second_user.pbx_extension_number, "1090")

        extension.with_context(voip_skip_config_bus=True).number = "1091"
        self.assertEqual(second_user.routing_extension_number, "1091")
        self.assertEqual(second_user.res_users_settings_id.pbx_extension_number, "1091")
        self.assertEqual(second_user.pbx_extension_number, "1091")

        with patch.object(self.env.registry["res.users"], "_bus_send", autospec=True) as bus_send:
            extension.unlink()

        bus_send.assert_called_once()
        self.assertEqual(bus_send.call_args.args[0], second_user)
        self.assertFalse(second_user.routing_extension_id)
        self.assertFalse(second_user.routing_extension_number)
        self.assertFalse(second_user.has_routing_extension)
        self.assertFalse(second_user.res_users_settings_id.pbx_extension_number)
        self.assertFalse(second_user.pbx_extension_number)

    def test_provider_warning_uses_the_user_extension(self):
        provider = self.env["voip.provider"].create({
            "name": "External Extension Warning Provider",
            "mode": "prod",
            "pbx_ip": "sip.example.com",
            "ws_server": "wss://sip.example.com",
        })
        user = new_test_user(self.env, login="extension_warning_user", name="Extension Warning", tz="Europe/Brussels")
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True)._find_or_create_for_user(user)

        form = Form(user, view="base.view_users_form_simple_modif")
        form.voip_provider_id = provider
        self.assertEqual(form.pbx_extension_number, extension.number)
        form.save()
        self.assertFalse(user.has_assigned_did_number)

        view_arch = self.env["res.users"].get_view(
            self.env.ref("base.view_users_form_simple_modif").id,
        )["arch"]
        self.assertIn("Select <em>Odoo Phone Service</em> to make", view_arch)
        self.assertIn('<span invisible="has_assigned_did_number">internal </span>calls', view_arch)
        self.assertIn("uses_odoo_provider or not pbx_extension_number", view_arch)

        self.env["voip.did.number"].with_context(install_mode=True).create({
            "did_number": "+3287000065",
            "did_number_type": "local",
            "state": "active",
            "destination_ref": f"res.users,{user.id}",
        })
        self.env.invalidate_all()
        self.assertTrue(user.has_assigned_did_number)

    def test_phone_number_and_provider_list_layout(self):
        extension_list_arch = self.env["voip.extension"].get_view(
            self.env.ref("voip.voip_extension_view_list").id,
        )["arch"]
        extension_form_arch = self.env["voip.extension"].get_view(
            self.env.ref("voip.voip_extension_view_form").id,
        )["arch"]
        did_form_arch = self.env["voip.did.number"].get_view(
            self.env.ref("voip.voip_did_number_form_view").id,
        )["arch"]
        did_list_arch = self.env["voip.did.number"].get_view(
            self.env.ref("voip.voip_did_number_list_view").id,
        )["arch"]
        main_number_help = (
            "One (and only one) number must be the default outgoing number. It is used as a fallback "
            "outgoing number for users who have an extension and no phone number."
        )
        self.assertIn("Default Outgoing Number", did_form_arch)
        self.assertIn(main_number_help, did_form_arch)
        self.assertIn(main_number_help, did_list_arch)
        did_form_root = etree.fromstring(did_form_arch)
        form_badges = did_form_root.xpath("//div[normalize-space()='Default Outgoing Number']")
        self.assertEqual(len(form_badges), 1)
        self.assertEqual(form_badges[0].get("data-tooltip"), main_number_help)
        did_list_root = etree.fromstring(did_list_arch)
        did_number_field = did_list_root.xpath("//field[@name='did_number']")[0]
        destination_field = did_list_root.xpath("//field[@name='destination_ref']")[0]
        self.assertEqual(did_number_field.get("widget"), "voip_flag_phone")
        self.assertEqual(destination_field.get("widget"), "voip_extension_destination")
        self.assertTrue(did_list_root.xpath("//field[@name='country_id' and @column_invisible='True']"))
        self.assertTrue(did_list_root.xpath("//field[@name='country_flag_url' and @column_invisible='True']"))
        list_badges = did_list_root.xpath("//button[@string='Default Outgoing Number']")
        self.assertEqual(len(list_badges), 1)
        self.assertEqual(list_badges[0].get("type"), "button")
        self.assertEqual(list_badges[0].get("title"), main_number_help)
        self.assertEqual(list_badges[0].get("aria-label"), main_number_help)
        self.assertIn("px-2", list_badges[0].get("class", "").split())
        self.assertIn("py-1", list_badges[0].get("class", "").split())
        self.assertNotIn('editable=', did_list_arch)
        self.assertIn('open_form_view="1"', did_list_arch)
        self.assertEqual(
            dict(self.env["voip.did.number"]._fields["state"].selection)["pending"],
            "Under Review",
        )
        self.assertLess(
            did_list_arch.index('name="destination_ref"'),
            did_list_arch.index('string="Default Outgoing Number"'),
        )
        self.assertLess(
            did_list_arch.index('string="Default Outgoing Number"'),
            did_list_arch.index('name="state"'),
        )
        self.assertNotIn('name="active_did_number"', extension_list_arch)
        self.assertIn('name="active_did_number"', extension_form_arch)

        provider_list_arch = self.env["voip.provider"].get_view(
            self.env.ref("voip.voip_provider_tree_view").id,
        )["arch"]
        provider_form_arch = self.env["voip.provider"].get_view(
            self.env.ref("voip.voip_provider_view_form").id,
        )["arch"]
        self.assertNotIn('name="voicemail_code"', provider_list_arch)
        self.assertIn('name="voicemail_code"', provider_form_arch)

    def test_explicit_odoo_routing_assignments_select_odoo_provider(self):
        external_provider = self.env["voip.provider"].create({
            "name": "External Before Routing",
            "mode": "prod",
        })
        odoo_provider = self.env.ref("voip.odoo_provider")

        direct_user = new_test_user(self.env, login="direct_routing_user")
        direct_user.voip_provider_id = external_provider
        self.env["voip.extension"].create({
            "destination_ref": f"res.users,{direct_user.id}",
        })
        self.assertEqual(direct_user.voip_provider_id, odoo_provider)

        did_user = new_test_user(self.env, login="did_routing_user")
        did_user.voip_provider_id = external_provider
        self.env["voip.did.number"].create({
            "did_number": "+3287000066",
            "did_number_type": "local",
            "state": "active",
            "destination_ref": f"res.users,{did_user.id}",
        })
        self.assertEqual(did_user.voip_provider_id, odoo_provider)

        group_user = new_test_user(self.env, login="group_routing_user")
        group_user.voip_provider_id = external_provider
        call_group = self.env["voip.call.group"].create({
            "name": "Routing Group",
            "user_ids": [Command.link(group_user.id)],
        })
        self.assertEqual(group_user.voip_provider_id, odoo_provider)

        queue_user = new_test_user(self.env, login="queue_routing_user")
        self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        )._find_or_create_for_user(queue_user)
        queue_user.voip_provider_id = external_provider
        queue = self.env["voip.queue"].create({
            "name": "Routing Queue",
            "allowed_user_ids": [Command.link(queue_user.id)],
        })
        self.assertEqual(queue_user.voip_provider_id, odoo_provider)

        group_user.voip_provider_id = external_provider
        queue_user.voip_provider_id = external_provider
        call_group.name = "Renamed Routing Group"
        queue.name = "Renamed Routing Queue"

        self.assertEqual(group_user.voip_provider_id, external_provider)
        self.assertEqual(queue_user.voip_provider_id, external_provider)

    def test_switching_back_to_odoo_provider_resyncs_user_extension(self):
        external_provider = self.env["voip.provider"].create({
            "name": "External Before Odoo",
            "mode": "prod",
            "pbx_ip": "sip.example.com",
            "ws_server": "wss://sip.example.com",
        })
        user = new_test_user(self.env, login="switch_back_odoo_user", name="Switch Back")
        settings = user.res_users_settings_id
        settings.with_context(voip_skip_pbx_sync=True).voip_provider_id = external_provider
        extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True)._find_or_create_for_user(user)
        user.with_context(voip_skip_pbx_sync=True).write({
            "voip_pbx_user_id": 999,
            "voip_pbx_user_uuid": "existing-user-uuid",
            "voip_pbx_line_id": 998,
        })
        extension.with_context(voip_skip_pbx_sync=True).pbx_extension_id = 997
        pbx_routes = []

        def capture(route, params, **kw):
            pbx_routes.append(route)
            return pbx_router(route, params)

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=capture):
            settings.write({"voip_provider_id": self.env.ref("voip.odoo_provider").id})

        self.assertIn("/api/phone_service/1/pbx/sync_user_extension", pbx_routes)
        self.assertEqual(user.voip_pbx_user_id, 999)
        self.assertEqual(extension.pbx_extension_id, 997)

    def test_automatic_odoo_provider_selection_resyncs_existing_extension(self):
        external_provider = self.env["voip.provider"].create({
            "name": "External Before Automatic Odoo Selection",
            "mode": "prod",
        })
        user = new_test_user(self.env, login="automatic_odoo_user")
        settings = user.res_users_settings_id
        settings.with_context(voip_skip_pbx_sync=True).write({
            "voip_provider_id": external_provider.id,
            "voip_username": "external-username",
            "voip_secret": "external-secret",
        })
        extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        )._find_or_create_for_user(user)
        user.with_context(voip_skip_pbx_sync=True).write({
            "voip_pbx_user_id": 999,
            "voip_pbx_user_uuid": "existing-user-uuid",
            "voip_pbx_line_id": 998,
        })
        extension.with_context(voip_skip_pbx_sync=True).pbx_extension_id = 997
        pbx_routes = []

        def capture(route, params, **kw):
            pbx_routes.append(route)
            return pbx_router(route, params)

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=capture):
            user._select_odoo_voip_provider()

        self.assertIn("/api/phone_service/1/pbx/sync_user_extension", pbx_routes)
        self.assertEqual(settings.voip_provider_id, self.env.ref("voip.odoo_provider"))

        pbx_routes.clear()
        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=capture):
            user._select_odoo_voip_provider()

        self.assertFalse(pbx_routes)

    def test_config_without_provider_falls_back_to_demo(self):
        user = new_test_user(self.env, login="no_provider_config_user", name="No Provider")

        config = user._get_voip_config()

        self.assertFalse(user.voip_provider_id)
        self.assertEqual(config["mode"], "demo")
        self.assertEqual(config["pbxAddress"], "localhost")
        self.assertEqual(config["webSocketUrl"], "ws://localhost")

    def test_config_exposes_pending_assigned_odoo_number(self):
        user = self.env["res.users"].create({
            "login": "pending_number_user",
            "name": "Pending Number User",
            "voip_provider_id": self.env["voip.provider"].get_or_create_odoo_provider().id,
        })
        extension = self.env["voip.extension"].with_context(
            voip_skip_pbx_sync=True,
        )._find_or_create_for_user(user)
        self.env["voip.did.number"].create({
            "did_number": "+3287000099",
            "did_number_type": "local",
            "state": "ordering",
            "destination_ref": f"res.users,{user.id}",
        })

        config = user._get_voip_config()

        self.assertEqual(config["didNumber"], "+3287000099")
        self.assertEqual(config["didNumberFormatted"], "+32 87 00 00 99")
        self.assertEqual(config["didNumberState"], "ordering")
        self.assertTrue(config["isInternalCallingProvisioned"])
        self.assertEqual(config["pbxExtensionNumber"], extension.number)
        self.assertTrue(user.res_users_settings_id.voip_username)
        self.assertTrue(user.res_users_settings_id.voip_secret)

    def test_config_uses_personal_active_did_then_main_number(self):
        user = self.env["res.users"].create({
            "login": "caller_id_config_user",
            "name": "Caller ID Config User",
            "voip_provider_id": self.env.ref("voip.odoo_provider").id,
        })
        main = self.env["voip.did.number"].with_context(
            install_mode=True,
            voip_skip_pbx_sync=True,
        ).create({
            "did_number": "+3287000080",
            "did_number_type": "local",
            "state": "active",
            "is_default_outgoing_number": True,
        })
        personal = self.env["voip.did.number"].with_context(
            install_mode=True,
            voip_skip_pbx_sync=True,
        ).create({
            "did_number": "+3287000081",
            "did_number_type": "local",
            "state": "pending",
            "destination_ref": f"res.users,{user.id}",
        })

        config = user._get_voip_config()

        self.assertEqual(config["outboundCallerId"], main.did_number)
        self.assertEqual(config["outboundCallerIdFormatted"], "+32 87 00 00 80")

        personal.with_context(voip_skip_pbx_sync=True).state = "active"
        config = user._get_voip_config()

        self.assertEqual(config["didNumber"], personal.did_number)
        self.assertEqual(config["mainNumber"], main.did_number)
        self.assertEqual(config["mainNumberFormatted"], main._phone_get_formatted(main.did_number))
        self.assertEqual(config["outboundCallerId"], personal.did_number)
        self.assertEqual(config["outboundCallerIdFormatted"], "+32 87 00 00 81")

    def test_config_separates_personal_and_shared_active_dids(self):
        provider = self.env.ref("voip.odoo_provider")
        user = new_test_user(
            self.env,
            login="multiple_did_user",
            voip_provider_id=provider.id,
        )
        other_user = new_test_user(self.env, login="other_did_user")
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Shared DID destination",
        })
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Shared DID queue",
        })
        country = self.env.ref("base.be")
        common_values = {
            "country_id": country.id,
            "did_number_type": "local",
            "state": "active",
        }
        personal_dids = self.env["voip.did.number"].with_context(
            install_mode=True,
            voip_skip_pbx_sync=True,
        ).create([
            {
                **common_values,
                "did_number": "+32470000001",
                "destination_ref": f"res.users,{user.id}",
            },
            {
                **common_values,
                "did_number": "+32470000002",
                "destination_ref": f"res.users,{user.id}",
            },
        ])
        shared_did = self.env["voip.did.number"].with_context(
            install_mode=True,
            voip_skip_pbx_sync=True,
        ).create({
            **common_values,
            "did_number": "+32470000003",
            "destination_ref": f"voip.call.group,{call_group.id}",
        })
        shared_queue_did = self.env["voip.did.number"].with_context(
            install_mode=True,
            voip_skip_pbx_sync=True,
        ).create({
            **common_values,
            "did_number": "+32470000006",
            "destination_ref": f"voip.queue,{queue.id}",
        })
        self.env["voip.did.number"].with_context(
            install_mode=True,
            voip_skip_pbx_sync=True,
        ).create([
            {
                **common_values,
                "did_number": "+32470000004",
                "destination_ref": f"res.users,{other_user.id}",
            },
            {
                **common_values,
                "did_number": "+32470000005",
            },
        ])

        config = user._get_voip_config()

        self.assertEqual(
            [number["number"] for number in config["outboundNumbers"]],
            [did.did_number for did in reversed(personal_dids)],
        )
        self.assertTrue(all(
            number["countryId"] == country.id
            for number in config["outboundNumbers"]
        ))
        self.assertEqual(config["sharedOutboundNumbers"], [
            {
                "countryId": country.id,
                "countryName": country.name,
                "destinationType": "queue",
                "flagUrl": country.image_url,
                "formatted": shared_queue_did._phone_get_formatted(shared_queue_did.did_number),
                "number": shared_queue_did.did_number,
            },
            {
                "countryId": country.id,
                "countryName": country.name,
                "destinationType": "call_group",
                "flagUrl": country.image_url,
                "formatted": shared_did._phone_get_formatted(shared_did.did_number),
                "number": shared_did.did_number,
            },
        ])

    def test_config_resolves_extension_destination_for_personal_and_shared_dids(self):
        """A DID assigned to an extension is treated as if it were assigned
        directly to whatever that extension routes to."""
        provider = self.env.ref("voip.odoo_provider")
        user = new_test_user(self.env, login="extension_routed_did_user", voip_provider_id=provider.id)
        other_user = new_test_user(self.env, login="other_extension_routed_user")
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Extension-routed queue",
        })

        own_extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "destination_ref": f"res.users,{user.id}",
        })
        other_extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "destination_ref": f"res.users,{other_user.id}",
        })
        queue_extension = self.env["voip.extension"].with_context(voip_skip_pbx_sync=True).create({
            "destination_ref": f"voip.queue,{queue.id}",
        })

        common_values = {"did_number_type": "local", "state": "active"}
        extension_personal_did, extension_other_user_did, extension_queue_did = self.env[
            "voip.did.number"
        ].with_context(install_mode=True, voip_skip_pbx_sync=True).create([
            {
                **common_values,
                "did_number": "+32470000010",
                "destination_ref": f"voip.extension,{own_extension.id}",
            },
            {
                **common_values,
                "did_number": "+32470000011",
                "destination_ref": f"voip.extension,{other_extension.id}",
            },
            {
                **common_values,
                "did_number": "+32470000012",
                "destination_ref": f"voip.extension,{queue_extension.id}",
            },
        ])

        config = user._get_voip_config()

        self.assertEqual(
            [number["number"] for number in config["outboundNumbers"]],
            [extension_personal_did.did_number],
        )
        self.assertEqual(
            [
                (number["number"], number["destinationType"])
                for number in config["sharedOutboundNumbers"]
            ],
            [(extension_queue_did.did_number, "queue")],
        )
        shown_numbers = [
            number["number"]
            for number in config["outboundNumbers"] + config["sharedOutboundNumbers"]
        ]
        self.assertNotIn(extension_other_user_did.did_number, shown_numbers)

    def test_config_exposes_did_state_on_non_odoo_provider(self):
        """The DID lifecycle is the user's own, so it is surfaced even when the
        user's extension has been moved to a non-Odoo provider."""
        user = self.env["res.users"].create({
            "login": "non_odoo_did_user",
            "name": "Non-Odoo DID User",
        })
        self.env["voip.did.number"].create({
            "did_number": "+3287000088",
            "did_number_type": "local",
            "state": "pending",
            "destination_ref": f"res.users,{user.id}",
        })
        user.voip_provider_id = self.env["voip.provider"].create({"name": "Axivox", "mode": "prod"})

        config = user._get_voip_config()

        self.assertFalse(config["usesOdooProvider"])
        self.assertEqual(config["didNumber"], "+3287000088")
        self.assertEqual(config["didNumberState"], "pending")

    def test_suspended_number_keeps_user_provisioned(self):
        pbx_provider = self.env.ref("voip.odoo_provider")
        user = self.env["res.users"].create({
            "login": "suspended_number_user",
            "name": "Suspended Number User",
        })
        did = self.env["voip.did.number"].create({
            "did_number": "+3287000077",
            "did_number_type": "local",
            "state": "active",
            "destination_ref": f"res.users,{user.id}",
        })
        settings = user.res_users_settings_id
        settings.write({"voip_username": "suspended_number_user", "voip_secret": "Top Secret 🤫"})

        did.write({"state": "suspended"})

        self.assertEqual(settings.voip_provider_id, pbx_provider)
        self.assertEqual(settings.voip_secret, "Top Secret 🤫")
        config = user._get_voip_config()
        self.assertEqual(config["didNumber"], "+3287000077")
        self.assertEqual(config["didNumberState"], "suspended")

        did.write({"state": "active"})

        self.assertEqual(settings.voip_secret, "Top Secret 🤫")
        config = user._get_voip_config()
        self.assertEqual(config["didNumberState"], "active")

        did.write({"state": "released"})

        # Releasing the number keeps the reusable PBX user credentials.
        self.assertEqual(settings.voip_provider_id, pbx_provider)
        self.assertEqual(settings.voip_secret, "Top Secret 🤫")
        config = user._get_voip_config()
        self.assertFalse(config["didNumber"])
        self.assertFalse(config["didNumberFormatted"])
        self.assertFalse(config["didNumberState"])
