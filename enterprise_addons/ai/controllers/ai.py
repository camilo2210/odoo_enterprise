# Part of Odoo. See LICENSE file for full copyright and licensing details.
from werkzeug.exceptions import BadRequest, NotFound

from odoo import http
from odoo.http import request

from odoo.addons.iap import InsufficientCreditError

from ..utils.ai_utils import call_odoo_ai, get_text_from_parts, markdown_format


class AIController(http.Controller):
    @http.route(["/ai/get_direct_response"], type="jsonrpc", auth="user")
    def get_direct_response(self, prompt, interface_key=None, record_model=None, enable_html_response=False, schema=None):
        ai_agent = self.env["ai.composer"]._get_composer_from_key_and_model(interface_key, record_model).ai_agent_id
        if enable_html_response and schema:
            raise BadRequest("Cannot enable html response with structured outputs")
        if not ai_agent:
            raise NotFound()
        # todo: files/images?
        response_parts = ai_agent._generate_single_response(
            [{"type": "text", "text": prompt}],
            schema=schema
        )
        text_response = get_text_from_parts(response_parts)
        return markdown_format(text_response) if enable_html_response else text_response

    @http.route(["/ai/transcription/summary"], type="jsonrpc", auth="user")
    def get_transcription_summary(self, composer_id: int, summarization_instructions: str, text_to_summarize: str, ai_prompt_button_context: dict | None = None):
        transcription_composer = self.env['ai.composer'].search([
            ('id', '=', composer_id),
            ('interface_key', '=', 'voice_transcription_component'),
            ('ai_agent_id', '!=', False),
        ])
        if not transcription_composer:
            raise NotFound()
        ai_prompt_button_context = ai_prompt_button_context or {}
        ai_prompt_button = next(
            (p for p in transcription_composer.available_prompt_ids if p.id == ai_prompt_button_context.get('ai_prompt_button_ref')),
            self.env['ai.prompt.button']
        )
        composer_default_prompt = transcription_composer.default_prompt or ""
        if ai_prompt_button:
            prompt = ai_prompt_button._render_prompt(ai_prompt_button_context.get('rendering_record_id'))
            # The first part is the prompt. See _render_prompt method in ai.prompt.button model
            prompt[0]['text'] = f'{composer_default_prompt}\n{prompt[0]['text']}\n{summarization_instructions}\n{text_to_summarize}'
        else:
            prompt = [{
                'type': 'text',
                'text': f'{composer_default_prompt}\n{summarization_instructions}\nThis is the text to summarize:\n{text_to_summarize}',
            }]
        response_parts = transcription_composer.ai_agent_id._generate_single_response(prompt)
        return markdown_format(get_text_from_parts(response_parts))

    @http.route(["/ai/transcription/session"], methods=["POST"], type="jsonrpc", auth="user", readonly=True)
    def get_session_token(self, language: str, prompt: str):
        params = {
            'language': language,
            'prompt': prompt,
        }
        try:
            response = call_odoo_ai(self.env, '1/get_realtime_session_token', params)
            return {
                'status': 'success',
                'session_token': response['session_token'],
                'iap_transaction_token': response['iap_transaction_token'],
            }
        except InsufficientCreditError:
            return {
                'status': 'insufficient_credit',
            }

    @http.route("/ai/transcription/report_realtime_session_usage", type="jsonrpc", auth="user", methods=["POST"])
    def report_usage(self, iap_transaction_token, usage):
        params = {
            'iap_transaction_token': iap_transaction_token,
            'usage': usage,
        }
        call_odoo_ai(self.env, '1/report_realtime_session_usage', params, add_iap_token=False, timeout=5)

    @http.route("/ai/transcription", type="jsonrpc", auth="user")
    def transcribe(self, audio_base64, language=None):
        if not audio_base64:
            raise BadRequest("No audio data provided")

        params = {
            'audio': audio_base64,
            'mimetype': 'audio/mp3',
        }
        if language:
            params['language'] = language
        try:
            response = call_odoo_ai(self.env, '1/get_transcription', params)
            return {
                'status': 'success',
                'text': response['text'],
            }
        except InsufficientCreditError:
            return {
                'status': 'insufficient_credit',
            }

    @http.route("/ai/transcription/call", type="jsonrpc", auth="user", methods=["POST"])
    def transcribe_call(self, call_model, call_id):
        Model = request.env.get(call_model)
        Mixin = request.env.registry.get("call.transcription.mixin")

        if not (
            Model is not None and Mixin
            and isinstance(Model, Mixin)
            and "artifact_ids" in Model._fields
        ):
            raise BadRequest()

        try:
            call_id = int(call_id)
        except (ValueError, TypeError):
            raise BadRequest()
        call = Model.search_fetch([("id", "=", call_id)], ["artifact_ids"])
        if not call:
            raise NotFound()
        pending_artifacts = call.artifact_ids.filtered(
            lambda a: a.is_stt and a.transcription_state == "pending"
        )
        if pending_artifacts:
            pending_artifacts.action_transcribe_gevent()
        return "OK"

    @http.route(['/ai/url_scraper_result_ready/<batch_uuid>'], type='http', auth='public', methods=['POST'], csrf=False)
    def url_scraper_result_ready(self, batch_uuid):
        # This route is called by the website scraper server to notify the client that the result is ready.
        batch = request.env['ai.web.scraper.batch'].sudo().search([
            ('uuid', '=', batch_uuid),
            ('state', '=', 'submitted'),
        ], limit=1)
        if not batch:
            raise NotFound()

        request.env.ref('ai.ir_cron_run_web_scraper')._trigger()
