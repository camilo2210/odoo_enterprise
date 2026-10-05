# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.ai.tests.common import TestAICommon


class TestAIAgentSource(TestAICommon):
    def test_unlink_source_should_unlinks_attachment(self):
        """Tests that unlinking a source unlinks its linked attachment."""

        attachment_id = self.test_source.attachment_id

        self.test_source.unlink()
        self.assertFalse(attachment_id.exists(), "Attachment should be deleted with its source.")

    def test_ai_web_page_source_unlink_if_single_source(self):
        """Tests that unlinking a source unlinks its linked web page
        if it's the only source referencing that web page."""

        web_page = self.env["ai.web.page"].create({
                "url": "http://example.com",
                "content": "<p>Some content</p>",
        })

        source_a = self.env["ai.agent.source"].create({
            "name": "Some web source",
            "agent_id": self.agent.id,
            "type": "url",
            "web_page_id": web_page.id,
            "status": "indexed",
        })

        source_b = self.env["ai.agent.source"].create({
            "name": "Some web source",
            "agent_id": self.agent.id,
            "type": "url",
            "web_page_id": web_page.id,
            "status": "indexed",
        })

        source_a.unlink()
        self.assertTrue(web_page.exists(), "Web page should not be deleted if still referenced by a source.")
        source_b.unlink()
        self.assertFalse(web_page.exists(), "Web page should be deleted if not linked to any source.")
