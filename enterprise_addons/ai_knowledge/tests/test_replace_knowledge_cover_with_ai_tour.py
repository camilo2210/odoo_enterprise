# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged, HttpCase

from odoo.addons.ai.tests.common import mock_iap_results
from odoo.addons.base.tests.files import PNG_B64, JPG_B64


@tagged('post_install', '-at_install')
class TestAIImageGeneration(HttpCase):
    def test_replace_knowledge_cover_with_ai_tour(self):
        generated_attachment = self.env['ir.attachment'].create({
            'name': "AI Generated 1",
            'type': 'binary',
            'raw': PNG_B64,
            'mimetype': 'image/png',
            'public': True,
        })

        iap_result = [
            {'type': 'text', 'text': "AI Generated 1"},
            {
                'type': 'inline_data',
                'metadata': {'attachment_id': generated_attachment.id},
                'data': PNG_B64,
                'mimetype': 'image/png',
            },
        ]

        attachment = self.env['ir.attachment'].create({
            'name': 'Initial Cover',
            'type': 'binary',
            'raw': JPG_B64,
            'mimetype': 'image/jpeg',
            'public': True,
        })
        cover = self.env['knowledge.cover'].create({
            'attachment_id': attachment.id,
        })
        self.env['knowledge.article'].create({
            'name': 'Article with Cover',
            'cover_image_id': cover.id,
        })

        with mock_iap_results(self.env, [iap_result]):
            self.start_tour("/odoo", "replace_knowledge_cover_with_ai_tour", login="admin")
