# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAIWebPage(TransactionCase):

    def _create_web_page(self, url):
        return self.env["ai.web.page"].create({"url": url})

    def test_robots_txt_uses_main_domain_for_internal_urls(self):
        self.env["website"].create({
            "name": "Internal Website",
            "domain": "https://shop.example.com",
        })
        web_page = self._create_web_page("https://blog.example.com/article")

        self.assertIn("example.com", web_page._get_internal_domains())
        self.assertFalse(web_page._should_check_robots_txt())
