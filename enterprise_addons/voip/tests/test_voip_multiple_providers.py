from odoo.exceptions import UserError
from odoo.tests import common, tagged

from odoo.addons.mail.tools.discuss import Store
from odoo.addons.voip.models.voip_provider import ODOO_PROVIDER_VALS


@tagged("voip", "post_install", "-at_install")
class TestVoipMultipleProviders(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_str("cloud_storage_provider", "test_cloud_storage_provider")
        cls.provider_1 = cls.env["voip.provider"].create({
            "name": "demo",
            "mode": "demo",
        })
        cls.provider_2 = cls.env["voip.provider"].create({
            "name": "prod",
            "mode": "prod",
            "pbx_ip": "localhost",
            "recording_policy": "always",
            "ws_server": "ws://localhost",
            "voicemail_code": "*98",
        })

    def test_voip_init_messaging(self):
        user = self.env.user
        user.voip_provider_id = self.provider_1
        data = Store().add_global_values(user._store_init_global_fields).as_dict()
        self.assertEqual(data["Store"]["voipConfig"]["mode"], self.provider_1.mode)
        self.assertEqual(data["Store"]["voipConfig"]["pbxAddress"], self.provider_1.pbx_ip)
        self.assertEqual(data["Store"]["voipConfig"]["recordingPolicy"], self.provider_1.recording_policy)
        self.assertEqual(data["Store"]["voipConfig"]["webSocketUrl"], self.provider_1.ws_server)
        self.assertEqual(data["Store"]["voipConfig"]["voicemailCode"], self.provider_1.voicemail_code or None)

        user.voip_provider_id = self.provider_2
        data = Store().add_global_values(user._store_init_global_fields).as_dict()
        self.assertEqual(data["Store"]["voipConfig"]["mode"], self.provider_2.mode)
        self.assertEqual(data["Store"]["voipConfig"]["pbxAddress"], self.provider_2.pbx_ip)
        self.assertEqual(data["Store"]["voipConfig"]["recordingPolicy"], self.provider_2.recording_policy)
        self.assertEqual(data["Store"]["voipConfig"]["webSocketUrl"], self.provider_2.ws_server)
        self.assertEqual(data["Store"]["voipConfig"]["voicemailCode"], self.provider_2.voicemail_code or None)

    def test_odoo_provider_cannot_be_deleted(self):
        odoo_provider = self.env.ref("voip.odoo_provider")
        self.env.user.voip_provider_id = odoo_provider
        settings = self.env.user.res_users_settings_id
        with self.assertRaisesRegex(UserError, "You cannot delete Odoo Phone Service"), self.env.cr.savepoint():
            odoo_provider.unlink()

        self.assertEqual(settings.voip_provider_id, odoo_provider)
        custom_provider = self.env["voip.provider"].create({"name": "Deletable Provider"})
        custom_provider.unlink()
        self.assertFalse(custom_provider.exists())

    def test_get_or_create_odoo_provider_is_idempotent(self):
        providers = self.env["voip.provider"]
        provider = providers.get_or_create_odoo_provider()

        self.assertEqual(providers.get_or_create_odoo_provider(), provider)

        self.env["ir.model.data"].search([
            ("module", "=", "voip"),
            ("name", "=", "odoo_provider"),
        ]).unlink()
        provider.unlink()
        recreated_provider = providers.get_or_create_odoo_provider()

        self.assertEqual(providers.get_or_create_odoo_provider(), recreated_provider)
        self.assertEqual(self.env.ref("voip.odoo_provider"), recreated_provider)
        self.assertEqual(
            recreated_provider.read(ODOO_PROVIDER_VALS)[0],
            {"id": recreated_provider.id, **ODOO_PROVIDER_VALS},
        )
