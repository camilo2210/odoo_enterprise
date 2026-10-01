# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAIUrlScraperController(HttpCase, CronMixinCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = cls.env["ai.agent"].create({
            "name": "Agent URL Source Controller Tests",
        })

    def _create_batch(self, batch_uuid, state="submitted"):
        page = self.env["ai.web.page"].create({
            "url": "https://example.com/controller-test",
        })
        self.env["ai.agent.source"].create({
            "name": "Controller Test Source",
            "agent_id": self.agent.id,
            "type": "url",
            "web_page_id": page.id,
        })
        batch = self.env["ai.web.scraper.batch"].create({
            "uuid": batch_uuid,
            "state": state,
            "url_payloads": page._get_scraper_urls_params(),
            "callback_model": "ai.web.page",
        })
        page.batch_id = batch.id
        return batch

    def test_callback_triggers_cron_for_pending_batch(self):
        batch = self._create_batch("batch-callback-ok")
        cron_id = self.env.ref("ai.ir_cron_run_web_scraper").id

        with self.capture_triggers(cron_id) as captured_triggers:
            response = self.url_open(
                f"/ai/url_scraper_result_ready/{batch.uuid}",
                method="POST",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(captured_triggers.records)

    def test_callback_returns_404_for_unknown_batch(self):
        response = self.url_open(
            "/ai/url_scraper_result_ready/unknown-batch-uuid",
            method="POST",
        )
        self.assertEqual(response.status_code, 404)

    def test_callback_returns_404_when_batch_not_submitted(self):
        batch = self._create_batch("batch-callback-todo", state="to_submit")
        response = self.url_open(
            f"/ai/url_scraper_result_ready/{batch.uuid}",
            method="POST",
        )
        self.assertEqual(response.status_code, 404)
