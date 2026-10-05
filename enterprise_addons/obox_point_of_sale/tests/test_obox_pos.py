from odoo.tests import TransactionCase


class TestOboxPos(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.obox = cls.env["obox.obox"].create({
            "name": "Test Obox",
            "serial_number": "POS-TEST",
            "state": "02_paired",
            "token": "dummy",
        })
        cls.other_obox = cls.env["obox.obox"].create({
            "name": "Other Obox",
            "serial_number": "POS-OTHER",
            "state": "02_paired",
            "token": "dummy-other",
        })
        cls.pos_config = cls.env["pos.config"].create({
            "name": "Obox Shop",
        })

    def test_the_pos_loads_the_obox_behind_its_printers(self):
        printer = self.env["pos.printer"].create({
            "name": "Kitchen printer",
            "printer_type": "obox",
            "proxy_obox_id": self.obox.id,
        })
        data = {"pos.config": self.pos_config, "pos.printer": printer}

        domain = self.env["obox.obox"]._load_pos_data_domain(data)

        self.assertEqual(self.env["obox.obox"].search(domain), self.obox)

    def test_the_pos_loads_no_obox_without_a_printer_behind_one(self):
        data = {"pos.config": self.pos_config, "pos.printer": self.env["pos.printer"]}

        domain = self.env["obox.obox"]._load_pos_data_domain(data)

        self.assertFalse(self.env["obox.obox"].search(domain))

    def test_the_pos_session_loads_oboxes_and_their_devices(self):
        models = self.env["pos.session"]._load_pos_data_models(self.pos_config)

        self.assertIn("obox.obox", models)
        self.assertIn("obox.device", models)

    def test_a_print_job_is_queued_on_its_obox(self):
        payload = {"url": "/cgi-bin/epos/service.cgi", "body": "<epos-print/>"}

        uuids = self.obox.create_job(payload)

        job = self.env["obox.queue"].search([("uuid", "in", uuids)])
        self.assertEqual(job.obox_id, self.obox)
        self.assertEqual(job.payload, payload)
