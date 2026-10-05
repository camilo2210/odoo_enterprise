from .common import TestVoipSaleCommon


class TestResPartner(TestVoipSaleCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_commercial_partner_sale_order_count(self):
        self.assertEqual((self.parent_partner | self.partner | self.child_partner).mapped("commercial_partner_sale_order_count"), [1, 1, 1],
            "The commercial partner sale order count should be the sum of all sale orders in this partner's family.")
