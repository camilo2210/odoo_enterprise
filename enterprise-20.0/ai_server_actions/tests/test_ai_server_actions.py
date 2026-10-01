from odoo.addons.ai.tests.common import TestAICommon
from odoo.tests import tagged


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestAiServerActions(TestAICommon):

    def test_update_with_ai_server_action(self):
        """Test the 'update with AI' server action"""
        partner = self.env["res.partner"].create({"name": "Partner"})
        field = self.env["ir.model.fields"]._get(partner._name, "name").id
        action = self.env["ir.actions.server"].create({
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "state": "object_write",
            "name": "Test",
            "evaluation_type": "ai_computed",
            "ai_update_prompt": "Write 1337",
            "update_field_id": field,
        })

        with self.mock_completion_request([self.mock_text_response('{"value": "1337"}')]) as mock_request:
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        # check that the value has been written in the record
        self.assertEqual(partner.name, "1337")
        kw = mock_request.call_args.kwargs
        # check action prompt is in the message
        txt = mock_request.call_args.args[0][0]['content'][0]['text']
        self.assertIn('Write 1337', txt)
        # check some additional info about the field is in the message as well
        self.assertIn('{"type": "char", "name": "name", "description": "Name"}', txt)
        # check some additional info about the record is in the message as well
        self.assertIn(f'"model": "{partner._name}", "id": {partner.id}', txt)
        # check schema contains string parameter value
        self.assertEqual(kw['schema']['properties']['value']['type'], 'string')
        # check web web_grounding is set
        self.assertTrue(kw['web_grounding'], 'Web search should be enabled when updating with ai')
