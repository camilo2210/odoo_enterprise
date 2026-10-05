# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AiSession(models.Model):
    _inherit = 'ai.session'

    def _get_request_context_snapshot(self, context=None):
        context = self.env.context if context is None else context
        return {
            **super()._get_request_context_snapshot(context),
            **{key: context[key] for key in ('website_id', 'pricelist_id', 'fiscal_position_id') if key in context},
        }
