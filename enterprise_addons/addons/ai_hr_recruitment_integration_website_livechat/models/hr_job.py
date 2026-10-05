# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class HrJob(models.Model):
    _name = 'hr.job'
    _inherit = ['hr.job', 'ai.preview.card.mixin']

    def _ai_get_preview_cards_render_context(self):
        return ('website_hr_recruitment.job_card', [{'job': record} for record in self], '')
