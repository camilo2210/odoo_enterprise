# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta

import requests

from odoo import api, fields, models

from odoo.addons.iap.tools import iap_tools

_logger = logging.getLogger(__name__)


class AIWebScraperBatch(models.Model):
    _name = 'ai.web.scraper.batch'
    _description = 'AI Web Scraper Batch'

    uuid = fields.Char(string="Batch UUID", index=True)
    state = fields.Selection(
        selection=[
            ('to_submit', 'To Submit'),
            ('submitted', 'Submitted'),
            ('done', 'Done'),
            ('failed', 'Failed'),
        ],
        default='to_submit',
        required=True,
        index=True,
    )
    submitted_on = fields.Datetime(string="Submission Date")
    timeout_at = fields.Datetime(string="Timeout At", index="btree_not_null")
    url_payloads = fields.Json(string="URL Payloads")
    result = fields.Json(string="Scraper Result")
    error = fields.Text(string="Error")

    # Model whose `_web_scraper_result_ready` hook is called once the batch
    # reaches a terminal state (see `_cron_run_web_scraper`).
    callback_model = fields.Char(string="Callback Model", required=True)

    _SCRAPER_API_VERSION = '1.0'
    _SCRAPER_BASE_URL_PARAM = 'ai.scraper_base_url'
    _DEFAULT_WSS_ENDPOINT = 'https://iap-scraper.odoo.com'
    _BATCH_SIZE = 200
    _CRON_MAX_SCRAPER_CALLS = 10
    _MAX_FETCH_WAIT = timedelta(hours=24)
    _REQUEST_TIMEOUT = 60

    @api.model
    def _enqueue(self, url_payloads, callback_model, fetch_image_urls=False, take_screenshot=False, timeout_seconds=None):
        """Create a scraper batch and schedule it for submission.

        ``fetch_image_urls`` and ``take_screenshot`` are batch-wide defaults.
        A value explicitly set on an individual URL payload takes precedence,
        allowing one batch to request media only for selected pages.  When
        requested, the scraper puts an ``images`` list and/or a
        ``screenshot_url`` data URI in that page's JSON-encoded ``payload`` in
        :attr:`result`.

        :param url_payloads: list of scraper URL payloads, e.g.
            ``[{'url': ..., 'check_robots_txt': ..., 'fetch_image_urls': ...,
            'take_screenshot': ...}]``
        :type url_payloads: list of dict
        :param callback_model: model implementing ``_web_scraper_result_ready(batch)``,
            called once the batch reaches a terminal state.
        :type callback_model: str
        :param bool fetch_image_urls: request image metadata for URLs that do
            not define their own value. Each image is an object containing its
            source URL and contextual metadata.
        :param bool take_screenshot: request a PNG screenshot data URI for
            URLs that do not define their own value.
        :param int timeout_seconds: optional deadline for the whole batch. The
            batch is failed and dispatched if it is not terminal by that deadline.
        :return: the created batch
        :rtype: ai.web.scraper.batch
        """
        if not isinstance(fetch_image_urls, bool) or not isinstance(take_screenshot, bool):
            msg = "Scraper media options must be booleans."
            raise TypeError(msg)
        if timeout_seconds is not None and (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            msg = "Scraper timeout must be a positive number of seconds."
            raise ValueError(msg)

        payloads = []
        for payload in url_payloads:
            if not isinstance(payload, dict):
                msg = "Scraper url payload must be a dictionary."
                raise TypeError(msg)

            payload = dict(payload)
            for option, default in {
                'fetch_image_urls': fetch_image_urls,
                'take_screenshot': take_screenshot,
            }.items():
                value = payload.setdefault(option, default)
                if not isinstance(value, bool):
                    raise TypeError(f'Scraper option "{option}" must be a boolean.')
            payloads.append(payload)

        timeout_at = (
            fields.Datetime.now() + timedelta(seconds=timeout_seconds)
            if timeout_seconds else False
        )
        batch = self.create({
            'url_payloads': payloads,
            'callback_model': callback_model,
            'state': 'to_submit',
            'timeout_at': timeout_at,
        })
        cron = self.env.ref('ai.ir_cron_run_web_scraper')
        cron._trigger([fields.Datetime.now(), *([timeout_at] if timeout_at else [])])
        return batch

    def _call_scraper(self, path, params=None):
        params = dict(params or {})
        params.setdefault('dbuuid', self.env['ir.config_parameter'].sudo().get_str('database.uuid'))
        scraper_base_url = self.env['ir.config_parameter'].sudo().get_str(
            self._SCRAPER_BASE_URL_PARAM,
            default=self._DEFAULT_WSS_ENDPOINT,
        )

        return iap_tools.iap_jsonrpc(
            f"{scraper_base_url}{path}",
            params=params,
            timeout=self._REQUEST_TIMEOUT,
        )

    @api.model
    def _cron_run_web_scraper(self):
        cron = self.env['ir.cron']

        # Fetch results for batches already submitted first; each fetch is its own
        # blocking scraper call, so the number processed per run is capped. Batches
        # with a deadline are served first (ASC puts the deadline-less ones last), so
        # that a slow backlog cannot starve them into timing out unpolled.
        submitted = self.search(
            [('state', '=', 'submitted')],
            limit=self._CRON_MAX_SCRAPER_CALLS,
            order='timeout_at ASC, id ASC',
        )
        cron._commit_progress(remaining=len(submitted))
        for batch in submitted:
            batch._poll()
            if not cron._commit_progress(1):
                self.env.ref('ai.ir_cron_run_web_scraper')._trigger()
                return

        # Submit the new batches (capped and ordered the same way).
        to_submit = self.search(
            [('state', '=', 'to_submit')],
            limit=self._CRON_MAX_SCRAPER_CALLS,
            order='timeout_at ASC, id ASC',
        )
        cron._commit_progress(remaining=len(to_submit))
        for batch in to_submit:
            batch._submit()
            if not cron._commit_progress(1):
                self.env.ref('ai.ir_cron_run_web_scraper')._trigger()
                return

        # Fail the batches that are still pending past their deadline. The phases
        # above gave the ones that fit in this run a last poll/submit attempt.
        timed_out = self.search([
            ('timeout_at', '<=', fields.Datetime.now()),
            ('state', 'in', ('to_submit', 'submitted')),
        ])
        for batch in timed_out:
            batch._fail(self.env._("Web scraping did not finish before the timeout."))

        # If either phase hit its cap there is more work: run again promptly.
        if len(submitted) >= self._CRON_MAX_SCRAPER_CALLS or len(to_submit) >= self._CRON_MAX_SCRAPER_CALLS:
            self.env.ref('ai.ir_cron_run_web_scraper')._trigger()

        # Commit timeout changes before dispatch, then isolate each consumer in
        # its own transaction. Failed callbacks keep their batch for a later retry.
        batches = self.search([('state', 'in', ('done', 'failed'))])
        if not cron._commit_progress(remaining=len(batches)):
            return
        for batch in batches:
            batch_id, callback_model = batch.id, batch.callback_model
            try:
                self.env[callback_model]._web_scraper_result_ready(batch)
                batch.unlink()
                if not cron._commit_progress(1):
                    return
            except Exception:  # noqa: BLE001
                self.env.cr.rollback()
                _logger.exception(
                    "AI web scraper: %s._web_scraper_result_ready failed for batch %s",
                    callback_model, batch_id,
                )
                if not cron._commit_progress():
                    return

    def _submit(self):
        """Submit this batch's URLs to the scraper."""
        self.ensure_one()
        try:
            result = self._call_scraper(
                f'/website_scraper/url_sources/{self._SCRAPER_API_VERSION}/submit_batch',
                {
                    'urls': self.url_payloads,
                    'db_url': self.env['ir.config_parameter'].sudo().get_base_url(),
                },
            )
        except requests.RequestException:
            # Assumed transient (network/DNS/TLS/HTTP-level failure): keep the batch
            # pending and retry on the next run.
            _logger.warning("AI web scraper: batch %s submission failed", self.id, exc_info=True)
            return
        if result is None:
            return
        if result.get('status') != 'accepted':
            _logger.warning(
                "AI web scraper: batch %s submission rejected, status=%s — %s",
                self.id, result.get('status'), result.get('status_msg'),
            )
            self._fail(self.env._("Failed to submit this URL for processing."))
            return
        self.write({
            'uuid': result['uuid'],
            'state': 'submitted',
            'submitted_on': fields.Datetime.now(),
        })

    def _poll(self):
        """Fetch the results of this already-submitted batch."""
        self.ensure_one()
        try:
            result = self._call_scraper(
                f'/website_scraper/url_sources/{self._SCRAPER_API_VERSION}/batch/{self.uuid}',
            )
        except requests.RequestException:
            # Assumed transient (network/DNS/TLS/HTTP-level failure): try again next
            # run, same as "still processing". Bounded by ``_MAX_FETCH_WAIT`` via
            # ``_handle_not_ready``, so a persistent failure eventually surfaces.
            _logger.warning("AI web scraper: batch %s fetch failed", self.id, exc_info=True)
            self._handle_not_ready()
            return
        if result is None:
            self._handle_not_ready()
            return

        status = result.get('status')
        if status == 'success':
            self.write({'state': 'done', 'result': result})
        elif status == 'error_still_processing':
            self._handle_not_ready()
        else:
            _logger.warning(
                "AI web scraper: batch %s fetch returned unexpected status=%s — %s",
                self.id, status, result.get('status_msg', ''),
            )
            self._fail(self.env._("Failed to fetch the content of this URL."))

    def _handle_not_ready(self):
        """Leave the batch pending, unless it has been outstanding longer than ``_MAX_FETCH_WAIT``.

        Failure is based on elapsed time since submission rather than a number of fetch
        attempts, so that unrelated batches finishing (and triggering extra cron runs) don't
        cause this batch to fail prematurely.
        """
        self.ensure_one()
        if not self.submitted_on or fields.Datetime.now() - self.submitted_on < self._MAX_FETCH_WAIT:
            return
        max_wait_hours = int(self._MAX_FETCH_WAIT.total_seconds() // 3600)
        self._fail(self.env._(
            "This URL took too long to process and timed out after %(hours)d hours.",
            hours=max_wait_hours,
        ))

    def _fail(self, error):
        self.write({'state': 'failed', 'error': error})
