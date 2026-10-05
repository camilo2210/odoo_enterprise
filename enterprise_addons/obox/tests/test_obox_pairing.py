from unittest.mock import patch

from .common import CommonOboxTest


class TestOboxPairing(CommonOboxTest):

    def test_offline_connect_brings_an_archived_box_back(self):
        self.obox.active = False

        result = self.env["obox.obox"].connect_offline("1.2.3.4", " test ")

        self.assertEqual(result["id"], self.obox.id)
        self.assertTrue(self.obox.active)
        self.assertEqual(self.obox.state, "01_pairing")
        self.assertIn(f"token={self.obox.token}", result["url"])
        self.assertEqual(
            self.env["obox.obox"].with_context(active_test=False).search_count([("serial_number", "=", "TEST")]),
            1,
        )

    def test_offline_connect_creates_an_unknown_box(self):
        result = self.env["obox.obox"].connect_offline("1.2.3.5", "odo-new")

        obox = self.env["obox.obox"].browse(result["id"])
        self.assertEqual(obox.serial_number, "ODO-NEW")
        self.assertEqual(obox.name, "Obox ODO-NEW")
        self.assertEqual(obox.state, "01_pairing")

    def test_a_pairing_code_restarts_the_pairing_of_the_box_it_names(self):
        self.obox.active = False
        old_token = self.obox.token
        with patch("odoo.addons.obox.models.obox_obox.requests.post") as post:
            post.return_value.json.return_value = {"result": [{"serial_number": "TEST"}]}

            box_id = self.env["obox.obox"].pair_obox("123456")

        self.assertEqual(box_id, self.obox.id)
        self.assertTrue(self.obox.active)
        self.assertEqual(self.obox.state, "01_pairing")
        self.assertNotEqual(self.obox.token, old_token)
        self.assertEqual(post.call_args.kwargs["json"]["params"]["token"], self.obox.token)

    def test_an_unknown_pairing_code_pairs_nothing(self):
        with patch("odoo.addons.obox.models.obox_obox.requests.post") as post:
            post.return_value.json.return_value = {"error": "not found"}

            with self.assertLogs("odoo.addons.obox.models.obox_obox", level="WARNING") as logs:
                self.assertIsNone(self.env["obox.obox"].pair_obox("000000"))

        self.assertIn("not found", logs.output[0])
