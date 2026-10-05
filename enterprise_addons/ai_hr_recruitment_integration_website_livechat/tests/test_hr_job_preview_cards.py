# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase

from odoo.addons.ai_website_livechat.tests.common import AIPreviewCardCase


class TestAIHrJobPreviewCards(AIPreviewCardCase, TransactionCase):
    def test_hr_job_preview_card_renders(self):
        job = self.env['hr.job'].create({
            'name': 'AI Preview Job',
            'is_published': True,
        })
        self.assertPreviewCardsRender(job, ['AI Preview Job'], expected_count=1)
