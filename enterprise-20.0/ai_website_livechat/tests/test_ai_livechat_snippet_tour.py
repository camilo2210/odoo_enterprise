from odoo.addons.ai.tests.common import mock_iap_results, TestAICommon
from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestAILivechatSnippet(HttpCase, TestAICommon):

    def test_ai_livechat_snippet_tour(self):
        mock_responses = [self.mock_text_response("This is a test response from AI.")]
        with mock_iap_results(self.env, mock_responses):
            self.env['ai.agent'].create({'name': 'Test Agent'})
            self.start_tour(self.env["website"].get_client_action_url("/", True), 'ai_livechat_snippet_tour', login="admin")
