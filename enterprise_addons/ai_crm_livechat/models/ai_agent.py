# Part of Odoo. See LICENSE file for full copyright and licensing details.

from textwrap import dedent

from odoo import models

CRM_LIVECHAT_PREPROMPT = dedent("""
    ## CRM Integration
    - Secondary goal: when a user's request cannot be handled with high confidence, collect contact details (if not already known) and create a lead so a human can follow up.
    - You have access to the "Lead creation" skill which provides tools to create a lead in our CRM.

    ## Decision rules
    1) If you can answer with high confidence from internal data → answer directly.
    2) If you cannot answer, the request requires human follow-up, or the user asks to be contacted → start the Lead creation flow (defined by the Lead creation skill).
    3) If the user provides contact info unsolicited while you are in normal Q&A, confirm whether they'd like a human follow-up; if yes, run the Lead creation flow.
""").strip()


class AIAgent(models.Model):
    _inherit = 'ai.agent'

    def _get_livechat_preprompt(self):
        livechat_preprompt = super()._get_livechat_preprompt()
        return f"{livechat_preprompt}\n{CRM_LIVECHAT_PREPROMPT}"
