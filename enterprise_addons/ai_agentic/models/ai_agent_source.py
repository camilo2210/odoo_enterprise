# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AiAgentSource(models.Model):
    _inherit = "ai.agent.source"

    file_sources_count = fields.Integer('Number of file sources', compute="_compute_file_sources_count")

    @api.depends('child_ids')
    def _compute_file_sources_count(self):
        for source in self:
            descendants = source._get_descendants().filtered(lambda s: not s.is_folder)
            source.file_sources_count = len(descendants)

    @api.model
    def get_agent_sources_tree(self, agent_id, fields, unfolded_ids=None):
        """Return the sources shown by the sources browser in the agent panel:
        top-level sources, plus the children of whichever folders are unfolded.
        """
        domain = [
            ('agent_id', '=', agent_id),
            '|', ('parent_id', '=', False), ('parent_id', 'in', unfolded_ids or []),
        ]
        return self.search_read(domain, list({*fields, 'parent_id'}))
