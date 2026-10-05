# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import models


class AiSession(models.Model):
    _inherit = 'ai.session'

    def _get_request_context_snapshot(self, context=None):
        snapshot = super()._get_request_context_snapshot(context)
        if self and (audit_id := (self.request_context or {}).get('working_file_id')):
            snapshot['working_file_id'] = audit_id
        return snapshot

    def _get_tool_execution_context(self):
        context = super()._get_tool_execution_context()
        if self:
            # Read this session's selection, not the environment of a returning child.
            context['working_file_id'] = (self.request_context or {}).get('working_file_id')
        return context

    def _get_context_input(self, text):
        current_view_info = self.env.context.get('current_view_info')
        if not isinstance(current_view_info, dict) or 'current_account_report' not in current_view_info:
            return super()._get_context_input(text)
        clean_view = {key: value for key, value in current_view_info.items() if key != 'current_account_report'}
        context_input = super(AiSession, self.with_context(current_view_info=clean_view or None))._get_context_input(text)
        current_report = self.env(su=False)['ai.tool']._get_current_account_report_context()
        if not current_report:
            return context_input
        payload = json.dumps({'current_account_report': current_report}, ensure_ascii=False)
        return context_input.replace('</odoo_current_context>',
                                     f'\n## Current account report\n{payload}</odoo_current_context>')
