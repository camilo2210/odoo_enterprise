# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import socket
from contextlib import contextmanager
from io import BytesIO
from unittest.mock import Mock, patch

import requests
from lxml import html as lxml_html

from odoo.tests import tagged, users

from odoo.addons.ai.models.ai_session import AiSession
from odoo.addons.ai.models.ai_tool import AITool
from odoo.addons.ai.tests.common import TestAICallbackCommon
from odoo.addons.ai.utils.ai_utils import UserInputResponse
from odoo.addons.ai_website.models.ir_attachment import (
    _IMAGE_DOWNLOAD_BATCH_DEADLINE,
    _MAX_IMAGE_BYTES,
    _MAX_IMAGE_REDIRECTS,
    _MAX_IMAGES_PER_BATCH,
)
from odoo.addons.base.tests.files import PNG_B64, PNG_RAW
from odoo.addons.mail.tools.discuss import Store
from odoo.addons.web_unsplash.models.ir_attachment import (
    IrAttachment as WebUnsplash_IrAttachment,
)

_IR_ATTACHMENT = "odoo.addons.ai_website.models.ir_attachment"
_SESSION_SEND = f"{_IR_ATTACHMENT}.requests.Session.send"
_ORIGINAL_SESSION_SEND = requests.Session.send
_MONOTONIC = f"{_IR_ATTACHMENT}.monotonic"
_SVG_RAW = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    b'<rect width="10" height="10"/></svg>'
)


class _FakeResponse:
    """Minimal stand-in for a streamed ``requests`` response."""

    def __init__(self, content=b"", status_code=200, headers=None):
        self.content = content
        self.next = None
        self.status_code = status_code
        self.headers = headers or {}

    def iter_content(self, chunk_size=None):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _image_http_response(content=PNG_RAW, status=200, headers=None):
    headers = {'Content-Length': str(len(content)), **(headers or {})}
    head = f'HTTP/1.1 {status} Response\r\n' + ''.join(f'{key}: {value}\r\n' for key, value in headers.items())
    return head.encode() + b'\r\n' + content


@contextmanager
def _mock_image_transport(responses=(), peers=('93.184.216.34',)):
    """Exercise Requests and urllib3 with in-memory sockets; no network access."""
    responses = iter(responses)
    sockets = []
    for peer in peers:
        sock = Mock(spec=socket.socket)
        sock.getpeername.return_value = (peer, 443)
        sock.makefile.side_effect = lambda *args, **kwargs: BytesIO(next(responses))
        sockets.append(sock)
    with (
        patch(_SESSION_SEND, _ORIGINAL_SESSION_SEND),
        patch('urllib3.util.connection.create_connection', side_effect=sockets) as connect,
        patch('urllib3.connection._ssl_wrap_socket_and_match_hostname',
              side_effect=lambda sock, **kwargs: Mock(socket=sock, is_verified=True)),
        patch('urllib3.connectionpool.is_connection_dropped', return_value=False),
    ):
        yield connect, sockets


