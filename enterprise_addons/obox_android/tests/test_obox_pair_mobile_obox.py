from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user

from odoo.addons.obox.tests.common import CommonOboxTest


class TestPairMobileObox(CommonOboxTest):

    def test_a_new_device_gets_a_record_and_a_token(self):
        result = self.env["obox.obox"].pair_mobile_obox("odo-android-1", platform="android", name="Counter tablet")

        obox = self.env["obox.obox"].browse(result["id"])
        self.assertEqual(obox.serial_number, "ODO-ANDROID-1")
        self.assertEqual(obox.name, "Counter tablet")
        self.assertEqual(obox.platform, "android")
        self.assertEqual(obox.state, "01_pairing")
        self.assertEqual(result["token"], obox.token)
        self.assertEqual(result["url"], obox.get_base_url())

    def test_a_known_device_is_reactivated_with_a_fresh_token(self):
        self.obox.active = False
        old_token = self.obox.token

        result = self.env["obox.obox"].pair_mobile_obox("test")

        self.assertEqual(result["id"], self.obox.id)
        self.assertTrue(self.obox.active)
        self.assertEqual(self.obox.state, "01_pairing")
        self.assertNotEqual(self.obox.token, old_token)
        self.assertEqual(self.obox.name, "Test Obox")
        self.assertEqual(self.obox.platform, "rpi", "a platform that is not given is left as it was")

    def test_a_serial_number_is_required(self):
        for serial_number in (None, "", "   "):
            with self.subTest(serial_number=serial_number), self.assertRaises(UserError):
                self.env["obox.obox"].pair_mobile_obox(serial_number, platform="android")

    def test_pairing_needs_the_right_to_create_a_box(self):
        user = new_test_user(self.env, login="nobody")

        with self.assertRaises(AccessError):
            self.env["obox.obox"].with_user(user).pair_mobile_obox("ODO-ANDROID-2")
