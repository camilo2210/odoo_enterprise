# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.addons.ai.tests.common import TestAICommon
from odoo.tests import tagged, HttpCase


@tagged("ai_marketing_automation")
class TestAIMarketingCampaignBuilder(MarketingAutomationCommon, TestAICommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.campaign_builder_agent = cls.env.ref('ai_marketing_automation.ai_agent_campaign_builder')

    def _create_ai_campaign_builder_session(self):
        session_data = self.env['ai.agent'].action_launch_ai_chat(
            interface_key='campaign_builder_ai'
        )
        ai_session = self.env['ai.session'].search(
            [['channel_id', '=', session_data['ai_channel_id']]])
        return ai_session

    def test_ai_campaign_initial_context(self):
        ai_session = self._create_ai_campaign_builder_session()
        self.assertEqual(ai_session.agent_id, self.campaign_builder_agent,
            "AI session should be launched with the Campaign Builder agent when using the 'campaign_builder_ai' interface key.")