@tagged('post_install', '-at_install')
class TestAIWebsiteBuilder(TestAICallbackCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website_builder_agent = cls.env.ref('ai_website.ai_agent_website_builder')
        cls.website = cls.env['ai.website.service']._current_website()
        cls._VIEW_INFO = {
            "website_page": {
                "is_page_ai_editable": True,
                "main_object": {"model": "website.page", "id": 1},
                "website_id": cls.website.id,
                "location": "/test",
                "editable_zones": {"main": "<section>Hello</section>", "footer": ""},
            },
        }

    def setUp(self):
        super().setUp()
        self.patch(self.env.registry['ai.tool'], '_call_ai_reviewer', lambda *args, **kwargs: (True, ""))

    def _create_ai_website_builder_session(self, user=None):
        agent = self.env['ai.agent'].with_user(user or self.env.user)
        session_data = agent.action_launch_ai_chat(
            interface_key='website_builder_ai')
        ai_session = self.env['ai.session'].with_user(user or self.env.user).sudo().search(
            [['channel_id', '=', session_data['ai_channel_id']]])
        return ai_session

    def _create_page_tool_context(self):
        return {
            'state': {},
            'tool_request_confirmed': False,
        }

    def test_ai_website_initial_context(self):
        ai_session = self._create_ai_website_builder_session()
        self.assertEqual(ai_session.agent_id, self.website_builder_agent,
                         "AI session should be launched with the Website Builder agent when using the 'website_builder_ai' interface key.")
        first_event_content = ai_session.event_ids[0].metadata['content'][0]['text']
        self.assertIn("# Available snippets", first_event_content,
                      "The initial context for the Website Builder agent should include the list of available snippets.")
        website_builder_skill = self.env.ref('ai_website.ai_skill_website_builder')
        self.assertIn(self.env.ref('ai_website.ir_actions_server_get_site_profile'), website_builder_skill.tool_ids)
        self.assertIn(self.env.ref('ai_website.ir_actions_server_get_page_html'), website_builder_skill.tool_ids)

    @users('admin')
    def test_ai_custom_response(self):
        ai_session = self._create_ai_website_builder_session()
        self.authenticate(self.env.user.login, self.env.user.login)

        open_builder_message = "Please open the website builder to use this AI on the website."
        cases = [
            (
                {"current_view_info": {
                    "website_page": {"is_page_ai_editable": False},
                }},
                "The current page is a special page that cannot be edited by the AI.",
            ),
            ({"current_view_info": {}}, open_builder_message),
            ({}, open_builder_message),
        ]

        for extra_params, expected_message in cases:
            with self.subTest(params=extra_params):
                message = ai_session.channel_id.message_post(
                    body="Build my page",
                    message_type="comment",
                )
                with patch(
                    "odoo.addons.ai.models.ai_session.call_odoo_ai_transport",
                    return_value={},
                ) as transport:
                    response = self.make_jsonrpc_request(
                        "/ai/start_session_advance",
                        {
                            "channel_id": ai_session.channel_id.id,
                            "mail_message_id": message.id,
                            **extra_params,
                        },
                    )

                transport.assert_not_called()
                self.assertEqual(response, {"loop_state": "ready"})
                self.env.invalidate_all()
                self.assertEqual(
                    ai_session.channel_id.message_ids[0].preview,
                    expected_message,
                )

    @users('admin')
    def test_scraper_resume_ignores_obsolete_or_unready_notifications(self):
        session = self._create_ai_website_builder_session().with_context(
            current_view_info=self._VIEW_INFO,
        )
        session._save_context_for_async_resume()
        session.write({
            'request_uuid': 'scraper-request', 'request_payload': {'messages': []},
            'request_user_id': self.env.user.id, 'request_webhook_secret': 'test-secret',
            'request_round': 1, 'request_round_limit': 2,
        })
        self.authenticate(self.env.user.login, self.env.user.login)
        ready_state = {'website_scraper_results': {'scrape-1': {'state': 'done', 'result': {}}}}
        pending = {'call_id': 'scrape-1', 'await_external_result': True}
        cases = [
            ('cancelled', False, ready_state, self._VIEW_INFO, 'scrape-1'),
            ('replaced', {**pending, 'call_id': 'scrape-2'}, ready_state, self._VIEW_INFO, 'scrape-1'),
            ('consumed', {**pending, 'await_external_result': False}, ready_state, self._VIEW_INFO, 'scrape-1'),
            ('not ready', pending, False, self._VIEW_INFO, 'scrape-1'),
            ('missing call', pending, ready_state, self._VIEW_INFO, None),
            ('no editor', pending, ready_state, {}, 'scrape-1'),
            ('other page', pending, ready_state, {'website_page': {
                **self._VIEW_INFO['website_page'], 'main_object': {'model': 'website.page', 'id': 2},
            }}, 'scrape-1'),
            ('other website', pending, ready_state, {'website_page': {
                **self._VIEW_INFO['website_page'], 'website_id': self.website.id + 1,
            }}, 'scrape-1'),
        ]
        for name, pending_call, state, view_info, call_id in cases:
            with self.subTest(name), patch(
                'odoo.addons.ai.models.ai_session.call_odoo_ai_transport', return_value={},
            ) as transport:
                loop_state = 'waiting_external_result' if pending_call else 'ready'
                resume_token = 'scraper-resume-token' if pending_call else False
                session.write({
                    'pending_tool_call': pending_call, 'state': state,
                    'loop_state': loop_state, 'resume_token': resume_token,
                })
                self.make_jsonrpc_request('/ai/resume_pending_interaction', {
                    'channel_id': session.channel_id.id, 'session_id': session.id,
                    'resume_token': 'scraper-resume-token',
                    'response': {'kind': 'async', 'call_id': call_id},
                    'current_view_info': view_info,
                })
                transport.assert_not_called()
                self.env.invalidate_all()
                self.assertEqual(session.pending_tool_call, pending_call)
                self.assertEqual(session.state, state)
                self.assertEqual(session.loop_state, loop_state)
                self.assertEqual(session.resume_token, resume_token)

    def test_scraper_callback_ignores_cancelled_requests(self):
        session = self._create_ai_website_builder_session()
        batch = self.env['ai.web.scraper.batch'].create({
            'callback_model': 'ai.tool', 'ai_session_id': session.id,
            'tool_call_id': 'cancelled', 'state': 'done', 'result': {},
        })
        with patch.object(self.registry['res.users'], '_bus_send') as bus_send:
            self.env.ref('ai.ir_cron_run_web_scraper').method_direct_trigger()
        self.assertFalse(any(call.args[0] == 'ai_website/scraper_result_ready' for call in bus_send.call_args_list))
        self.assertFalse(batch.exists())
        self.assertNotIn('website_scraper_results', session.state or {})

    def test_scraper_result_resumes_through_the_editor_stream(self):
        self._check_scraper_result_resumes_through_the_editor_stream('done')

    def test_failed_scraper_result_resumes_through_the_editor_stream(self):
        self._check_scraper_result_resumes_through_the_editor_stream('failed')

    def test_scraper_suspends_and_resumes_for_non_admin_designer(self):
        self.user_internal.group_ids |= self.env.ref('website.group_website_designer')
        self.assertFalse(self.user_internal.has_group('base.group_system'))
        self._check_scraper_result_resumes_through_the_editor_stream('done', user=self.user_internal)

    def _check_scraper_result_resumes_through_the_editor_stream(self, state, user=None):
        user = user or self.env.user
        session = self._create_ai_website_builder_session(user=user)
        # These replies cover the page workflow, not channel-title generation.
        session.channel_id.name = 'Website scraper test'
        message = session.channel_id.message_post(
            body='Build a page from https://example.com', message_type='comment',
        )
        scrape = self.env.ref('ai_website.ir_actions_server_scrape_website_pages')
        apply_html = self.env.ref('ai_website.ir_actions_server_apply_html_to_page')
        tools = scrape | apply_html
        scrape_response = self.mock_tool_response(scrape, {'urls': [{
            'url': 'https://example.com', 'fetch_images': False, 'take_screenshot': False,
        }]})
        scrape_response[0]['call_id'] = 'scrape-1'
        with (
            self.with_user(user.login),
            self.mock_default_tools(tools),
            self.mock_callback_completions([scrape_response]),
        ):
            self._call_ai_endpoint('/ai/start_session_advance', {
                'channel_id': session.channel_id.id, 'mail_message_id': message.id,
                'current_view_info': self._VIEW_INFO,
            })
        self.assertEqual(session.loop_state, 'waiting_external_result')
        self.assertTrue(session.pending_tool_call['await_external_result'])
        # Capture the page identity with the session's privileges, never the live HTML.
        self.assertEqual(session.website_builder_context['current_view_info'], {
            'website_page': {key: self._VIEW_INFO['website_page'][key]
                             for key in ('main_object', 'location', 'website_id')},
        })
        batch = self.env['ai.web.scraper.batch'].search([('ai_session_id', '=', session.id)])
        batch.write({'state': state, 'result': {'pages': {}}, 'error': 'Scraping timed out' if state == 'failed' else False})

        call_id = batch.tool_call_id
        scraper_resume_token = session.resume_token
        with (
            self.mock_callback_completions([]) as api_request,
            patch.object(self.registry['res.users'], '_bus_send', autospec=True) as bus_send,
        ):
            self.env.ref('ai.ir_cron_run_web_scraper').method_direct_trigger()
        api_request.assert_not_called()
        self.assertFalse(batch.exists())

        delivered = [
            call.args for call in bus_send.call_args_list
            if call.args[1] == 'ai_website/scraper_result_ready'
        ]
        self.assertEqual(len(delivered), 1)
        recipient, _event, payload = delivered[0]
        self.assertEqual(recipient, session.create_uid)
        self.assertEqual(payload, {
            'channel_id': session.channel_id.id,
            'session_id': session.id,
            'resume_token': scraper_resume_token,
            'tool_call_id': call_id,
            'target_page': {
                'main_object': self._VIEW_INFO['website_page']['main_object'],
                'location': '/test', 'website_id': self.website.id,
            },
        })
        self.assertTrue(session.pending_tool_call['await_external_result'])
        self.assertIn(call_id, session.state['website_scraper_results'])

        # The editor resumes with live page context and receives a pending client tool.
        resume_params = {
            'channel_id': session.channel_id.id, 'session_id': session.id,
            'resume_token': scraper_resume_token,
            'response': {'kind': 'async', 'call_id': call_id},
            'current_view_info': {'website_page': {
                **self._VIEW_INFO['website_page'],
                'editable_zones': {'main': '<section>Updated while scraping</section>', 'footer': ''},
            }},
        }
        with (
            self.with_user(user.login),
            self.mock_default_tools(tools),
            self.mock_callback_completions([
                self.mock_tool_response(apply_html, {'actions': [{
                    'zone': 'main', 'mode': 'replace', 'selector': '', 'content': '<section>Hello</section>',
                }]}),
            ]) as api_request,
        ):
            self._call_ai_endpoint('/ai/resume_pending_interaction', resume_params)
        messages = json.dumps(api_request.call_args.args[2]['messages'])
        self.assertIn('Updated while scraping', messages)
        if state == 'failed':
            self.assertIn('Web scraping failed: Scraping timed out', messages)
        self.assertEqual(session.loop_state, 'waiting_client_result')
        pending_client_tool = session.pending_tool_call
        client_resume_token = session.resume_token
        self.assertEqual(pending_client_tool['client_tool']['name'], 'finalize_website_page')
        self.assertIn('<section>Hello</section>', pending_client_tool['client_tool']['params']['html'])
        self.assertFalse(pending_client_tool.get('await_external_result'))
        self.assertNotIn(call_id, session.state['website_scraper_results'])
        with self.with_user(user.login), self.mock_callback_completions([]) as api_request:
            self._call_ai_endpoint('/ai/resume_pending_interaction', resume_params)
        api_request.assert_not_called()
        self.assertEqual(session.pending_tool_call, pending_client_tool,
                         'A duplicate notification must not rerun generation or consume the client tool.')
        self.assertEqual(session.resume_token, client_resume_token)
        self.assertEqual(session.loop_state, 'waiting_client_result')

        with (
            self.with_user(user.login),
            self.mock_default_tools(tools),
            self.mock_callback_completions([self.mock_text_response('Your page is ready.')]),
        ):
            self._call_ai_endpoint('/ai/resume_pending_interaction', {
                **resume_params, 'resume_token': client_resume_token,
                'response': {'kind': 'client_result', 'value': 'Page ready'},
            })
        self.assertEqual(session.loop_state, 'ready')
        self.assertFalse(session.pending_tool_call)
        self.assertEqual(session.channel_id.message_ids[0].preview, 'Your page is ready.')

    def test_ready_scraper_results_recovers_only_own_ready_calls_on_current_page(self):
        self.user_internal.group_ids |= self.env.ref('website.group_website_designer')
        session = self._create_ai_website_builder_session(user=self.user_internal).with_context(
            current_view_info=self._VIEW_INFO,
        )
        session._set_pending_tool_call({'call_id': 'scrape-1', 'await_external_result': True})
        session.resume_token = 'scrape-1-token'
        batch = self.env['ai.web.scraper.batch'].create({
            'callback_model': 'ai.tool', 'ai_session_id': session.id,
            'tool_call_id': 'scrape-1', 'state': 'done', 'result': {'pages': {}},
        })
        # The result remains discoverable after the cron has discarded the batch.
        self.env.ref('ai.ir_cron_run_web_scraper').method_direct_trigger()
        self.assertFalse(batch.exists())
        other_session = self._create_ai_website_builder_session().with_context(current_view_info=self._VIEW_INFO)
        other_session.write({'state': session.state, 'resume_token': 'other-scrape-token'})
        other_session._set_pending_tool_call(dict(session.pending_tool_call))

        self.authenticate(self.user_internal.login, self.user_internal.login)
        params = {'website_id': self.website.id, 'main_object': self._VIEW_INFO['website_page']['main_object']}
        self.assertEqual(self.make_jsonrpc_request('/ai_website/ready_scraper_results', params), [{
            'channel_id': session.channel_id.id,
            'session_id': session.id,
            'resume_token': 'scrape-1-token',
            'tool_call_id': 'scrape-1',
            'target_page': {
                'main_object': self._VIEW_INFO['website_page']['main_object'],
                'location': '/test', 'website_id': self.website.id,
            },
        }])
        for changed in ({'website_id': self.website.id + 1}, {'main_object': {'model': 'website.page', 'id': 2}}):
            self.assertEqual(self.make_jsonrpc_request('/ai_website/ready_scraper_results', params | changed), [])
        session._finish_exchange()
        self.assertEqual(self.make_jsonrpc_request('/ai_website/ready_scraper_results', params), [])
        session._set_pending_tool_call({'call_id': 'scrape-2', 'await_external_result': True})
        session.resume_token = 'scrape-2-token'
        self.assertEqual(self.make_jsonrpc_request('/ai_website/ready_scraper_results', params), [])

    def test_scraper_resume_can_retry_a_busy_session(self):
        session = self._create_ai_website_builder_session().with_context(current_view_info=self._VIEW_INFO)
        pending = {'call_id': 'scrape-1', 'await_external_result': True}
        state = {'website_scraper_results': {'scrape-1': {'state': 'done', 'result': {}}}}
        session._set_pending_tool_call(pending)
        session.write({
            'loop_state': 'waiting_external_result', 'resume_token': 'scrape-1-token',
            'request_uuid': 'scraper-request', 'request_payload': {'messages': []},
            'request_user_id': self.env.user.id, 'request_webhook_secret': 'test-secret',
            'request_round': 1, 'request_round_limit': 2, 'state': state,
        })
        with (
            self.mock_callback_completions([]) as api_request,
            patch.object(
                self.registry['ai.session'], 'try_lock_for_update', return_value=self.env['ai.session'],
            ) as try_lock,
        ):
            response = self._call_ai_endpoint('/ai/resume_pending_interaction', {
                'channel_id': session.channel_id.id, 'session_id': session.id,
                'resume_token': 'scrape-1-token',
                'response': {'kind': 'async', 'call_id': 'scrape-1'},
                'current_view_info': self._VIEW_INFO,
            })
        try_lock.assert_called_once()
        api_request.assert_not_called()
        self.assertEqual(response, {
            'loop_state': 'waiting_external_result', 'interactionConsumed': False,
        })
        self.assertEqual(session.pending_tool_call, pending)
        self.assertEqual(session.state, state)
        self.assertEqual(session.resume_token, 'scrape-1-token')
        self.assertEqual(session.loop_state, 'waiting_external_result')
        self.assertTrue(session._get_scraper_resume_data())
        self.assertTrue(session._accept_scraper_resume('scrape-1'))

    def test_selected_elements_are_added_to_user_message(self):
        ai_session = self._create_ai_website_builder_session()
        user_message = [{'type': 'text', 'text': 'Update these profiles'}]
        with patch.object(AiSession, '_submit_agent_request') as parent_continue:
            ai_session.with_context(current_view_info={'website_page': {
                'is_page_ai_editable': True,
                'selected_elements': [{
                    'id': 'ai-first',
                    'tag': 'section',
                    'text': 'Jordan Ellis',
                    'computed_style': {'display': 'block'},
                }],
            }})._submit_agent_request(user_message)

        self.assertEqual(parent_continue.call_args.args[0], [*user_message, {
            'type': 'text',
            'text': (
                "<website_element_attachments>\n"
                "[{'id': 'ai-first', 'tag': 'section', 'text': 'Jordan Ellis'}]\n"
                "</website_element_attachments>"
            ),
        }])

    def test_selected_element_labels_round_trip_without_field(self):
        ai_session = self._create_ai_website_builder_session()
        message = ai_session.channel_id.with_context(
            ai_website_element_labels=['First profile'],
        ).message_post(body='Update these profiles', message_type='comment')

        stored_message = (
            Store().add(message, '_store_message_fields')
            ._build_result()['mail.message'][0]
        )
        self.assertNotIn('ai_website_element_labels', self.env['mail.message']._fields)
        self.assertEqual(stored_message['ai_website_element_labels'], ['First profile'])
        self.assertEqual(
            message._convert_to_parts()[0]['text'], '<p>Update these profiles</p>'
        )

    def test_ai_tool_generate_image(self):
        ai_session = self._create_ai_website_builder_session()

        def mocked_generate(self, tool_context, prompt, images_paths, image_title, feedback, aspect_ratio='1:1'):
            """Mock the _ai_tool_generate_image method from the ai module"""
            return {'response': "mocked_generate_image_result"}

        with patch.object(AITool, '_ai_tool_generate_image', mocked_generate):
            attachment = self.env['ir.attachment'].create({
                'name': 'Fake Generated Image',
                'type': 'binary',
                'raw': PNG_B64,
                'mimetype': 'image/png',
                'public': False,
            })
            tool_context = {'session_id': ai_session.id, 'final_message': [
                {'type': 'text', 'text': attachment.name},
                {
                    'type': 'inline_data',
                    'data': attachment.raw.content,
                    'mimetype': attachment.mimetype,
                    'metadata': {'attachment_id': attachment.id},
                }
            ]}
            result = self.env['ai.tool']._ai_tool_generate_image(tool_context, '', [], '', '', '')['response']
            self.assertEqual(
                result,
                (
                    "Generated 1 image(s). Permanent URLs:\n"
                    f"- ID: {attachment.id}, URL: /web/image/{attachment.id + 1}-33c042bd/Fake%20Generated%20Image\n\n"
                    "You MUST now call `apply_html_to_page` to place these images on the page "
                    "using appropriate selectors. Do not message the user until placement is done."
                ))
            self.assertIsNone(tool_context['final_message'],
                              "final_message must be cleared so the loop continues into image placement.")

    def test_ai_tool_get_snippets(self):
        result = self.env['ai.tool']._ai_tool_get_snippets([])
        self.assertEqual(
            result, "No snippet keys provided. Please specify which snippets you want to retrieve.")

        result = self.env['ai.tool']._ai_tool_get_snippets(["s_non_existent_snippet"])['response']
        self.assertIn(
            '## Snippet: s_non_existent_snippet\nNo snippet found with this key. Try another one.\n\n', result)

        result = self.env['ai.tool']._ai_tool_get_snippets(["s_cover", "s_banner"])['response']
        self.assertIn(
            'Here are the HTML structures of the snippets you requested.\n\n', result)
        self.assertIn(
            '## Snippet: s_cover\n_Cover_ — full-screen background image with centered text and a primary CTA\n\n```html\n<section class="s_cover', result)
        self.assertIn(
            '## Snippet: s_banner\n_Banner_ — prominent hero with a large headline and a call-to-action button\n\n```html\n<section class="s_banner', result)

    def test_ai_tool_scrape_website_pages_requests_page_assets(self):
        url = "https://example.com/page"
        ai_session = self._create_ai_website_builder_session()
        tool_context = {
            "tool_call_id": "scrape-page-assets",
            "state": {},
            "session_id": ai_session.id,
        }

        result = self.env["ai.tool"].with_context(
            current_view_info=self._VIEW_INFO,
        )._ai_tool_scrape_website_pages(tool_context, [
            {"url": url, "fetch_images": True, "take_screenshot": True},
        ])

        self.assertIsNone(result)
        self.assertTrue(tool_context["await_external_result"])
        self.assertEqual(
            tool_context["external_wait_message"],
            "Having a look at your reference(s), give me a minute or two",
        )
        batch_id = tool_context["state"]["website_scraper_requests"]["scrape-page-assets"]
        batch = self.env["ai.web.scraper.batch"].browse(batch_id)
        self.assertTrue(batch.timeout_at)
        self.assertEqual(batch.ai_session_id, ai_session)
        self.assertEqual(batch.url_payloads, [{
            "url": url,
            "check_robots_txt": True,
            "fetch_image_urls": True,
            "take_screenshot": True,
        }])
        self.assertFalse(ai_session.website_builder_context, "The session, not the tool, saves the snapshot.")

    def test_ai_tool_scrape_website_pages_requests_media_per_url(self):
        """Media is paid for per page: only ask the scraper for what the AI wants."""
        ai_session = self._create_ai_website_builder_session()
        tool_context = {
            "tool_call_id": "scrape-per-url",
            "state": {},
            "session_id": ai_session.id,
        }

        self.env["ai.tool"].with_context(
            current_view_info=self._VIEW_INFO,
        )._ai_tool_scrape_website_pages(tool_context, [
            {"url": "https://example.com/read", "fetch_images": True, "take_screenshot": False},
            {"url": "https://example.com/look", "fetch_images": True, "take_screenshot": True},
            # A bare URL is a text-only request.
            "https://example.com/plain",
            {"url": "https://example.com/read", "fetch_images": False, "take_screenshot": False},
        ])

        batch_id = tool_context["state"]["website_scraper_requests"]["scrape-per-url"]
        self.assertEqual(self.env["ai.web.scraper.batch"].browse(batch_id).url_payloads, [
            {
                "url": "https://example.com/read",
                "check_robots_txt": True,
                "fetch_image_urls": True,
                "take_screenshot": False,
            },
            {
                "url": "https://example.com/look",
                "check_robots_txt": True,
                "fetch_image_urls": True,
                "take_screenshot": True,
            },
            {
                "url": "https://example.com/plain",
                "check_robots_txt": True,
                "fetch_image_urls": False,
                "take_screenshot": False,
            },
        ])

    def test_ai_tool_scrape_website_pages_without_session_does_not_suspend(self):
        """Suspending with nowhere to deliver the result would freeze the chat for good."""
        tool_context = {"tool_call_id": "no-session", "state": {}}

        result = self.env["ai.tool"]._ai_tool_scrape_website_pages(
            tool_context, [{"url": "https://example.com/page", "fetch_images": False, "take_screenshot": False}],
        )

        self.assertEqual(result, "Web scraping is not available in this conversation.")
        self.assertFalse(tool_context.get("await_external_result"))

    def test_ai_tool_scrape_website_pages_caps_the_number_of_urls(self):
        ai_session = self._create_ai_website_builder_session()
        tool_context = {
            "tool_call_id": "too-many",
            "state": {},
            "session_id": ai_session.id,
        }

        result = self.env["ai.tool"]._ai_tool_scrape_website_pages(
            tool_context, [
                {"url": f"https://example.com/page-{i}", "fetch_images": False, "take_screenshot": False}
                for i in range(11)
            ],
        )

        self.assertIn("Too many URLs", result)
        self.assertFalse(tool_context.get("await_external_result"))

    def test_format_web_scraper_result_includes_images_and_screenshot(self):
        url = "https://example.com/page"
        result = self.env["ai.tool"]._format_web_scraper_result({
            "pages": {
                url: {
                    "failed": False,
                    "payload": json.dumps({
                        "text": "Example page content",
                        "images": [
                            {
                                "src": "https://example.com/image.png",
                                "kind": "img",
                                "alt": "Example image",
                            },
                        ],
                        "screenshot_url": "data:image/png;base64,c2NyZWVuc2hvdA==",
                    }),
                },
            },
        }, [{"url": url, "fetch_image_urls": True, "take_screenshot": True}])

        self.assertEqual(result[0]["type"], "text")
        self.assertIn("Example page content", result[0]["text"])
        self.assertIn('URL: "https://example.com/image.png"', result[0]["text"])
        self.assertIn('Alt text: "Example image"', result[0]["text"])
        self.assertEqual(result[1], {
            "type": "inline_data",
            "mimetype": "image/png",
            "data": "c2NyZWVuc2hvdA==",
            "metadata": {"source_url": url},
        })

    def test_format_web_scraper_result_drops_media_that_was_not_requested(self):
        """The scraper may return more than was asked for; the conversation pays for it."""
        url = "https://example.com/page"
        result = self.env["ai.tool"]._format_web_scraper_result({
            "pages": {
                url: {
                    "failed": False,
                    "payload": json.dumps({
                        "text": "Example page content",
                        "images": [{"src": "https://example.com/image.png"}],
                        "screenshot_url": "data:image/png;base64,c2NyZWVuc2hvdA==",
                    }),
                },
            },
        }, [{"url": url, "fetch_image_urls": False, "take_screenshot": False}])

        self.assertIsInstance(result, str, "Without a screenshot the result is plain text.")
        self.assertIn("Example page content", result)
        self.assertNotIn("https://example.com/image.png", result)
        self.assertNotIn("screenshot", result.lower())

    def test_ai_tool_search_images(self):
        def mocked_fetch_unsplash_images(self, **post):
            return {
                "results": [
                    {
                        "urls": {"regular": "https://example.com/image1.jpg"},
                        "width": 800,
                        "height": 400,
                        "asset_type": "drawing",
                        "description": "A beautiful scenery.",
                        "slug": "beautiful-scenery",
                        "color": "#aabbcc",
                    },
                    {
                        "urls": {"regular": "https://example.com/image2.jpg"},
                    }
                ]
            }
        with patch.object(WebUnsplash_IrAttachment, '_fetch_unsplash_images', mocked_fetch_unsplash_images):
            result = self.env['ai.tool']._ai_tool_search_images('test query')['response']

        self.assertEqual(
            result, (
                'Here are some images from Unsplash that match your search query.\n'
                '- URL: "https://example.com/image1.jpg", Type: "drawing", Description: "A beautiful scenery.", Slug: "beautiful-scenery", Average color: "#aabbcc", Aspect ratio (W/H): 2.0\n'
                '- URL: "https://example.com/image2.jpg", Type: "photo", Description: "No description", Slug: "N/A", Average color: "N/A", Aspect ratio (W/H): N/A\n'
            ))

    def test_ai_tool_create_image_attachments(self):
        ai_session = self._create_ai_website_builder_session()
        invalid_attachment = self.env['ir.attachment'].create({
            'name': 'Website Image',
            'type': 'binary',
            'raw': PNG_B64,
            'mimetype': 'image/png',
            'public': True,
        })
        valid_attachment = invalid_attachment.copy({
            'res_model': 'discuss.channel',
            'res_id': ai_session.channel_id,
        })
        result = self.env['ai.tool']._ai_tool_create_image_attachments(
            [invalid_attachment.id, -1, valid_attachment.id])['response']
        self.assertIn(
            f"- ID: {invalid_attachment.id}, Not found. Please make sure the attachment was provided by the user.", result)
        self.assertIn(
            "- ID: -1, Not found. Please make sure the attachment was provided by the user.", result)
        self.assertIn(
            f"- ID: {valid_attachment.id}, URL: /web/image/{valid_attachment.id + 1}-33c042bd/Website%20Image", result)

    def test_localize_external_image_urls_stores_the_bytes_locally(self):
        source_url = "https://example.com/logo.png"

        with patch(_SESSION_SEND, return_value=_FakeResponse(PNG_RAW)) as requests_send:
            result = self.env["ir.attachment"]._localize_external_image_urls([source_url])

        self.assertEqual(requests_send.call_args.kwargs["allow_redirects"], False,
                         "Redirects must stay within the explicit redirect limit.")
        attachment = self.env["ir.attachment"].search([("name", "=", "logo.png")])
        self.assertEqual(len(attachment), 1)
        # The point of the localization: the image lives in Odoo, so the page does not
        # depend on the source host still serving it.
        self.assertEqual(attachment.raw.content, PNG_RAW)
        self.assertEqual(attachment.type, "binary")
        self.assertFalse(attachment.url)
        self.assertTrue(attachment.image_src.startswith(f"/web/image/{attachment.id}-"))
        self.assertEqual(result, {"sources": {source_url: attachment.image_src}, "errors": {}})

    def test_localize_external_image_urls_deduplicates_and_caps_the_batch(self):
        """The URL list comes from the browser, so its size must be bounded server side."""
        urls = [f"https://example.com/image{i}.png" for i in range(_MAX_IMAGES_PER_BATCH + 5)]

        with patch(_SESSION_SEND, return_value=_FakeResponse(PNG_RAW)) as requests_send:
            result = self.env["ir.attachment"]._localize_external_image_urls(
                # Duplicates must be downloaded once and reported for both occurrences.
                urls + urls[:3] + ["", "   ", None, 42],
            )

        self.assertEqual(requests_send.call_count, _MAX_IMAGES_PER_BATCH)
        self.assertEqual(len(result["sources"]), _MAX_IMAGES_PER_BATCH)
        self.assertEqual(result["errors"], {})

    def test_localize_external_image_urls_rejects_non_public_hosts(self):
        """Check the actual peer before sending HTTP data, for either scheme."""
        for scheme in ('http', 'https'):
            for address in ('127.0.0.1', '169.254.169.254', '10.1.2.3', '100.64.0.1',
                            '::1', '::ffff:127.0.0.1', '::ffff:100.64.0.1', '::ffff:224.0.0.1',
                            '224.0.0.1', 'ff02::1', '4000::1'):
                with self.subTest(scheme=scheme, address=address):
                    url = f"{scheme}://example.com/image.png"
                    with _mock_image_transport(peers=[address]) as (_connect, sockets):
                        result = self.env["ir.attachment"]._localize_external_image_urls([url])
                    self.assertIn("only publicly reachable hosts are allowed", result["errors"][url])
                    self.assertFalse(result["sources"])
                    sockets[0].sendall.assert_not_called()
                    sockets[0].close.assert_called_once_with()

    def test_localize_external_image_urls_rejects_non_http_schemes(self):
        result = self.env["ir.attachment"]._localize_external_image_urls([
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:image/png;base64,iVBORw0KGgo=",
        ])
        self.assertFalse(result["sources"])
        self.assertEqual(len(result["errors"]), 3)
        for error in result["errors"].values():
            self.assertIn("only HTTP(S) image URLs are supported", error)

    def test_localize_external_image_urls_stores_svg(self):
        """SVG is a supported image everywhere else in the editor, so it is here too.

        What keeps a scraped SVG from running on the website's origin is the
        ``default-src 'none'`` CSP served with every image response, not a check here.
        """
        url = "https://example.com/logo.svg"
        with patch(_SESSION_SEND, return_value=_FakeResponse(_SVG_RAW)):
            result = self.env["ir.attachment"]._localize_external_image_urls([url])

        attachment = self.env["ir.attachment"].search([("name", "=", "logo.svg")])
        self.assertEqual(len(attachment), 1)
        self.assertEqual(attachment.raw.content, _SVG_RAW)
        self.assertEqual(attachment.mimetype, "image/svg+xml")
        self.assertEqual(result, {"sources": {url: attachment.image_src}, "errors": {}})

    def test_localize_external_image_urls_rejects_html_sniffed_as_svg(self):
        """`guess_mimetype` calls anything containing "<svg" an SVG.

        An error page with an inline icon in it must not be stored as an image.
        """
        url = "https://example.com/logo.svg"
        page = b"<!DOCTYPE html><html><body>Not found <svg></svg></body></html>"
        with patch(_SESSION_SEND, return_value=_FakeResponse(page)):
            result = self.env["ir.attachment"]._localize_external_image_urls([url])

        self.assertIn("does not point to a supported image", result["errors"][url])
        self.assertFalse(self.env["ir.attachment"].search([("name", "=", "logo.svg")]))

    def test_localize_external_image_urls_leaves_no_attachment_behind_on_failure(self):
        url = "https://example.com/broken.png"
        with patch(_SESSION_SEND, return_value=_FakeResponse(b"not an image at all")):
            result = self.env["ir.attachment"]._localize_external_image_urls([url])

        self.assertIn("does not point to a supported image", result["errors"][url])
        self.assertFalse(self.env["ir.attachment"].search([("name", "=", "broken.png")]))

    def test_localize_external_image_urls_handles_streaming_failures(self):
        for exception in (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ContentDecodingError,
        ):
            with self.subTest(exception=exception.__name__):
                name = f"broken-stream-{exception.__name__}.png"
                broken_url = f"https://example.com/{name}"
                valid_url = f"https://example.com/valid-{exception.__name__}.png"

                def stream(*args, **kwargs):
                    yield PNG_RAW[:10]
                    raise exception("stream interrupted")

                response = requests.Response()
                response.status_code = 200
                response.raw = Mock()
                response.raw.stream.side_effect = stream
                with (
                    patch(_SESSION_SEND, side_effect=[response, _FakeResponse(PNG_RAW)]),
                    patch(_MONOTONIC, return_value=0),
                ):
                    result = self.env["ir.attachment"]._localize_external_image_urls([broken_url, valid_url])

                self.assertEqual(result["errors"], {broken_url: "image could not be reached."})
                self.assertEqual(list(result["sources"]), [valid_url])
                self.assertTrue(result["sources"][valid_url].startswith('/web/image/'))
                self.assertFalse(self.env["ir.attachment"].search([("name", "=", name)]))
                response.raw.close.assert_called_once_with()

    def test_localize_external_image_urls_revalidates_redirect_targets(self):
        for scheme, target_scheme in (('https', 'http'), ('http', 'https')):
            with self.subTest(scheme=scheme):
                url = f"{scheme}://example.com/redirect.png"
                redirect = _image_http_response(b'', 302, {'Location': f'{target_scheme}://images.example.com/image.png'})
                with _mock_image_transport([redirect], ['93.184.216.34', '10.1.2.3']) as (connect, sockets):
                    result = self.env["ir.attachment"]._localize_external_image_urls([url])
                self.assertIn("only publicly reachable hosts are allowed", result["errors"][url])
                self.assertEqual(connect.call_count, 2)
                sockets[0].sendall.assert_called_once()
                sockets[1].sendall.assert_not_called()

    def test_localize_external_image_urls_reuses_connections(self):
        for scheme, peer in (('http', '93.184.216.34'), ('https', '2606:4700:4700::1111')):
            with self.subTest(scheme=scheme):
                urls = [f'{scheme}://example.com/image.png', f'{scheme}://example.com/other.png']
                responses = [
                    _image_http_response(b'Redirecting', 302, {'Location': '/images/image.png'}),
                    _image_http_response(),
                    _image_http_response(),
                ]
                with (
                    _mock_image_transport(responses, [peer]) as (connect, sockets),
                    patch.dict('os.environ', {'HTTP_PROXY': 'http://proxy.example.com:8080',
                                              'HTTPS_PROXY': 'http://proxy.example.com:8080'}),
                    patch('requests.sessions.get_netrc_auth') as netrc_auth,
                ):
                    result = self.env['ir.attachment']._localize_external_image_urls(urls)
                self.assertFalse(result['errors'])
                self.assertEqual(list(result['sources']), urls)
                connect.assert_called_once()
                self.assertEqual(connect.call_args.args[0], ('example.com', 443 if scheme == 'https' else 80))
                self.assertEqual(sockets[0].getpeername.call_count, 3)
                self.assertEqual(sockets[0].sendall.call_count, 3)
                self.assertIn(b'GET /images/image.png HTTP/1.1', sockets[0].sendall.call_args_list[1].args[0])
                sockets[0].close.assert_called_once_with()
                netrc_auth.assert_not_called()

    def test_localize_external_image_urls_revalidates_reconnections(self):
        urls = ['https://example.com/image.png', 'https://example.com/other.png']
        with (
            _mock_image_transport([_image_http_response()], ['93.184.216.34', '10.1.2.3']) as (connect, sockets),
            patch('urllib3.connectionpool.is_connection_dropped', return_value=True),
        ):
            result = self.env['ir.attachment']._localize_external_image_urls(urls)
        self.assertEqual(list(result['sources']), urls[:1])
        self.assertIn('only publicly reachable hosts are allowed', result['errors'][urls[1]])
        self.assertEqual(connect.call_count, 2)
        sockets[1].sendall.assert_not_called()

    def test_localize_external_image_urls_handles_wrapped_tls_sockets(self):
        url = 'https://example.com/image.png'

        def wrap_socket(sock, **kwargs):
            wrapped = Mock(socket=sock, makefile=sock.makefile, sendall=sock.sendall,
                           close=sock.close, settimeout=sock.settimeout)
            return Mock(socket=wrapped, is_verified=True)

        with (
            _mock_image_transport([_image_http_response()]) as (_connect, sockets),
            patch('urllib3.connection._ssl_wrap_socket_and_match_hostname', side_effect=wrap_socket),
        ):
            result = self.env['ir.attachment']._localize_external_image_urls([url])
        self.assertFalse(result['errors'])
        self.assertEqual(list(result['sources']), [url])
        sockets[0].getpeername.assert_called_once_with()

    def test_localize_external_image_urls_limits_redirects(self):
        url = 'https://example.com/image.png'
        redirect = _image_http_response(b'', 302, {'Location': '/image.png'})
        with _mock_image_transport([redirect] * (_MAX_IMAGE_REDIRECTS + 1)) as (connect, sockets):
            result = self.env['ir.attachment']._localize_external_image_urls([url])
        self.assertEqual(result, {'sources': {}, 'errors': {url: 'too many redirects.'}})
        connect.assert_called_once()
        self.assertEqual(sockets[0].sendall.call_count, _MAX_IMAGE_REDIRECTS + 1)

    def test_localize_external_image_urls_bounds_redirect_bodies(self):
        url = 'https://example.com/image.png'
        for redirect in (
            _image_http_response(b'x' * 17, 302, {'Location': '/image.png'}),
            b'HTTP/1.1 302 Response\r\nLocation: /image.png\r\n\r\n' + b'x' * 17,
        ):
            with (
                _mock_image_transport([redirect]) as (_connect, sockets),
                patch(f'{_IR_ATTACHMENT}._MAX_IMAGE_BYTES', 16),
            ):
                result = self.env['ir.attachment']._localize_external_image_urls([url])
            self.assertFalse(result['sources'])
            self.assertIn('larger than', result['errors'][url])
            sockets[0].sendall.assert_called_once()
            sockets[0].close.assert_called_once_with()

    def test_localize_external_image_urls_caps_the_download_size(self):
        url = "https://example.com/huge.png"
        headers = {"content-length": str(50 * 1024 * 1024)}

        with patch(_SESSION_SEND, return_value=_FakeResponse(PNG_RAW, headers=headers)):
            result = self.env["ir.attachment"]._localize_external_image_urls([url])

        self.assertIn(
            f"larger than {_MAX_IMAGE_BYTES // (1024 * 1024)}MB", result["errors"][url])

    def test_localize_external_image_urls_stops_at_the_batch_deadline(self):
        """A slow host must not be able to hold a page save open for minutes."""
        urls = ["https://example.com/slow.png", "https://example.com/next.png"]

        with (
            patch(_SESSION_SEND, return_value=_FakeResponse(PNG_RAW)) as requests_send,
            # The first download exhausts the whole batch deadline.
            patch(_MONOTONIC, side_effect=[0, 0, _IMAGE_DOWNLOAD_BATCH_DEADLINE + 1]),
        ):
            result = self.env["ir.attachment"]._localize_external_image_urls(urls)

        self.assertEqual(requests_send.call_count, 1, "The second URL must not be attempted.")
        self.assertEqual(list(result["sources"]), urls[:1])
        self.assertIn("took too long", result["errors"][urls[1]])

    def test_ai_tool_custom_css(self):
        response_empty = "The user_custom_rules.scss file is empty (no custom CSS rules yet)."
        # The refinement CSS pass writes this file on every page build, so the
        # database cannot be assumed to start without custom rules.
        self.env['ai.tool']._ai_tool_write_custom_css("")
        self.assertEqual(self.env['ai.tool']._ai_tool_read_custom_css()['response'], response_empty)

        self.env['ai.tool']._ai_tool_write_custom_css("#test { color: red; }")
        self.assertEqual(self.env['ai.tool']._ai_tool_read_custom_css()['response'],
                         "#test { color: red; }")

        self.env['ai.tool']._ai_tool_write_custom_css("")
        self.assertEqual(self.env['ai.tool']._ai_tool_read_custom_css()['response'], response_empty)

        # Shouldn't crash when using css variables
        self.env['ai.tool']._ai_tool_write_custom_css("#test { background-color: var(--o-view-background-color); }")

    def test_ai_tool_get_current_brand_kit(self):
        self.assertEqual(
            self.env['ai.website.service']._get_current_brand_kit(),
            "Current palette: theme default (not customized). "
            "Current fonts: theme default (not customized).",
        )

        result = self.env['ai.tool']._ai_tool_apply_brand_kit(
            {'tool_request_confirmed': True},
            palette={
                'o_color_1': '#C83E2B', 'o_color_2': '#E8A856', 'o_color_3': '#F9F5EE',
                'o_color_4': '#FFFFFF', 'o_color_5': '#231B15',
            },
            typography={'heading_font': 'Fraunces', 'body_font': 'Plus Jakarta Sans'},
        )['response']
        self.assertIn("Applied brand kit", result)

        brand_kit = self.env['ai.website.service']._get_current_brand_kit()
        self.assertIn('#C83E2B', brand_kit)
        self.assertIn('#231B15', brand_kit)
        self.assertIn('Fraunces', brand_kit)
        self.assertIn('Plus Jakarta Sans', brand_kit)

    def test_ai_tool_custom_css_localizes_external_images(self):
        """Custom SCSS never reaches the editable, so the tool localizes it itself."""
        with patch(_SESSION_SEND, return_value=_FakeResponse(PNG_RAW)):
            result = self.env['ai.tool']._ai_tool_write_custom_css(
                '#test { background-image: url("https://example.com/hero.png"); }')['response']

        attachment = self.env["ir.attachment"].search([("name", "=", "hero.png")])
        self.assertEqual(len(attachment), 1)
        self.assertEqual(
            self.env['ai.tool']._ai_tool_read_custom_css()['response'],
            f'#test {{ background-image: url("{attachment.image_src}"); }}')
        self.assertEqual(result, "Custom CSS successfully written.")

    def test_ai_tool_custom_css_reports_images_it_could_not_localize(self):
        """A failed download must not lose the rule, but the agent has to hear about it."""
        with patch(_SESSION_SEND, return_value=_FakeResponse(b"not an image at all")):
            result = self.env['ai.tool']._ai_tool_write_custom_css(
                "#test { background-image: url(https://example.com/hero.png); }")['response']

        self.assertEqual(
            self.env['ai.tool']._ai_tool_read_custom_css()['response'],
            "#test { background-image: url(https://example.com/hero.png); }")
        self.assertIn("could not be copied into Odoo", result)
        self.assertIn("https://example.com/hero.png", result)

    def test_ai_tool_apply_invalid_css(self):
        with self.assertRaisesRegex(ValueError, "CSS content contains potentially dangerous patterns"):
            self.env['ai.tool']._ai_tool_write_custom_css(
                "@import 'https://evil.com/steal.css'; body { color: red; }"
            )

        with self.assertRaisesRegex(ValueError, "CSS content contains potentially dangerous patterns"):
            self.env['ai.tool']._ai_tool_write_custom_css(
                "@import url('https://evil.com/steal.css'); body { color: red; }"
            )

        with self.assertRaisesRegex(ValueError, "CSS content contains potentially dangerous patterns"):
            self.env['ai.tool']._ai_tool_write_custom_css(
                "body { background: url(\"javascript:alert(1)\"); }"
            )

        with (
            self.assertRaisesRegex(ValueError, "Invalid CSS"),
            self.assertLogs('odoo.addons.base.models.assetsbundle', level="WARNING")
        ):
            self.env['ai.tool']._ai_tool_write_custom_css("#test { : 15px; }")

        # We are preprocessing css in an external bundle, and we don't have
        # access to scss variables there
        with (
            self.assertRaisesRegex(ValueError, "Undefined variable"),
            self.assertLogs('odoo.addons.base.models.assetsbundle', level="WARNING")
        ):
            self.env['ai.tool']._ai_tool_write_custom_css("#test { background-color: $o-view-background-color; }")

        # This breaks when bundle rewrites relative url()s
        with (
            self.assertRaisesRegex(ValueError, "Invalid CSS"),
            self.assertLogs('odoo.addons.base.models.assetsbundle', level="WARNING")
        ):
            self.env['ai.tool']._ai_tool_write_custom_css('$img: "a.png"; #test { background: url($img); }')

    def test_ai_tool_apply_html_scripts_disabled(self):
        """With AI JavaScript off, any action carrying a <script> is refused."""
        tool_context = self._create_page_tool_context()
        with self.assertRaisesRegex(ValueError, "adding JavaScript is turned off"):
            self.env['ai.tool']._ai_tool_apply_html_to_page(tool_context, [{
                'zone': 'main',
                'mode': 'replace',
                'selector': '#target',
                'content': '<section><script data-ai-script-id="a">(() => {})();</script></section>',
            }])

        # Static markup still goes through.
        self.env['ai.tool']._ai_tool_apply_html_to_page(tool_context, [{
            'zone': 'main',
            'mode': 'replace',
            'selector': '#target',
            'content': '<section><p>Hello</p></section>',
        }])

        # A `javascript:` URL is a forbidden pattern, not something to sanitize away.
        with self.assertRaisesRegex(ValueError, "forbidden pattern"):
            self.env['ai.tool']._ai_tool_apply_html_to_page(tool_context, [{
                'zone': 'main',
                'mode': 'replace',
                'selector': '#target',
                'content': '<a href="javascript:alert(1)">click</a>',
            }])

    def test_ai_tool_apply_html_full_build_defers_to_client_tool(self):
        """A full-page build (zone=main, mode=replace, no selector) is handed off to the
        client for finalization instead of being applied directly."""
        tool_context = self._create_page_tool_context()
        target_page = {
            'main_object': {'model': 'website.page', 'id': 42},
            'location': '/about-us',
        }
        result = self.env['ai.tool'].with_context(
            current_view_info={'website_page': target_page},
        )._ai_tool_apply_html_to_page(tool_context, [{
            'zone': 'main',
            'mode': 'replace',
            'content': '<section><p>Hello</p></section>',
        }])
        self.assertEqual(result['client_tool']['name'], 'finalize_website_page')
        self.assertEqual(result['client_tool']['params']['target_page'], target_page)
        self.assertIn('<p>Hello</p>', result['client_tool']['params']['html'])
        self.assertIn('do not apply the page again', result['client_tool']['params']['note'])

        # A zone-scoped action bundled in the same call rides along in the client
        # tool's params — applied together with the finalized page, rather than as
        # a second tool call that could land before or after it.
        with patch.object(self.registry['res.users'], '_bus_send') as bus_send:
            result = self.env['ai.tool']._ai_tool_apply_html_to_page(tool_context, [
                {'zone': 'main', 'mode': 'replace', 'content': '<section><p>Hello</p></section>'},
                {'zone': 'main', 'mode': 'replace', 'selector': '#footer', 'content': '<footer></footer>'},
            ])
        bus_send.assert_not_called()
        self.assertEqual(result['client_tool']['params']['other_actions'], [
            {'zone': 'main', 'mode': 'replace', 'selector': '#footer', 'content': '<footer></footer>'},
        ])
        self.assertIn('applied immediately', result['client_tool']['params']['note'])

    def test_ai_tool_apply_html_names_the_page_it_edits(self):
        """The builder needs it to refuse edits meant for a page the user has left."""
        view_info = {
            "website_page": {
                "is_page_ai_editable": True,
                "location": "/about-us",
                "main_object": {"model": "website.page", "id": 42},
            },
        }
        actions = [{"zone": "main", "mode": "replace", "selector": "#target", "content": "<section><p>Hi</p></section>"}]
        tool_context = self._create_page_tool_context()

        with patch.object(self.env.registry["res.users"], "_bus_send") as bus_send:
            result = self.env["ai.tool"].with_context(
                current_view_info=view_info,
            )._ai_tool_apply_html_to_page(tool_context, actions)

        bus_send.assert_not_called()
        self.assertEqual(result['client_tool']['name'], 'website_apply_html')
        self.assertEqual(result['client_tool']['params'], {
            "actions": actions,
            "target_page": {
                "main_object": {"model": "website.page", "id": 42},
                "location": "/about-us",
            },
        })

    def test_ai_tool_set_webform_action(self):
        result = self.env['ai.tool']._ai_tool_set_webform_action(
            'send_mail', 'section.s_website_form',
            [{'name': 'email_to', 'value': 'someone@example.com'}])
        self.assertEqual(result['client_tool']['name'], 'website_set_form_action')
        self.assertEqual(result['client_tool']['params'], {
            'selector': 'section.s_website_form',
            'action_key': 'send_mail',
            'fields': [{'name': 'email_to', 'value': 'someone@example.com'}],
        })

        result = self.env['ai.tool']._ai_tool_set_webform_action('no_such_action', 'form', [])
        self.assertIn("Unknown form action 'no_such_action'", result)
        self.assertIn('send_mail', result,
                      "The error should list the available action keys.")

    def test_ai_webform_normalizer_bounces(self):
        """Each violation that needs the model to rewrite its HTML errors
        back through the tool result; the in-place repairs are covered by
        `test_ai_webform_normalizer_repairs_and_passes`."""
        self._patch_authorized_fields(self.WEBFORM_FIELDS)
        subject = self._form_field('<input class="s_website_form_input" name="subject"/>', label='Subject')
        cases = [
            # An empty name is as lost on submission as a missing one.
            ('nameless input', self._webform_content(
                '<div class="s_website_form_field">'
                '<input class="s_website_form_input" name=""/></div>'),
             r"without a name", {}),
            # e.g. the HTML-ism "number": the editor has no such field template.
            ('invalid data-type', self._webform_content(
                '<div class="s_website_form_field" data-type="number">'
                '<input class="s_website_form_input" name="Guests"/></div>'),
             r"data-type", {}),
            # One label-less field breaks the sidebar for the whole form.
            ('missing structural label', self._webform_content(
                '<div class="s_website_form_field" data-type="boolean">'
                '<div class="form-check">'
                '<input type="checkbox" class="s_website_form_input form-check-input" name="NDA" value="Yes"/>'
                '<label class="form-check-label s_website_form_check_label">I agree</label>'
                '</div></div>'),
             r"s_website_form_label", {}),
            # A native date input posts a raw ISO value the insert cannot
            # parse; only the picker wrapper's value gets serialized.
            ('native date input', self._webform_content(
                self._form_field('<input type="date" class="s_website_form_input" name="When"/>', 'date')),
             r"native date inputs", {}),
            ('date field without its picker wrapper', self._webform_content(
                self._form_field('<input type="text" class="s_website_form_input" name="When"/>', 'date')),
             r"picker", {}),
            # The submit validator matches accept entries against MIME types:
            # an extension list rejects every upload.
            ('file accept extension list', self._webform_content(
                self._form_field('<input type="file" class="s_website_form_input" name="CV" accept=".pdf,.doc"/>', 'binary')),
             r"accept value\(s\) \.pdf, \.doc", {}),
            # A bound choice input posts its option value verbatim: it must be
            # a selection key (not the label) or a record id (not a name).
            ('selection option with the label as value',
             self._webform_content(self._radio('Medium')), r"'0' = Low", {}),
            ('relational option with a name as value',
             self._webform_content(self._select('partner_id', 'Bob')), r"numeric id", {}),
            ('hidden preset with a name as value', self._webform_content(
                '<div class="s_website_form_field s_website_form_dnone">'
                '<input type="hidden" class="s_website_form_input" name="partner_id" value="Bob"/></div>'),
             r"numeric id", {}),
            # 'model' is required but not form-writable: the server fills it,
            # so only 'subject' may be demanded (the trailing "-" pins the
            # missing list to exactly that).
            ('missing required writable field', self._webform_content(
                self._form_field('<input class="s_website_form_input" name="Question"/>')),
             r"mandatory field\(s\) subject -", {}),
            # The palette only ever nests the form section inside a wrapper
            # snippet section; page-level placements always bounce.
            ('form section inserted at page level', self._webform_content(subject),
             r"nested inside a wrapper", {'mode': 'after', 'selector': 'section:last-child'}),
            ('form section replacing a whole zone', self._webform_content(subject),
             r"nested inside a wrapper", {'selector': ''}),
            # Same zone, named rather than left empty.
            ('form section replacing a named whole zone', self._webform_content(subject),
             r"nested inside a wrapper", {'selector': '#wrap'}),
            # The end message is all the visitor sees after submitting.
            ('message mode without an end message',
             self._webform_content(subject, 'data-success-mode="message"'),
             r"s_website_form_end_message", {}),
            ('message mode with an empty end message',
             self._webform_content(subject, 'data-success-mode="message"',
                                   end_message='<div class="s_website_form_end_message d-none"></div>'),
             r"s_website_form_end_message", {}),
            ('end message outside the form\'s parent',
             self._webform_content(subject, 'data-success-mode="message"')
             + '<div class="s_website_form_end_message d-none"><p>Thanks!</p></div>',
             r"s_website_form_end_message", {}),
        ]
        for label, content, pattern, action in cases:
            with self.subTest(label), self.assertRaisesRegex(ValueError, pattern):
                self._apply_webform(content, **action)

    # Deterministic mail.mail fields for the normalizer tests. 'model' is
    # required but not form-writable (blacklisted): it must never be demanded.
    WEBFORM_FIELDS = {
        'email_to': {'type': 'char', 'string': 'Email To'},
        'email_from': {'type': 'char', 'string': 'Email From'},
        'subject': {'type': 'char', 'string': 'Subject', 'required': True},
        'model': {'type': 'char', 'string': 'Related Model', 'required': True},
        'priority': {'type': 'selection', 'string': 'Priority',
                     'selection': [('0', 'Low'), ('1', 'Medium')]},
        'partner_id': {'type': 'many2one', 'string': 'Customer'},
    }

    def _patch_authorized_fields(self, fields):
        self.patch(self.env.registry['ir.model'], 'get_authorized_fields',
                   lambda _self, model_name, property_origins=None: dict(fields))

    def _webform_content(self, fields_html, form_attrs='', email_to='a@b.c', end_message=''):
        return (
            '<section class="s_website_form"><div class="container-fluid">'
            f'<form data-model_name="mail.mail" {form_attrs}>'
            '<div class="s_website_form_rows">'
            '<div class="s_website_form_field s_website_form_dnone">'
            f'<input type="hidden" class="s_website_form_input" name="email_to" value="{email_to}"/></div>'
            f'{fields_html}'
            '</div>'
            '<div class="s_website_form_submit"><span id="s_website_form_result"></span>'
            '<a class="s_website_form_send">Send</a></div>'
            f'</form>{end_message}</div></section>'
        )

    def _form_field(self, inner, data_type='char', label='Field'):
        return (
            f'<div class="s_website_form_field" data-type="{data_type}">'
            f'<label class="s_website_form_label"><span class="s_website_form_label_content">{label}</span></label>'
            f'{inner}</div>'
        )

    def _radio(self, value):
        return self._form_field(
            '<div class="row s_website_form_multiple" data-name="priority">'
            '<div class="radio"><div class="form-check">'
            f'<input type="radio" class="s_website_form_input form-check-input" name="priority" value="{value}" id="o1"/>'
            '<label class="form-check-label s_website_form_check_label" for="o1">Whenever</label>'
            '</div></div></div>', 'selection', 'Priority')

    def _select(self, name, value):
        return self._form_field(
            f'<select class="form-select s_website_form_input" name="{name}" id="o2">'
            f'<option value=""></option><option value="{value}">X</option></select>',
            'many2one', 'Customer')

    def _apply_webform(self, content, **action):
        # A targeted replace of the form section itself: the one case where a
        # top-level s_website_form fragment root is legitimate.
        return self.env['ai.tool']._ai_tool_apply_html_to_page(self._create_page_tool_context(), [{
            'zone': 'main',
            'mode': 'replace',
            'selector': 'section.s_website_form',
            'content': content,
            **action,
        }])

    def test_ai_webform_normalizer_repairs_and_passes(self):
        """Purely mechanical details are repaired in place, and a form that
        follows the rules is applied."""
        self._patch_authorized_fields(self.WEBFORM_FIELDS)
        action = {
            'zone': 'main',
            'mode': 'replace',
            'selector': 'section.s_website_form',
            'content': (
                '<section class="s_website_form">'
                '<form data-model_name="mail.mail" data-success-mode="confetti">'
                '<div class="s_website_form_rows">'
                '<div class="s_website_form_field s_website_form_dnone">'
                '<input type="hidden" class="s_website_form_input" name="email_to" value="a@b.c"/></div>'
                # A bound field wrongly marked custom and a custom field
                # unmarked, their input ids copied verbatim from a snippet.
                '<div class="s_website_form_field s_website_form_custom" data-type="char">'
                '<label class="s_website_form_label" for="dup"><span class="s_website_form_label_content">Your Email</span></label>'
                '<input class="s_website_form_input" name="email_from" id="dup"/></div>'
                '<div class="s_website_form_field" data-type="char">'
                '<label class="s_website_form_label" for="dup"><span class="s_website_form_label_content">Nickname</span></label>'
                '<input class="s_website_form_input" name="Nickname" id="dup"/></div>'
                + self._form_field('<input class="s_website_form_input" name="subject"/>', label='Subject')
                + self._form_field(
                    '<div class="s_website_form_date input-group date">'
                    '<input type="text" class="form-control datetimepicker-input s_website_form_input" name="When"/>'
                    '</div>', 'date')
                + self._form_field('<input type="file" class="s_website_form_input" name="CV" accept="image/*"/>', 'binary')
                + self._radio('1') + self._select('partner_id', '7') + self._select('Topic', 'Anything')
                + '</div>'
                '<div class="s_website_form_submit">'
                '<a class="s_website_form_send">Send</a></div>'
                '</form></section>'
            ),
        }
        result = self.env['ai.tool']._ai_tool_apply_html_to_page(self._create_page_tool_context(), [action])
        self.assertEqual(result['client_tool']['name'], 'website_apply_html')
        root = lxml_html.fromstring(action['content'])

        self.assertTrue(
            root.xpath('//div[contains(@class, "s_website_form_submit")]/span[@id="s_website_form_result"]'),
            "The missing submission status span should be injected.")

        self.assertFalse(
            root.xpath('//div[contains(@class, "s_website_form_custom")]/input[@name="email_from"]'),
            "A field bound to a model field must lose the custom marker.")
        self.assertTrue(
            root.xpath('//div[contains(@class, "s_website_form_custom")]/input[@name="Nickname"]'),
            "A field with an unknown name must gain the custom marker.")

        ids = root.xpath('//input[not(@type="hidden")]/@id | //select/@id')
        self.assertNotIn('dup', ids)
        self.assertEqual(len(set(ids)), len(ids), "Copied duplicate input ids must be regenerated.")
        for name in ('email_from', 'Nickname'):
            field = root.xpath(f'//input[@name="{name}"]/parent::div')[0]
            self.assertEqual(field.xpath('label/@for'), field.xpath('input/@id'),
                             "Labels must point at their field's regenerated input id.")

        # Missing file count/size limits render as a broken "0 MB": stamped.
        self.assertIn('data-max-files-number="1"', action['content'])
        self.assertIn('data-max-file-size="64"', action['content'])
        form = root.xpath('//form')[0]
        self.assertEqual(form.get('data-success-mode'), 'redirect',
                         "An invalid success mode falls back to redirect.")
        self.assertEqual(form.get('data-success-page'), '/contactus-thank-you')

        # Nested inside a wrapper snippet section, page-level placements pass.
        subject = self._form_field('<input class="s_website_form_input" name="subject"/>', label='Subject')
        wrapped = ('<section class="s_title_form"><div class="o_container_small">'
                   f'{self._webform_content(subject)}</div></section>')
        placements = {
            'website_apply_html': {'mode': 'after', 'selector': 'section:last-child'},
            # An empty selector on the main zone is a full-page build, which
            # goes to the client for finalization rather than a plain apply.
            'finalize_website_page': {'selector': ''},
        }
        for tool_name, placement in placements.items():
            result = self._apply_webform(wrapped, **placement)
            self.assertEqual(result['client_tool']['name'], tool_name)

        # Message mode with a real end message next to the form passes.
        result = self._apply_webform(self._webform_content(
            subject, 'data-success-mode="message"',
            end_message='<div class="s_website_form_end_message d-none"><p>Thanks!</p></div>'))
        self.assertEqual(result['client_tool']['name'], 'website_apply_html')

    def test_ai_tool_get_webform_info(self):
        result = self.env['ai.tool']._ai_tool_get_webform_info('')
        self.assertIn('send_mail', result,
                      "The no-key form should list the available actions.")
        self.assertIn('mail.mail', result)

        result = self.env['ai.tool']._ai_tool_get_webform_info('no_such_action')
        self.assertIn("Unknown form action 'no_such_action'", result)
        self.assertIn('send_mail', result,
                      "The error should list the available action keys.")

        self._patch_authorized_fields(self.WEBFORM_FIELDS)
        result = self.env['ai.tool']._ai_tool_get_webform_info('send_mail')
        self.assertIn('"mail.mail"', result)
        # The model can only write valid option values if it has seen the
        # selection keys, not just the labels.
        self.assertIn("'0' = Low, '1' = Medium", result)
        self.assertIn('chosen by the user', result,
                      "The send-mail action must flag the recipient as the user's choice.")

    def test_ai_tool_request_ai_scripts_scopes(self):
        """The scripts can be inserted only in the allowed scope."""
        ai_tool = self.env['ai.tool']
        website = self.env['ai.website.service']._current_website()
        script_action = [{
            'zone': 'footer',
            'mode': 'replace',
            'content': '<section><script data-ai-script-id="a">(() => {})();</script></section>',
        }]

        tool_context = self._create_page_tool_context()
        with self.assertRaisesRegex(ValueError, "scope must be"):
            ai_tool._ai_tool_request_ai_scripts(tool_context, 'everywhere')
        self.assertFalse(website.ai_allow_scripts)

        ai_tool._ai_tool_request_ai_scripts(tool_context, 'chat')
        self.assertEqual(tool_context['state'], {'website_ai_allow_scripts': True})
        self.assertFalse(website.ai_allow_scripts)

        # The chat that was granted the permission can write scripts; another one cannot.
        self.assertEqual(
            ai_tool._ai_tool_apply_html_to_page(tool_context, script_action)['client_tool']['name'],
            'website_apply_html',
        )
        with self.assertRaisesRegex(ValueError, "adding JavaScript is turned off"):
            ai_tool._ai_tool_apply_html_to_page({'state': {}}, script_action)

        website_context = self._create_page_tool_context()
        ai_tool._ai_tool_request_ai_scripts(website_context, 'website')
        self.assertTrue(website.ai_allow_scripts)
        self.assertEqual(
            ai_tool._ai_tool_apply_html_to_page({'state': {}}, script_action)['client_tool']['name'],
            'website_apply_html',
        )

    def test_ai_tool_get_website_menus(self):
        website = self.env['ai.website.service']._current_website()
        menu = self.env['website.menu'].create({
            'name': 'Test Menu',
            'url': '/test-menu',
            'website_id': website.id,
            'parent_id': website.menu_id.id,
        })
        submenu = self.env['website.menu'].create({
            'name': 'Test Submenu',
            'url': '/test-submenu',
            'website_id': website.id,
            'parent_id': menu.id,
        })
        result = self.env['ai.tool']._ai_tool_get_website_menus()['response']
        self.assertIn(f'- ID: {menu.id}, Name: "Test Menu", URL: "#"', result,
                      "The menu tree should list the menu items with their IDs; a parent item's URL becomes '#'.")
        self.assertIn(f'    - ID: {submenu.id}, Name: "Test Submenu", URL: "/test-submenu"', result,
                      "Sub-menu items should be indented under their parent.")
        self.assertIn("# Website pages", result,
                      "The result should include the list of website pages.")
        self.assertIn('- URL: "/contactus", Name: "', result,
                      "Default pages such as /contactus should be listed.")

    def test_ai_tool_edit_website_menus_confirmation(self):
        tool_context = {'tool_request_confirmed': False}
        result = self.env['ai.tool']._ai_tool_edit_website_menus(tool_context, [
            {'type': 'create', 'name': 'Contact', 'url': 'contactus'},
        ])
        self.assertIsNone(result, "The tool should not apply anything before the user confirms.")
        self.assertEqual(tool_context['user_input_request']['type'], 'confirmation')
        self.assertFalse(
            self.env['website.menu'].search([('name', '=', 'Contact')]),
            "No menu item should be created before the user confirms.",
        )

    def test_ai_tool_edit_website_menus(self):
        Menu = self.env['website.menu']
        website = self.env['ai.website.service']._current_website()
        client_call = self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
            {'type': 'create', 'name': 'Contact', 'url': 'contactus'},
            {'type': 'create', 'name': 'About', 'temp_id': 'new_about'},
            {'type': 'create', 'name': 'Team', 'url': '/team', 'parent_temp_id': 'new_about'},
            {'type': 'create', 'name': 'Email us', 'url': 'info@example.com'},
        ])
        result = client_call['client_tool']['params']
        self.assertIn("Menu operations applied successfully:", result)
        self.assertIn("Here is the updated menu structure:", result,
                      "The result should include the updated menu tree so the AI knows the new IDs.")

        contact = Menu.search([('name', '=', 'Contact'), ('website_id', '=', website.id)])
        self.assertEqual(contact.url, '/contactus',
                         "The URL should be normalized to the matched page URL.")
        self.assertTrue(contact.page_id, "The menu should be linked to the page matching its URL.")

        about = Menu.search([('name', '=', 'About'), ('website_id', '=', website.id)])
        team = Menu.search([('name', '=', 'Team'), ('website_id', '=', website.id)])
        self.assertEqual(team.parent_id, about,
                         "parent_temp_id should nest the item under the menu created earlier in the same call.")
        self.assertEqual(about.url, '#', "A parent menu item should have '#' as URL.")

        email_menu = Menu.search([('name', '=', 'Email us'), ('website_id', '=', website.id)])
        self.assertEqual(email_menu.url, 'info@example.com')
        self.assertEqual(email_menu._clean_url(), 'mailto:info@example.com',
                         "Email URLs should render as mailto links.")

        # Update: rename, re-point, nest and un-nest
        self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
            {'type': 'update', 'menu_id': contact.id, 'name': 'Reach Us', 'url': 'https://example.com', 'new_window': True},
            {'type': 'update', 'menu_id': email_menu.id, 'parent_menu_id': about.id},
        ])
        self.assertEqual(contact.name, 'Reach Us')
        self.assertEqual(contact.url, 'https://example.com')
        self.assertTrue(contact.new_window)
        self.assertFalse(contact.page_id, "Pointing to an external URL should unlink the page.")
        self.assertEqual(email_menu.parent_id, about)

        self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
            {'type': 'update', 'menu_id': email_menu.id, 'parent_menu_id': 0},
        ])
        self.assertEqual(email_menu.parent_id, website.menu_id,
                         "parent_menu_id 0 should move the item back to the top level.")

        # Delete a parent: children go with it
        self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
            {'type': 'delete', 'menu_id': about.id},
        ])
        self.assertFalse(about.exists())
        self.assertFalse(team.exists(), "Deleting a menu item should also delete its sub-items.")

    def test_ai_tool_edit_website_menus_invalid(self):
        website = self.env['ai.website.service']._current_website()

        with self.assertRaisesRegex(ValueError, "not found on the current website"):
            self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
                {'type': 'delete', 'menu_id': -1},
            ])

        with self.assertRaisesRegex(ValueError, "root menu"):
            self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
                {'type': 'update', 'menu_id': website.menu_id.id, 'name': 'Hacked'},
            ])

        with self.assertRaisesRegex(ValueError, '"name" is required'):
            self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
                {'type': 'create', 'url': '/no-name'},
            ])

        with self.assertRaisesRegex(ValueError, "Unknown parent_temp_id"):
            self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
                {'type': 'create', 'name': 'Orphan', 'parent_temp_id': 'missing'},
            ])

        with self.assertRaisesRegex(ValueError, "Too many operations"):
            self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
                {'type': 'create', 'name': f'Menu {i}'} for i in range(51)
            ])

        # Model constraints (e.g. two-level nesting) are reported with
        # guidance, and a failing batch is rolled back entirely.
        parent_a = self.env['website.menu'].create({
            'name': 'Parent A',
            'website_id': website.id,
            'parent_id': website.menu_id.id,
        })
        parent_b = self.env['website.menu'].create({
            'name': 'Parent B',
            'website_id': website.id,
            'parent_id': website.menu_id.id,
        })
        child_a = self.env['website.menu'].create({
            'name': 'Child of A',
            'url': '/child-a',
            'website_id': website.id,
            'parent_id': parent_a.id,
        })
        with self.assertRaisesRegex(ValueError, "is itself a sub-item"):
            self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
                {'type': 'create', 'name': 'Too Deep', 'parent_menu_id': child_a.id},
            ])

        with self.assertRaisesRegex(ValueError, "has sub-items, so it cannot be nested"):
            self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
                {'type': 'update', 'menu_id': parent_a.id, 'parent_menu_id': parent_b.id},
            ])

        with self.assertRaisesRegex(ValueError, "None of the operations were applied"):
            self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
                {'type': 'create', 'name': 'Survivor'},
                # Invalid: parent_a already has sub-items
                {'type': 'update', 'menu_id': parent_a.id, 'parent_menu_id': parent_b.id},
            ])
        self.assertEqual(parent_a.parent_id, website.menu_id,
                         "The invalid nesting must not be applied.")
        self.assertFalse(self.env['website.menu'].search([('name', '=', 'Survivor')]),
                         "A failing batch must be rolled back entirely.")

        other_website = self.env['website'].create({'name': 'Other Website'})
        other_menu = self.env['website.menu'].create({
            'name': 'Other Menu',
            'url': '/other',
            'website_id': other_website.id,
            'parent_id': other_website.menu_id.id,
        })
        with self.assertRaisesRegex(ValueError, "not found on the current website"):
            self.env['ai.tool']._ai_tool_edit_website_menus({'tool_request_confirmed': True}, [
                {'type': 'delete', 'menu_id': other_menu.id},
            ])
        self.assertTrue(other_menu.exists(),
                        "Menus of other websites must not be editable.")

    def test_ai_tool_create_page_with_menu(self):
        tool_context = self._create_page_tool_context()
        result = self.env['ai.tool']._ai_tool_create_page(
            tool_context, 'AI Tool Page With Menu', add_to_menu=True,
        )

        page = self.env['website.page'].search([('url', '=', '/ai-tool-page-with-menu')])
        self.assertTrue(page)
        self.assertTrue(page.menu_ids)
        client_tool = result['client_tool']
        self.assertEqual(client_tool['name'], 'ai_website_navigate_to_edit')
        self.assertEqual(client_tool['params']['url'], page.url)
        self.assertFalse(client_tool['params']['save'])
        self.assertEqual(tool_context['state']['page_url_pending_html'], page.url)

    def test_ai_tool_create_page_refuses_when_previous_page_has_no_content(self):
        tool_context = self._create_page_tool_context()
        tool = self.env['ai.tool']
        first_page = tool._ai_tool_create_page(tool_context, 'AI Tool Page First')
        first_page_url = first_page['client_tool']['params']['url']

        # The client always navigates to the page it was just told to create
        # before the next tool call, so its reported location is that page's.
        result = tool.with_context(
            current_view_info={'website_page': {'location': first_page_url}},
        )._ai_tool_create_page(tool_context, 'AI Tool Page Second')

        self.assertIn('Cannot create another page yet', result)
        self.assertFalse(self.env['website.page'].search([
            ('url', '=', '/ai-tool-page-second'),
        ]))

    def test_ai_tool_apply_html_to_page_clears_pending_state(self):
        tool_context = self._create_page_tool_context()
        tool = self.env['ai.tool']
        tool._ai_tool_create_page(tool_context, 'AI Tool Page Third')
        self.assertIn('page_url_pending_html', tool_context['state'])

        tool._ai_tool_apply_html_to_page(tool_context, [{
            'zone': 'main', 'mode': 'replace', 'content': '<section></section>',
        }])

        self.assertNotIn('page_url_pending_html', tool_context['state'])

    def test_ai_tool_create_page_without_menu(self):
        tool_context = self._create_page_tool_context()
        self.env['ai.tool']._ai_tool_create_page(
            tool_context, 'AI Tool Page Without Menu', add_to_menu=False,
        )

        page = self.env['website.page'].search([('url', '=', '/ai-tool-page-without-menu')])
        self.assertTrue(page)
        self.assertFalse(page.menu_ids)

    def test_ai_tool_create_page_asks_confirmation_when_unsaved_changes(self):
        tool_context = self._create_page_tool_context()
        result = self.env['ai.tool'].with_context(
            current_view_info={'website_page': {'pending_changes': True}},
        )._ai_tool_create_page(tool_context, 'AI Tool Page With Unsaved Changes')

        self.assertIsNone(result)
        self.assertEqual(tool_context['user_input_request']['type'], 'confirmation')
        choice_values = {choice['value'] for choice in tool_context['user_input_request']['choices']}
        self.assertEqual(choice_values, {UserInputResponse.CONFIRM_ONCE, UserInputResponse.AUTO_CONFIRM, UserInputResponse.DECLINE})
        self.assertFalse(self.env['website.page'].search([
            ('url', '=', '/ai-tool-page-with-unsaved-changes'),
        ]))

    def test_ai_tool_create_page_saves_changes_on_confirmation(self):
        tool_context = self._create_page_tool_context()
        tool_context['tool_request_confirmed'] = True
        tool = self.env['ai.tool'].with_context(
            current_view_info={'website_page': {'pending_changes': True}},
        )
        result = tool._ai_tool_create_page(tool_context, 'AI Tool Page Save Changes')

        page = self.env['website.page'].search([('url', '=', '/ai-tool-page-save-changes')])
        self.assertTrue(page)
        client_tool = result['client_tool']
        self.assertEqual(client_tool['name'], 'ai_website_navigate_to_edit')
        self.assertEqual(client_tool['params']['url'], page.url)
        self.assertTrue(client_tool['params']['save'])

    def test_ai_tool_get_site_profile(self):
        self.env['website'].new_page(name='Profile Test Page', add_menu=True)

        result = self.env['ai.tool']._ai_tool_get_site_profile()
        self.assertIn('Here is the site profile:', result)

        profile = json.loads(result.split('```json\n', 1)[1].rsplit('```', 1)[0])
        self.assertIn('website_name', profile)
        self.assertIn('company', profile)
        self.assertIn('menu_tree', profile)
        self.assertIn('Profile Test Page', [page['name'] for page in profile['pages']])

    def test_ai_tool_get_page_html(self):
        self.env['website'].new_page(name='Page Html Test', add_menu=False)

        result = self.env['ai.tool']._ai_tool_get_page_html('/page-html-test')
        self.assertIn('Here is the HTML content of the /page-html-test:', result)
        self.assertIn('<div id="wrap"', result)

        result = self.env['ai.tool']._ai_tool_get_page_html()
        self.assertIn('Here is the HTML content of the homepage:', result)

        shared_page = self.env['website'].new_page(name='Shared Page Html Test', add_menu=False)
        self.env['website.page'].browse(shared_page['page_id']).website_id = False
        result = self.env['ai.tool']._ai_tool_get_page_html('/shared-page-html-test')
        self.assertIn('Here is the HTML content of the /shared-page-html-test:', result)

        result = self.env['ai.tool']._ai_tool_get_page_html('/does-not-exist')
        self.assertEqual(result, 'No page found at URL: /does-not-exist')
