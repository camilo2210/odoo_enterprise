from typing import override

from odoo import _, fields, models

from .ai_website_service import MAX_GENERATED_IMAGES

WEBSITE_BUILDER_TIMEOUT = 180


class AiSession(models.Model):
    _inherit = 'ai.session'

    # Page identity captured when scraping suspends the conversation. The editor
    # supplies fresh context when it resumes; this snapshot guards against navigation.
    website_builder_context = fields.Json(string="Website Builder Context")

    @override
    def _get_model_round_options(self):
        completion_options = super()._get_model_round_options()
        if self._is_website_builder_session():
            completion_options['timeout'] = WEBSITE_BUILDER_TIMEOUT
        return completion_options

    @override
    def _submit_agent_request(self, message=None):
        if message is not None and self._is_website_builder_session():
            website_page = self.env.context['current_view_info']['website_page']
            if selected_elements := website_page.get('selected_elements'):
                selected_elements_data = [
                    {key: element[key] for key in ('id', 'tag', 'text')}
                    for element in selected_elements
                ]
                message = [*message, {
                    'type': 'text',
                    'text': f"<website_element_attachments>\n{selected_elements_data}\n</website_element_attachments>",
                }]
        return super()._submit_agent_request(message)

    @override
    def _resume_pending_interaction(self, response, ai_session_config=None, *, automatic=False):
        if self._is_website_builder_session() and response['kind'] == 'async':
            if not self._accept_scraper_resume(response['call_id']):
                return
        return super()._resume_pending_interaction(
            response, ai_session_config=ai_session_config, automatic=automatic,
        )

    @override
    def _get_session_advance_unavailable_message(self):
        self.ensure_one()
        if not self._is_website_builder_session():
            return False
        current_view_info = self.env.context.get('current_view_info')
        if not current_view_info or 'website_page' not in current_view_info:
            return _("Please open the website builder to use this AI on the website.")
        if not current_view_info['website_page']['is_page_ai_editable']:
            return _("The current page is a special page that cannot be edited by the AI.")
        return False

    def _get_context_input(self, rag_context):
        """State whether the AI may add JavaScript, the site's current brand kit,
        and the generated-image ceiling, with every single message."""
        context = super()._get_context_input(rag_context)
        if self._is_website_builder_session():
            state = "ON" if self.env['ai.website.service']._ai_scripts_allowed(self.state or {}) else "OFF"
            brand_kit = self.env['ai.website.service']._get_current_brand_kit()
            return context.replace(
                "</odoo_current_context>",
                f"\n## AI JavaScript\n{state}\n## Brand kit\n{brand_kit}\n"
                f"## Generated images\nAt most {MAX_GENERATED_IMAGES} `data-ai-image-prompt` "
                "placeholders total, across every action in one `apply_html_to_page` call.\n"
                "</odoo_current_context>",
            )
        return context

    def _run_agentic_loop(self, *args, **kwargs):
        if self._is_website_builder_session():
            kwargs['timeout'] = WEBSITE_BUILDER_TIMEOUT
        yield from super()._run_agentic_loop(*args, **kwargs)

    def _set_pending_tool_call(self, pending_tool_call):
        # Session bookkeeping runs with the session's privileges; the tool itself
        # runs as the editor, who need not have write access to ai.session.
        if pending_tool_call.get('await_external_result'):
            self._save_context_for_async_resume()
        super()._set_pending_tool_call(pending_tool_call)

    def _save_context_for_async_resume(self):
        """Remember the target page, without retaining its editable HTML."""
        self.ensure_one()
        if not self._is_website_builder_session():
            return
        page = (self.env.context.get('current_view_info') or {}).get('website_page') or {}
        self.website_builder_context = {
            'current_view_info': {'website_page': {
                key: page.get(key) for key in ('main_object', 'location', 'website_id')
            }},
        }

    def _get_scraper_resume_data(self):
        """Expose a ready call's identity, without sending its scraped content."""
        self.ensure_one()
        pending = self.pending_tool_call or {}
        call_id = str(pending.get('call_id'))
        if (
            not self.channel_id
            or not self._is_website_builder_session()
            or not pending.get('await_external_result')
            or call_id not in (self.state or {}).get('website_scraper_results', {})
        ):
            return False
        snapshot = (self.website_builder_context or {}).get('current_view_info') or {}
        page = snapshot.get('website_page') or {}
        return {
            'channel_id': self.channel_id.id,
            'session_id': self.id,
            'resume_token': self.resume_token,
            'tool_call_id': call_id,
            'target_page': {key: page.get(key) for key in ('main_object', 'location', 'website_id')},
        }

    def _accept_scraper_resume(self, call_id):
        """Ignore obsolete notifications and let only one editor resume a ready result."""
        self.ensure_one()
        if not call_id or not self.try_lock_for_update():
            return False
        self.invalidate_recordset(['pending_tool_call', 'state', 'website_builder_context'])
        pending = self.pending_tool_call or {}
        if (
            not pending.get('await_external_result')
            or str(pending.get('call_id')) != str(call_id)
            or str(call_id) not in (self.state or {}).get('website_scraper_results', {})
        ):
            return False
        snapshot = (self.website_builder_context or {}).get('current_view_info') or {}
        target = snapshot.get('website_page') or {}
        current = (self.env.context.get('current_view_info') or {}).get('website_page') or {}
        return bool(
            target.get('main_object')
            and target['main_object'] == current.get('main_object')
            and target.get('website_id') == current.get('website_id')
        )

    def _is_website_builder_session(self):
        return len(self) == 1 and self.ai_composer_id.interface_key == 'website_builder_ai'
