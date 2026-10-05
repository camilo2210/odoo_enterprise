# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged, HttpCase

from odoo.addons.ai.tests.common import mock_iap_results
from odoo.addons.base.tests.files import PNG_B64, JPG_B64, WEBP_B64


@tagged('post_install', '-at_install')
class TestAIImageGeneration(HttpCase):
    def test_replace_image_with_ai_tour(self):
        # Current image that will be replaced with AI
        attachment = self.env['ir.attachment'].create({
            'name': 'Website Image',
            'type': 'binary',
            'raw': PNG_B64,
            'mimetype': 'image/png',
            'public': True,
        })
        # Setup website with a dummy image for the tour to interact with
        self.env['website.page'].create({
            'name': 'AI Image Test',
            'url': '/ai_image_test',
            'type': 'qweb',
            'key': 'ai_website.ai_image_test',
            'arch': f'<t t-call="website.layout"><div><img id="test_image" src="/web/image/ir.attachment/{attachment.id}/raw"/></div></t>',
            'website_id': self.env['website'].search([], limit=1).id,
        })

        image_data = [
            ("AI Generated 1", JPG_B64, "image/jpeg"),
            ("AI Generated 2", WEBP_B64, "image/webp"),
        ]

        iap_results = []
        for image_name, base64_data, mimetype in image_data:
            attachment = self.env['ir.attachment'].create({
                'name': image_name,
                'type': 'binary',
                'raw': base64_data,
                'mimetype': mimetype,
                'public': True,
            })
            iap_results.append([
                {'type': 'text', 'text': image_name},
                {
                    'type': 'inline_data',
                    'metadata': {'attachment_id': attachment.id},
                    'data': base64_data,
                    'mimetype': mimetype,
                },
            ])

        with mock_iap_results(self.env, iap_results):
            self.start_tour(self.env["website"].get_client_action_url("/ai_image_test", True), "replace_website_image_with_ai_tour", login="admin")
