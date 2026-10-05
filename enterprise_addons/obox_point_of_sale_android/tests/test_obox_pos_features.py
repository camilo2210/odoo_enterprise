from odoo.tests import TransactionCase


class TestOboxPosAndroidFeatures(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.obox = cls.env["obox.obox"].create({
            "name": "Test Obox",
            "serial_number": "POS-TEST",
            "state": "02_paired",
            "token": "dummy",
        })
        cls.pos_config = cls.env["pos.config"].create({
            "name": "Obox Shop",
        })

    def test_the_pos_loads_the_obox_address(self):
        fields = self.env["obox.obox"]._load_pos_data_fields(self.pos_config)

        self.assertIn("local_ip", fields)
        self.assertIn("local_address", fields)

    def test_a_pos_config_declares_the_feature(self):
        self.assertIn("point_of_sale", self.obox._get_obox_features())

    def test_the_point_of_sale_detail_lists_the_config_with_its_url(self):
        detail = self.obox._get_obox_feature_details("point_of_sale")
        entry = next(pos for pos in detail["point_of_sale"] if pos["id"] == self.pos_config.id)
        self.assertEqual(entry["name"], self.pos_config.name)
        self.assertTrue(entry["url"].endswith(f"/pos/ui/{self.pos_config.id}"))
        self.assertEqual(entry["timezone"], self.pos_config.company_id.tz)
