from collections import defaultdict

from markupsafe import Markup

from odoo import api, fields, models


class AIAgentSource(models.Model):
    _name = 'ai.agent.source'
    _inherit = ['ai.agent.source']

    document_id = fields.Many2one('documents.document', string="Source Document", index=True, ondelete="cascade")
    type = fields.Selection(
        selection_add=[('document', 'Document')],
        ondelete={'document': 'cascade'},
    )

    @api.depends_context('uid')
    @api.depends('document_id')
    def _compute_user_has_access(self):
        """Override to check if the user has access to the document."""
        document_sources = self.filtered(lambda s: s.type == 'document')
        for source in document_sources:
            source.user_has_access = source.document_id.user_permission != 'none'
        super(AIAgentSource, self - document_sources)._compute_user_has_access()

    @api.depends("document_id")
    def _compute_type(self):
        document_sources = self.filtered("document_id")
        for source in document_sources:
            source.type = "document"
        super(AIAgentSource, self - document_sources)._compute_type()

    @api.model
    def _get_sources_status_depends(self):
        return super()._get_sources_status_depends() + [
            "child_ids.status",
            "document_id.embedding_ids.embedding_vector",
            "document_id.embedding_ids.has_embedding_generation_failed",
            "document_id.embedding_ids.embedding_error",
        ]

    @api.model
    def create_from_selected_documents(self, document_ids, agent_id):
        """
        Create AI agent sources from a selection of documents.

        :param document_ids: list of document ids
        :type document_ids: list of int
        :param agent_id: agent id
        :type agent_id: int
        :return: recordset of created AI agent sources
        :rtype: recordset of ai.agent.source
        """
        documents = self.env['documents.document'].browse(document_ids)._get_valid_documents_with_descendants()
        return self._create_sources_from_documents(documents, agent_id)

    def _create_sources_from_documents(self, documents, agent_id, sync_hierarchy=True):
        """Create AI agent sources from documents.

        :param documents: recordset of documents
        :type documents: recordset of documents.document
        :param agent_id: agent id
        :type agent_id: int
        :param sync_hierarchy: whether to sync the hierarchy of the sources
        :type sync_hierarchy: bool
        :return: recordset of created AI agent sources
        :rtype: recordset of ai.agent.source
        """
        if not documents:
            return self.env['ai.agent.source']

        vals_list = [
            {
                "name": document.name,
                "agent_id": agent_id,
                "type": "document",
                "document_id": document.id,
                "attachment_id": False,
                "is_folder": document.type == "folder",
            }
            for document in documents
        ]

        sources = self.create(vals_list)
        if sync_hierarchy:
            sources._sync_sources_hierarchy(documents)

        return sources

    def _get_reindex_sources(self, source_filter=None):
        self.ensure_one()
        if self.document_id and not self.is_folder:
            return self.search([("document_id", "=", self.document_id.id), ("is_folder", "=", False)])
        return super()._get_reindex_sources(source_filter)

    def action_reprocess_index(self):
        """Reprocess the index of the sources."""
        self.ensure_one()
        if not self.document_id:
            super().action_reprocess_index()
            return

        sources_to_reprocess = self._get_reindex_sources(
            source_filter=lambda s: s.document_id,
        )

        if not sources_to_reprocess:
            return

        sources_to_reprocess._sync_sources_name()
        sources_to_reprocess._reindex_sources()

    def _sync_sources_state(self):
        """
        Override to sync document sources state.

        :return: recordset of synced document sources
        :rtype: recordset of ai.agent.source
        """
        self.ensure_one()
        if self.type != 'document':
            return super()._sync_sources_state()

        documents = self.document_id._get_valid_documents_with_descendants()
        valid_document_ids = set(documents.ids)

        # Process the folder sources of the document folder across all agents
        folder_sources = self.search([('document_id', '=', self.document_id.id)])
        all_sources_to_sync = folder_sources | folder_sources._get_descendants()

        # This loop to process the folder across agents to make sure all synchronized
        for folder_source in folder_sources:
            folder_descendants = folder_source._get_descendants()
            existing_doc_ids = set(folder_descendants.mapped('document_id').ids)
            existing_doc_ids.add(folder_source.document_id.id)

            document_ids_to_add = list(valid_document_ids - existing_doc_ids)
            current_folder_sources = folder_source | folder_descendants
            if document_ids_to_add:
                documents_to_add = self.env['documents.document'].browse(document_ids_to_add)
                new_created_sources = self._create_sources_from_documents(
                    documents_to_add,
                    folder_source.agent_id.id,
                    sync_hierarchy=False,
                )
                current_folder_sources |= new_created_sources
                all_sources_to_sync |= new_created_sources

            current_folder_sources._sync_sources_hierarchy(documents)

        # Unlink sources that are no longer available in the document hierarchy
        sources_to_unlink = all_sources_to_sync.filtered(
            lambda source: source.document_id.id not in valid_document_ids
        )
        if sources_to_unlink:
            sources_to_unlink.unlink()
            all_sources_to_sync -= sources_to_unlink

        return all_sources_to_sync

    def _sync_sources_hierarchy(self, target_records):
        """
        Override to sync the hierarchy of document sources.

        :param target_records: recordset of target records to mirror
        :type target_records: recordset of documents.document
        """

        if any(source.type != 'document' for source in self):
            super()._sync_sources_hierarchy(target_records)
            return

        document_to_source = {s.document_id.id: s for s in self}
        parent_to_children_map = defaultdict(lambda: self.env['ai.agent.source'])

        for document in target_records:
            parent_doc_id = document.folder_id.id
            if not parent_doc_id or parent_doc_id not in document_to_source:
                continue

            child_source = document_to_source.get(document.id)
            parent_source = document_to_source[parent_doc_id]

            if child_source:
                if child_source.parent_id.id != parent_source.id:
                    parent_to_children_map[parent_source.id] |= child_source

        for parent_id, child_sources in parent_to_children_map.items():
            child_sources.write({'parent_id': parent_id})

    def _sync_sources_name(self):
        """Override to sync the name of document sources."""

        if any(source.type != 'document' for source in self):
            super()._sync_sources_name()
            return

        document_names_map = defaultdict(list)
        for source in self:
            document_name = source.document_id.name
            if document_name and source.name != document_name:
                document_names_map[document_name].append(source.id)

        for name, ids in document_names_map.items():
            self.browse(ids).write({'name': name})

    def action_access_source(self):
        """Override to open the document record in the Documents app."""
        self.ensure_one()
        if self.type == 'document' and self.document_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/odoo/documents/{self.document_id.access_token}',
                'target': 'self',
            }
        return super().action_access_source()

    def _get_target_records(self):
        self.ensure_one()
        if self.document_id:
            return self.document_id
        return super()._get_target_records()

    @api.model
    def _get_target_models(self):
        return super()._get_target_models() + ["documents.document"]

    def _get_source_link(self, link_label=None):
        self.ensure_one()
        label = link_label if link_label else self.name
        if self.document_id:
            href = f"/web/content/{self.document_id.attachment_id.id}"
            return Markup(
                '<a href="%s" target="_blank" rel="noreferrer noopener" style="text-decoration: none;">%s</a>',
            ) % (href, label)
        return super()._get_source_link(label)
