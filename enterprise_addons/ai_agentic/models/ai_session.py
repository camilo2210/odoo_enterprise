# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AiSession(models.Model):
    _inherit = "ai.session"

    def _get_request_context_snapshot(self, context=None):
        snapshot = super()._get_request_context_snapshot(context)
        if self.env.context.get('ai_automation_run') or (self.request_context or {}).get('ai_automation_run'):
            snapshot['ai_automation_run'] = True
        return snapshot

    def _finish_exchange(self, status='completed', *, content=None):
        super()._finish_exchange(status, content=content)
        if (self.request_context or {}).get("ai_automation_run"):
            self.auto_confirm = False
