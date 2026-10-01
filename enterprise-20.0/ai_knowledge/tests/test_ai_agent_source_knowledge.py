from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAIAgentSourceKnowledge(TransactionCase, CronMixinCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent_a = cls.env["ai.agent"].create({"name": "Knowledge Agent A"})
        cls.agent_b = cls.env["ai.agent"].create({"name": "Knowledge Agent B"})

    def _create_article(self, name, body="<p>content text</p>", parent=None):
        vals = {"name": name, "body": body}
        if parent:
            vals["parent_id"] = parent.id
        else:
            vals["internal_permission"] = "write"
        return self.env["knowledge.article"].create(vals)

    def _create_sources_from_articles(self, articles, agent, folder_articles=None):
        folder_sources = self.env["ai.agent.source"]
        if folder_articles:
            folder_sources = self.env["ai.agent.source"]._create_folder_sources(folder_articles, agent.id)
        return self.env["ai.agent.source"].create_from_articles(articles, agent.id, folder_sources)

    def test_create_sources_from_articles_with_hierarchy(self):
        """Create knowledge sources and keep the folder/file hierarchy."""
        root = self._create_article("Root Article")
        child = self._create_article("Child Article", parent=root)
        articles = root | child

        sources = self._create_sources_from_articles(articles, self.agent_a, folder_articles=root)

        self.assertEqual(len(sources), 3, "Should create 3 sources (root folder + 2 content sources)")
        root_folder = sources.filtered(lambda s: s.article_id == root and s.is_folder)
        root_content = sources.filtered(lambda s: s.article_id == root and not s.is_folder)
        child_source = sources.filtered(lambda s: s.article_id == child and not s.is_folder)

        self.assertTrue(root_folder.exists(), "Root folder source should exist")
        self.assertTrue(root_content.exists(), "Root content source should exist")
        self.assertTrue(child_source.exists(), "Child content source should exist")
        self.assertEqual(root_content.parent_id, root_folder, "Root content should be under root folder source")
        self.assertEqual(child_source.parent_id, root_folder, "Child source should be under root folder source")

    def test_sync_article_hierarchy_and_folder_creation(self):
        """Discover new folder needs and sync hierarchy after moves."""
        root = self._create_article("Root Article")
        subfolder = self._create_article("Subfolder Article", parent=root)
        child = self._create_article("Child Article", parent=root)

        sources = self._create_sources_from_articles(root | subfolder | child, self.agent_a, folder_articles=root)
        root_folder = sources.filtered(lambda s: s.article_id == root and s.is_folder)
        subfolder_content = sources.filtered(lambda s: s.article_id == subfolder and not s.is_folder)
        child_source = sources.filtered(lambda s: s.article_id == child and not s.is_folder)

        self.assertTrue(root_folder.exists(), "Root folder source should exist")

        child.parent_id = subfolder.id
        root_folder.action_reprocess_index()

        all_sources = root_folder._get_descendants() | root_folder
        subfolder_folder = all_sources.filtered(lambda s: s.article_id == subfolder and s.is_folder)
        subfolder_content.invalidate_recordset()
        child_source.invalidate_recordset()

        self.assertTrue(subfolder_folder.exists(), "Subfolder should gain a folder source once it has children")
        self.assertEqual(subfolder_folder.parent_id, root_folder, "Subfolder folder should be under the root folder")
        self.assertEqual(subfolder_content.parent_id, subfolder_folder, "Subfolder content should be under its folder")
        self.assertEqual(child_source.parent_id, subfolder_folder, "Child source should be under the subfolder folder")

    def test_collapse_empty_folder_sources(self):
        """Collapse folder sources when their articles have no children."""
        root = self._create_article("Root Article")
        child = self._create_article("Child Article", parent=root)

        sources = self._create_sources_from_articles(root | child, self.agent_a, folder_articles=root)
        root_folder = sources.filtered(lambda s: s.article_id == root and s.is_folder)
        self.assertTrue(root_folder.exists(), "Root folder source should exist")

        child.unlink()
        root_folder.action_reprocess_index()

        root_content = self.env["ai.agent.source"].search([
            ("article_id", "=", root.id),
            ("agent_id", "=", self.agent_a.id),
            ("is_folder", "=", False),
        ])
        self.assertFalse(root_folder.exists(), "Folder source should be removed after collapsing")
        self.assertTrue(root_content.exists(), "Root content source should remain after collapsing")
        self.assertFalse(root_content.is_folder, "Root content should remain a file source")
        self.assertFalse(root_content.parent_id, "Root content should be moved to the top level")
