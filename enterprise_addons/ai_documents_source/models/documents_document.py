# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.fields import Domain

ALLOWED_AI_DOCUMENT_EXTENSIONS = (
    "pdf",
    "docx",
    "doc",
    "xlsx",
    "xls",
    "pptx",
    "ppt",
    "odt",
    "ods",
    "txt",
    "csv",
)


class DocumentsDocument(models.Model):
    _name = "documents.document"
    _inherit = ["documents.document", "ai.embedding.mixin"]

    ai_sources_ids = fields.One2many("ai.agent.source", "document_id", string="AI Agent Sources")

    def _get_descendants(self):
        """
        Return all descendants of documents.

        :return: recordset of all descendants
        :rtype: recordset of documents.document
        """
        # Documents has their own child_of search method (no batching search)
        all_descendants = self.env['documents.document']
        for document in self:
            descendants = self.search([
                ('id', '!=', document.id),
                ('folder_id', 'child_of', document.id)
            ])
            all_descendants |= descendants
        return all_descendants

    def _is_valid_ai_source_document(self):
        """
        Check if a document record is a valid source document for processing.

        :return: True if the document is a valid source document, False otherwise
        :rtype: bool
        """
        self.ensure_one()
        return (
            self.type == "binary"
            and self.file_extension
            and self.file_extension.lower() in ALLOWED_AI_DOCUMENT_EXTENSIONS
            and bool(self.attachment_id)
        )

    def _get_valid_documents_with_descendants(self):
        """
        Return all valid source documents in the hierarchy.

        :return: recordset of valid source documents (binary files and their folders if included)
        :rtype: recordset of documents.document
        """
        folders = self.filtered(lambda d: d.type == 'folder')
        all_documents = folders._get_descendants() | self
        valid_binary_documents = all_documents.filtered(lambda d: d._is_valid_ai_source_document())
        if not valid_binary_documents:
            return self.env['documents.document']

        # Build the output set by including valid binary documents and all their
        # ancestor folders within the hierarchy the user added
        valid_documents = valid_binary_documents
        for document in valid_binary_documents:
            current_folder = document.folder_id
            while current_folder:
                if current_folder not in all_documents:
                    break
                valid_documents |= current_folder
                current_folder = current_folder.folder_id

        return valid_documents

    @api.ondelete(at_uninstall=False)
    def _unlink_sources(self):
        """Delete sources when a document is deleted."""
        source_linked_to_document = self.env['ai.agent.source'].search([('document_id', 'in', self.ids)])
        if source_linked_to_document:
            source_linked_to_document.unlink()

        self.embedding_ids.unlink()

    def _create_embedding_records(self, embedding_models: set[str]):
        documents = self.filtered(lambda document: document.type != "folder")  # Filtering out folders since they have no content to embed
        return super(DocumentsDocument, documents)._create_embedding_records(embedding_models)

    def _get_embedding_content(self):
        self.ensure_one()
        content = self.attachment_id._get_attachment_content()
        if not content:
            raise ValueError(self.env._("Failed to extract content from the document. Content must be at least 10 characters long."))
        return content

    def _get_embedding_chunks(self):
        self.ensure_one()
        if self.attachment_id.mimetype in self.attachment_id.TABULAR_FILE_TYPES:
            content = self._get_embedding_content()
            return content.split('\n')
        return super()._get_embedding_chunks()

    def _get_duplicate_domain(self):
        self.ensure_one()
        return Domain("attachment_id.checksum", "=", self.attachment_id.checksum)

    @api.model
    def _get_records_to_embed_domain(self):
        return (
            super()._get_records_to_embed_domain()
            & Domain("ai_sources_ids", "!=", False)
            & Domain("ai_sources_ids.is_folder", "=", False)
            & Domain("ai_sources_ids.status", "!=", "failed")
        )

    def _get_embedding_models(self):
        self.ensure_one()
        return {source.agent_id.embedding_model for source in self.ai_sources_ids}

    def _on_embedding_failure(self, error):
        super()._on_embedding_failure(error)
        self.ai_sources_ids.write({
            "status": "skipped",
            "error_details": str(error),
        })
