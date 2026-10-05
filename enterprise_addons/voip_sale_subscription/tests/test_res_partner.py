from .common import TestVoipSubscriptionCommon


class TestResPartner(TestVoipSubscriptionCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_commercial_partner_subscription_count(self):
        child_partner = self.env["res.partner"].create({
            "name": "child partner",
        })
        child_partner.parent_id = self.parent_partner.id
        self.assertEqual(
            (self.parent_partner | self.partner | child_partner).mapped("commercial_partner_subscription_count"),
            [2, 2, 2],
            "The commercial partner subscription count should be the sum of all subscriptions in this partner's family.",
        )
