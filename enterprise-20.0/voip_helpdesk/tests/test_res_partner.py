from .common import VoipHelpdeskCommon


class TestResPartner(VoipHelpdeskCommon):
    def test_commercial_partner_ticket_count(self):
        self.assertEqual(
            [self.partner.commercial_partner_ticket_count, self.company_partner.commercial_partner_ticket_count],
            [7, 7],
            "The commercial partner ticket count should be 7 for both the partner and its parent company.",
        )

    def test_commercial_partner_open_ticket_count(self):
        self.assertEqual(
            [self.partner.commercial_partner_open_ticket_count, self.company_partner.commercial_partner_open_ticket_count],
            [4, 4],
            "The commercial partner open ticket count should be 4 for both the partner and its parent company.",
        )
