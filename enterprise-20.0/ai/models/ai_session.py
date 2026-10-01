# Part of Odoo. See LICENSE file for full copyright and licensing details.

import copy
import json
import logging
import secrets
import uuid
from markupsafe import Markup
from textwrap import dedent
from typing import Unpack

from odoo import api, Command, fields, models
from odoo.exceptions import AccessError, ConcurrencyError, MissingError, UserError, ValidationError
from odoo.modules.registry import Registry
from odoo.sql_db import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY
from odoo.tools import html_sanitize
from odoo.tools.urls import urljoin as url_join

from odoo.addons.iap import InsufficientCreditError
from odoo.addons.mail.tools.discuss import Store

from ..utils.ai_citation import apply_web_citations
from ..utils.ai_utils import (
    call_odoo_ai,
    call_odoo_ai_transport,
    disable_skills,
    enable_tools,
    format_tool_result,
    format_tool_summary,
    get_odoo_ai_connection_data,
    IAP_TRANSPORT_TIMEOUT,
    markdown_format,
    ODOO_AI_COMPLETION_CALLBACK_PATH,
    get_text_from_parts,
    UserInputResponse,
)
from ..utils.types import (
    AIMessageParts, CompletionFailure, CompletionOptions, CompletionResponse,
    CompletionSuccess, Message, PendingInteractionResponse, Tool,
)

_logger = logging.getLogger(__name__)

DEFAULT_SESSION_SCOPED_TOOLS = [
    "ai.ir_actions_server_ask_user_question",
]

SUBAGENT_TOOL_XMLIDS = (
    'ai.ir_actions_server_start_session',
    'ai.ir_actions_server_continue_session',
)


class AiSessionEvent(models.Model):
    """Holds metadata of a message exchanged with a LLM.
    Metadata can be a list of text messages, tool call requests/results, thinking signatures etc.
    """
    _name = 'ai.session.event'
    _description = 'AI Session Event'
    _order = 'create_date desc, id desc'

    ai_session_id = fields.Many2one('ai.session', ondelete='cascade', index='btree_not_null')
    metadata = fields.Json('json representation of the event', required=True)

    def get_tool_params(self, call_id):
        self.ensure_one()
        if not self.env.user._is_internal():
            raise AccessError(self.env._("Only internal users can view tool parameters."))
        # sudo: access is based on session's channel access (internal users can't access events)
        event_sudo = self.sudo()
        event_sudo.ai_session_id.channel_id.sudo(False).check_access('read')
        tool_call = next(
            (part for part in event_sudo.metadata['content'] if part['type'] == 'tool_call' and part['call_id'] == call_id),
            None,
        )
        if not tool_call:
            return
        # remove technical args
        return {k: v for k, v in tool_call['args'].items() if k not in {'tool_status', '__final_message', 'explanation'}}


