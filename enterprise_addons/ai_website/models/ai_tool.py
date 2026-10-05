# Part of Odoo. See LICENSE file for full copyright and licensing details.

import inspect
import json
import logging
import re
from urllib.parse import urlsplit

from markupsafe import Markup

from odoo import _, api, models
from odoo.exceptions import ConcurrencyError, MissingError, UserError
from odoo.fields import Domain
from odoo.sql_db import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY

from .ai_website_service_brand_kit import (
    _USER_COLOR_PALETTE_URL,
    _USER_WEBSITE_VALUES_URL,
)
from odoo.addons.ai.utils.ai_utils import (
    UserInputResponse,
    get_text_from_parts,
    make_confirmation_request_preview,
)
from odoo.addons.ai_website.models.ir_attachment import ALLOWED_IMAGE_SCHEMES

_logger = logging.getLogger(__name__)

_WEBSITE_SCRAPER_TIMEOUT_SECONDS = 600
_MAX_SCRAPE_URLS = 10
_MAX_SCREENSHOT_BYTES = 50 * 1024 * 1024

# Shape check only: cheaper than decoding a multi-megabyte screenshot to throw the result away.
_BASE64_RE = re.compile(r'[A-Za-z0-9+/]*={0,2}')

_MAX_MENU_OPERATIONS = 50

_REVIEW_RESULT_SCHEMA = {
    'type': 'object',
    'properties': {
        'safe': {
            'type': 'boolean',
            'description': 'True if the content is safe to apply to the website page.',
        },
        'reason': {
            'type': 'string',
            'description': 'Empty string when safe. A brief, specific explanation of the safety concern when unsafe.',
        },
    },
    'required': ['safe', 'reason'],
    'additionalProperties': False,
}

# External image URLs inside a CSS/SCSS `url()`, e.g. `background-image: url("https://…")`.
_CSS_URL_RE = re.compile(r'url\(\s*[\'"]?(https?://[^\'")\s]+)[\'"]?\s*\)', re.IGNORECASE)

# Routes an AI script must never reach.
_DENIED_ROUTE_PREFIXES = (
    '/jsonrpc',
    '/xmlrpc',
    '/web/dataset',
    '/web/session',
    '/web/database',
    '/web/action',
    '/web/webclient',
    '/web/binary/upload',
    '/web/login',
    '/web/signup',
    '/web/reset_password',
)

_MAX_ROUTE_SEARCH_RESULTS = 30


def _get_route_doc(endpoint):
    """
    Return the documentation of a route, gathered along the whole
    controller hierarchy.
    """
    method = getattr(endpoint, 'func', endpoint)
    controller = getattr(method, '__self__', None)
    if controller is None:
        return inspect.getdoc(method) or ""

    docs = []
    for cls in reversed(type(controller).mro()):
        submethod = cls.__dict__.get(method.__name__)
        doc = getattr(submethod, '__doc__', None)
        doc = inspect.cleandoc(doc) if doc else ""
        if doc and doc not in docs:
            docs.append(doc)
    return "\n\n".join(docs)


