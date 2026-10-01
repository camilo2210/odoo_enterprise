from textwrap import dedent

from odoo import fields, models

PREPROMPTS = {
    'livechat': dedent("""
        - You are a live chat operator. Your communication style must be strictly Q&A. When a user asks a question, identify the core question and provide a direct answer. If a question is unclear, ask for clarification in a Q&A format.
          Example Interaction Style:
          User: "How do I reset my password?"
          Your Response: "To reset your password, navigate to the login page and click 'Forgot Password'. Follow the prompts to receive a reset link via email."
        - Give short concise answers.
    """).strip(),
}


class AIAgent(models.Model):
    _inherit = 'ai.agent'

    livechat_channel_rule_ids = fields.One2many(
        comodel_name='im_livechat.channel.rule',
        inverse_name='ai_agent_id',
    )

    def _is_user_access_allowed(self):
        return super()._is_user_access_allowed() or self.livechat_channel_rule_ids

    def _get_livechat_preprompt(self):
        return PREPROMPTS['livechat']

    def _get_instructions(self, extra_instructions=None, restrict_to_resources_override=None):
        if self.env.context.get('discuss_channel', self.env['discuss.channel']).channel_type == 'livechat':
            livechat_preprompt = self._get_livechat_preprompt()
            if livechat_preprompt:
                if extra_instructions:
                    extra_instructions += f"\n{livechat_preprompt}"
                else:
                    extra_instructions = livechat_preprompt
        return super()._get_instructions(extra_instructions, restrict_to_resources_override)
