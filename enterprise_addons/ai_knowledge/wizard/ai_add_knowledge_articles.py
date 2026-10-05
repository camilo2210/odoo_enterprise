from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AIAddKnowledgeArticles(models.TransientModel):
    _name = 'ai.add.knowledge.articles'
    _description = 'Wizard to add knowledge articles to an AI agent'

    agent_id = fields.Many2one('ai.agent', required=True)
    article_ids = fields.Many2many('knowledge.article', string='Articles', required=True)

    total_articles = fields.Integer(compute='_compute_total_articles')
    include_children = fields.Boolean(default=True)
    has_child_articles = fields.Boolean(compute='_compute_has_child_articles')

    @api.depends('article_ids', 'include_children')
    def _compute_total_articles(self):
        for record in self:
            articles = record.article_ids
            if record.include_children and articles:
                articles = articles | articles._get_descendants()
            record.total_articles = len(articles)

    @api.depends('article_ids')
    def _compute_has_child_articles(self):
        for record in self:
            record.has_child_articles = bool(record.article_ids and record.article_ids._get_descendants())

    def action_add_knowledge_articles(self):
        self.ensure_one()
        if not self.article_ids:
            raise UserError(_("Please select at least one article."))

        agent_id = self.agent_id.id

        articles = self.article_ids
        folder_sources = self.env['ai.agent.source']
        if self.include_children:
            articles |= articles._get_descendants()
            # Create folder sources for articles that have children
            folder_articles = articles.filtered('child_ids')
            folder_sources = self.env['ai.agent.source']._create_folder_sources(folder_articles, agent_id)

        self.env['ai.agent.source'].create_from_articles(articles, agent_id, folder_sources)

        return {
            'type': 'ir.actions.act_window_close',
            'infos': {'sourcesAdded': True},
        }
