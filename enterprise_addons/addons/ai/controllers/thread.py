# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import secrets
from textwrap import dedent

from odoo import http

from odoo.addons.mail.controllers.thread import ThreadController
from odoo.addons.mail.tools.discuss import add_guest_to_context
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.tools import hmac, str2bool

from ..utils.ai_utils import ODOO_AI_COMPLETION_CALLBACK_PATH, UserInputResponse
from ..utils.types import CompletionFailure, CompletionSuccess, PendingInteractionResponse, SessionResponse


_logger = logging.getLogger(__name__)


CHANNEL_NAME_INSTRUCTIONS = dedent("""
    You are a conversation title generator.
    You will be given the first user query from a conversation between a user and a LLM.
    Using that message and by predicting how the conversation will evolve,
    generate a title for the conversation describing the topic/theme of it.
    Use as few words as possible, because the title will be shown in a limited space.
    Your reply will be inserted as is, so don't add any commentary or a header, just the title.
""")


class AIThreadController(ThreadController):
    def _get_browser_context_snapshot(self, session, current_view_info, ai_session_identifier):
        """Add browser metadata while retaining the current request's actor."""
        context = self._extend_context(dict(self.env.context))
        context['ai_session_identifier'] = ai_session_identifier
        if current_view_info is not None:
            context['current_view_info'] = current_view_info
        snapshot = session._get_request_context_snapshot(context)
        if snapshot.get('active_company_ids'):
            snapshot['allowed_company_ids'] = snapshot['active_company_ids']
        return snapshot

    def _get_channel_ai_session(self, channel):
        return self.env["ai.session"].sudo().search([("channel_id", "=", channel.id), ("parent_session_id", "=", False)])

    @staticmethod
    def _validate_session_request_company_access(env, context_snapshot):
        accessible_company_ids = frozenset(env.user.company_ids.ids)
        for key in ("allowed_company_ids", "active_company_ids"):
            if any(
                company_id not in accessible_company_ids
                for company_id in context_snapshot.get(key, ())
            ):
                raise AccessError(env._(
                    "Your company access changed while this AI response was running."
                ))

    @http.route(
        ["/ai/start_session_advance"],
        type="jsonrpc",
        methods=["POST"],
        auth="public",
    )
    @add_guest_to_context
    def start_session_advance(
        self, channel_id, mail_message_id, current_view_info=None,
        ai_session_config=None, ai_session_identifier=None, debug=False,
    ) -> SessionResponse:
        env = self.env
        ai_session_config = ai_session_config or {}

        channel = env['discuss.channel'].search([('id', '=', channel_id)])
        if not channel or not channel.sudo().ai_agent_id:
            raise MissingError(env._("AI session expired. Please start a new session."))
        session = self._get_channel_ai_session(channel)
        if len(session) != 1:
            raise MissingError(env._("AI session expired. Please start a new session."))
        context_snapshot = self._get_browser_context_snapshot(session, current_view_info, ai_session_identifier)
        # A new user message takes over the chat; automation-only restrictions must not carry over.
        context_snapshot.pop("ai_automation_run", None)
        context_snapshot['debug'] = str2bool(debug)
        http.request.update_context(**context_snapshot)
        env = self.env
        session = session.with_env(env).sudo()
        origin_message = self._get_message_with_access(mail_message_id)
        if not origin_message or origin_message.channel_id != channel:
            raise MissingError(env._("The AI prompt message was not found."))
        message = origin_message._convert_to_parts()
        channel_name_message = message
        should_name_channel = (
            env.user._is_internal()
            and channel.channel_type == "ai_chat"
            and channel.message_count == 1
        )
        ai_prompt_button_ref = ai_session_config.get('ai_prompt_button_ref')
        if env.user._is_internal() and ai_prompt_button_ref:
            prompt_button = env['ai.prompt.button'].search([
                ('id', '=', ai_prompt_button_ref),
            ]) if isinstance(ai_prompt_button_ref, int) else env.ref(
                ai_prompt_button_ref, raise_if_not_found=False,
            )
            message = prompt_button._render_prompt(session.res_id)
        if unavailable_message := session._get_session_advance_unavailable_message():
            session._post_ai_response(unavailable_message)
            return {'loop_state': session.loop_state}
        if session.loop_state != 'ready':
            if not (message and session.loop_state in (
                'waiting_confirmation', 'waiting_answer', 'waiting_client_result', 'waiting_external_result',
            ) and session.pending_tool_call):
                raise UserError(env._("The AI is already responding in this chat."))
            if any('child_session_id' in result for result in session.pending_tool_call.get('pending_results', [])):
                raise UserError(env._("The AI is still waiting for its agents."))
            session._abort_pending_tools()
        session.request_context = context_snapshot
        session.update_session_config(ai_session_config)
        session._submit_agent_request(message)
        if should_name_channel:
            try:
                title_session = env["ai.session"].sudo().create({'parent_session_id': session.id})
                title_session._save_and_submit_request(
                    {
                        "messages": [{"role": "user", "content": channel_name_message}],
                        "instructions": CHANNEL_NAME_INSTRUCTIONS,
                        "tools": [],
                        "usage": "channel_name",
                    },
                    callback_type="channel_name",
                    request_round=1,
                    request_round_limit=1,
                    state={},
                )
            except Exception:  # noqa: BLE001
                _logger.exception("Failed to submit the AI channel name request")
        return {'loop_state': session.loop_state}

    @http.route(
        ODOO_AI_COMPLETION_CALLBACK_PATH,
        type='json2',
        auth='public',
        methods=['POST'],
        save_session=False,
    )
    def completion_result_ready(self, request_uuid: str, llm_result, llm_error, signature):
        session = self.env['ai.session'].sudo().search([
            ('request_uuid', '=', request_uuid),
            ('loop_state', '=', 'waiting_model'),
        ], limit=1)
        if not session:
            return None
        expected_signature = hmac(None, "odoo_ai-webhook", (
            request_uuid,
            llm_result,
            llm_error,
        ), secret=session.request_webhook_secret)
        if not signature or not secrets.compare_digest(signature, expected_signature):
            return None
        completion_result: CompletionSuccess | CompletionFailure
        if llm_result is False:
            completion_result = {'kind': 'failure', 'code': 'request_failed'}
        else:
            completion_result = {'kind': 'success', 'message': llm_result['result']}
        context = session.request_context or {}
        guest_id = session.request_guest_id.id
        http.request.update_env(user=session.request_user_id.id, context=context, su=False)
        if guest_id:
            http.request.update_context(guest=self.env['mail.guest'].browse(guest_id))
        # Rebuild the conversation recordset, which cannot be saved in the JSON context.
        http.request.update_context(discuss_channel=self.env['discuss.channel'].browse(session.channel_id.id))
        session = session.with_env(self.env).sudo()
        self._validate_session_request_company_access(session.env, session.request_context or {})
        match session.state['callback_type']:
            case 'agent_loop':
                session._continue_agent_loop(completion_result)
            case 'channel_name':
                session._continue_channel_name(completion_result)

    @http.route(
        "/ai/resume_pending_interaction",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
    )
    @add_guest_to_context
    def resume_pending_interaction(
        self, channel_id, session_id, resume_token, response: PendingInteractionResponse,
        current_view_info=None, ai_session_config=None, ai_session_identifier=None, debug=False,
    ) -> SessionResponse:
        env = self.env
        session = env['ai.session'].sudo().browse(session_id).exists()
        if not session or session._root_session().channel_id.id != channel_id:
            raise AccessError(env._("This AI interaction is not available."))

        channel = env["discuss.channel"].search([("id", "=", channel_id)], limit=1)
        if not channel or not channel.sudo().ai_agent_id:
            raise AccessError(env._("This AI interaction is not available."))
        context_snapshot = self._get_browser_context_snapshot(session, current_view_info, ai_session_identifier)
        context_snapshot['debug'] = str2bool(debug)
        http.request.update_context(**context_snapshot)
        session = session.with_env(self.env).sudo()
        interaction_consumed = True
        if session.loop_state in (
            'waiting_confirmation', 'waiting_answer', 'waiting_client_result', 'waiting_external_result',
        ) and secrets.compare_digest(resume_token, session.resume_token):
            session._resume_pending_interaction(
                response, ai_session_config=ai_session_config,
            )
            # Consuming an interaction clears its token or replaces it at the next pause.
            interaction_consumed = not secrets.compare_digest(resume_token, session.resume_token or '')
            root = session._root_session()
            # A consumed affirmative reply may also approve other pending confirmations.
            if (
                response['kind'] == 'confirmation'
                and response['value'] in (
                    UserInputResponse.CONFIRM_ONCE,
                    UserInputResponse.AUTO_CONFIRM,
                )
                and interaction_consumed
                and root.auto_confirm
            ):
                pending_sessions = self.env['ai.session'].sudo().search([
                    ('channel_id', '=', root.channel_id.id), ('loop_state', '=', 'waiting_confirmation'),
                ])
                for pending_session in pending_sessions:
                    pending_session._resume_pending_interaction({
                        'kind': 'confirmation', 'value': UserInputResponse.CONFIRM_ONCE,
                    }, automatic=True)
        return {
            'interactionConsumed': interaction_consumed,
            'loop_state': session.loop_state,
        }

    def _extend_context(self, context):
        """Add request-derived values to the generator environment context. To be Overridden"""
        context["active_company_ids"] = [int(cid) for cid in http.request.cookies.get("cids", "").split("-") if cid]
        context['HTTP_HOST'] = http.request.httprequest.environ.get('HTTP_HOST', '')
        context['ai_show_tool_status'] = self.env.user._is_internal()
        return context
