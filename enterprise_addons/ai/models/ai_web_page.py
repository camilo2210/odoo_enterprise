# Part of Odoo. See LICENSE file for full copyright and licensing details.
import hashlib
import json
from collections import defaultdict

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools.mail import url_domain_extract

from odoo.addons.mail.tools import link_preview


class AIWebPage(models.Model):
    _name = 'ai.web.page'
    _inherit = ["ai.embedding.mixin"]
    _description = 'AI Web Page'
    _explanation = "Represents the scraped content of a URL, shared by every AI agent source pointing to that URL."

    url = fields.Char(required=True, index=True)
    content = fields.Text()
    checksum = fields.Char(compute='_compute_checksum', store=True)
    batch_id = fields.Many2one(
        'ai.web.scraper.batch', string="Scraper Batch", index=True, ondelete='set null',
        export_string_translation=False,
    )
    ai_sources_ids = fields.One2many("ai.agent.source", "web_page_id", string="AI Agent Sources")

    _url_uniq = models.Constraint('unique(url)', "A web page for this URL already exists.")

    @api.depends('content')
    def _compute_checksum(self):
        for page in self:
            page.checksum = hashlib.sha1(page.content.encode()).hexdigest() if page.content else False

    @api.model
    def _get_or_create_from_urls(self, urls):
        """Get or create web pages for the given URLs, deduplicated by URL.

        :param urls: list of urls
        :type urls: list of str
        :return: dict mapping url to ai.web.page record
        :rtype: dict
        """
        existing_by_url = {page.url: page for page in self.search([('url', 'in', urls)])}
        missing_urls = [url for url in urls if url not in existing_by_url]
        for page in self.create([{'url': url} for url in missing_urls]):
            existing_by_url[page.url] = page
        return existing_by_url

    def _get_name(self):
        """Get the display name for a web page, based on its link preview title.

        :return: name of the web page
        :rtype: str
        """
        self.ensure_one()
        preview = link_preview.get_link_preview_from_url(self.url)
        if preview and preview.get('og_title'):
            return preview['og_title']
        return self.url

    def _get_internal_domains(self):
        """Return domains considered internal for URL scraping. Extended in ai_website."""
        domain = self._get_url_domain(self.get_base_url())
        return [domain] if domain else []

    def _get_url_domain(self, url):
        """Return the normalized registrable domain for an URL or raw domain."""
        if not url:
            return False
        url_to_parse = url
        if '://' not in url_to_parse:
            url_to_parse = f'https://{url_to_parse}'
        domain = url_domain_extract(url_to_parse)
        if not domain:
            return False
        domain = domain.lower()
        try:
            return domain.encode('idna').decode('ascii')
        except UnicodeError:
            return domain

    def _get_normalized_internal_domains(self):
        """Return the deduplicated set of internal domains.
        :rtype: set of str
        """
        return set(self._get_internal_domains())

    def _should_check_robots_txt(self, internal_domains=None):
        """Check whether the scraper should respect robots.txt for this web page.

        :param internal_domains: pre-normalized internal domains (see
            ``_get_normalized_internal_domains``); computed on the fly if not given.
        :type internal_domains: set of str or None
        :return: False for internal domains, True otherwise
        :rtype: bool
        """
        self.ensure_one()
        if internal_domains is None:
            internal_domains = self._get_normalized_internal_domains()
        if not internal_domains or not self.url:
            return True

        url_domain = self._get_url_domain(self.url)
        if not url_domain:
            return True

        return url_domain not in internal_domains

    def _get_scraper_urls_params(self):
        """Return URL payloads with robots.txt policy for the scraper."""
        internal_domains = self[:1]._get_normalized_internal_domains()
        return [
            {
                'url': page.url,
                'check_robots_txt': page._should_check_robots_txt(internal_domains),
            }
            for page in self
        ]

    def _submit_to_scraper(self):
        """Enqueue these web pages for scraping, chunked into scraper batches."""
        Batch = self.env['ai.web.scraper.batch']
        for i in range(0, len(self), Batch._BATCH_SIZE):
            chunk = self[i:i + Batch._BATCH_SIZE]
            batch = Batch._enqueue(chunk._get_scraper_urls_params(), 'ai.web.page')
            chunk.batch_id = batch.id

    def _reset_for_scraping(self):
        """Detach from any previous batch and re-submit to the scraper."""
        self.write({'batch_id': False})
        self.embedding_ids.unlink()
        self._submit_to_scraper()

    @api.model
    def _web_scraper_result_ready(self, batch):
        """Scraper-batch consumer hook: called when one of our batches is terminal.

        :param batch: the batch that reached a terminal state (``done`` or ``failed``)
        :type batch: ai.web.scraper.batch
        """
        pages = self.search([('batch_id', '=', batch.id)])
        if not pages:
            return

        if batch.state == 'failed':
            for page in pages:
                for source in page.ai_sources_ids:
                    env = source._get_source_env()
                    source.write({
                        'status': 'failed',
                        'error_details': batch.error or env._("Failed to process this URL."),
                    })
            pages.write({'batch_id': False})
            return

        pages._process_batch_results(batch.result or {})

    def _process_batch_results(self, result):
        pages_result = result.get('pages', {})
        sources_by_error = defaultdict(lambda: self.env['ai.agent.source'])
        sources_to_sync = self.env['ai.agent.source']

        for page in self:
            page_result = pages_result.get(page.url, {})
            if page_result.get('failed'):
                sources_by_error[page_result.get('reason') or 'fetch_failed'] |= page.ai_sources_ids
                continue

            try:
                payload = json.loads(page_result.get('payload') or '{}')
            except (json.JSONDecodeError, TypeError):
                sources_by_error['invalid_payload'] |= page.ai_sources_ids
                continue

            if not isinstance(payload, dict):
                sources_by_error['invalid_payload'] |= page.ai_sources_ids
                continue

            content = payload.get('text') or ''
            if not content:
                sources_by_error['empty_content'] |= page.ai_sources_ids
                continue

            old_checksum = page.checksum
            page.write({'content': content})
            if old_checksum != page.checksum:
                page.embedding_ids.unlink()  # Content of the page changed, the embedding has to be re-computed
            sources_to_sync |= page.ai_sources_ids

        self.write({'batch_id': False})

        default_error_messages = {
            'fetch_failed': self.env._("Failed to fetch the content of this URL."),
            'invalid_payload': self.env._("Failed to process the content of this URL."),
            'empty_content': self.env._("No text content could be extracted from this URL."),
        }
        for error_key, sources in sources_by_error.items():
            sources.write({
                'status': 'failed',
                'error_details': default_error_messages.get(error_key, error_key),
            })

        if sources_to_sync:
            sources_to_sync._trigger_embedding_generation()

    def _create_embedding_records(self, embedding_models: set[str]):
        # Filtering the created records to avoid having the "skipped" status
        # for web-pages that have not been processed by the scraper yet.
        return super(AIWebPage, self.filtered(lambda w: w.content))._create_embedding_records(embedding_models)

    def _get_embedding_content(self):
        self.ensure_one()
        min_content_len = 10
        if self.content and len(self.content) > min_content_len:
            return self.content
        raise ValueError(self.env._("Failed to retrieve web page content. Content must be at least 10 characters long."))

    @api.model
    def _get_records_to_embed_domain(self):
        return super()._get_records_to_embed_domain() & Domain("ai_sources_ids", "!=", False) & Domain("ai_sources_ids.status", "not in", ["failed", "skipped"])

    def _get_embedding_models(self):
        self.ensure_one()
        return {source.agent_id.embedding_model for source in self.ai_sources_ids}

    def _on_embedding_failure(self, error):
        super()._on_embedding_failure(error)
        self.ai_sources_ids.write({
            "status": "skipped",
            "error_details": str(error),
        })
