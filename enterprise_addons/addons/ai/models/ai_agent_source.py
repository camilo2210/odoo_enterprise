# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class AIAgentSource(models.Model):
    _name = 'ai.agent.source'
    _description = 'AI Agent Source'
    _explanation = "Represents a source of information for an AI agent, such as a URL or a file. Sources are indexed into embeddings to provide context for RAG (Retrieval-Augmented Generation)."
    _parent_store = True
    _order = 'name'

    name = fields.Char(string="Name")
    agent_id = fields.Many2one('ai.agent', string="Agent", index=True, required=True)
    type = fields.Selection(
        [("url", "URL"), ("binary", "File")],
        default="binary",
        compute="_compute_type",
        string="Type",
        required=True,
        readonly=True,
    )

    # For folder sources, status/is_active/error_details are computed from children.
    # Leaf sources keep their own logic.
    status = fields.Selection(
        string="Status",
        selection=[('processing', 'Processing'), ('indexed', 'Indexed'), ('incomplete', 'Incomplete'), ('failed', 'Failed'), ('skipped', 'Skipped')],
        default='processing',
        compute='_compute_sources_status',
        store=True,
        readonly=False,
        recursive=True,
    )

    is_active = fields.Boolean(
        string="Active",
        help="If the source is active, it will be used in the RAG context.",
        compute='_compute_is_active',
        inverse='_inverse_is_active',
        store=True,
        readonly=False,
        recursive=True,
        default=True,
    )

    error_details = fields.Text(
        string="Error Details",
        compute='_compute_error_details',
        store=True,
        readonly=False,
    )

    attachment_id = fields.Many2one('ir.attachment', string="Attachment", index=True, ondelete="cascade")
    mimetype = fields.Char(related='attachment_id.mimetype')
    file_size = fields.Integer(related='attachment_id.file_size')

    user_has_access = fields.Boolean(compute="_compute_user_has_access", readonly=True)

    # Hierarchy for the sources list view
    parent_id = fields.Many2one("ai.agent.source", string="Parent Source", index=True)
    child_ids = fields.One2many("ai.agent.source", "parent_id", string="Child Sources")
    parent_path = fields.Char(index=True)
    is_folder = fields.Boolean(string="Source is a folder", default=False, readonly=True, required=True)

    web_page_id = fields.Many2one(
        'ai.web.page', string="Web Page", index=True,
        help="Scraped web page this source's content is fetched from, when the source type is 'url'.",
        ondelete="cascade",
    )

    @api.model_create_multi
    def create(self, vals_list):
        sources = super().create(vals_list)
        for source in sources:
            if source.attachment_id:
                source.attachment_id.write({
                    'res_model': 'ai.agent.source',
                    'res_id': source.id,
                })

        if sources_to_index := sources.filtered(lambda s: not s.is_folder):
            sources_to_index._trigger_embedding_generation()

        return sources

    @api.model
    def create_from_binary_files(self, files_datas, agent_id):
        """
        Create AI agent sources from binary files.

        :param files_datas: list of dictionaries with file data
        :type files_datas: list of dicts
        :param agent_id: agent id
        :type agent_id: int
        :return: recordset of created AI agent sources
        :rtype: recordset of ai.agent.source
        """
        attachments = self.env['ir.attachment'].create(files_datas)
        vals_list = []
        for attachment in attachments:
            source = {
                'name': attachment.name,
                'agent_id': agent_id,
                'attachment_id': attachment.id,
            }
            vals_list.append(source)

        return self.create(vals_list)

    @api.model
    def create_from_urls(self, urls, agent_id):
        """
        Create AI agent sources from a list of URLs.

        :param urls: list of urls
        :type urls: list of str
        :param agent_id: agent id
        :type agent_id: int
        :return: recordset of created AI agent sources
        :rtype: recordset of ai.agent.source
        """
        if not urls:
            return self.env['ai.agent.source']

        if not self.env.is_system():
            raise AccessError(self.env._('Only administrators can create sources from URLs.'))

        pages_by_url = self.env['ai.web.page']._get_or_create_from_urls(urls)

        vals_list = [{
            'name': pages_by_url[url]._get_name(),
            'agent_id': agent_id,
            'web_page_id': pages_by_url[url].id,
            'type': 'url',
        } for url in urls]

        sources = self.create(vals_list)

        ready_sources = sources.filtered(lambda s: s.web_page_id.content)
        if ready_sources:
            ready_sources._trigger_embedding_generation()

        pages_to_scrape = sources.web_page_id.filtered(lambda p: not p.content and not p.batch_id)
        if pages_to_scrape:
            pages_to_scrape._submit_to_scraper()

        return sources

    def _get_source_env(self):
        """Return an env using the source owner's language for cron-stored messages."""
        self.ensure_one()
        lang = self.agent_id.create_uid.lang or 'en_US'
        return self.with_context(lang=lang).env

    def _get_descendants(self):
        """
        Get the descendants of sources.

        :return: descendants of self sources
        :rtype: ai.agent.source records
        """
        return self.env['ai.agent.source'].search([('id', 'not in', self.ids), ('parent_id', 'child_of', self.ids)])

    def _is_folder(self):
        """Check if the source is a folder."""
        self.ensure_one()
        return self.is_folder

    @api.ondelete(at_uninstall=False)
    def _unlink_child_sources(self):
        """Delete child sources when a source is deleted."""
        self.child_ids.unlink()

    @api.ondelete(at_uninstall=False)
    def _unlink_linked_records(self):
        """Deletes linked records when a source is deleted."""
        attachment_ids = self.attachment_id
        web_page_ids = self.web_page_id.filtered(lambda w: not (w.ai_sources_ids - self))

        attachment_ids.unlink()
        web_page_ids.unlink()

    @api.depends_context('uid')
    @api.depends('attachment_id')
    def _compute_user_has_access(self):
        """
        Compute user access by delegating to the underlying source.
        """
        self.filtered(lambda s: s.type == 'binary').user_has_access = self.env.user._is_internal()
        self.filtered(lambda s: s.type == 'url').user_has_access = True

    @api.depends("attachment_id", "web_page_id")
    def _compute_type(self):
        for source in self:
            source.type = "binary" if source.attachment_id else "url"

    @api.depends(lambda self: self._get_sources_status_depends())
    def _compute_sources_status(self):
        for source in self:
            if source.is_folder:
                statuses = set(source.child_ids.mapped('status'))
                if not statuses or statuses == {'failed'}:
                    source.status = 'failed'
                elif 'processing' in statuses:
                    source.status = 'processing'
                elif 'incomplete' in statuses or ('failed' in statuses and 'indexed' in statuses):
                    source.status = 'incomplete'
                else:
                    source.status = 'indexed'
            else:
                if source.status == "skipped":
                    continue
                records = source._get_target_records()
                if not records:
                    continue
                embeddings = records.embedding_ids
                if embeddings and any(e.has_embedding_generation_failed for e in embeddings):
                    source.status = "failed"
                elif not embeddings or not all(e.embedding_vector for e in embeddings):
                    source.status = "processing"
                else:
                    source.status = "indexed"

    @api.model
    def _get_sources_status_depends(self):
        """Returns the dependencies of the `_compute_sources_status` and `_compute_error_details` methods.

        :return: a list of dependencies of the compute
        :rtype: list[str]
        """
        return [
            "child_ids.status",
            "attachment_id.embedding_ids.embedding_vector",
            "attachment_id.embedding_ids.has_embedding_generation_failed",
            "attachment_id.embedding_ids.embedding_error",
            "web_page_id.embedding_ids.embedding_vector",
            "web_page_id.embedding_ids.has_embedding_generation_failed",
            "web_page_id.embedding_ids.embedding_error",
        ]

    @api.depends(lambda self: self._get_sources_status_depends())
    def _compute_error_details(self):
        for source in self:
            if source.is_folder:
                statuses = set(source.child_ids.mapped('status'))
                if not statuses:
                    source.error_details = self.env._("No attached sources found for this source folder.")
                elif statuses == {'failed'}:
                    source.error_details = self.env._("The attached sources could not be processed.")
                elif 'incomplete' in statuses or ('failed' in statuses and 'indexed' in statuses):
                    source.error_details = self.env._("Some of the attached sources of this folder failed to be processed.")
                else:
                    source.error_details = False
            else:
                records = source._get_target_records()
                if not records:
                    continue
                failed_embeddings = records.embedding_ids.filtered("has_embedding_generation_failed")
                if failed_embeddings:
                    if any(e.embedding_error == "iap_credit_error" for e in failed_embeddings):
                        source.error_details = self.env._("Not enough credits to use Odoo AI.")
                    else:
                        source.error_details = self.env._("Odoo AI failed to index this source.")

    @api.depends('child_ids.is_active')
    def _compute_is_active(self):
        for source in self:
            if source.is_folder:
                any_active = source.child_ids and any(child.is_active for child in source.child_ids)
                source.is_active = any_active

    def _inverse_is_active(self):
        for source in self.filtered('is_folder'):
            new_active_state = source.is_active
            source.child_ids.filtered(lambda child: child.status in ('indexed', 'incomplete')).write({'is_active': new_active_state})

    def _reindex_sources(self):
        """Reindex sources."""
        web_sources = self.filtered("web_page_id")
        if web_sources:
            web_sources.web_page_id._reset_for_scraping()

        for source in self - web_sources:
            if target := source._get_target_records():
                target._recreate_embeddings()

    def _trigger_embedding_generation(self):
        """Trigger the embedding generation for the sources."""
        if not self:
            return
        sources_to_index = self.env["ai.agent.source"]

        for source in self:
            if target := source._get_target_records():
                created = target._create_embedding_records({source.agent_id.embedding_model})
                if any(not embedding.embedding_vector for embedding in created):
                    sources_to_index |= source

        if sources_to_index:
            sources_to_index.write({
                'status': 'processing',
                'error_details': False,
            })
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()

        if already_embedded_sources := (self - sources_to_index):
            already_embedded_sources._compute_sources_status()

    def _sync_sources_state(self):
        """
        To be overriden to sync the state of the folder sources.
        :return: sources recordset to be processed
        :rtype: recordset of ai.agent.source
        """
        return self.env['ai.agent.source']

    def _sync_sources_hierarchy(self, target_records):
        """
        To be overriden. Sync the hierarchy of the folder sources.

        :param target_records: recordset of target records to sync the hierarchy with
        :type target_records: recordset of target records
        """
        pass

    def _sync_sources_name(self):
        """Sync the display name of URL sources with their web page's link preview title."""
        url_sources = self.filtered(lambda s: s.type == 'url' and s.web_page_id)
        if not url_sources:
            return

        names_by_page = {page.id: page._get_name() for page in url_sources.web_page_id}
        for source in url_sources:
            name = names_by_page.get(source.web_page_id.id)
            if name and source.name != name:
                source.name = name

    def _get_reindex_sources(self, source_filter=None):
        """
        Get the sources to reindex.

        :param source_filter: optional lambda to filter synced sources for non-URL folders
        :type source_filter: callable or None
        :return: sources to act on
        :rtype: ai.agent.source recordset
        """
        self.ensure_one()
        if self._is_folder():
            synced_sources = self._sync_sources_state()
            if not synced_sources:
                return self.env['ai.agent.source']
            return synced_sources.filtered(source_filter)

        # Non-folder sources: find all sources with the same content
        if self.type == 'url' and self.web_page_id:
            return self.env['ai.agent.source'].search([
                ('web_page_id', '=', self.web_page_id.id)
            ])
        return self.env['ai.agent.source'].search([
            ('attachment_id.checksum', '=', self.attachment_id.checksum),
        ])

    def action_access_source(self):
        """Access the source content."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.web_page_id.url if self.web_page_id else f"/web/content/{self.attachment_id.id}",
            'target': 'new',
        }

    def action_reprocess_index(self):
        """Reprocess the index of the sources."""
        self.ensure_one()
        sources_to_reprocess = self._get_reindex_sources(
            source_filter=lambda s: s.attachment_id
        )

        if not sources_to_reprocess:
            return

        sources_to_reprocess._sync_sources_name()
        sources_to_reprocess._reindex_sources()

    def action_retry_failed_source(self):
        """Retry failed sources"""
        self.ensure_one()
        if self.status not in ('failed', 'incomplete'):
            return

        sources_to_retry = self._get_reindex_sources(
            source_filter=lambda s: s.status == 'failed' and not s.is_folder
        )
        if not sources_to_retry:
            return

        embedding_model = self.agent_id.embedding_model
        self.env['ai.embedding'].search([
            ('res_model', '=', sources_to_retry.attachment_id._name),
            ('res_id', 'in', sources_to_retry.attachment_id.ids),
            ('embedding_model', '=', embedding_model),
        ]).unlink()

        sources_to_retry._sync_sources_name()
        sources_to_retry._reindex_sources()

    def _create_sources_attachments(self, attachments_vals):
        """
        Create attachments for self rcords.

        :param attachments_vals: list of dictionaries with attachment values
        :type attachments_vals: list of dicts
        """
        if not self:
            return
        new_attachments = self.env['ir.attachment'].create(attachments_vals)
        for source, new_attachment in zip(self, new_attachments):
            source.attachment_id = new_attachment.id

    def _update_attachment_content(self, content):
        """Create or replace the source attachment content.

        Unlinks the old attachment when content changes, cascading to its
        embeddings.

        :param content: content as bytes
        :type content: bytes
        """
        self.ensure_one()

        old_attachment = self.attachment_id
        if old_attachment:
            checksum = self.env['ir.attachment']._compute_checksum(content)
            if old_attachment.checksum == checksum:
                return

        self._create_sources_attachments([{
            'name': old_attachment.name if old_attachment else self.name,
            'res_model': 'ai.agent.source',
            'res_id': self.id,
            'raw': content,
            'mimetype': old_attachment.mimetype if old_attachment else 'text/plain',
        }])

        if old_attachment:
            old_attachment.unlink()

    def _get_target_per_model(self):
        """
        Collect RAG target models and IDs from all sources targets in the recordset.

        :return: mapping of model names to lists of record IDs for all sources
                 that have a valid RAG target
        :rtype: dict[str, recordset]
        """
        models_map = {}
        for source in self:
            target = source._get_target_records()
            if not target:
                continue
            if models_map.get(target._name):
                models_map[target._name] |= target
            else:
                models_map[target._name] = target
        return models_map

    def _get_target_records(self):
        """
        Return the RAG target records this source.

        :return: target model or None if no target model defined
        """
        self.ensure_one()
        if self.attachment_id:
            return self.attachment_id
        if self.web_page_id:
            return self.web_page_id
        return None

    def _get_target_models(self):
        """Returns a list of target models available for the sources.

        :return: a list of `res_model`
        :rtype: list[str]
        """
        return ["ir.attachment", "ai.web.page"]

    def _get_source_link(self, link_label: str | None = None):
        """
        Build an HTML anchor tag linking to the source content.

        :param link_label: custom label for the link; defaults to display_name
        :return: safe HTML anchor element pointing to the source URL or attachment
        :rtype: markupsafe.Markup
        """
        self.ensure_one()
        label = link_label if link_label else self.display_name
        href = self.web_page_id.url if self.web_page_id else f"/web/content/{self.attachment_id.id}"
        return Markup(
            '<a href="%s" target="_blank" rel="noreferrer noopener" style="text-decoration: none;">%s</a>',
        ) % (href, label)

    @api.autovacuum
    def _gc_sources_targets(self):
        """
        Autovacuum: Cleanup embeddings for records that are not linked to any sources.
        """
        for model in self._get_target_models():
            unbound_records = self.env[model].search([("embedding_ids", "!=", False), ("ai_sources_ids", "=", False)], limit=10_000)
            if unbound_records:
                unbound_records.embedding_ids.unlink()