class AITool(models.AbstractModel):
    _inherit = 'ai.tool'

    @api.model
    def _ai_tool_generate_image(self, tool_context, prompt, images_paths, image_title, feedback, aspect_ratio='1:1'):
        """In a builder session, persist the generated images, return their URLs
        and keep the agentic loop alive so the model chains into
        apply_html_to_page instead of ending the turn."""
        is_builder_session = self.env['ai.session'].sudo().browse(
            tool_context.get('session_id'))._is_website_builder_session()

        result = super()._ai_tool_generate_image(tool_context, prompt, images_paths, image_title, feedback, aspect_ratio)
        if not is_builder_session:
            return result
        final_message = tool_context.get('final_message') or []
        attachments = self.env['ir.attachment'].search([('id', 'in', [
            part['metadata']['attachment_id']
            for part in final_message
            if part.get('type') == 'inline_data' and part.get('metadata', {}).get('attachment_id')
        ])])
        if not attachments:
            return result
        # The base tool set final_message to the image result; left set it ends
        # the turn, so clear it to keep the loop alive for image placement.
        tool_context['final_message'] = None
        service = self.env['ai.website.service']
        urls = "\n".join(f"- ID: {a.id}, URL: {service._create_public_image_url(a)}" for a in attachments)
        result['response'] = (
            f"Generated {len(attachments)} image(s). Permanent URLs:\n{urls}\n\n"
            "You MUST now call `apply_html_to_page` to place these images on the page "
            "using appropriate selectors. Do not message the user until placement is done."
        )
        return result

    @api.model
    def _ai_tool_get_snippets(self, snippet_keys):
        """
        Return the HTML structures of the requested snippets, along with a
        description of their purpose and content.
        """
        if not snippet_keys:
            return "No snippet keys provided. Please specify which snippets you want to retrieve."
        service = self.env['ai.website.service']
        result = (
            "Here are the HTML structures of the snippets you requested.\n\n"
        )
        for snippet_key in snippet_keys:
            result += f"## Snippet: {snippet_key}\n"
            hint, html = service._get_snippet_html(snippet_key)
            if hint:
                result += f"_{hint.label}_ — {hint.intent}\n\n"
            if not html:
                result += "No snippet found with this key. Try another one.\n\n"
            else:
                result += f"```html\n{html}\n```\n\n"
        return {
            'response': result,
            'summary': {'icon': 'explore', 'text': self.env._("Looked up snippets")},
        }

    @api.model
    @api.ormcache()
    def _ai_get_backend_routes_map__(self):  # noqa: PLW3201
        """
        Return {path: {path, methods, type, auth, endpoint_name, doc}} for every
        route of this database, minus the ones an AI script must never reach.
        """
        router = self.env['ir.http'].routing_map()
        actions = {}
        for rule in router.iter_rules():
            if rule.rule in actions or rule.rule.startswith(_DENIED_ROUTE_PREFIXES):
                continue
            endpoint = rule.endpoint
            methods = endpoint.routing.get('methods')
            endpoint_func = getattr(endpoint, 'func', endpoint)
            actions[rule.rule] = {
                'path': rule.rule,
                'methods': methods,
                'type': endpoint.routing.get('type', 'http'),
                'auth': endpoint.routing.get('auth', 'user'),
                'endpoint_name': getattr(endpoint_func, '__name__', ''),
                'doc': _get_route_doc(endpoint),
            }
        return actions

    @api.model
    def _ai_tool_search_backend_routes(self, pattern):
        """
        Return the routes whose path, endpoint name or documentation matches
        the given regular expression.
        """
        try:
            route_re = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"'{pattern}' is not a valid regular expression ({e}). Search again."

        matches = []
        for action in self._ai_get_backend_routes_map__().values():
            # The path alone is too narrow: "cart" must find a route named
            # add_to_cart or one that has "cart" in the doc .
            if route_re.search(f"{action['path']} {action['endpoint_name']} {action['doc']}"):
                matches.append(action)

        if not matches:
            return (
                f"No route matches '{pattern}'. Try a broader pattern (a single word, or "
                "several joined with |). If nothing turns up, tell the user this isn't "
                "supported yet rather than calling a path you haven't found here."
            )

        truncated = len(matches) - _MAX_ROUTE_SEARCH_RESULTS
        result = f"# Routes matching '{pattern}'\n\n"
        for action in matches[:_MAX_ROUTE_SEARCH_RESULTS]:
            result += self._ai_format_route(action)
        if truncated > 0:
            result += (
                f"{truncated} more route(s) matched and are not shown. "
                "Search again with a narrower pattern to see them.\n"
            )
        return {
            'response': result,
            'summary': {'icon': 'search', 'text': self.env._("Searched backend routes")},
        }

    @api.model
    def _ai_format_route(self, action):
        """
        Render one route: what it does, and the `type`/`methods`/`auth` the
        skill's own encoding rules key off.
        """
        methods = action['methods']
        return (
            f"## {action['path']}\n"
            f"- methods: {', '.join(methods) if methods else 'any'}\n"
            f"- type: {action['type']}\n"
            f"- auth: {action['auth']}\n"
            f"{action['doc'] or 'No documentation available. Do not guess its parameters.'}\n\n"
        )

    @api.model
    def _ai_tool_get_backend_route_docs(self, paths):
        """
        Return the full documentation (as written in its own docstring) for
        each of the given backend route.
        """
        actions = self._ai_get_backend_routes_map__()
        result = ""
        for path in paths:
            action = actions.get(path)
            if not action:
                result += (
                    f"## {path}\n"
                    "No such route on this database, or it is one an AI script is never "
                    "allowed to call. Do not call it: find the right path with the "
                    "\"Search Backend Routes\" tool.\n\n"
                )
                continue
            result += self._ai_format_route(action)
        return {
            'response': result,
            'summary': {'icon': 'description', 'text': self.env._("Read backend routes docs")}
        }

    @api.model
    def _ai_tool_search_images(self, query):
        """
        Search for images using the Unsplash API.
        """

        response = self.env['ir.attachment']._fetch_unsplash_images(
            query=query, page=1, per_page=30)

        if response.get('error') in ('no_access', 'key_not_found'):
            return (
                'No stock photo library is configured, so no image can be searched. '
                'Do NOT call this tool again this turn. Keep the default placeholder images that '
                'come with the snippets exactly as they are: leave their `src` (or `background-image` '
                'style) untouched and do NOT remove them. Do NOT generate images instead: only write '
                '<img data-ai-image-prompt="..."> if the user explicitly asked for AI generated images.'
            )
        if 'error' in response:
            return f"An unknown error occurred while searching Unsplash: {response['error']}"

        if not response.get('results'):
            return (
                f'No stock photo matches "{query}". Try another query, and if nothing usable comes '
                'back, keep the default placeholder images that come with the snippets exactly as '
                'they are. Do NOT generate images instead: only write '
                '<img data-ai-image-prompt="..."> if the user explicitly asked for AI generated images.'
            )

        result = (
            "Here are some images from Unsplash that match your search query.\n"
        )
        for image in response['results']:
            width = image.get('width') or None
            height = image.get('height') or None
            result += (
                f'- URL: "{image['urls']['regular']}", '
                f'Type: "{image.get('asset_type') or 'photo'}", '
                f'Description: "{image.get('description') or 'No description'}", '
                f'Slug: "{image.get('slug') or 'N/A'}", '
                f'Average color: "{image.get('color') or 'N/A'}", '
                f'Aspect ratio (W/H): {round(width / height, 2) if width and height else 'N/A'}\n'
            )
        return {
            'response': result,
            'summary': {'icon': 'public', 'text': self.env._("Searched images on Unsplash")},
        }

    @api.model
    def _ai_tool_create_image_attachments(self, attachments_ids):
        """
        Process the images given in attachments_ids, create permanent
        attachments to prevent them from being deleted at the end of the AI
        session.
        Return the public image URLs.
        """
        attachments = self.env['ir.attachment'].search([('id', 'in', attachments_ids)])
        if not attachments:
            return "No attachments with the given IDs were found."

        result = (
            "Here are the public URLs of the images you uploaded. "
            "Use these URLs to reference the images in your HTML and CSS.\n\n"
        )

        def is_valid_attachment(attachment):
            if attachment.res_model != 'discuss.channel':
                return False
            channel = self.env['discuss.channel'].browse(attachment.res_id)
            return channel.sudo().ai_agent_id and self.env.user.partner_id in channel.channel_member_ids.partner_id

        service = self.env['ai.website.service']
        error_not_found = "Not found. Please make sure the attachment was provided by the user.\n"
        for attachment in attachments:
            result += f"- ID: {attachment.id}, "
            try:
                if is_valid_attachment(attachment):
                    result += f"URL: {service._create_public_image_url(attachment)}\n"
                else:
                    result += error_not_found
            except MissingError:
                result += error_not_found

        for attachment_id in attachments_ids:
            if attachment_id not in attachments.ids:
                result += f"- ID: {attachment_id}, {error_not_found}"
        return {
            'response': result,
            'summary': {'icon': 'edit_square', 'text': self.env._("Created Attachments")},
        }

    @api.model
    def _call_ai_reviewer(self, prompt):
        """Call the ai reviewer agent with a pre-formatted prompt.

        Returns ``(is_safe, reason)`` where ``is_safe`` is a bool and ``reason``
        is an explanation string (empty when safe).
        """
        reviewer = self.env.ref('ai_website.ai_agent_reviewer', raise_if_not_found=False)

        try:
            response = reviewer._generate_single_response(
                message=[{'type': 'text', 'text': prompt}],
                schema=_REVIEW_RESULT_SCHEMA,
            )
        except (*PG_CONCURRENCY_EXCEPTIONS_TO_RETRY, ConcurrencyError):
            raise
        except Exception:  # noqa: BLE001
            return False, "Safety reviewer call failed"
        if not response:
            return False, "Safety reviewer returned no response"
        try:
            result = json.loads(get_text_from_parts(response))
            return bool(result.get('safe', False)), result.get('reason', '')
        except (json.JSONDecodeError, TypeError, KeyError):
            return False, "Safety reviewer returned unparseable response"

    @api.model
    def _ai_review(self, actions):
        """Ask the safety reviewer to assess AI-generated actions."""
        items = []
        for i, action in enumerate(actions):
            header = (
                f"### Action {i + 1}\n"
                f"- zone: {action.get('zone', 'n/a')}\n"
                f"- mode: {action.get('mode', 'n/a')}\n"
                f"- selector: {action.get('selector') or 'none'}\n"
            )
            items.append(header + f"```html\n{action.get('content', '')}\n```")
        prompt = (
            "Review the following HTML actions that an AI assistant is about to apply "
            "to a public-facing Odoo website page. The HTML of an action may embed its "
            "JavaScript in <script data-ai-script-id=\"...\"> tags:\n\n"
            + "\n\n".join(items)
        )
        return self._call_ai_reviewer(prompt)

    @api.model
    def _ai_tool_request_ai_scripts(self, tool_context, scope):
        """Turn AI JavaScript on, in the scope the user asked for in the chat."""
        session_state = tool_context['state']
        ai_website_service = self.env['ai.website.service']
        if ai_website_service._ai_scripts_allowed(session_state):
            return "JavaScript is already enabled. You can write script actions."

        if scope not in ('chat', 'website'):
            raise ValueError("scope must be 'chat' or 'website', whichever the user asked for.")

        if scope == 'website':
            website = ai_website_service._current_website()
            website.check_access('write')
            website.sudo().ai_allow_scripts = True
            reach = "for the whole website, until they switch the setting back off"
        else:
            session_state['website_ai_allow_scripts'] = True
            reach = "for this conversation only"

        return {
            'response': (
                f"Enabled {reach}: you can write script actions from here on. "
                "Load the Website JavaScript skill for the rules they must follow."
            ),
            'summary': {'icon': 'settings', 'text': self.env._("Enabled JavaScript")}
        }

    @api.model
    def _format_web_scraper_result(self, result, scrape_requests):
        """Format scraper text and assets as an AI tool result.

        Screenshots are returned as inline image parts rather than embedded in the text
        result, so vision-capable providers can inspect them as images. They are dropped
        past ``_MAX_SCREENSHOT_BYTES``: a tool result is stored in the session history and
        replayed to the provider on every later request of the conversation, so an
        oversized one is paid for again on each turn.

        :param scrape_requests: the scraper URL payloads the result answers, as built by
            :meth:`_clean_scrape_requests`
        """
        pages = (result or {}).get('pages', {})
        formatted_pages = []
        screenshot_parts = []
        for scrape_request in scrape_requests:
            url = scrape_request['url']
            page = pages.get(url, {})
            if page.get('failed'):
                formatted_pages.append(
                    f"## URL: {url}\n"
                    f"Scraping failed: {page.get('reason') or 'The scraper reported a failure for this URL.'}",
                )
                continue

            try:
                payload = json.loads(page.get('payload') or '{}')
            except (json.JSONDecodeError, TypeError):
                payload = None

            if not isinstance(payload, dict):
                formatted_pages.append(f"## URL: {url}\nInvalid scraper payload returned for this URL.")
                continue

            page_parts = [f"## URL: {url}"]
            content = (payload.get('text') or '').strip()
            page_parts.append(content or "No text content returned by the scraper.")

            images = (payload.get('images') or []) if scrape_request['fetch_image_urls'] else []
            image_lines = []
            for image in images:
                if not isinstance(image, dict) or not isinstance(image.get('src'), str):
                    continue
                # The page is third-party content: only relay srcs that can end up in
                # the page and be localized on save, never `javascript:`/`data:` ones.
                if urlsplit(image['src']).scheme not in ALLOWED_IMAGE_SCHEMES:
                    continue
                image_details = [f'URL: "{image["src"]}"']
                for field, label in (
                    ('kind', 'Type'),
                    ('alt', 'Alt text'),
                    ('title', 'Title'),
                    ('label', 'Label'),
                    ('top', 'Top'),
                    ('left', 'Left'),
                    ('width', 'Width'),
                    ('height', 'Height'),
                ):
                    field_value = image.get(field)
                    if isinstance(field_value, int):
                        field_value = str(field_value)
                    if isinstance(field_value, str) and field_value.strip():
                        image_details.append(f'{label}: "{field_value}"')
                image_lines.append(f"- {', '.join(image_details)}")
            if image_lines:
                page_parts.extend([
                    "Image source URLs (use these to reference the original page assets):",
                    *image_lines,
                ])

            screenshot_url = payload.get('screenshot_url') if scrape_request['take_screenshot'] else None
            screenshot_prefix = 'data:image/png;base64,'
            if isinstance(screenshot_url, str) and screenshot_url.startswith(screenshot_prefix):
                screenshot_data = screenshot_url.removeprefix(screenshot_prefix)
                if len(screenshot_data) > _MAX_SCREENSHOT_BYTES:
                    _logger.info(
                        "AI website scraper: dropped a %d bytes screenshot for %s (max %d)",
                        len(screenshot_data), url, _MAX_SCREENSHOT_BYTES,
                    )
                elif _BASE64_RE.fullmatch(screenshot_data):
                    page_parts.append("A screenshot of this page is attached for visual reference.")
                    screenshot_parts.append({
                        'type': 'inline_data',
                        'mimetype': 'image/png',
                        'data': screenshot_data,
                        'metadata': {'source_url': url},
                    })

            formatted_pages.append("\n".join(page_parts))

        if not formatted_pages:
            return "The web scraper did not return any page content."

        intro = (
            "Here is the scraped content for the requested URLs. Use the text to extract relevant "
            "information, and the image source URLs, where you asked for them, to reuse page assets."
        )
        if screenshot_parts:
            intro += " The attached screenshots are visual references for the page you are building."
        formatted_result = f"{intro}\n\n" + "\n\n".join(formatted_pages)
        if not screenshot_parts:
            return formatted_result
        return [{'type': 'text', 'text': formatted_result}, *screenshot_parts]

    @api.model
    def _clean_scrape_requests(self, urls):
        """Turn the tool's ``urls`` argument into scraper URL payloads.

        Each entry carries its own media options: fetching image URLs and rendering a
        screenshot both cost time on the scraper side, and a screenshot is replayed to the
        provider on every later turn, so the agent opts in page by page. A bare string is
        accepted as a text-only request.

        :param urls: the raw tool argument, a list of URLs and/or
            ``{'url', 'fetch_images', 'take_screenshot'}`` objects
        :return: deduplicated scraper URL payloads, in the order they were requested
        :rtype: list of dict
        """
        requests_by_url = {}
        for entry in urls or []:
            if isinstance(entry, str):
                entry = {'url': entry}
            if not isinstance(entry, dict) or not isinstance(entry.get('url'), str):
                continue
            url = entry['url'].strip()
            if not url:
                continue

            fetch_image_urls = bool(entry.get('fetch_images'))
            take_screenshot = bool(entry.get('take_screenshot'))
            if old_entry := requests_by_url.get(url):
                fetch_image_urls = fetch_image_urls or old_entry['fetch_image_urls']
                take_screenshot = take_screenshot or old_entry['take_screenshot']

            requests_by_url[url] = {
                'url': url,
                'check_robots_txt': True,
                'fetch_image_urls': fetch_image_urls,
                'take_screenshot': take_screenshot,
            }
        return list(requests_by_url.values())

    @api.model
    def _ai_tool_scrape_website_pages(self, tool_context, urls):
        """Start/resume scraping one or more specific web pages."""
        scrape_requests = self._clean_scrape_requests(urls)
        if not scrape_requests:
            return "No URLs provided. Please provide one or more URLs to scrape."
        if len(scrape_requests) > _MAX_SCRAPE_URLS:
            return (
                f"Too many URLs ({len(scrape_requests)}). Scrape at most {_MAX_SCRAPE_URLS} URLs "
                "per call, starting with the most relevant ones."
            )

        call_id = str(tool_context['tool_call_id'])
        request_by_call = tool_context['state'].setdefault('website_scraper_requests', {})
        result_by_call = tool_context['state'].setdefault('website_scraper_results', {})

        if scraper_result := result_by_call.pop(call_id, None):
            request_by_call.pop(call_id, None)
            if scraper_result.get('state') == 'failed':
                return f"Web scraping failed: {scraper_result.get('error') or 'Unknown error'}"
            return self._format_web_scraper_result(scraper_result.get('result'), scrape_requests)

        session = self.env['ai.session'].browse(tool_context.get('session_id'))
        if not session:
            return "Web scraping is not available in this conversation."

        Batch = self.env['ai.web.scraper.batch'].sudo()
        batch_id = request_by_call.get(call_id)
        batch = Batch.browse(batch_id).exists() if batch_id else Batch.browse()
        if not batch:
            batch = Batch._enqueue(
                scrape_requests,
                'ai.tool',
                timeout_seconds=(
                    self.env['ir.config_parameter'].sudo().get_int('ai_website.scraper_timeout_seconds')
                    or _WEBSITE_SCRAPER_TIMEOUT_SECONDS
                ),
            )
            batch.write({
                'ai_session_id': session.id,
                'tool_call_id': call_id,
            })
            request_by_call[call_id] = batch.id

        if batch.state in ('to_submit', 'submitted'):
            tool_context['await_external_result'] = True
            tool_context['external_wait_message'] = self.env._(
                "Having a look at your reference(s), give me a minute or two"
            )
            return None
        if batch.state == 'done':
            request_by_call.pop(call_id, None)
            return self._format_web_scraper_result(batch.result, scrape_requests)
        if batch.state == 'failed':
            request_by_call.pop(call_id, None)
            return f"Web scraping failed: {batch.error or 'Unknown error'}"
        return "Web scraping request was not found."

    @api.model
    def _web_scraper_result_ready(self, batch):
        """Hand a finished scraper batch back to the conversation that asked for it."""
        if not batch.ai_session_id or not batch.tool_call_id:
            return

        session = batch.ai_session_id.sudo()
        pending = session.pending_tool_call or {}
        if not pending.get('await_external_result') or str(pending.get('call_id')) != str(batch.tool_call_id):
            # The session moved on (the user cancelled, or a new turn replaced the pending
            # call), so nothing will ever read this result. Drop it rather than parking it
            # in `state`, where it would linger for the life of the session.
            _logger.info(
                "AI website scraper: batch %s no longer matches the pending tool call of session %s",
                batch.id, session.id,
            )
            return

        state = dict(session.state or {})
        result_by_call = dict(state.get('website_scraper_results', {}))
        result_by_call[str(batch.tool_call_id)] = {
            'state': batch.state,
            'result': batch.result,
            'error': batch.error,
        }
        state['website_scraper_results'] = result_by_call
        session.state = state

        # Resume through the editor's HTTP request, where client tools can
        # run and return their results. The editor can also discover this saved
        # result after reopening or reconnecting if it missed the notification.
        if resume_data := session._get_scraper_resume_data():
            session.create_uid._bus_send('ai_website/scraper_result_ready', resume_data)

    @api.model
    def _edited_page_identity(self):
        """Identify the page this turn is editing, as the builder reported it.

        Sent along the edits so the builder can check they are still meant for the page it
        has open: generation can take long enough for the user to navigate elsewhere.
        """
        website_page = (self.env.context.get('current_view_info') or {}).get('website_page') or {}
        return {
            'main_object': website_page.get('main_object'),
            'location': website_page.get('location'),
        }

    def _ai_tool_create_page(self, tool_context, page_name, add_to_menu=False, leave_empty=False):
        """Create a page, then have the editor navigate to it before returning."""
        current_page = self.env.context.get('current_view_info', {}).get('website_page', {})
        pending_url = tool_context['state'].get('page_url_pending_html')
        if pending_url and pending_url == current_page.get('location'):
            return (
                f"Cannot create another page yet: {pending_url} was just created and still has "
                "no content. Call 'Apply HTML to Page' for it first, then create the next page."
            )
        tool_context['state'].pop('page_url_pending_html', None)

        save_current_page = tool_context['tool_request_confirmed']
        if current_page.get('pending_changes') and not save_current_page:
            tool_context['user_input_request'] = {
                'type': 'confirmation',
                'body': _("Do you want to save your changes to the current page before creating the new one?"),
                'choices': [
                    {'label': _("Save changes and create new page"), 'value': UserInputResponse.CONFIRM_ONCE},
                    {'label': _("Always save changes when creating a page"), 'value': UserInputResponse.AUTO_CONFIRM},
                    {'label': _("Keep editing this page"), 'value': UserInputResponse.DECLINE},
                ],
                'allow_free_text': False,
            }
            return None

        website = (
            self.env.website
            or self.env['website'].browse(self.env.context.get('host_id'))
            or self.env.ref('base.default_website')
        )
        page = website.with_context(website_id=website.id).new_page(
            name=page_name, add_menu=add_to_menu,
        )
        if not leave_empty:
            tool_context['state']['page_url_pending_html'] = page['url']
        return {
            'client_tool': {
                'name': 'ai_website_navigate_to_edit',
                'params': {
                    'url': page['url'],
                    'save': bool(save_current_page),
                    'success_message': (
                        _("Page created successfully.") if leave_empty
                        else _("Page created successfully. Now apply the requested HTML to the new page.")
                    ),
                },
            },
        }

    @api.model
    def _ai_tool_apply_html_to_page(self, tool_context, actions):
        """Review, validate and sanitize the AI's HTML actions, then hand them to the
        client tool that applies them — or, for a full-page build, finalizes it."""
        if isinstance(actions, str):
            try:
                actions = json.loads(actions)
            except json.JSONDecodeError as e:
                _logger.error("apply_html: actions string is not valid JSON: %s", e)
                return f"Invalid `actions` payload — expected a JSON array, got a string that won't parse ({e})."
        if not isinstance(actions, list) or not actions:
            return "Invalid `actions` payload — expected a non-empty list of action objects."
        is_safe, reason = self._ai_review(actions)
        if not is_safe:
            raise ValueError(f"HTML content blocked by safety review: {reason}")
        service = self.env['ai.website.service']
        service._validate_html_actions(actions, tool_context['state'])
        service._sanitize_html_actions(actions)
        service._validate_image_placeholders(actions)
        tool_context['state'].pop('page_url_pending_html', None)

        full_build = next((
            a for a in actions
            if a.get('zone') == 'main'
            and a.get('mode') == 'replace'
            and not (a.get('selector') or '').strip()
        ), None)

        # Any other action bundled in the same call (e.g. a footer edit) targets a
        # zone the full build doesn't touch. It rides along in the finalize tool's
        # params and is applied together with the finalized page, rather than as a
        # second client tool call that could land before or after it.
        other_actions = [action for action in actions if action is not full_build] if full_build else []
        actions_to_resolve = other_actions if full_build else actions

        scoped = service.with_context(website_id=service._current_website().id)
        for action in actions_to_resolve:
            action['content'] = scoped._generate_placeholder_images(action['content'])

        if full_build:
            note = self.env._(
                "Page composed. Images and the finishing passes now run separately and "
                "the result is shown to the user when they complete — do not apply the "
                "page again."
            )
            if other_actions:
                note += self.env._(" The other actions in this call were applied immediately.")
            return {
                'client_tool': {
                    'name': 'finalize_website_page',
                    'params': {
                        'html': full_build['content'],
                        'target_page': self._edited_page_identity(),
                        'other_actions': other_actions,
                        'note': note,
                    },
                },
                'summary': {'icon': 'design_services', 'text': self.env._("Applied changes to the page")},
            }

        return {
            'client_tool': {
                'name': 'website_apply_html',
                'params': {
                    'actions': actions,
                    'target_page': self._edited_page_identity(),
                },
            },
            'summary': {'icon': 'design_services', 'text': self.env._("Applied changes to the page")},
        }

    @api.model
    def _ai_tool_read_custom_css(self):
        """Read the current content of user_custom_rules.scss."""
        return {
            'response': self.env['ai.website.service']._read_custom_css(),
            'summary': {'icon': 'description', 'text': self.env._("Read custom style")}
        }

    @api.model
    def _localize_css_external_images(self, css_content):
        """Replace external image URLs inside ``url()`` by local attachment URLs.

        The builder localizes external images on save, but custom SCSS never goes through
        the editable DOM, so it needs its own pass. Returns ``(css_content, note)`` where
        ``note`` reports the URLs that had to be left external, for the AI to relay.
        """
        external_urls = _CSS_URL_RE.findall(css_content)
        if not external_urls:
            return css_content, ""

        localized = self.env['ir.attachment']._localize_external_image_urls(external_urls)
        for source_url, local_url in localized['sources'].items():
            css_content = css_content.replace(source_url, local_url)
        if not localized['errors']:
            return css_content, ""
        return css_content, "\n".join([(
                "These image URLs could not be copied into Odoo and are still pointing at the "
                "external site, so they may break later. Consider using another image:"
            ),
            *(f'- URL: "{url}", Error: {error}' for url, error in localized['errors'].items()),
        ])

    @api.model
    def _ai_tool_get_website_menus(self):
        """Return the website menu structure and the list of website pages."""
        service = self.env['ai.website.service']
        website = service._current_website()
        result = (
            "# Website menu\n"
            "Here is the current navigation menu structure of the website. "
            "Items are ordered by sequence; nested items are sub-menus of the "
            "item above them.\n"
            "The menu supports at most two levels: only top-level items can "
            "have sub-items.\n"
            f"{service._format_website_menu_tree(website)}\n"
            "# Website pages\n"
            "Here are the existing pages of the website that menu items can "
            "link to.\n"
        )
        pages = self.env['website.page'].search(website.website_domain(), order='url')
        for page in pages:
            result += f'- URL: "{page.url}", Name: "{page.name}"'
            if not page.is_published:
                result += " (unpublished)"
            result += "\n"
        return {
            'response': result,
            'summary': {'icon': 'explore', 'text': self.env._("Read the website menu")}
        }

    @api.model
    def _ai_tool_edit_website_menus(self, tool_context, operations):
        """Create, update and delete website menu items."""
        if not operations:
            return "No operations provided. Please specify the menu operations to apply."
        if len(operations) > _MAX_MENU_OPERATIONS:
            raise ValueError(f"Too many operations ({len(operations)}). Maximum allowed per call is {_MAX_MENU_OPERATIONS}.")

        service = self.env['ai.website.service']
        website = service._current_website()
        menus_by_id = service._prefetch_menus_for_operations(website, operations)

        root_menu = website.menu_id
        created_by_temp_id = {}
        created_ids = set()
        updated_ids = set()
        deleted_records = []

        def get_menu(menu_id):
            menu = menus_by_id.get(int(menu_id))
            if not menu:
                raise ValueError(f"Menu item with ID {menu_id} not found on the current website.")
            return menu

        def resolve_parent(operation):
            if parent_temp_id := operation.get('parent_temp_id'):
                if parent_temp_id not in created_by_temp_id:
                    raise ValueError(
                        f'Unknown parent_temp_id "{parent_temp_id}". It must reference the '
                        'temp_id of a menu item created by a previous operation in the same call.'
                    )
                parent = created_by_temp_id[parent_temp_id]
            else:
                parent_menu_id = operation.get('parent_menu_id')
                # 0 (or unset on create) means the top level of the menu
                parent = get_menu(parent_menu_id) if parent_menu_id else root_menu
            if parent != root_menu:
                # Fail early with actionable messages instead of the generic
                # website.menu constraint errors.
                if parent.parent_id != root_menu:
                    raise ValueError(
                        f'Menu item "{parent.name}" (ID: {parent.id}) is itself a sub-item, '
                        'so it cannot have sub-items: the menu supports at most two levels '
                        '(top-level items and their sub-items).',
                    )
                if parent.is_mega_menu:
                    raise ValueError(
                        f'Menu item "{parent.name}" (ID: {parent.id}) is a mega menu: '
                        'it cannot have sub-items.',
                    )
            return parent

        def prepare_url_vals(url):
            # Link the menu to the website.page matching its URL (if any) so
            # the menu URL stays in sync when the page is renamed.
            vals = {'url': url, 'page_id': False}
            if '#' not in url:
                domain = website.website_domain() & (
                    Domain('url', '=', url) | Domain('url', '=', f'/{url}')
                )
                if page := self.env['website.page'].search(domain, limit=1):
                    vals.update(page_id=page.id, url=page.url)
            return vals

        def apply_operation(index, operation):
            operation_type = operation.get('type')
            if operation_type == 'create':
                if not operation.get('name'):
                    raise ValueError(f'Operation #{index}: "name" is required to create a menu item.')
                vals = {
                    'name': operation['name'],
                    'website_id': website.id,
                    'parent_id': resolve_parent(operation).id,
                    **prepare_url_vals(operation.get('url') or '#'),
                }
                if operation.get('sequence') is not None:
                    vals['sequence'] = int(operation['sequence'])
                if operation.get('new_window') is not None:
                    vals['new_window'] = bool(operation['new_window'])
                menu = self.env['website.menu'].create(vals)
                if temp_id := operation.get('temp_id'):
                    created_by_temp_id[temp_id] = menu
                created_ids.add(menu.id)
                return f'Created menu item "{menu.name}" (ID: {menu.id}).'

            if operation_type not in ('update', 'delete'):
                raise ValueError(f'Operation #{index}: unknown operation type "{operation_type}".')
            if not operation.get('menu_id'):
                raise ValueError(f'Operation #{index}: "menu_id" is required to {operation_type} a menu item.')
            menu = get_menu(operation['menu_id'])
            if menu == root_menu:
                raise ValueError(f'Operation #{index}: the root menu (ID: {menu.id}) cannot be edited or deleted.')

            if operation_type == 'delete':
                name = menu.name
                # Deleting cascades to sub-items (ondelete="cascade" on parent_id).
                # Keep track of what gets deleted
                for record in menu | menu.child_id:
                    deleted_records.append({
                        'id': record.id,
                        'name': record.name,
                        'parent_id': record.parent_id.id,
                        'sequence': record.sequence,
                        'new_window': record.new_window,
                        'is_mega_menu': record.is_mega_menu,
                    })
                menu.unlink()
                return f'Deleted menu item "{name}" (and its sub-items, if any).'

            vals = {}
            if operation.get('name'):
                vals['name'] = operation['name']
            if operation.get('url'):
                if menu.is_mega_menu:
                    raise ValueError(f'Operation #{index}: a mega menu has no URL to update.')
                vals.update(prepare_url_vals(operation['url']))
            if operation.get('sequence') is not None:
                vals['sequence'] = int(operation['sequence'])
            if operation.get('new_window') is not None:
                vals['new_window'] = bool(operation['new_window'])
            if operation.get('parent_temp_id') or operation.get('parent_menu_id') is not None:
                parent = resolve_parent(operation)
                if parent != root_menu and menu.child_id:
                    raise ValueError(
                        f'Menu item "{menu.name}" (ID: {menu.id}) has sub-items, so it '
                        'cannot be nested under another item. Move or delete its '
                        'sub-items first (operations are applied in order, so you can '
                        'do both in the same call).',
                    )
                vals['parent_id'] = parent.id
            if not vals:
                raise ValueError(f'Operation #{index}: no values to update for menu item {menu.id}.')
            menu.write(vals)
            updated_ids.add(menu.id)
            return f'Updated menu item "{menu.name}" (ID: {menu.id}).'

        # Apply the batch atomically: on any error, roll back so the menu, the
        # AI's view of it and the page shown to the user stay consistent.
        results = []
        index = 0
        try:
            with self.env.cr.savepoint() as sp:
                for index, operation in enumerate(operations):
                    results.append(apply_operation(index, operation))

                if not tool_context['tool_request_confirmed']:
                    # Create a preview to display to the user then roleback.
                    # The idea is to accurately and clearly show the user the changes
                    # before applying them.
                    preview_html = service._format_website_menu_tree_html(
                        website, created_ids, updated_ids, deleted_records,
                    )
                    sp.close(rollback=True)
                    tool_context['user_input_request'] = make_confirmation_request_preview(
                        self.env,
                        Markup("<p>%s</p>%s<p><b>%s</b></p>") % (
                            self.env._(
                                "Here is the proposed navigation menu "
                                "(additions in green, changes in yellow, removals in red):",
                            ),
                            preview_html,
                            self.env._(
                                "Your menu is shared by every page. I'll save this page too, "
                                "with any unsaved changes on it. Shall I go ahead?",
                            ),
                        ),
                    )
                    return None
        except (UserError, ValueError) as e:
            raise ValueError(
                f"Operation #{index} failed: {e}\n"
                "None of the operations were applied. Fix the failing operation and "
                "send the full list of operations again.\n"
                "Reminder: the menu supports at most two levels, an item that "
                "already has sub-items cannot be nested under another item, and "
                "a mega menu cannot have a parent or sub-items.",
            ) from e

        summary = "\n".join(f"- {line}" for line in results)
        return_message = (
            "Menu operations applied successfully:\n"
            f"{summary}\n\n"
            "Here is the updated menu structure:\n"
            f"{service._format_website_menu_tree(website)}"
        )
        return {
            'client_tool': {'name': 'website_reload_editor', 'params': return_message},
            'summary': {'icon': 'edit', 'text': self.env._("Updated the website menu")},
        }

    @api.model
    def _ai_tool_write_custom_css(self, css_content):
        """Rewrite the entire content of user_custom_rules.scss and reload assets."""
        service = self.env['ai.website.service']
        service._validate_css_content(css_content)
        css_content, localization_note = self._localize_css_external_images(css_content)
        service._save_custom_css(css_content)
        message = "Custom CSS successfully written."
        if localization_note:
            message += f"\n\n{localization_note}"
        if unscoped := service._find_unscoped_css_selectors(css_content):
            message += ("\nWARNING: these top-level selectors are not scoped under a class or id and "
                        "will leak across ALL pages of the website: "
                        + ", ".join(f"`{s}`" for s in unscoped)
                        + ". Scope them under the section's unique class (e.g. `.ai_home_hero h2`) and write the file again.")
        return {
            'response': message,
            'summary': {'icon': 'design_services', 'text': self.env._("Edited custom style")}
        }

    @api.model
    def _ai_tool_apply_brand_kit(self, tool_context, palette=None, typography=None, design=None):
        """Establish the brand kit in one atomic call: palette, typography and
        corner/shadow language. Writes user_color_palette.scss + user_values.scss
        then fires a single asset reload. Each part is optional; at least one is
        required. For a new page or an explicit "change the whole look" — not a
        single-section edit, which must adopt the existing site look."""
        service = self.env['ai.website.service']
        applied = []
        palette_values = None
        if palette:
            palette_values, error = service._build_palette_values(
                palette.get('o_color_1'), palette.get('o_color_2'), palette.get('o_color_3'),
                palette.get('o_color_4'), palette.get('o_color_5'), palette.get('cc_presets'),
            )
            if error:
                return error
            applied.append(f"palette ({palette_values['o-color-1']}…)")

        website_values = {}
        typo_values, error = service._build_typography_values(typography)
        if error:
            return error
        if typo_values:
            website_values.update(typo_values)
            applied.append(f"fonts ({typography['heading_font']} / {typography['body_font']})")

        design_values, error = service._build_design_values(design)
        if error:
            return error
        if design_values:
            website_values.update(design_values)
            language = ", ".join(part for part in (
                f"{design['corners']} corners" if design.get('corners') else '',
                f"{design['shadow']} shadows" if design.get('shadow') else '',
            ) if part)
            applied.append(f"design language ({language})")

        if not palette_values and not website_values:
            return "Nothing to apply — provide at least one of 'palette', 'typography' or 'design'."

        if not tool_context.get('tool_request_confirmed'):
            tool_context['user_input_request'] = make_confirmation_request_preview(
                self.env,
                service._brand_kit_confirmation_message(palette_values, typography, design),
            )
            return

        if palette_values:
            service._write_scss_customization(_USER_COLOR_PALETTE_URL, palette_values)
        if website_values:
            service._write_scss_customization(_USER_WEBSITE_VALUES_URL, website_values)
        self.env.user._bus_send("ai_website/reload_css_bundles", {})
        return {
            'response': "Applied brand kit: " + "; ".join(applied) + ". These now apply site-wide; build the page to match them.",
            'summary': {'icon': 'edit', 'text': self.env._("Set the art direction")},
        }

    @api.model
    def _ai_tool_get_site_profile(self):
        """Return company info, pages list, menu tree, and language settings."""
        profile = self.env['website'].get_site_profile()
        return f"Here is the site profile:\n\n```json\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n```"

    @api.model
    def _ai_tool_get_page_html(self, url=None):
        """Return the div#wrap HTML of a website page."""
        website = self.env.website or self.env.website.browse(self.env.context.get('host_id')) or self.env.ref('base.default_website')
        target_url = url or website.homepage_url or '/'
        html = self.env['website'].get_page_html(target_url, website.id)

        target = url or 'homepage'
        if html is None:
            return f"No page found at URL: {target}"
        return f"Here is the HTML content of the {target}:\n\n```html\n{html}\n```"
