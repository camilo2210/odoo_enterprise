# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from datetime import timedelta
from unittest.mock import patch

from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout as RequestsTimeout

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.ai.models.ai_web_scraper_batch import AIWebScraperBatch
from odoo.addons.base.tests.test_ir_cron import CronMixinCase

_CALL_SCRAPER = "odoo.addons.ai.models.ai_web_scraper_batch.AIWebScraperBatch._call_scraper"
_MAX_SCRAPER_CALLS = "odoo.addons.ai.models.ai_web_scraper_batch.AIWebScraperBatch._CRON_MAX_SCRAPER_CALLS"


def _patch_call_scraper(**kwargs):
    """Patch ``_call_scraper`` with a mock that cannot pass for an ``@api.ondelete`` hook.

    A bare ``MagicMock`` answers ``hasattr(mock, "_ondelete")`` with True, so
    ``BaseModel._ondelete_methods`` picks the patched method up and calls it with the recordset
    on every ``unlink()`` -- inflating the call count (and memoizing the mock on the registry
    class). Speccing the mock on the real function removes that phantom attribute.
    """
    return patch(_CALL_SCRAPER, spec=AIWebScraperBatch._call_scraper, **kwargs)


@tagged("post_install", "-at_install")
class TestAIWebPage(TransactionCase, CronMixinCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = cls.env["ai.agent"].create({
            "name": "Agent URL Source Tests",
        })

    def setUp(self):
        super().setUp()
        # These tests call the cron method directly, outside of an actual cron job context,
        # so _commit_progress() would otherwise try to really commit the (test) transaction.
        commit_progress_patcher = patch("odoo.addons.base.models.ir_cron.IrCron._commit_progress")
        commit_progress_patcher.start()
        self.addCleanup(commit_progress_patcher.stop)

    def _create_url_source(self, name, url, status="processing", is_active=False, content=None):
        page = self.env["ai.web.page"].search([("url", "=", url)]) or self.env["ai.web.page"].create({"url": url})
        source = self.env["ai.agent.source"].create({
            "name": name,
            "agent_id": self.agent.id,
            "type": "url",
            "web_page_id": page.id,
        })
        if content is not None:
            page.write({"content": content})
        source.write({
            "status": status,
            "is_active": is_active,
        })
        return source

    def _create_batch(self, sources, uuid=False, state="submitted", submitted_on=None, timeout_at=None):
        pages = sources.web_page_id
        batch = self.env["ai.web.scraper.batch"].create({
            "uuid": uuid,
            "state": state,
            "submitted_on": submitted_on,
            "timeout_at": timeout_at,
            "url_payloads": pages._get_scraper_urls_params(),
            "callback_model": "ai.web.page",
        })
        pages.batch_id = batch.id
        return batch

    def test_reprocess_resets_scraper_tracking_and_triggers_scrape_cron(self):
        url = "https://example.com/article"
        source_a = self._create_url_source(
            "Source A", url, status="indexed", is_active=True, content="<p>Old content</p>",
        )
        source_b = self._create_url_source(
            "Source B", url, status="indexed", is_active=True, content="<p>Old content</p>",
        )
        old_batch = self._create_batch(source_a | source_b, uuid="old-batch")

        scraper_cron = self.env.ref("ai.ir_cron_run_web_scraper").id
        with self.capture_triggers(scraper_cron) as captured_triggers, \
                patch("odoo.addons.ai.models.ai_web_page.AIWebPage._get_name", return_value="Updated title"):
            source_a.action_reprocess_index()

        source_a.invalidate_recordset()
        source_b.invalidate_recordset()

        self.assertEqual(source_a.status, "processing")
        self.assertEqual(source_b.status, "processing")
        self.assertEqual(source_a.name, "Updated title")
        self.assertEqual(source_b.name, "Updated title")
        # The pages have been detached from the old batch and re-enqueued in a fresh one.
        self.assertNotEqual(source_a.web_page_id.batch_id, old_batch)
        self.assertNotEqual(source_b.web_page_id.batch_id, old_batch)
        self.assertEqual(source_a.web_page_id.batch_id.state, "to_submit")
        self.assertTrue(captured_triggers.records)

    def test_scraping_cron_submits_pending_url_sources(self):
        external_url = "https://external.example/a"
        source_a = self._create_url_source("Source A", external_url)
        source_a.web_page_id._submit_to_scraper()

        with _patch_call_scraper(return_value={
            "status": "accepted",
            "uuid": "batch-submit",
        }) as call_scraper:
            self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        call_scraper.assert_called_once_with(
            "/website_scraper/url_sources/1.0/submit_batch",
            {
                "urls": [
                    {
                        "url": external_url,
                        "check_robots_txt": True,
                        "fetch_image_urls": False,
                        "take_screenshot": False,
                    },
                ],
                "db_url": self.env["ir.config_parameter"].sudo().get_base_url(),
            },
        )
        batch = source_a.web_page_id.batch_id
        self.assertEqual(batch.uuid, "batch-submit")
        self.assertEqual(batch.state, "submitted")
        self.assertTrue(batch.submitted_on)

    def test_enqueue_adds_media_options_and_preserves_url_specific_values(self):
        batch = self.env["ai.web.scraper.batch"]._enqueue(
            [
                {"url": "https://example.com/default"},
                {
                    "url": "https://example.com/override",
                    "fetch_image_urls": False,
                    "take_screenshot": True,
                },
            ],
            "ai.agent.source.url",
            fetch_image_urls=True,
            take_screenshot=False,
        )

        self.assertEqual(batch.url_payloads, [
            {
                "url": "https://example.com/default",
                "fetch_image_urls": True,
                "take_screenshot": False,
            },
            {
                "url": "https://example.com/override",
                "fetch_image_urls": False,
                "take_screenshot": True,
            },
        ])

    def test_enqueue_with_timeout_schedules_scraper_cron_at_deadline(self):
        scraper_cron = self.env.ref("ai.ir_cron_run_web_scraper").id
        with self.capture_triggers(scraper_cron) as captured_triggers:
            batch = self.env["ai.web.scraper.batch"]._enqueue(
                [{"url": "https://example.com/timeout"}],
                "ai.web.page",
                timeout_seconds=600,
            )

        self.assertTrue(batch.timeout_at)
        self.assertIn(batch.timeout_at, captured_triggers.records.mapped("call_at"))

    def test_poll_keeps_requested_media_in_batch_result(self):
        url = "https://example.com/media"
        batch = self.env["ai.web.scraper.batch"].create({
            "uuid": "batch-media",
            "state": "submitted",
            "url_payloads": [{
                "url": url,
                "fetch_image_urls": True,
                "take_screenshot": True,
            }],
            "callback_model": "ai.agent.source.url",
        })
        scraper_result = {
            "status": "success",
            "pages": {
                url: {
                    "failed": False,
                    "payload": json.dumps({
                        "text": "Page content",
                        "images": [{"src": "https://example.com/image.png", "kind": "img"}],
                        "screenshot_url": "data:image/png;base64,c2NyZWVuc2hvdA==",
                    }),
                },
            },
        }

        with patch(_CALL_SCRAPER, return_value=scraper_result):
            batch._poll()

        self.assertEqual(batch.state, "done")
        payload = json.loads(batch.result["pages"][url]["payload"])
        self.assertEqual(payload["images"], [{"src": "https://example.com/image.png", "kind": "img"}])
        self.assertEqual(payload["screenshot_url"], "data:image/png;base64,c2NyZWVuc2hvdA==")

    def test_scraping_cron_processes_successes_without_restaging_failures(self):
        success_url = "https://example.com/success"
        failed_url = "https://example.com/failure"
        success_source = self._create_url_source("Success", success_url)
        failed_source = self._create_url_source("Failure", failed_url, content="<p>Old</p>")
        batch = self._create_batch(success_source | failed_source, uuid="batch-mixed")

        scraper_result = {
            "status": "success",
            "pages": {
                success_url: {
                    "failed": False,
                    "payload": json.dumps({"text": "<p>Fresh content</p>"}),
                },
                failed_url: {
                    "failed": True,
                    "reason": "Fetch failed",
                },
            },
        }

        ai_generate_embedding_cron = self.env.ref("ai.ir_cron_generate_embedding").id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers_embedding, \
                _patch_call_scraper(return_value=scraper_result) as call_scraper:
            self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        success_source.invalidate_recordset()
        failed_source.invalidate_recordset()

        self.assertEqual(success_source.web_page_id.content, "<p>Fresh content</p>")
        self.assertEqual(success_source.status, "processing")
        self.assertEqual(failed_source.status, "failed")
        self.assertEqual(failed_source.error_details, "Fetch failed")
        self.assertTrue(captured_triggers_embedding.records)
        # Regression check: a fetched batch must not be resubmitted to the scraper within the
        # same cron tick (only the fetch call happens; the cron never re-scans sources).
        call_scraper.assert_called_once()
        # The batch is discarded once dispatched to its consumer.
        self.assertFalse(batch.exists())

    def test_scraping_cron_unlinks_embeddings_when_content_changes(self):
        url = "https://example.com/refresh"
        source = self._create_url_source(
            "Refresh Needed", url, content="<p>Old content</p>",
        )
        embedding = self.env["ai.embedding"].create({
            "res_model": "ai.web.page",
            "res_id": source.web_page_id.id,
            "content": "chunk content",
            "embedding_model": source.agent_id.embedding_model,
        })
        self._create_batch(source, uuid="batch-refresh")

        updated_content = "<p>Updated content</p>"
        scraper_result = {
            "status": "success",
            "pages": {
                url: {
                    "failed": False,
                    "payload": json.dumps({"text": updated_content}),
                },
            },
        }

        ai_generate_embedding_cron = self.env.ref("ai.ir_cron_generate_embedding").id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers_embedding, \
                _patch_call_scraper(return_value=scraper_result):
            self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        source.invalidate_recordset()
        self.assertEqual(source.web_page_id.content, updated_content)
        self.assertEqual(source.status, "processing")
        self.assertTrue(captured_triggers_embedding.records)
        self.assertFalse(self.env["ai.embedding"].browse(embedding.id).exists())

    def test_scraping_cron_marks_source_failed_on_invalid_payload(self):
        url = "https://example.com/invalid-payload"
        source = self._create_url_source("Invalid Payload", url)
        self._create_batch(source, uuid="batch-invalid-payload")
        scraper_result = {
            "status": "success",
            "pages": {
                url: {
                    "failed": False,
                    "payload": "{not valid",
                },
            },
        }

        ai_generate_embedding_cron = self.env.ref("ai.ir_cron_generate_embedding").id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers_embedding, \
                _patch_call_scraper(return_value=scraper_result):
            self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        source.invalidate_recordset()
        self.assertEqual(source.status, "failed")
        self.assertEqual(source.error_details, "Failed to process the content of this URL.")
        self.assertFalse(captured_triggers_embedding.records)

    def test_scraping_cron_marks_batch_failed_after_configured_timeout(self):
        source = self._create_url_source("Configured Timeout", "https://example.com/configured-timeout")
        batch = self._create_batch(
            source,
            uuid="batch-configured-timeout",
            submitted_on=fields.Datetime.now(),
            timeout_at=fields.Datetime.now() - timedelta(seconds=1),
        )

        with patch(_CALL_SCRAPER, return_value={"status": "error_still_processing"}):
            self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        source.invalidate_recordset()
        self.assertEqual(source.status, "failed")
        self.assertFalse(source.is_active)
        self.assertEqual(source.error_details, "Web scraping did not finish before the timeout.")
        self.assertFalse(batch.exists())

    def test_scraping_cron_marks_batch_failed_after_max_fetch_wait(self):
        source = self._create_url_source("Timeout", "https://example.com/timeout")
        max_wait = self.env["ai.web.scraper.batch"]._MAX_FETCH_WAIT
        self._create_batch(
            source,
            uuid="batch-timeout",
            submitted_on=fields.Datetime.now() - max_wait - timedelta(hours=1),
        )

        with _patch_call_scraper(return_value={
            "status": "error_still_processing",
        }):
            self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        source.invalidate_recordset()
        self.assertEqual(source.status, "failed")
        self.assertEqual(source.error_details, "This URL took too long to process and timed out after 24 hours.")
        # Terminal batch is dispatched and discarded, detaching the page.
        self.assertFalse(source.web_page_id.batch_id)

    def test_repeated_fetch_attempts_do_not_prematurely_fail_batch(self):
        """Regression test for attempt poisoning: a batch must not fail just because it was
        polled many times by cron runs triggered from unrelated batches finishing. Only
        elapsed time since submission should matter."""
        source = self._create_url_source("Slow", "https://example.com/slow")
        batch = self._create_batch(source, uuid="batch-slow", submitted_on=fields.Datetime.now())

        with _patch_call_scraper(return_value={
            "status": "error_still_processing",
        }):
            for _ in range(25):  # more than the old count-based attempt limit (20)
                self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        source.invalidate_recordset()
        self.assertEqual(source.status, "processing")
        self.assertEqual(batch.state, "submitted")

    @mute_logger("odoo.addons.ai.models.ai_web_scraper_batch")
    def test_submit_batch_transient_error_is_retried_not_failed(self):
        source = self._create_url_source("Retry Submit", "https://example.com/retry-submit")
        source.web_page_id._submit_to_scraper()

        with _patch_call_scraper(side_effect=RequestsConnectionError("connection dropped")):
            self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        source.invalidate_recordset()
        self.assertEqual(source.status, "processing")
        self.assertFalse(source.web_page_id.batch_id.uuid)
        self.assertEqual(source.web_page_id.batch_id.state, "to_submit")

    @mute_logger("odoo.addons.ai.models.ai_web_scraper_batch")
    def test_fetch_batch_transient_error_is_retried_not_failed(self):
        source = self._create_url_source("Retry Fetch", "https://example.com/retry-fetch")
        batch = self._create_batch(source, uuid="batch-retry-fetch", submitted_on=fields.Datetime.now())

        with _patch_call_scraper(side_effect=RequestsTimeout("timed out")):
            self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        source.invalidate_recordset()
        self.assertEqual(source.status, "processing")
        self.assertEqual(batch.state, "submitted")

    def test_cron_retriggers_when_backlog_exceeds_call_cap(self):
        for i in range(3):
            self._create_url_source(
                f"Backlog {i}", f"https://example.com/backlog-{i}",
            ).web_page_id._submit_to_scraper()

        scraper_cron = self.env.ref("ai.ir_cron_run_web_scraper").id
        with self.capture_triggers(scraper_cron) as captured_triggers, \
                patch(_MAX_SCRAPER_CALLS, 2), \
                _patch_call_scraper(return_value={"status": "accepted", "uuid": "batch-backlog"}):
            self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

        self.assertTrue(captured_triggers.records)

    def test_cron_retriggers_when_scraper_call_exhausts_time_budget(self):
        scraper_cron = self.env.ref("ai.ir_cron_run_web_scraper").id
        for state, result, expected_state in (
            ("submitted", {"status": "success", "pages": {}}, "done"),
            ("to_submit", {"status": "accepted", "uuid": "batch-submit"}, "submitted"),
        ):
            with self.subTest(state=state):
                batches = self.env["ai.web.scraper.batch"].create([
                    {"state": state, "callback_model": "ai.web.page"} for _ in range(2)
                ])
                with (
                    self.capture_triggers(scraper_cron) as captured_triggers,
                    patch(_CALL_SCRAPER, return_value=result) as call_scraper,
                    patch("odoo.addons.base.models.ir_cron.IrCron._commit_progress", return_value=0),
                ):
                    self.env["ai.web.scraper.batch"]._cron_run_web_scraper()

                call_scraper.assert_called_once()
                self.assertEqual(batches[0].state, expected_state)
                self.assertEqual(batches[1].state, state)
                self.assertTrue(captured_triggers.records)
                batches.unlink()
