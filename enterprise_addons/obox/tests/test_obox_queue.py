from odoo.exceptions import UserError

from .common import CommonOboxTest


class TestOboxQueue(CommonOboxTest):
    def _pending(self, action_type):
        return self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", action_type),
            ("status", "=", "pending"),
        ])

    def test_a_unique_action_is_refused_while_one_is_waiting(self):
        self.obox._queue_action("restart", "/odoo/restart")

        with self.assertRaises(UserError):
            self.obox._queue_action("restart", "/odoo/restart")

    def test_an_action_being_processed_still_blocks_the_next_one(self):
        """The constraint looks at every action that is not done yet."""
        self.obox._queue_action("restart", "/odoo/restart")
        self.obox.get_next_actions()  # the Obox took it, it is now processing

        with self.assertRaises(UserError):
            self.obox._queue_action("restart", "/odoo/restart")

    def test_a_non_unique_action_is_always_queued(self):
        first = self.obox._queue_action("test", "/odoo/health")
        second = self.obox._queue_action("test", "/odoo/health")

        self.assertNotEqual(first, second)
        self.assertEqual(len(self._pending("test")), 2)
