from .common import TestVoipProjectCommon


class TestResPartner(TestVoipProjectCommon):
    def test_commercial_partner_task_count(self):
        self.assertEqual((self.parent_partner | self.partner_1 | self.partner_2 | self.partner_3).mapped("commercial_partner_task_count"), [2, 2, 2, 2],
            "The commercial partner task count should be the sum of all tasks in this partner's family.")