class AiSession(models.Model):
    _name = 'ai.session'
    _description = "AI Session"

    active = fields.Boolean(default=True)
    agent_id = fields.Many2one('ai.agent', ondelete='cascade', index='btree_not_null')
    ai_composer_id = fields.Many2one('ai.composer')
    channel_id = fields.Many2one('discuss.channel', ondelete='cascade', index='btree_not_null')
    parent_session_id = fields.Many2one('ai.session', ondelete='cascade', index='btree_not_null')
    event_ids = fields.One2many('ai.session.event', 'ai_session_id')
    state = fields.Json(string="State", help="Field that can be used to store data between tool calls")
    message_body_suffix = fields.Html(copy=False)
    res_model = fields.Char("Model")
    res_id = fields.Many2oneReference(model_field='res_model')
    pending_tool_call = fields.Json("Tool call waiting on the client")
    auto_confirm = fields.Boolean("Automatically confirm tool calls for the session", default=False)
    enable_web_search = fields.Boolean("Enable web search capability for the session")
    enable_think_longer = fields.Boolean("Enable think longer option for the session", default=False)
    enable_resources_only = fields.Boolean("Enable resource restriction for the session")
    show_agent_steps = fields.Boolean("Show agent steps")
    turn_notifications = fields.Json("Notifications collected during a turn, that will be shown after the final response")
    loop_state = fields.Selection([
        ("ready", "Ready"),
        ("waiting_model", "Waiting for Model"),
        ("waiting_confirmation", "Waiting for Confirmation"),
        ("waiting_answer", "Waiting for Answer"),
        ("waiting_client_result", "Waiting for Client Result"),
        ("waiting_external_result", "Waiting for External Result"),
        ("waiting_child", "Waiting for Child Session"),
    ], required=True, default="ready", index=True)
    request_uuid = fields.Char()
    request_webhook_secret = fields.Char(groups=fields.NO_ACCESS)
    request_payload = fields.Json()
    request_round = fields.Integer()
    request_round_limit = fields.Integer()
    request_user_id = fields.Many2one("res.users", ondelete="restrict")
    request_guest_id = fields.Many2one("mail.guest", ondelete="set null")
    request_context = fields.Json()
    resume_token = fields.Char()

    _request_uuid_unique = models.UniqueIndex(
        "(request_uuid)", "The active IAP request UUID must be unique.",
    )
    _valid_request_round = models.Constraint(
        "CHECK(loop_state = 'ready' OR (request_round IS NOT NULL AND request_round_limit IS NOT NULL "
        "AND request_round >= 1 AND request_round_limit >= request_round))",
        "The active AI request round must be within its exchange limit.",
    )
    _complete_request_data = models.Constraint(
        "CHECK(loop_state = 'ready' OR (request_uuid IS NOT NULL AND request_payload IS NOT NULL "
        "AND request_user_id IS NOT NULL "
        "AND request_webhook_secret IS NOT NULL))",
        "An active AI exchange must retain its complete model request data.",
    )
    _complete_interaction_wait = models.Constraint(
        "CHECK(loop_state NOT IN ('waiting_confirmation', 'waiting_answer', "
        "'waiting_client_result', 'waiting_external_result') "
        "OR (resume_token IS NOT NULL AND pending_tool_call IS NOT NULL))",
        "A waiting AI interaction must retain its continuation data.",
    )
    _complete_child_wait = models.Constraint(
        "CHECK(loop_state != 'waiting_child' OR pending_tool_call IS NOT NULL)",
        "A session waiting for a child must retain its pending tool call.",
    )

    def _store_session_fields(self, res: Store.FieldList):
        res.one("channel_id", [])
        res.one("parent_session_id", [])
        res.one("agent_id", ["name", "partner_id"])
        res.attr("res_model")
        res.attr("res_id")
        res.one("ai_composer_id", "_store_composer_fields")
        res.attr("config", lambda session: session.get_session_config())
        res.attr("config_rules", lambda session: session._get_session_config_rules())

        def get_user_input_request(session):
            if session.loop_state not in ("waiting_confirmation", "waiting_answer"):
                return False
            user_input_request = session.pending_tool_call["user_input_request"]
            return {
                "type": user_input_request["type"],
                "body": ['markup', str(html_sanitize(user_input_request['body'], sanitize_attributes=True, sanitize_style=True))],
                "choices": user_input_request["choices"],
                "multiSelect": user_input_request.get("multi_select", False),
                "allowFreeText": user_input_request.get("allow_free_text", False),
                "resumeToken": session.resume_token,
            }

        res.attr("userInputRequest", value=get_user_input_request)
        res.attr(
            "external_pending_tool",
            value=lambda session: bool((session.pending_tool_call or {}).get("await_external_result")),
        )

        def get_current_tool_status(session):
            if session.parent_session_id or not session.env.user._is_internal() or session.loop_state == 'ready':
                return False
            last_turns = session._get_history(2)
            if len(last_turns) != 2:
                # no assistant response yet, so no tool
                return False
            last_assistant_turn = last_turns[0] if last_turns[0]['role'] == 'assistant' else last_turns[1]
            last_tool_calls = [p for p in last_assistant_turn['content'] if p['type'] == 'tool_call']
            if not last_tool_calls:
                return False
            if session.pending_tool_call:
                pending_results = session.pending_tool_call.get('pending_results') or []
                current_tool = last_tool_calls[max(len(pending_results) - 1, 0)]
            else:
                current_tool = last_tool_calls[-1]
            return current_tool['args'].get('tool_status')
        res.attr("toolStatus", value=get_current_tool_status)

        def get_pending_client_tool_request(session):
            if session.loop_state != "waiting_client_result":
                return False
            client_tool = session.pending_tool_call["client_tool"]
            return {
                "name": client_tool["name"],
                "params": client_tool.get("params") or {},
                "resumeToken": session.resume_token,
                "aiSessionIdentifier": session.pending_tool_call["ai_session_identifier"],
            }

        res.attr("clientToolRequest", value=get_pending_client_tool_request)

        res.attr("loop_state")
        res.attr("resume_token")

    def _get_session_config_rules(self):
        """If a config key is True, these values must also hold."""
        return {
            "enable_web_search": {
                "enable_resources_only": False,
            },
            "enable_resources_only": {
                "enable_web_search": False,
            }
        }

    def _publish_response_state(self):
        self.ensure_one()
        if self.channel_id:
            Store(bus_channel=self.channel_id).add(self, "_store_session_fields")

    def _set_pending_tool_call(self, pending_tool_call):
        """Set the pending tool call; the caller publishes the updated loop state."""
        self.pending_tool_call = pending_tool_call

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("agent_id"):
                agent = self.env["ai.agent"].browse(vals["agent_id"])
                vals["enable_web_search"] = not agent.restrict_to_sources
                vals["enable_resources_only"] = agent.restrict_to_sources
        return super().create(vals_list)

    def _finish_exchange(self, status='completed', *, content=None):
        """Mark the exchange complete, then post or deliver its result.

        :param status: ``completed`` for normal completion, ``declined`` when
            the user declines or skips pending work, or ``failed`` when the
            exchange fails. All statuses return the session to ``ready``.
            Subagents include this status in the result delivered to their parent.
        """
        self.ensure_one()
        self.write({
            'loop_state': 'ready',
            'resume_token': False, 'pending_tool_call': False,
        })
        self._publish_response_state()
        if self.parent_session_id:
            self._post_turn_notifications()
            self._deliver_subagent_result(content, status=status)
        else:
            if content is not None:
                self._post_ai_response(content)
            self._post_turn_notifications()

    def _get_related_record(self):
        self.ensure_one()
        if not (self.res_model and self.res_id):
            return None
        if not (record := self.env[self.res_model].browse(self.res_id)).exists():
            raise MissingError(self.env._("The record linked to the session was not found."))
        record = record.sudo(False)
        record.check_access('read')
        return record

    def _get_session_default_tools(self):
        """Return the agent's default tools and tools available only in stateful sessions."""
        self.ensure_one()
        tools = self.agent_id._get_default_tools()
        if not self.env.user.share:
            for xmlid in DEFAULT_SESSION_SCOPED_TOOLS:
                if tool := self.env.ref(xmlid, raise_if_not_found=False):
                    tools |= tool
        if self.agent_id.allowed_agent_ids:
            ancestor, depth = self, 1
            while ancestor.parent_session_id:
                ancestor, depth = ancestor.parent_session_id, depth + bool(ancestor.agent_id)
            if depth < 4:
                for xmlid in SUBAGENT_TOOL_XMLIDS:
                    tools |= self.env.ref(xmlid)
        return tools

    def _initialize_tool_state(self, state):
        skills = self.env['ai.skill'].sudo().browse(state.get('loaded_skills', []))
        skills &= self.agent_id.sudo()._get_available_skills()
        web_search_skill = self.env.ref('ai.ai_skill_web_search').sudo()
        if self.enable_web_search:
            skills |= web_search_skill
        else:
            skills -= web_search_skill

        state['loaded_skills'] = skills.ids
        state['available_tools'] = (self._get_session_default_tools() | skills.tool_ids).ids

    def _build_tools_context(self, state):
        """Wrap saved tool state with temporary values for this execution."""
        self.ensure_one()
        return {
            'session_id': self.id,
            'state': state,
            'message_body_suffix': self.message_body_suffix,
            'res_model': self.res_model,
            'res_id': self.res_id,
            'agent_id': self.agent_id.id,
            'final_message': False,
            'user_input_request': None,
            'tool_request_confirmed': False,
            'auto_confirm': self._root_session().auto_confirm,
            'user_id': self.env.user.id,
            'enable_web_search': self.enable_web_search,
        }

    def _get_model_round_options(self):
        """Return model options that optional addons may extend per model round."""
        self.ensure_one()
        return {
            'usage': self.agent_id._get_usage_string(),
            'boost_reasoning': self.enable_think_longer,
        }

    def _get_tool_execution_context(self):
        """Return extra context for each tool call, including earlier tool changes."""
        return {}

    def _get_session_advance_unavailable_message(self):
        """Let optional addons stop a session advance when the browser context is unsuitable."""
        self.ensure_one()
        return False

    def _prepare_response_content(self, content: AIMessageParts | str | Markup):
        """Extract the body and create or reuse inline attachments."""
        self.ensure_one()
        if isinstance(content, str):
            content = [{'type': 'text', 'text': content}]

        inline_data_parts = [part for part in content if part['type'] == 'inline_data']
        attachment_vals = []
        attachment_ids = []
        for ai_response_part in inline_data_parts:
            if attachment_id := ai_response_part.get('metadata', {}).get('attachment_id'):
                attachment_ids.append(attachment_id)
            else:
                title = f'AI Generated image by {self.agent_id.name} ({uuid.uuid4().hex[:8]})'
                attachment_vals.append({
                    'raw': ai_response_part['data'],
                    'mimetype': ai_response_part['mimetype'],
                    'name': title,
                    'description': title,
                })
        if attachment_vals:
            new_attachment_ids = self.env['ai.attachment.vacuum']._create_attachments_and_mark_unused(attachment_vals)
            attachment_ids.extend(new_attachment_ids.ids)
        return get_text_from_parts(content) or '', attachment_ids

    def _post_ai_response(self, content: AIMessageParts | str | Markup, is_user_input_request=False):
        """Post the response in this session's chat."""
        body, attachment_ids = self._prepare_response_content(content)
        if is_user_input_request:
            body = Markup('<div class="ai_user_input_request">%s</div>') % body
        message_data = {
            'author_id': self._root_session().agent_id.partner_id.id,
            'message_type': "comment",
            'silent': True,
            'subtype_xmlid': 'mail.mt_comment',
        }
        if body:
            message_data['body'] = body
        if attachment_ids:
            message_data['attachment_ids'] = attachment_ids
        self.channel_id.message_post(**message_data)

    def _post_turn_notifications(self):
        """Posts the notifications collected during the turn and reset the field:
        notifications, such as previews or config changes, are shown after the turn's response
        """
        self.ensure_one()
        if self.parent_session_id:
            self.turn_notifications = None
            return
        for notification in self.turn_notifications or []:
            body = notification['body']
            if notification['type'] == 'ai_preview':
                body = html_sanitize(body)
            body = Markup("<div class='o_mail_notification' data-oe-type='%s'>%s</div>") % (notification['type'], body)
            self.channel_id.message_post(
                body=body,
                author_id=self.agent_id.partner_id.id,
                subtype_xmlid="mail.mt_comment",
                silent=True,
            )
        self.turn_notifications = None

    def post_agent_step(self, message, message_type):
        """Posts a progress message, which is either a message generated by the agent that explains
        what it is doing, or a tool call summary.
        If the user is not an internal user, the message is logged instead of posted because they
        should not receive these messages, but internal users can use them for debugging
        :param message: The content of the message to post
        :param message_type: 'notification' for the tool summary, 'comment' for the agent message
        """
        self.ensure_one()
        # Child activity stays in its session history; only the main agent posts progress.
        if self.parent_session_id:
            return
        last_event_id = self.event_ids[0].id
        message = Markup('<div class="o-ai-agent-step" data-id="%s">%s</div>') % (last_event_id, message)
        if self.env.user._is_internal():
            return self.channel_id.message_post(
                body=message,
                author_id=self.agent_id.partner_id.id,
                message_type=message_type,
                subtype_xmlid="mail.mt_note",
                is_internal=True,
                silent=True,
            )
        else:
            self.channel_id._message_log(
                body=message,
                author_id=self.agent_id.partner_id.id,
                message_type=message_type
            )

    def _format_final_message(self, response_parts):
        """Apply the existing visible final-message formatting outside the loop stack."""
        self.ensure_one()
        text = get_text_from_parts(response_parts)
        if text and self.enable_web_search and "[WEB_SOURCE:" in text:
            text = apply_web_citations(
                text,
                (self.state or {}).get('web_sources', {}),
                link_attrs='target="_blank" rel="noreferrer noopener"',
            )
        if text and self.agent_id.sources_ids:
            text = self.agent_id._get_llm_response_with_sources(text)
        if text:
            text = markdown_format(text)
        if suffix := self.message_body_suffix:
            text += suffix
            self.message_body_suffix = False
        return [
            *([{'type': 'text', 'text': text}] if text else []),
            *[part for part in response_parts if part['type'] != 'text'],
        ]

    def _get_history(self, limit=None):
        self.ensure_one()
        # reverse them to get the most recent event at the end of the list
        return self.env['ai.session.event'].search([('ai_session_id', '=', self.id)], limit=limit)[::-1].mapped('metadata')

    def _get_request_context_snapshot(self, context=None):
        """Capture bounded context from the environment executing this event."""
        context = self.env.context if context is None else context
        snapshot = {key: context[key] for key in (
            'allowed_company_ids', 'active_company_ids', 'current_view_info',
            'HTTP_HOST', 'lang', 'tz', 'cron_id', 'ai_session_identifier',
            'debug', 'ai_show_tool_status',
        ) if key in context}
        accessible_company_ids = frozenset(self.env.user.company_ids.ids)
        for key in ('allowed_company_ids', 'active_company_ids'):
            if key in snapshot:
                snapshot[key] = [company_id for company_id in snapshot[key] if company_id in accessible_company_ids]
        return snapshot

    def _save_and_submit_request(
        self, payload, *, callback_type,
        request_round, request_round_limit,
        state,
    ) -> None:
        """Save request state and schedule submission after the caller commits."""
        self.ensure_one()
        guest = self.env.context.get("guest")
        vals = {
            "loop_state": "waiting_model",
            "request_uuid": str(uuid.uuid4()),
            "request_webhook_secret": uuid.uuid4().hex,
            "request_round": request_round,
            "request_round_limit": request_round_limit,
            "request_payload": payload,
            "request_user_id": self.env.uid,
            "request_guest_id": guest.id if guest else False,
            "request_context": self._get_request_context_snapshot(),
            "resume_token": False,
            "pending_tool_call": False,
        }
        state["callback_type"] = callback_type
        vals["state"] = state
        self.write(vals)
        self._publish_response_state()
        connection = get_odoo_ai_connection_data(self.env)
        params = {
            **copy.deepcopy(payload),
            'request_uuid': vals["request_uuid"],
            'webhook_url': url_join(
                self.get_base_url(), ODOO_AI_COMPLETION_CALLBACK_PATH,
            ),
            'webhook_secret': vals["request_webhook_secret"],
            'webhook_dbname': self.env.cr.dbname,
            'llm_retry': False,
        }
        dbname = self.env.cr.dbname
        user_id = self.env.uid
        guest_id = vals["request_guest_id"]
        context = vals["request_context"]

        @self.env.cr.postcommit.add
        def submit():
            def rescue_session(error_msg, send_credit_notif=False):
                try:
                    with Registry(dbname).cursor() as cr:
                        env = api.Environment(cr, user_id, context)
                        if guest_id:
                            env = env(context={**env.context, 'guest': env['mail.guest'].browse(guest_id)})
                        session = env['ai.session'].sudo().search([('request_uuid', '=', params['request_uuid'])])
                        if session:
                            if callback_type == 'channel_name':
                                session.unlink()
                                return
                            if send_credit_notif and not env.context.get('cron_id'):
                                env['iap.account']._send_no_credit_notification(
                                    service_name='odoo_ai', title=error_msg,
                                )
                            session._finish_exchange('failed', content=error_msg if session.parent_session_id else None)
                except Exception:  # noqa: BLE001
                    _logger.exception("Failed to clean up failed AI session submission %s", params['request_uuid'])

            try:
                call_odoo_ai_transport(
                    connection, '1/get_completions', params,
                    timeout=IAP_TRANSPORT_TIMEOUT, raise_user_error=False,
                )
            except InsufficientCreditError:
                _logger.info("Insufficient credit for Odoo AI")
                rescue_session(
                    self.env._("Not enough credits to use Odoo AI"),
                    send_credit_notif=True,
                )
            except Exception:  # noqa: BLE001
                _logger.exception("Failed to submit AI request %s", params['request_uuid'])
                rescue_session(
                    self.env._("Odoo AI is currently unreachable. Please try again later."),
                )

    def _submit_agent_request(self, message=None) -> None:
        """If no message, it's for the succeeding round."""
        self.ensure_one()
        state = self.state or {}
        is_first_round = message is not None
        if not is_first_round:
            round_no = self.request_round + 1
            round_limit = self.request_round_limit
        else:
            self._initialize_tool_state(state)
            self.message_body_suffix = False
            round_no = 1
            round_limit = self.env['ir.config_parameter'].sudo().get_int('ai.max_successive_calls') or 30

        completion_options = self._get_model_round_options()
        messages = self._get_history()
        if message:
            user_event = {'role': 'user', 'content': list(message)}
            self.event_ids = [Command.create({'metadata': user_event})]
            messages.append(user_event)

        rag_context = None
        if messages:
            last_user_message = self._get_last_user_message(messages)
            if not is_first_round:
                rag_context = state['rag_context']
            else:
                text = get_text_from_parts(last_user_message['content'])
                if text and self.agent_id.sources_ids:
                    rag_context = self.agent_id._build_rag_context(text)
                state['rag_context'] = rag_context
            last_user_message['content'].append({
                'type': 'text',
                'text': self._get_context_input(rag_context),
            })

        updated_instructions = self._append_loaded_skills(
            self.agent_id._get_instructions(
                self.ai_composer_id.default_prompt if not self.parent_session_id else None,
                restrict_to_resources_override=self.enable_resources_only,
            ),
            state,
        )
        if round_no >= round_limit:
            tools = self.env.ref("ai.ir_actions_server_ask_user_question").sudo()
            warning_text = dedent("""
                <turn_limit_warning>
                You are about to exceed the turn limit.
                Primary Directive: Your next and ONLY action is to call the `ai_tool_ask_user_question` tool.
                Tool Arguments: You MUST provide the following arguments:
                    `choices`:
                         - Two choices meaning "continue" and "stop here", in the language used in this conversation.
                    `question`:
                        This must be a single string in the conversation's language, construct it by combining these parts:
                        1. A reason for pausing (e.g. "...is taking more steps than I can complete in one go, so I've paused here").
                        2. A summary of your progress so far (e.g. "I have found the partners in California...").
                        3. A description of the next step (e.g. "...and am about to check their open opportunities.").
                        4. A direct question asking to proceed (e.g. "Would you like me to continue?").
                </turn_limit_warning>
            """).strip()
            last_user_message = self._get_last_user_message(messages)
            last_user_message['content'].append({
                'type': 'text',
                'text': warning_text,
            })
        else:
            tools = self.env["ir.actions.server"].sudo().browse(state.get("available_tools")).exists()
        if tools and completion_options.get('web_grounding'):
            raise UserError(self.env._(
                "The web grounding option is not supported with tools. Use the web search skill instead."
            ))
        tools_by_name = {tool.ai_tool_name: tool for tool in tools}
        payload = {
            'messages': messages,
            'instructions': updated_instructions,
            'tools': self._prepare_tools(tools_by_name),
            **completion_options,
        }
        if 'ai_tool_start_session' in tools_by_name:
            payload['instructions'] = self._append_subagent_instructions(updated_instructions)
        self._save_and_submit_request(
            payload,
            callback_type="agent_loop",
            request_round=round_no,
            request_round_limit=round_limit,
            state=state,
        )

    def _root_session(self):
        session = self
        while session.parent_session_id:
            session = session.parent_session_id
        return session

    def _merge_child_result(self, child, result):
        """Replace a child marker and advance the parent when its loop can continue."""
        pending_batch = self.pending_tool_call or {}
        pending_results = pending_batch.get('pending_results', [])
        child_marker = next((result for result in pending_results if result.get('child_session_id') == child.id), None)
        if not child_marker or child.parent_session_id != self:
            return
        tool_result = format_tool_result(
            {'name': child_marker['tool_name'], 'call_id': child_marker['tool_call_id']},
            result={'session_id': child.id, **result},
        )
        tool_result['success'] = result['status'] == 'completed'
        file_parts = self.env['ir.attachment'].browse(result['attachment_ids'])._ai_read()[1]
        tool_result['result'] += file_parts
        child_marker.clear()
        child_marker.update(tool_result)
        self.pending_tool_call = pending_batch

        if self.loop_state != 'waiting_child' or pending_batch.get('call_id'):
            # Maybe a warning?
            return
        has_pending_children = any('child_session_id' in result for result in pending_results)
        if has_pending_children:
            return None
        if pending_batch.get('declined'):
            self.event_ids = [Command.create({'metadata': self._format_tool_output_message(pending_results)})]
            return self._finish_exchange("declined", content=pending_batch.get('final_message') or self.env._('Skipped'))
        return self._finish_tool_batch(
            pending_results, self._build_tools_context(self.state or {}),
            pending_batch.get('final_message'),
        )

    def _advance_tool_batch(self, pending_tool_response=None) -> None:
        """Consume tool events until the batch finishes or reaches its next wait."""
        self.ensure_one()
        pending = self.pending_tool_call or {}
        tools_context = self._build_tools_context(self.state or {})
        if pending.get('final_message'):
            tools_context['final_message'] = pending['final_message']
        tool_calls = self._get_last_tool_calls()
        if self.request_round >= self.request_round_limit:
            tools = self.env.ref("ai.ir_actions_server_ask_user_question").sudo()
        else:
            tools = self.env['ir.actions.server'].sudo().browse(tools_context['state']['available_tools']).exists()
        items = self._handle_tool_calls(
            tool_calls, {tool.ai_tool_name: tool for tool in tools},
            tools_context, self._get_related_record(), pending_tool_response,
            previous_results=pending.get('pending_results'),
        )
        client_tools = []
        for item in items:
            if 'intermediary_message' in item:
                self.post_agent_step(
                    markdown_format(item['intermediary_message']),
                    'notification' if item.get('is_tool_summary') else 'comment',
                )
            elif 'notifications' in item:
                self.turn_notifications = (self.turn_notifications or []) + item['notifications']
            elif 'client_tool' in item and item['client_tool'].get('oneway'):
                client_tools.append(item['client_tool'])
            elif 'tool_results' in item:
                tool_results = item['tool_results']
                final_message = item.get('final_message')
                if any('child_session_id' in result for result in tool_results):
                    self.write({
                        'loop_state': 'waiting_child', 'resume_token': False,
                        'pending_tool_call': {
                            'pending_results': tool_results, 'final_message': final_message,
                        },
                        'state': tools_context['state'],
                        'message_body_suffix': tools_context['message_body_suffix'],
                    })
                    self._publish_response_state()
                else:
                    self._finish_tool_batch(tool_results, tools_context, final_message)
                break
            else:
                pending = item['pending_tool_call']
                if tools_context['final_message']:
                    pending['final_message'] = tools_context['final_message']
                if 'client_tool' in item:
                    pending['client_tool'] = item['client_tool']
                    # A browser resume may come from a different tab than the last model request.
                    pending['ai_session_identifier'] = self.env.context.get('ai_session_identifier')
                    loop_state = 'waiting_client_result'
                elif 'external_wait_message' in item:
                    pending['await_external_result'] = True
                    loop_state = 'waiting_external_result'
                    self._post_ai_response(item['external_wait_message'])
                else:
                    pending['user_input_request'] = item['user_input_request']
                    loop_state = {
                        'confirmation': 'waiting_confirmation', 'question': 'waiting_answer',
                    }[item['user_input_request']['type']]
                self._set_pending_tool_call(pending)
                self.write({
                    'loop_state': loop_state,
                    'resume_token': secrets.token_urlsafe(32),
                    'state': tools_context['state'],
                    'message_body_suffix': tools_context['message_body_suffix'],
                })
                break

        if client_tools:
            self.channel_id._bus_send('ai.session/client_tools', {
                'channel_id': self.channel_id.id, 'commands': client_tools,
                'aiSessionIdentifier': self.env.context.get('ai_session_identifier'),
            })
        if 'pending_tool_call' in item:
            self._publish_response_state()

    def _finish_tool_batch(self, tool_results, tools_context, final_message=None) -> None:
        self.write({
            'state': tools_context['state'],
            'message_body_suffix': tools_context['message_body_suffix'],
        })
        if self.parent_session_id and final_message:
            tool_results[-1]['result'] += final_message
        self.event_ids = [Command.create({'metadata': self._format_tool_output_message(tool_results)})]
        if final_message is not None:
            return self._finish_exchange(content=self._format_final_message(final_message))
        if self.request_round >= self.request_round_limit:
            return self._finish_exchange('failed', content=self.env._(
                "The AI used too many successive tool rounds. Please try a more precise request."
            ))
        self._submit_agent_request()

    def _resume_pending_interaction(
        self, response: PendingInteractionResponse,
        ai_session_config=None, *, automatic=False,
    ) -> None:
        """Consume one durable interaction and continue its persisted tool batch."""

        self.ensure_one()
        pending_tool_call = self.pending_tool_call
        if self.loop_state == 'waiting_external_result':
            if response['kind'] == 'skip':
                return self._abort_pending_tools()
            if response['kind'] != 'async' or response['call_id'] != pending_tool_call['call_id']:
                return
        elif response['kind'] == 'async':
            return
        if unavailable_message := self._get_session_advance_unavailable_message():
            self._post_ai_response(unavailable_message)
            return

        if self.loop_state in ('waiting_confirmation', 'waiting_answer'):
            user_input_request = pending_tool_call['user_input_request']
            prompt_body = html_sanitize(
                user_input_request['body'], sanitize_attributes=True, sanitize_style=True,
            )
            self._post_ai_response(prompt_body, is_user_input_request=True)

        ai_session_config = ai_session_config or {}
        if response['kind'] == 'confirmation' and response['value'] == UserInputResponse.AUTO_CONFIRM:
            ai_session_config['auto_confirm'] = True
        if ai_session_config:
            self._root_session().update_session_config(ai_session_config)

        if response['kind'] == 'skip':
            return self._abort_pending_tools()

        if self.loop_state == "waiting_confirmation":
            confirmation_value = response["value"]
            selected_choice = next(
                (
                    choice
                    for choice in user_input_request["choices"]
                    if choice["value"] == confirmation_value
                ),
                None,
            )
            if not selected_choice:
                raise UserError(self.env._("This AI confirmation choice is no longer available."))
            if automatic:
                self.turn_notifications = (self.turn_notifications or []) + [{
                    'type': 'ai_note',
                    'body': self.env._("Approved automatically because auto-approval is enabled for this chat."),
                }]
            else:
                self.channel_id.sudo().message_post(
                    body=selected_choice["label"],
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            if confirmation_value == UserInputResponse.DECLINE:
                return self._abort_pending_tools()
        elif self.loop_state == "waiting_answer":
            values = response['value']
            selected_values = set(values)
            selected_choices = [
                choice
                for choice in user_input_request["choices"]
                if choice["value"] in selected_values
            ]
            known_values = {choice["value"] for choice in selected_choices}
            free_text_values = [
                value.strip() for value in values if value not in known_values
            ]
            ordered_values = [
                choice["value"] for choice in selected_choices
            ] + free_text_values
            ordered_labels = [
                choice["label"] for choice in selected_choices
            ] + free_text_values
            if (
                (not user_input_request["multi_select"] and len(values) != 1)
                or (
                    free_text_values
                    and (
                        not user_input_request["allow_free_text"]
                        or len(free_text_values) != 1
                    )
                )
                or len(ordered_values) != len(values)
            ):
                raise UserError(self.env._("This AI question response is not valid."))
            self.channel_id.sudo().message_post(
                body=", ".join(ordered_labels),
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            response = {'kind': 'question', 'value': ordered_values}
        # Resuming a pending tool starts a fresh allowance, as in the synchronous loop.
        self.request_round_limit = self.request_round + (
            self.env['ir.config_parameter'].sudo().get_int('ai.max_successive_calls') or 30
        )
        return self._advance_tool_batch(response)

    def _continue_agent_loop(self, completion_result: CompletionFailure | CompletionSuccess) -> None:
        self.ensure_one()
        if completion_result['kind'] == 'failure':
            error_code = completion_result['code']
            _logger.warning(
                "AI completion request %s failed with code %s",
                self.request_uuid,
                error_code,
            )
            self._finish_exchange('failed', content=self.env._("Oops, it looks like our AI is unreachable"))
            return

        output_message = completion_result['message']
        self.event_ids = [Command.create({'metadata': output_message})]
        if any(part['type'] == 'tool_call' for part in output_message['content']):
            if message := get_text_from_parts([part for part in output_message['content'] if part['type'] == 'text']):
                self.post_agent_step(markdown_format(message), 'comment')
            self._advance_tool_batch()
        else:
            response_parts = [
                part for part in output_message['content']
                if part['type'] in ('text', 'inline_data')
            ]
            self._finish_exchange(content=self._format_final_message(response_parts))

    def _deliver_subagent_result(self, content, *, status='completed'):
        """Pass this child's completed answer directly into its parent's pending batch."""
        if content is None:
            if status == 'declined':
                content = self.env._('Declined by the user. Do not attempt to run this sub-agent again unless explicitly instructed.')
            else:
                content = ''
        body, attachment_ids = self._prepare_response_content(content)
        self.env['ai.attachment.vacuum'].mark_attachments_used(attachment_ids)
        self.parent_session_id._merge_child_result(self, {
            'status': status, 'message': str(body), 'attachment_ids': attachment_ids,
            'sources': (self.state or {}).get('web_sources', {}),
        })

    def _continue_channel_name(self, completion_result):
        self.ensure_one()
        title = (
            get_text_from_parts(completion_result['message']['content']).strip().replace("\n", " ")
            if completion_result['kind'] == 'success' else ''
        )
        if title:
            channel = self._root_session().channel_id
            if channel and channel.channel_type == "ai_chat":
                channel.name = title
        else:
            _logger.warning("AI channel name request %s did not return a title", self.request_uuid)
        self.unlink()

    def _get_context_input(self, rag_context):
        self.ensure_one()
        context = "<odoo_current_context>\n"
        if rag_context:
            context += f"## RAG\n{rag_context}\n"
        context += f"## Date\n{fields.Datetime.now()} (UTC)"
        if self.env.user._is_internal():
            user_info = {k: v for k, v in self.env.user._ai_read(['name', 'function', 'partner_id'])[0][0].items() if v}
            user_info['user_id'] = user_info.pop('id')
        else:
            user_info = {k: v for k, v in self.env.user.partner_id._ai_read(['name', 'function'])[0][0].items() if v}
            user_info['is_public'] = True
        context += f"\n## User info\n{user_info}"

        active_companies = self.env["res.company"].search([("id", "in", self.env.context.get("active_company_ids"))])
        active_companies_infos = []
        for company in active_companies:
            company_info = {
                "model": "res.company",
                "id": company.id,
                "name": company.name,
            }
            if company.country_id.code:
                company_info["country_code"] = company.country_id.code
                if company.city:
                    company_info["country_city"] = company.city
            active_companies_infos.append(company_info)
        context += f"\n## Current active companies\n{active_companies_infos}"
        if view_info := self.env.context.get("current_view_info"):
            context += f"\n## Current view\n{view_info}"
        if related_record := self._get_related_record():
            # add up-to-date record info
            context += f"\n## Current record data\n{related_record._ai_serialize_fields_data()}"
        context += f"\n## Current agent (you)\nName: {self.agent_id.name}\nId: {self.agent_id.id}"
        if self._root_session().auto_confirm:
            context += "\n## Auto confirm\nTool auto-confirmation is enabled"
        context += "</odoo_current_context>"
        return context

    @api.model
    def _format_tool_output_message(self, tool_outputs):
        return {'role': 'user', 'content': [
            {'type': 'tool_result', **result} for result in tool_outputs
        ]}

    def _handle_tool_calls(
        self, tool_calls, tools_by_name, tools_context, record,
        pending_tool_response: PendingInteractionResponse | None = None, previous_results=None,
    ):
        """Processes a list of tool calls and returns the results.

        :param tool_calls: list of tool call dicts
        :param tools_by_name: dict of tool actions by name
        :param tools_context: tools_context to pass in the tools
        :param record: record on which to execute the tools
        :param pending_tool_response: response used to resume the first tool call, if any
        :param previous_results: completed prefix of this provider batch, including child markers
        :return: tool_results
        """
        max_tools_per_call = self.env["ir.config_parameter"].sudo().get_int("ai.max_tool_calls_per_call") or 20
        tool_results = copy.deepcopy(previous_results or [])
        failed_tool_call = any(result.get('success') is False for result in tool_results)
        record_context = {
            'active_model': record._name,
            'active_id': record.id,
            'active_ids': record.ids,
        } if record else {}

        for tc_idx, tool_call in enumerate(tool_calls[len(tool_results):], start=len(tool_results)):
            if tc_idx >= max_tools_per_call:
                # is this needed? tool calls are not the bottleneck, might be better to call
                # them now than having an additional round trip and call them in next iter
                tool_results.append(format_tool_result(tool_call, error="Not executed (tool call limit reached)"))
                if tc_idx == max_tools_per_call:
                    _logger.warning("AI: Tool call limit reached, stopping further tool calls")
                    failed_tool_call = True
                continue
            tools_context['tool_request_confirmed'] = (
                bool(pending_tool_response and pending_tool_response['kind'] == 'confirmation')
                or bool(tools_context['auto_confirm'])
            )
            if pending_tool_response:
                response, pending_tool_response = pending_tool_response, None
                if response['kind'] == 'client_result':
                    tool_results.append(format_tool_result(tool_call, result=response['value']))
                    continue
                if response['kind'] == 'client_error':
                    tool_results.append(format_tool_result(tool_call, error=response['value']))
                    failed_tool_call = True
                    continue
                if response['kind'] == 'question':
                    tool_results.append(format_tool_result(tool_call, result=f"USER ANSWER: {','.join(response['value'])}"))
                    continue
            tools_context['final_message'] = None
            if tool_call['name'] not in tools_by_name:
                _logger.error("AI: Try to call a non-available tool %s", tool_call['name'])
                tool_results.append(format_tool_result(tool_call, error=f"Unknown tool '{tool_call['name']}'"))
                failed_tool_call = True
                continue
            tools_context['user_input_request'] = None
            tools_context['await_external_result'] = False
            tools_context['external_wait_message'] = None
            tools_context['result'] = None
            tool = tools_by_name[tool_call['name']]
            tools_context['tool_call_id'] = tool_call['call_id']
            tool_args = dict(tool_call['args'])
            tool_args.pop('tool_status', None)
            tools_context_before_call = copy.deepcopy(tools_context)
            try:
                tool_result = tool.with_context(**(record_context | self._get_tool_execution_context()))._ai_tool_run(
                    record, tool_args, tools_context,
                )
            except (*PG_CONCURRENCY_EXCEPTIONS_TO_RETRY, ConcurrencyError):
                raise
            except Exception as e:  # noqa: BLE001
                tools_context.clear()
                tools_context.update(tools_context_before_call)
                tool_results.append(format_tool_result(tool_call, error=f"Tool call failed: {e}"))
                exception_msg = f"{tool_call['name']}: failed with the following error: {e}"
                _logger.warning(exception_msg, exc_info=_logger.isEnabledFor(logging.DEBUG))
                yield {
                    'intermediary_message': format_tool_summary({'icon': 'warning', 'text': tool.name}, tool_call),
                    'is_tool_summary': True,
                }
                failed_tool_call = True
                continue
            if isinstance(tool_result, dict):
                yield {
                    'intermediary_message': format_tool_summary(tool_result.get("summary", {'text': tool.name}), tool_call),
                    'is_tool_summary': True,
                }
                if 'child_session_id' in tool_result:
                    tool_results.append({
                        'tool_name': tool_call['name'], 'tool_call_id': tool_call['call_id'],
                        'child_session_id': tool_result['child_session_id'],
                    })
                    continue
                if action := tool_result.get('action'):
                    # tmp backward compatibility
                    # should harmonize the result dict and move stuff from tool context to it
                    yield {'client_tool': {'name': 'do_action', 'params': {'action': action}, 'oneway': True}}
                if client_tool := tool_result.pop('client_tool', None):
                    if not client_tool.get('oneway'):
                        yield {
                            'client_tool': client_tool,
                            'pending_tool_call': {
                                'call_id': tool_call['call_id'],
                                'pending_results': tool_results,
                            }
                        }
                        return
                    yield {'client_tool': client_tool}
                if 'response' in tool_result:
                    tool_result = tool_result['response']
            else:
                yield {
                    'intermediary_message': format_tool_summary({'text': tool.name}, tool_call),
                    'is_tool_summary': True,
                }
            if links := tools_context.pop("preview_links", None):
                yield {'notifications': [{'type': 'ai_preview', 'body': link} for link in links]}
            if user_input_request := tools_context['user_input_request']:
                yield {
                    'user_input_request': user_input_request,
                    'pending_tool_call': {
                        'call_id': tool_call['call_id'],
                        'pending_results': tool_results,
                    },
                }
                return
            if tools_context['await_external_result']:
                yield {
                    'external_wait_message': tools_context['external_wait_message'] or self.env._("Waiting for an external result…"),
                    'pending_tool_call': {
                        'call_id': tool_call['call_id'],
                        'pending_results': tool_results,
                    },
                }
                return
            tool_results.append(format_tool_result(tool_call, result=tool_result))
        item = {'tool_results': tool_results}
        if not failed_tool_call and (final_message := tools_context['final_message']):
            item['final_message'] = final_message
        yield item

    def _abort_pending_tools(self):
        """Decline the remaining tools, wait for launched children, and post the interruption note."""
        self.ensure_one()
        pending_batch = self.pending_tool_call
        pending_results = pending_batch['pending_results']
        last_tool_calls = self._get_last_tool_calls()
        error = "The user chose not to proceed with this. Do not attempt it again unless they bring it up themselves."
        pending_results += [
            format_tool_result(tool_call, error=error)
            for tool_call in last_tool_calls[len(pending_results):]
        ]
        if any('child_session_id' in result for result in pending_results):
            pending_batch['declined'] = True
            pending_batch.pop('call_id', None)
            pending_batch.pop('await_external_result', None)
            self.write({
                'loop_state': 'waiting_child', 'resume_token': False,
                'pending_tool_call': pending_batch,
            })
            self._publish_response_state()
        else:
            self.event_ids = [Command.create({'metadata': self._format_tool_output_message(pending_results)})]
            self._finish_exchange('declined')
        self.turn_notifications = (self.turn_notifications or []) + [{'type': 'ai_note', 'body': self.env._("Skipped")}]
        self._post_turn_notifications()

    def _get_last_tool_calls(self):
        self.ensure_one()
        last_message = self._get_history(1)[0]
        return [part for part in last_message['content'] if part['type'] == 'tool_call']

    @api.model
    def _get_direct_response(
        self, instructions: str, message: AIMessageParts, tools=None,
        record=None, agent_id=None, on_item_callback=None, **completion_options: Unpack[CompletionOptions]
    ) -> AIMessageParts:
        """Gets a response from the LLM without managing conversation history/session state.

        This method is designed for "one-shot" requests where you need an immediate
        response from the LLM based on a given set of inputs, without needing to
        persist or resume a conversation (eg. server actions).

        :param instructions: System-level instructions or context to guide the LLM's behavior.
        :param message: user message to send to the LLM.
        :param tools: A recordset of `ir.actions.server` representing tools the LLM can call.
        :param record: The current Odoo record related to the request, if any.
        :param agent_id: The agent ID, if any.
        :param on_item_callback: A function to call for each item produced by the agentic loop
        :return: formatted response from the LLM, typically a list of message parts
        """
        tools_context = {
            'state': {},
            'tool_request_confirmed': False,
            'user_input_request': None,
            'await_external_result': False,
            'external_wait_message': None,
            'auto_confirm': False,
            'final_message': False,
            'user_id': self.env.user.id,
            'agent_id': agent_id,
            'enable_web_search': True,  # Allow get_single_response to use web search when the web-search skill is included in the agents accessible skills.
        }

        enable_tools(tools_context, tools.ids if tools else [])
        response_generator = self.env['ai.session']._run_agentic_loop(
            instructions=instructions,
            message=message,
            tools_context=tools_context,
            record=record,
            **completion_options
        )
        for item in response_generator:
            if on_item_callback is not None:
                on_item_callback(item, tools_context)
            if response := item.get('final_message'):
                if completion_options.get('resolve_web_sources', True):
                    for part in response:
                        sources = tools_context['state'].get('web_sources', {}) or part.get('sources', {})
                        if part['type'] != 'text' or not sources or not "[WEB_SOURCE:" in part['text']:
                            continue
                        part['text'] = apply_web_citations(part['text'], sources)
                return response
        return None

    def _run_agentic_loop(self, instructions, message, tools_context, record=None, **completion_options):
        """Internal: runs the LLM completion loop, handling tool calls until done.

        Not meant to be called directly. Use `_get_direct_response` for one-shot
        requests. Stateful conversations use bounded session advances from persisted state.
        """
        max_successive_calls = self.env["ir.config_parameter"].sudo().get_int("ai.max_successive_calls") or 30
        messages = []
        if message:
            messages.append({'role': 'user', 'content': message})

        for api_request_idx in range(max_successive_calls):
            updated_instructions = self._append_loaded_skills(instructions, tools_context['state'])
            tools = self.env["ir.actions.server"].sudo().browse(tools_context["state"]["available_tools"]).exists()
            # gemini does not support tools + web_grounding so should use a web search tool instead
            # make it so for every provider for consistency (skill prompt etc.)
            if tools and completion_options.get('web_grounding'):
                raise UserError(self.env._("The web grounding option is not supported with tools. Use the web search skill instead."))
            tools_by_name = {tool.ai_tool_name: tool for tool in tools} if tools else {}
            formatted_tools = self._prepare_tools(tools_by_name) if tools else {}
            try:
                response = self._get_completions(
                    messages[:],
                    updated_instructions,
                    formatted_tools,
                    **completion_options,
                )
            except InsufficientCreditError:
                return  # Stop the loop

            output_message = response['result']
            messages.append(output_message)

            tool_calls = [part for part in output_message['content'] if part['type'] == 'tool_call']
            if tool_calls:
                if message := get_text_from_parts([part for part in output_message['content'] if part['type'] == 'text']):
                    yield {'intermediary_message': message}
                yield {'tool_calls': tool_calls}
                all_tool_results = []
                items_to_yield = []
                for item in self._handle_tool_calls(tool_calls, tools_by_name, tools_context, record):
                    if tool_results := item.get('tool_results'):
                        all_tool_results.extend(tool_results)
                    if item.get('intermediary_message'):
                        yield item
                    else:
                        items_to_yield.append(item)
                if all_tool_results:
                    messages.append(self._format_tool_output_message(all_tool_results))
                for item in items_to_yield:
                    yield item

            else:
                message_parts = [part for part in output_message['content'] if part['type'] in ('text', 'inline_data')]
                yield {'final_message': message_parts}
                return
        raise UserError(self.env._("Number of successive API calls exceeded, please try again with a more precise request."))

    def _get_completions(
        self,
        messages: list[Message],
        instructions: str,
        tools: list[Tool] | None = None,
        **options: Unpack[CompletionOptions],
    ) -> CompletionResponse:
        params = {
            'messages': messages,
            'instructions': instructions,
            'tools': tools,
            **options,
        }
        return call_odoo_ai(self.env, "1/get_completions_sync", params)

    @api.model
    def _get_last_user_message(self, messages: list[Message]):
        for msg in messages[::-1]:
            if msg['role'] == 'user' and any(part['type'] == 'text' for part in msg['content']):
                return msg
        raise ValueError("No valid user message found in list of messages")

    @api.model
    def _prepare_tools(self, tools_dict):
        tools_list = []
        for tool_name, tool in tools_dict.items():
            tool_schema = json.loads(dedent(schema).strip()) if (schema := tool.ai_tool_schema) else {'properties': {}, 'required': [], 'type': 'object'}
            if self.env.context.get('ai_show_tool_status'):
                tool_schema['properties']['tool_status'] = {
                    'type': 'string',
                    'description': "The short status displayed while the tool is running. Examples: Searching your leads, Reassigning tasks, Enabling skill (skill_name). It should not contain technical terms.",
                }
                tool_schema['required'].append('tool_status')
            tools_list.append({
                'name': tool_name,
                'instructions': dedent(tool.ai_tool_description).strip() if tool.ai_tool_description else '',
                'schema': tool_schema,
            })
        return tools_list

    @api.model
    def _append_instruction_block(self, base_instructions, tag, parts):
        block = f"\n\n<{tag}>\n" + "\n".join(parts) + f"\n</{tag}>"
        end_marker = "[[END OF INSTRUCTIONS]]"
        if base_instructions.endswith(end_marker):
            return base_instructions[:-len(end_marker)] + block + "\n" + end_marker
        return base_instructions + block

    @api.model
    def _append_loaded_skills(self, base_instructions, state):
        loaded_skill_ids = state.get("loaded_skills")
        if not loaded_skill_ids:
            return base_instructions
        skills = self.env["ai.skill"].sudo().browse(loaded_skill_ids).exists()
        if not skills:
            return base_instructions
        skill_parts = []
        for skill in skills:
            skill_parts.append(
                f'''<skill_content name="{skill.name}" type="{skill.type}">
                {dedent(skill.instructions or "").strip()}
                </skill_content>
                '''
            )
        return self._append_instruction_block(base_instructions, "loaded_skills", skill_parts)

    def _append_subagent_instructions(self, base_instructions):
        if not self.agent_id.allowed_agent_ids:
            return base_instructions
        subagent_parts = [
            (
                "You may start multiple sessions with the same allowed agent. Each session has its own conversation "
                "history and session state; application records remain shared. For independent tasks, issue "
                "ai_tool_start_session calls together in one response, including calls to the same agent. "
                "Wait between calls only when a later task requires an earlier result."
            ),
        ]
        for agent in self.agent_id.allowed_agent_ids:
            subagent_parts.append(f'<agent id="{agent.id}" name="{agent.name}" description="{agent.subtitle}">')
        return self._append_instruction_block(base_instructions, "allowed_subagents", subagent_parts)

    def _clean_session_state(self):
        """Disable the skills and tools the agent no longer owns"""
        for session in self:
            if not (state := session.state):
                continue
            skills = session.agent_id.skill_ids
            loaded_skills = state.get("loaded_skills", [])
            if not (skills_to_disable := [skill for skill in loaded_skills if skill not in skills.ids]):
                continue
            active_skills = skills.filtered(lambda skill: skill.id in loaded_skills)
            active_tools = (active_skills.tool_ids | session._get_session_default_tools()).ids
            tools_to_disable = [tool for tool in state["available_tools"] if tool not in active_tools]
            session.state = disable_skills(state, skills_to_disable, tools_to_disable)

    def get_session_config(self):
        return {
            "enable_web_search": self.enable_web_search,
            "enable_resources_only": self.enable_resources_only,
            "enable_think_longer": self.enable_think_longer,
            "auto_confirm": self.auto_confirm,
            "show_agent_steps": self.show_agent_steps,
        }

    def update_session_config(self, updated_config: dict):
        if "ai_prompt_button_ref" in updated_config:
            updated_config.pop("ai_prompt_button_ref")
        updated_config = self.validate_session_update(updated_config)
        self.write(updated_config)
        if "enable_web_search" in updated_config and (state := self.state):
            self._initialize_tool_state(state)
            self.state = state

        if "auto_confirm" in updated_config:
            if self.auto_confirm:
                message = self.env._("✅ Auto-approval enabled for this chat.")
            else:
                message = self.env._("⛔ Auto-approval deactivated.")
            self.turn_notifications = (self.turn_notifications or []) + [{'type': 'ai_note', 'body': message}]

        Store(bus_channel=self.channel_id).add(self, "_store_session_fields")

    def validate_session_update(self, updated_config: dict):
        session_config = self.get_session_config()
        valid_update_config = {}

        for key, value in updated_config.items():
            if key not in session_config:
                raise ValidationError(self.env._("Unrecognized AI session configuration key: %(key)s", key=key))
            elif value != session_config[key]:
                valid_update_config[key] = value

        if not valid_update_config:
            return {}

        session_config.update(valid_update_config)
        validation_rules = self._get_session_config_rules()

        for key, rules in validation_rules.items():
            if not session_config.get(key):
                continue

            for dependent_key, expected_value in rules.items():
                if session_config.get(dependent_key) != expected_value:
                    raise ValidationError(self.env._("Can not enable %(key1)s and %(key2)s at the same time", key1=dependent_key, key2=key))

        return valid_update_config
