# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

CAMPAIGN_BUILDER_TIMEOUT = 180


class AiSession(models.Model):
    _inherit = 'ai.session'

    def _get_model_round_options(self):
        completion_options = super()._get_model_round_options()
        if self._is_campaign_builder_session():
            completion_options['timeout'] = CAMPAIGN_BUILDER_TIMEOUT
        return completion_options

    def _run_agentic_loop(self, *args, **kwargs):
        if self._is_campaign_builder_session():
            kwargs['timeout'] = CAMPAIGN_BUILDER_TIMEOUT
        yield from super()._run_agentic_loop(*args, **kwargs)

    def _is_campaign_builder_session(self):
        return len(self) == 1 and self.ai_composer_id.interface_key == 'campaign_builder_ai'
