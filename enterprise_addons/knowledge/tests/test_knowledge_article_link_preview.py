from odoo.addons.knowledge.tests.common import KnowledgeCommon

from odoo.tests.common import HttpCase, tagged
from odoo.tools.json import scriptsafe as json_safe


@tagged('post_install', '-at_install')
class TestArticleLinkPreview(KnowledgeCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.knowledge_article = cls.env["knowledge.article"].create({
            "name": "Knowledge Article",
        })

    def test_article_link_preview(self):
        self.authenticate('admin', 'admin')
        self.knowledge_article.cover_image_id = self._create_cover().id

        article_urls = [
            f"/odoo/knowledge/{self.knowledge_article.id}",
            f"/knowledge/article/{self.knowledge_article.id}",
            f"/odoo/knowledge/{self.knowledge_article.id}?foo=bar",
            f"/knowledge/article/{self.knowledge_article.id}#fragment",
            f"/odoo/crm/10/knowledge/{self.knowledge_article.id}/",
        ]

        for article_url in article_urls:
            with self.subTest(article_url=article_url):
                # retrieve metadata of article
                response = self.url_open(
                    '/html_editor/link_preview_internal',
                    data=json_safe.dumps({
                        "params": {
                            "preview_url": article_url,
                        }
                    }),
                    headers={"Content-Type": "application/json"}
                )
                self.assertEqual(200, response.status_code)
                data = response.json()["result"]
                self.assertEqual(
                    data["display_name"], self.knowledge_article.display_name
                )
                self.assertEqual(data["description"], self.knowledge_article.summary)
                self.assertEqual(
                    data["preview_image_url"], self.knowledge_article.cover_image_url
                )
