import inspect
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.models import get_public_method
from odoo.tests import common, tagged
from odoo.tests.common import new_test_user

from odoo.addons.voip.models.pbx_service import PBXService
from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI
from odoo.addons.voip.tests.common_voip import pbx_router, forbid_phone_service_http, mock_pbx_layer


@tagged("voip", "post_install", "-at_install")
class TestPhoneServiceAccess(common.TransactionCase):
    def setUp(self):
        super().setUp()
        forbid_phone_service_http(self)
        mock_pbx_layer(self)

    def test_regular_user_cannot_reach_the_phone_service(self):
        user = new_test_user(self.env, login="phone_service_regular", groups="base.group_user")
        with self.assertRaises(AccessError):
            PhoneServiceAPI(self.env(user=user))

    def test_voip_admin_reaches_the_phone_service(self):
        user = new_test_user(
            self.env,
            login="phone_service_admin",
            groups="base.group_user,voip.group_voip_admin",
        )
        self.assertTrue(PhoneServiceAPI(self.env(user=user)))

    def test_sudo_reaches_the_phone_service(self):
        user = new_test_user(self.env, login="phone_service_sudo", groups="base.group_user")
        self.assertTrue(PhoneServiceAPI(self.env(user=user, su=True)))

    def test_pbx_service_exposes_nothing_over_rpc(self):
        service = self.env["voip.pbx.service"]
        for name, attribute in vars(PBXService).items():
            if not inspect.isroutine(attribute):
                continue
            with self.subTest(method=name), self.assertRaises(AccessError):
                get_public_method(service, name)

    def test_models_expose_no_phone_service_factory(self):
        self.assertFalse(hasattr(self.env["voip.pbx.service"], "_api"))
        self.assertFalse(hasattr(self.env["voip.did.number"], "_phone_service_api"))

    def test_user_joins_and_leaves_own_queue(self):
        user = new_test_user(self.env, login="phone_service_agent", groups="base.group_user")
        queue = self.env["voip.queue"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "pbx_queue_id": 70,
        })
        agent = self.env["voip.queue.agent"].create({
            "queue_id": queue.id,
            "user_id": user.id,
            "pbx_agent_id": 80,
            "agent_number": "100",
        })
        agent_model = self.env["voip.queue.agent"].with_user(user)
        routes = []

        def capture(route, params, **kw):
            routes.append(route)
            return pbx_router(route, params)

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=capture):
            agent_model.set_current_user_queue_membership(agent.id, True)
            agent_model.set_current_user_queue_membership(agent.id, False)

        self.assertEqual(
            [route for route in routes if "agent" in route.rsplit("/", 1)[-1]],
            [
                "/api/phone_service/1/pbx/login_agent_to_queue",
                "/api/phone_service/1/pbx/get_agents",
                "/api/phone_service/1/pbx/logoff_agent_from_queue",
                "/api/phone_service/1/pbx/get_agents",
            ],
        )

    def test_user_syncs_own_call_forwarding(self):
        user = new_test_user(self.env, login="phone_service_forwarding", groups="base.group_user")
        user.with_context(voip_skip_pbx_sync=True).write({"voip_pbx_user_id": 999})
        routes = []

        def capture(route, params, **kw):
            routes.append(route)
            return pbx_router(route, params)

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=capture):
            user.res_users_settings_id.with_user(user).write(
                {
                    "voip_busy_destination_type": "forward",
                    "voip_busy_destination_kind": "external",
                    "voip_busy_outcall_number": "+32471234567",
                    "voip_disconnected_destination_type": "forward",
                    "voip_disconnected_destination_kind": "external",
                    "voip_disconnected_outcall_number": "+32471234568",
                },
            )

        self.assertEqual(routes, ["/api/phone_service/1/pbx/update_user_routing"])

    def test_user_cannot_set_mismatched_call_forwarding_destination(self):
        user = new_test_user(self.env, login="mismatched_forwarding", groups="base.group_user")
        call_group = self.env["voip.call.group"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Sales",
        })

        with self.assertRaisesRegex(
            ValidationError,
            "The selected destination does not match the destination kind.",
        ):
            user.with_user(user).write({
                "voip_busy_destination_type": "forward",
                "voip_busy_destination_kind": "voip.queue",
                "voip_busy_destination_ref": f"voip.call.group,{call_group.id}",
            })
