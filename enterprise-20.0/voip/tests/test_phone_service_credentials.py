from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.addons.voip.models.phone_service_api import (
    CLIENT_SECRET_PARAM,
    CLIENT_UUID_PARAM,
    WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM,
    PhoneServiceAPI,
)
from odoo.addons.voip.tests.common_voip import forbid_phone_service_http
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("-at_install", "post_install")
class TestPhoneServiceCredentials(TransactionCase):
    def setUp(self):
        super().setUp()
        forbid_phone_service_http(self)
        self.icp = self.env["ir.config_parameter"].sudo()
        self.icp.search([("key", "in", [CLIENT_UUID_PARAM, CLIENT_SECRET_PARAM])]).unlink()

    def test_generates_and_persists_credentials(self):
        client_uuid, client_secret = self.icp._voip_get_client_credentials()
        self.assertTrue(client_uuid)
        self.assertTrue(client_secret)
        self.assertNotEqual(client_uuid, client_secret)
        self.assertEqual(self.icp.get_str(CLIENT_UUID_PARAM), client_uuid)
        self.assertEqual(self.icp.get_str(CLIENT_SECRET_PARAM), client_secret)

    def test_is_idempotent(self):
        first = self.icp._voip_get_client_credentials()
        second = self.icp._voip_get_client_credentials()
        self.assertEqual(first, second)

    def test_webhook_url_sync_cron_clears_pending_flag(self):
        self.icp.set_bool(WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM, True)

        with (
            patch("odoo.addons.voip.models.ir_config_parameter.module.current_test", False),
            patch.object(
                PhoneServiceAPI,
                "_call_phone_service",
                return_value={"success": True},
            ) as call_phone_service,
        ):
            self.icp._cron_sync_webhook_event_url()

        call_phone_service.assert_called_once_with(
            "/api/phone_service/1/update_client",
            {"updates": {"webhook_event_url": f"{self.icp.get_base_url()}/voip/api/phone_service/event"}},
        )
        self.assertFalse(self.icp.get_bool(WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM))

    @mute_logger("odoo.addons.voip.models.ir_config_parameter")
    def test_failed_webhook_url_sync_schedules_cron(self):
        cron = self.env.ref("voip.ir_cron_voip_sync_webhook_event_url")
        before = fields.Datetime.now()

        with (
            patch("odoo.addons.voip.models.ir_config_parameter.module.current_test", False),
            patch.object(
                PhoneServiceAPI,
                "sync_webhook_event_url",
                side_effect=UserError("sync failed"),
            ),
            patch("odoo.addons.base.models.ir_cron.IrCron._trigger") as trigger,
        ):
            self.icp._voip_try_sync_webhook_event_url()

        self.assertTrue(cron.active)
        scheduled_at = trigger.call_args.kwargs["at"]
        self.assertGreaterEqual(scheduled_at, before + timedelta(hours=1))
        self.assertLessEqual(scheduled_at, fields.Datetime.now() + timedelta(hours=1))
        self.assertTrue(self.icp.get_bool(WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM))
