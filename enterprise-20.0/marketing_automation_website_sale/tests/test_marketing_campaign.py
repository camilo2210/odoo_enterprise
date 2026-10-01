from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.tests import tagged


@tagged('-at_install', 'post_install')
class TestCampaignTemplate(MarketingAutomationCommon):

    def test_anniversary_template(self):
        anniversary = self.campaign._get_marketing_template_anniversary()
        self.assertTrue(anniversary)
