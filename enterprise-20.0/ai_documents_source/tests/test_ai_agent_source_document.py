from odoo.tests import tagged
from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAIDocumentSource(TransactionCase, CronMixinCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent_a = cls.env["ai.agent"].create({"name": "Document Agent A", 'embedding_model': 'model'})
        cls.agent_b = cls.env["ai.agent"].create({"name": "Document Agent B"})

    def _create_document(self, name, content):
        attachment = self.env["ir.attachment"].create({
            "name": f"{name} Attachment.txt",
            "raw": content,
            "mimetype": "text/plain",
        })
        return self.env["documents.document"].create({
            "name": attachment.name,
            "attachment_id": attachment.id,
            "type": "binary",
        })

    def _create_sources_for_document(self, document, agents):
        sources = self.env["ai.agent.source"]
        for agent in agents:
            sources |= self.env["ai.agent.source"].create_from_selected_documents([document.id], agent.id)
        return sources

    def test_reprocess_document_source_with_unchanged_document(self):
        document = self._create_document("Doc Source", b"Original content")
        source = self._create_sources_for_document(document, [self.agent_a])
        self.assertTrue(source, "Source should be created for the document")
        source.write({
            "status": "indexed",
            "is_active": True,
            "type": "document",
            "document_id": document.id,
        })

        ai_generate_embedding_cron = self.env.ref("ai.ir_cron_generate_embedding").id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers:
            source.action_reprocess_index()

        source.invalidate_recordset()

        self.assertEqual(source.status, "processing")
        self.assertTrue(source.is_active)
        self.assertTrue(captured_triggers.records, "Embedding cron should trigger for the staged source")

        embedding_model = self.agent_a.embedding_model
        source.document_id.embedding_ids = self.env["ai.embedding"].create({
            "res_model": "documents.document",
            "res_id": source.document_id.id,
            "content": "chunk content",
            "embedding_model": embedding_model,
        })

        source.document_id.embedding_ids.embedding_vector = [0.1] * 1536

        source.invalidate_recordset()
        self.assertEqual(source.status, "indexed")
        self.assertTrue(source.is_active)

    def test_reprocess_document_source_refreshes_content_and_triggers_embeddings(self):
        document = self._create_document("Doc Source", b"First version")
        sources = self._create_sources_for_document(document, [self.agent_a, self.agent_b])
        self.assertTrue(sources, "Sources should be created for the document")
        sources.write({
            "status": "indexed",
            "is_active": True,
            "type": "document",
            "document_id": document.id,
        })

        for source in sources:
            self.env["ai.embedding"].create({
                "res_model": "documents.document",
                "res_id": source.document_id.id,
                "content": "chunk",
                "embedding_model": source.agent_id.embedding_model,
            })
        new_attachment = self.env["ir.attachment"].create({
            "name": "Doc Source v2",
            "raw": b"Second version",
        })
        document.write({
            "attachment_id": new_attachment.id,
        })

        ai_generate_embedding_cron = self.env.ref("ai.ir_cron_generate_embedding").id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers:
            sources[:1].action_reprocess_index()

        sources.invalidate_recordset()

        self.assertTrue(all(source.status == "processing" for source in sources))
        self.assertTrue(all(source.is_active for source in sources))
        self.assertTrue(captured_triggers.records, "Embedding cron should trigger when content updates")
        self.assertTrue(all(source.name == document.name for source in sources), "Source names should reflect the document title")

    def test_create_sources_from_document_folder(self):
        """Test creating AI sources from a documents folder preserves hierarchy."""
        root_folder = self.env["documents.document"].create({"name": "Root Folder", "type": "folder"})
        sub_folder = self.env["documents.document"].create({"name": "Sub Folder", "type": "folder", "folder_id": root_folder.id})
        doc = self._create_document("Test Doc", b"content text")
        doc.folder_id = sub_folder.id

        sources = self.env["ai.agent.source"].create_from_selected_documents([root_folder.id], self.agent_a.id)

        self.assertEqual(len(sources), 3, "Should create 3 sources (2 folders + 1 document)")
        root_source = sources.filtered(lambda s: s.document_id == root_folder)
        sub_source = sources.filtered(lambda s: s.document_id == sub_folder)
        doc_source = sources.filtered(lambda s: s.document_id == doc)

        self.assertEqual(sub_source.parent_id, root_source, "Sub folder source should be child of root folder source")
        self.assertEqual(doc_source.parent_id, sub_source, "Document source should be child of sub folder source")

    def test_folder_status_and_is_active_propagation(self):
        """Test folder status computation and is_active propagation."""
        root_folder = self.env["documents.document"].create({"name": "Root Folder", "type": "folder"})
        doc_1 = self._create_document("Doc 1", b"content text 1")
        doc_1.folder_id = root_folder.id
        doc_2 = self._create_document("Doc 2", b"content text 2")
        doc_2.folder_id = root_folder.id

        sources = self.env["ai.agent.source"].create_from_selected_documents([root_folder.id], self.agent_a.id)
        folder_source = sources.filtered(lambda s: s.document_id == root_folder)
        child_1 = sources.filtered(lambda s: s.document_id == doc_1)
        child_2 = sources.filtered(lambda s: s.document_id == doc_2)

        # Mark children as indexed
        child_1.status = "indexed"
        child_2.status = "indexed"

        folder_source._compute_sources_status()
        self.assertEqual(folder_source.status, "indexed")

        # Test is_active propagation
        folder_source.is_active = False
        self.assertFalse(child_1.is_active)
        self.assertFalse(child_2.is_active)

        folder_source.is_active = True
        self.assertTrue(child_1.is_active)
        self.assertTrue(child_2.is_active)

        # Status propagation
        # One processing -> folder processing
        child_1.status = "processing"
        folder_source._compute_sources_status()
        self.assertEqual(folder_source.status, "processing")

        # One failed, one indexed -> folder incomplete
        child_1.status = "failed"
        folder_source._compute_sources_status()
        self.assertEqual(folder_source.status, "incomplete")

        # Both failed -> folder failed
        child_2.status = "failed"
        folder_source._compute_sources_status()
        self.assertEqual(folder_source.status, "failed")

        # Deleting both children should update folder status to failed
        (child_1 | child_2).unlink()
        self.env.cr.precommit.run()
        self.assertEqual(folder_source.status, "failed")

    def test_sync_document_folder_hierarchy(self):
        """Test document source discovery and hierarchy synchronization."""
        root_folder = self.env["documents.document"].create({"name": "Root Folder", "type": "folder"})
        doc_1 = self._create_document("Doc 1", b"content text 1")
        doc_1.folder_id = root_folder.id

        # Initial creation
        root_sources = self.env["ai.agent.source"].create_from_selected_documents([root_folder.id], self.agent_a.id)
        root_source = root_sources.filtered(lambda s: s.document_id == root_folder)
        doc_1_source = root_sources.filtered(lambda s: s.document_id == doc_1)
        self.assertEqual(len(root_sources), 2, "Root and one document source should be created")

        # Discover new document in the same folder
        doc_2 = self._create_document("Doc 2", b"content text 2")
        doc_2.folder_id = root_folder.id
        root_source.action_reprocess_index()

        all_sources = root_source._get_descendants() | root_source
        self.assertEqual(len(all_sources), 3, "New document should be discovered during reprocess")
        # Create a new subfolder and move doc_1 into it
        folder_2 = self.env["documents.document"].create({
            "name": "Folder 2",
            "type": "folder",
            "folder_id": root_folder.id
        })
        doc_1.folder_id = folder_2.id

        root_source.action_reprocess_index()

        all_sources = root_source._get_descendants() | root_source
        folder_2_source = all_sources.filtered(lambda s: s.document_id == folder_2)
        doc_1_source.invalidate_recordset()

        self.assertTrue(folder_2_source.exists(), "Subfolder source should be discovered")
        self.assertEqual(doc_1_source.parent_id, folder_2_source, "Source hierarchy should reflect the move to the subfolder")

    def test_sync_document_content_update(self):
        """Test that updating document content/metadata triggers re-indexing."""
        root_folder = self.env["documents.document"].create({"name": "Root Folder", "type": "folder"})
        doc_1 = self._create_document("Doc 1", b"content text 1")
        doc_1.folder_id = root_folder.id
        root_sources = self.env["ai.agent.source"].create_from_selected_documents([root_folder.id], self.agent_a.id)
        root_source = root_sources.filtered(lambda s: s.document_id == root_folder)
        doc_1_source = root_sources.filtered(lambda s: s.document_id == doc_1)

        # Update metadata and content
        new_attachment = self.env["ir.attachment"].create({"name": "Updated Doc 1.txt", "raw": b"new content 1"})
        doc_1.write({"attachment_id": new_attachment.id, "name": "Updated Doc 1.txt"})

        ai_generate_embedding_cron = self.env.ref("ai.ir_cron_generate_embedding").id
        with self.capture_triggers(ai_generate_embedding_cron) as captured:
            root_source.action_reprocess_index()

        doc_1_source.invalidate_recordset()
        self.assertTrue(len(captured.records), "Embedding cron should be triggered for the updated document")
        self.assertEqual(doc_1_source.status, "processing", "Updated document should move to processing status")
        self.assertEqual(doc_1_source.name, "Updated Doc 1.txt", "Source name should sync with document name")

    def test_sync_document_unlink_propagation(self):
        """Test that deleting a document unlinks its AI source."""
        root_folder = self.env["documents.document"].create({"name": "Root Folder", "type": "folder"})
        doc_1 = self._create_document("Doc 1", b"content text 1")
        doc_1.folder_id = root_folder.id
        root_sources = self.env["ai.agent.source"].create_from_selected_documents([root_folder.id], self.agent_a.id)
        doc_1_source = root_sources.filtered(lambda s: s.document_id == doc_1)

        self.assertTrue(doc_1_source.exists())
        doc_1.unlink()
        self.assertFalse(doc_1_source.exists(), "AI source should be deleted immediately when the document is unlinked")
