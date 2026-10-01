# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AIWebScraperBatch(models.Model):
    _inherit = 'ai.web.scraper.batch'

    # Set when the batch is started by the `scrape_website_pages` AI tool, so that
    # `ai.tool._web_scraper_result_ready` knows which conversation and which suspended
    # tool call the result belongs to.
    ai_session_id = fields.Many2one('ai.session', string="AI Session", ondelete='set null')
    tool_call_id = fields.Char(string="Tool Call ID")
