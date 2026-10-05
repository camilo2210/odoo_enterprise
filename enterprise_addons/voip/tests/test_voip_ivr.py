from unittest.mock import patch

from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.voip.models.voip_ivr import VoipIvr
from odoo.addons.voip.tests.common_voip import tts_sound_values


@tagged("voip", "post_install", "-at_install")
class TestVoipIvr(TransactionCase):
    def test_create_from_call_flow_defers_pbx_sync(self):
        with patch.object(VoipIvr, "_sync_pbx") as sync_pbx:
            self.env["voip.ivr"].with_context(
                voip_call_flow_node_configuration=True,
            ).create({
                "name": "Main Menu",
                **tts_sound_values("Choose one or two."),
            })

        sync_pbx.assert_not_called()

    def test_write_from_call_flow_defers_pbx_sync(self):
        menu = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Main Menu",
            **tts_sound_values("Choose one or two."),
        })

        with patch.object(VoipIvr, "_sync_pbx") as sync_pbx:
            menu.with_context(voip_call_flow_node_configuration=True).write({
                "option_ids": [Command.create({"digit": "1"})],
            })

        sync_pbx.assert_not_called()
        self.assertEqual(menu.option_ids.digit, "1")

    def test_write_generated_tts_sound(self):
        menu = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Main Menu",
            **tts_sound_values("Choose one or two."),
        })

        menu.write(tts_sound_values("Choose three or four."))

        self.assertEqual(menu.tts_text, "Choose three or four.")
        self.assertEqual(menu.generated_tts_text, "Choose three or four.")

    def test_menu_owns_its_sound(self):
        menu = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Main Menu",
            **tts_sound_values("Press one for sales."),
        })

        self.assertTrue(menu.menu_sound_id)
        self.assertEqual(menu.name, "Main Menu")
        self.assertEqual(menu.menu_sound_id.name, "Main Menu")
        self.assertEqual(menu.tts_text, "Press one for sales.")

    def test_copy_creates_an_independent_menu_sound(self):
        menu = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Main Menu",
            **tts_sound_values("Press one for sales."),
        })

        duplicate = menu.copy({"name": "Main Menu Copy"})

        self.assertNotEqual(duplicate.menu_sound_id, menu.menu_sound_id)
        self.assertEqual(duplicate.menu_sound_id.name, "Main Menu Copy")
        self.assertEqual(duplicate.tts_text, menu.tts_text)

    def test_deleting_menu_deletes_its_sound(self):
        menu = self.env["voip.ivr"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Main Menu",
            **tts_sound_values("Press one for sales."),
        })
        menu_sound = menu.menu_sound_id

        menu.unlink()

        self.assertFalse(menu_sound.exists())
