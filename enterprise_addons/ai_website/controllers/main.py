import logging
import psycopg2
import werkzeug.exceptions

from odoo import http
from odoo.http import request
from odoo.exceptions import ConcurrencyError, UserError

_logger = logging.getLogger(__name__)


class AIWebsiteController(http.Controller):

    @http.route('/ai_website/ready_scraper_results', type='jsonrpc', auth='user', website=True)
    def ready_scraper_results(self, website_id, main_object):
        """Recover this editor's ready calls when their bus notification was missed."""
        if not request.env.user.has_group('website.group_website_designer'):
            raise werkzeug.exceptions.Forbidden()

        sessions = request.env['ai.session'].sudo().search([
            ('create_uid', '=', request.env.uid),
            ('ai_composer_id.interface_key', '=', 'website_builder_ai'),
            ('channel_id', '!=', False),
            ('pending_tool_call', '!=', False),
        ])
        return [
            data for session in sessions
            if (data := session._get_scraper_resume_data())
            and data['target_page']['website_id'] == website_id
            and data['target_page']['main_object'] == main_object
        ]

    @http.route(['/ai_website/generate_page'], type='jsonrpc', auth='user', website=True)
    def generate_website_page_content(self, instructions, name, sectionsArch, tone, templateId, **post):
        """Generate website content using the AI agent with text-only processing."""
        if not request.env.user.has_group('website.group_website_restricted_editor'):
            raise werkzeug.exceptions.Forbidden()

        context = f"""- Page name: {name} - Instructions: {instructions} - Tone: {tone}"""
        try:
            ai_generated_html = request.env['website.page']._generate_ai_website_page_html(templateId, sectionsArch, context, **post)
            result = {'html': ai_generated_html}
        except UserError as e:
            _logger.warning("Failed to generate page content, returning an empty page. Cause: %s", str(e))
            result = {'error': str(e), 'html': sectionsArch}

        return result

    @http.route(['/ai_website/finalize_page'], type='jsonrpc', auth='user', website=True)
    def finalize_page(self, html, current_view_info=None, step='images'):
        """Run one image batch or both refinement passes on a page the AI just composed."""
        if not request.env.user.has_group('website.group_website_restricted_editor'):
            raise werkzeug.exceptions.Forbidden()

        try:
            return request.env['ai.website.service'].with_context(
                current_view_info=current_view_info,
            )._finalize_page(html, step=step)
        except (psycopg2.Error, ConcurrencyError):
            # Let `retrying` roll back and replay rather than answer from a dead cursor.
            raise
        except Exception:
            _logger.exception("page finalization failed; returning the composed page unfinished")
            # Skip a failed image batch and attempt refinements; a failed refinements
            # request ends finalization.
            return {'html': html, 'next_step': 'refinements' if step == 'images' else None, 'error': True}

    @http.route(['/ai_website/localize_external_images'], type='jsonrpc', auth='user', website=True)
    def localize_external_images(self, urls, **post):
        """Copy external images into Odoo attachments and return the local URLs.

        Called by the builder right before saving, so that a page never ships a hotlink
        to a third-party host. Only reachable by users who can edit the website.
        """
        if not request.env.user.has_group('website.group_website_restricted_editor'):
            raise werkzeug.exceptions.Forbidden()

        return request.env['ir.attachment']._localize_external_image_urls(urls)
