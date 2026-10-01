from odoo.tests import tagged
from odoo.addons.base.tests.common import HttpCaseWithUserPortal


@tagged("-at_install", "post_install")
class TestRecurringDonation(HttpCaseWithUserPortal):

    def test_recurring_donation(self):
        self.start_tour(
            self.env["website"].get_client_action_url("/", True),
            "donation_snippet_edition",
            login="admin",
        )
        self.start_tour("/", "recurring_donation_use")
