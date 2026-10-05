# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from datetime import datetime
from unittest.mock import patch

from odoo.addons.ai.models.ai_session import _logger as ai_session_logger
from odoo.addons.ai.models.ir_actions_server import IrActionsServer
from odoo.addons.ai.utils.ai_citation import apply_web_citations
from odoo.addons.ai.utils.ai_utils import get_text_from_parts
from odoo.addons.ai.tests.common import TestAICommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestLLMToolCalling(TestAICommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = cls.env['ir.actions.server'].create([{
            'model_id': cls.env["ir.model"]._get_id('ai.agent'),
            'state': 'code',
            'name': f'tool_{i + 1}',
            'ai_tool_name': f'tool_{i + 1}',
            'use_in_ai': True,
            'code': f"ai['result'] = 'tc_{i + 1}'"
        } for i in range(3)])

    def test_tool_call_result_serializes_datetime(self):
        """Tool results containing datetime objects are JSON-serialized properly."""
        mocked_result = {'executed_at': datetime(2026, 3, 30, 8, 15, 42)}

        mocked_responses = [
            self.mock_tool_response(self.tools[0]),
            self.mock_text_response("Done"),
        ]

        with patch.object(IrActionsServer, '_ai_tool_run', return_value=mocked_result), \
            self.mock_completion_request(mocked_responses) as mock_request:
            self.env['ai.session']._get_direct_response(
                instructions="do this",
                message=[{'type': 'text', 'text': "test"}],
                tools=self.tools,
            )

        history = mock_request.call_args.args[0]
        tool_output = history[-1]  # last item is the tool result
        self.assertEqual(tool_output['content'][0]['type'], 'tool_result')
        self.assertIn('2026-03-30 08:15:42', tool_output['content'][0]['result'][0]['text'])

    def test_max_api_calls_reached(self):
        max_calls = 2
        self.env["ir.config_parameter"].sudo().set_int("ai.max_successive_calls", max_calls)

        # return more tool calls than allowed
        mocked_responses = [self.mock_tool_response(self.tools[0])] * (max_calls + 1)

        with self.assertRaises(UserError) as e, self.mock_completion_request(mocked_responses) as mock_request:
            self.env['ai.session']._get_direct_response(
                instructions="Do this",
                message=[{'type': 'text', 'text': "test_prompt"}],
                tools=self.tools
            )
        self.assertEqual(
            str(e.exception),
            "Number of successive API calls exceeded, please try again with a more precise request."
        )

        self.assertEqual(mock_request.call_count, max_calls)

    def test_max_tool_calls_reached(self):
        max_calls = 1
        self.env["ir.config_parameter"].sudo().set_int("ai.max_tool_calls_per_call", max_calls)

        mocked_responses = [
            # first response: more calls than allowed
            [*self.mock_tool_response(self.tools[0]), *self.mock_tool_response(self.tools[1])],
            # second response, text answer
            self.mock_text_response("Final answer"),
        ]

        with self.assertLogs(ai_session_logger, level='WARNING') as mock_session_logger, \
            self.mock_completion_request(mocked_responses) as mock_request:
            response = self.env['ai.session']._get_direct_response(
                instructions="Do this",
                message=[{'type': 'text', 'text': "test prompt"}],
                tools=self.tools,
            )

        self.assertEqual(get_text_from_parts(response), "Final answer")

        warning_log, = mock_session_logger.records
        self.assertEqual(warning_log.message, "AI: Tool call limit reached, stopping further tool calls")

        # check the messags sent
        self.assertEqual(mock_request.call_args.args[0], [
            {'role': 'user', 'content': [{'type': 'text', 'text': 'test prompt'}]},
            {
                'role': 'assistant',
                'content': [
                    {'args': {}, 'call_id': 1, 'name': 'tool_1', 'type': 'tool_call'},
                    {'args': {}, 'call_id': 2, 'name': 'tool_2', 'type': 'tool_call'},
                ],
                'provider_metadata': {},
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'tool_result',
                        'tool_call_id': 1,
                        'tool_name': 'tool_1',
                        'result': [{'type': 'text', 'text': 'tc_1'}],
                        'success': True,
                    },
                    # tool call should not have been executed
                    {
                        'type': 'tool_result',
                        'tool_call_id': 2,
                        'tool_name': 'tool_2',
                        'result': [{'type': 'text', 'text': 'Error: Not executed (tool call limit reached)'}],
                        'success': False,
                    },
                ]
            },
        ])

    def test_unknown_tool_call(self):
        mocked_tool_response = self.mock_tool_response(self.tools[0])
        unknown_tool_name = mocked_tool_response[0]['name'] + "abc"
        mocked_tool_response[0]['name'] = unknown_tool_name
        mocked_responses = [
            # first answer: unknown tool
            mocked_tool_response,
            # second answer: final answer
            self.mock_text_response("Final answer")
        ]

        with self.assertLogs(ai_session_logger, level='ERROR') as mock_session_logger, \
            self.mock_completion_request(mocked_responses) as mock_request:
            response = self.env['ai.session']._get_direct_response(
                instructions="Do this",
                message=[{'type': 'text', 'text': "test prompt"}],
                tools=self.tools,
            )

        self.assertEqual(get_text_from_parts(response), "Final answer")

        error_log, = mock_session_logger.records
        self.assertEqual(error_log.message, f"AI: Try to call a non-available tool {unknown_tool_name}")

        # check the messages sent
        self.assertEqual(mock_request.call_args.args[0], [
            {'role': 'user', 'content': [{'type': 'text', 'text': 'test prompt'}]},
            {
                'role': 'assistant',
                'content': [{'type': 'tool_call', 'name': unknown_tool_name, 'args': {}, 'call_id': 1}],
                'provider_metadata': {},
            },
            # tool should not have been executed since not found
            {
                'role': 'user',
                'content': [{
                    'type': 'tool_result',
                    'tool_call_id': 1,
                    'tool_name': unknown_tool_name,
                    'result': [{'type': 'text', 'text': f"Error: Unknown tool '{unknown_tool_name}'"}],
                    'success': False,
                }],
            },
        ])

    def test_ai_web_search(self):
        web_search_tool = self.env.ref('ai.ir_actions_server_ai_web_search')
        mocked_responses = [
            # first answer: agent requesting web_search tool
            self.mock_tool_response(web_search_tool, {'query': "Search for the latest news", 'retrieval_mode': 'fact'}),
            # second answer: response of the web search tool
            self.mock_text_response("Web search result"),
            # third answer: agent answer using the tool result
            self.mock_text_response("This is what I found"),
        ]

        with self.mock_completion_request(mocked_responses) as mock_request:
            response = self.env['ai.session']._get_direct_response(
                instructions="Look this on the web",
                message=[{'type': 'text', 'text': "Latest News"}],
                tools=web_search_tool,
            )

        self.assertEqual(response, [{'type': 'text', 'text': "This is what I found"}])
        args = mock_request.call_args.args
        kw = mock_request.call_args.kwargs
        self.assertNotIn('web_grounding', kw)  # should use the tool, not the native param
        self.assertIn('ai_tool_web_search', json.dumps(args[2]))
        # should be the tool response containing the result of the web search
        self.assertEqual(args[0][-1], {
            'role': 'user',
            'content': [{
                'type': 'tool_result',
                'tool_call_id': 1,
                'tool_name': web_search_tool.ai_tool_name,
                'result': [{'type': 'text', 'text': "Web search result"}],
                'success': True,
            }],
        })

    def test_apply_web_citations(self):
        text = "First claim.[WEB_SOURCE:aaa111] Second claim.[WEB_SOURCE:bbb222]"
        sources = {
            'aaa111': {'url': 'https://a.com', 'source_name': 'a.com'},
            'bbb222': {'url': 'https://b.com', 'source_name': 'b.com'},
        }
        result = apply_web_citations(text, sources)
        self.assertNotIn('[WEB_SOURCE:', result)
        self.assertIn("href='https://a.com'", result)
        self.assertIn("href='https://b.com'", result)

    def test_apply_web_citations_unknown_id_ignored(self):
        text = "Some claim.[WEB_SOURCE:0]"
        result = apply_web_citations(text, {})
        self.assertNotIn('[WEB_SOURCE:', result)
        self.assertNotIn('<a ', result)
        self.assertIn('Some claim.', result)
