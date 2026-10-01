# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase


class TestKnowledgeArticle(TransactionCase):
    def test_get_embedding_content_ignores_embedded_records(self):
        """Extract article text, and ignore embedded records"""
        article = self.env["knowledge.article"].create(
            {
                "name": "Article Title",
                "body": '<p>Useful content</p><div data-embedded="view">Ignored content</div>',
            },
        )

        embeddable_content = article._get_embedding_content()
        self.assertEqual(embeddable_content, "Article Title\n\nUseful content")
        self.assertNotIn("Ignored content", embeddable_content)
