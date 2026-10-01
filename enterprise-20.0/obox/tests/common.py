import json
from odoo.tests import TransactionCase


class CommonOboxTest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref("obox.group_obox_user")
        cls.obox = cls.env["obox.obox"].create([{
            "name": "Test Obox",
            "serial_number": "TEST",
            "local_ip": "1.2.3.4",
            "state": "02_paired",
            "token": "test_obox_token",
        }])
        cls.obox_printer = cls.env["obox.device"].create([{
            "name": "Test Obox Printer",
            "identifier": "test_obox_printer",
            "type": "printer",
            "obox_id": cls.obox.id,
        }])
        cls.obox_scale = cls.env["obox.device"].create([{
            "name": "Test Obox Scale",
            "identifier": "test_obox_scale",
            "type": "scale",
            "obox_id": cls.obox.id,
        }])

    def respond_to_pending_actions(self, response):
        actions = self.obox.get_next_actions()
        for action in actions:
            queue = self.env["obox.queue"].search([("uuid", "=", action["uuid"])])
            queue.handle_obox_response(json.dumps(response))
