from .common import CommonOboxTest


class TestOboxCheckWebsocket(CommonOboxTest):

    def test_checking_a_box_queues_a_test_action(self):
        self.assertTrue(self.obox.action_check_websocket())
        self.assertTrue(self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", "test"),
        ]))

    def test_checking_a_deleted_box_queues_nothing(self):
        """The status widget may still poll a box deleted meanwhile."""
        box = self.env["obox.obox"].browse(self.obox.id)
        self.obox.unlink()

        self.assertFalse(box.action_check_websocket())
        self.assertFalse(self.env["obox.queue"].search([("action_type", "=", "test")]))
