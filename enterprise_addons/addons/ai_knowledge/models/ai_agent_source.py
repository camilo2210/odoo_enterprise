from collections import defaultdict
from markupsafe import Markup

from odoo import api, fields, models


class AIAgentSource(models.Model):
    _name = 'ai.agent.source'
    _inherit = ['ai.agent.source']

    article_id = fields.Many2one('knowledge.article', string="Source Article", ondelete="cascade", index=True)
    type = fields.Selection(
        selection_add=[('knowledge_article', 'Knowledge Article')],
        ondelete={'knowledge_article': 'cascade'}
    )

    @api.model
    def create_from_articles(self, articles, agent_id, folder_sources=None):
        """
        Create AI agent sources from knowledge articles.

        :param articles: recordset of knowledge articles
        :type articles: recordset of knowledge.article
        :param agent_id: agent id
        :type agent_id: int
        :param folder_sources: recordset of the to-be-created sources' folders
        :type folder_sources: recordset of ai.agent.source
        :return: recordset of created AI agent sources
        :rtype: recordset of ai.agent.source
        """
        if not articles:
            return self.env['ai.agent.source']

        vals_list = [{
            'name': article.name,
            'agent_id': agent_id,
            'article_id': article.id,
            'type': 'knowledge_article',
        } for article in articles]

        sources = self.create(vals_list)

        # Sync hierarchy if folder sources are provided
        if folder_sources:
            sources |= folder_sources
            sources._sync_sources_hierarchy(articles)

        return sources

    @api.model
    def _create_folder_sources(self, articles, agent_id):
        """
        Create folder sources for articles that need folder representation.

        :param articles: recordset of knowledge articles
        :type articles: recordset of knowledge.article
        :param agent_id: agent id
        :type agent_id: int
        :return: recordset of created folder sources
        :rtype: recordset of ai.agent.source
        """
        if not articles:
            return self.env['ai.agent.source']

        vals_list = [{
            'name': article.name,
            'agent_id': agent_id,
            'article_id': article.id,
            'type': 'knowledge_article',
            'is_folder': True,
        } for article in articles]

        return self.create(vals_list)

    @api.depends_context('uid')
    @api.depends('article_id')
    def _compute_user_has_access(self):
        """
        Override to check if the user has access to the article.
        """
        article_sources = self.filtered(lambda s: s.type == 'knowledge_article')
        for source in article_sources:
            # evaluate access with the current user without elevating to sudo (used in LLM response flow)
            source.user_has_access = source.article_id.with_user(self.env.user).user_can_read
        super(AIAgentSource, self - article_sources)._compute_user_has_access()

    @api.depends("article_id")
    def _compute_type(self):
        article_sources = self.filtered("article_id")
        for source in article_sources:
            source.type = "knowledge_article"
        super(AIAgentSource, self - article_sources)._compute_type()

    def action_access_source(self):
        """Opens the article if article_id exists"""
        self.ensure_one()
        if self.article_id:
            return {
                'type': 'ir.actions.act_url',
                'url': self.article_id.article_url,
                'target': 'new',
            }
        return super().action_access_source()

    @api.model
    def _get_sources_status_depends(self):
        return super()._get_sources_status_depends() + [
            "child_ids.status",
            "article_id.embedding_ids.embedding_vector",
            "article_id.embedding_ids.has_embedding_generation_failed",
            "article_id.embedding_ids.embedding_error",
        ]

    def _is_folder(self):
        """Override to treat sources linked to articles with children as folders if not already set."""
        self.ensure_one()
        is_child_of_same_article = self.parent_id.article_id == self.article_id
        should_be_folder = self.article_id and not self.is_folder and self.article_id.child_ids and not is_child_of_same_article
        if should_be_folder:
            article_sources = self.search([
                ('article_id', '=', self.article_id.id),
                ('agent_id', '=', self.agent_id.id),
                ('is_folder', '=', False),
            ])
            article_sources.write({'is_folder': True})
            return True
        return super()._is_folder()

    def _get_reindex_sources(self, source_filter=None):
        self.ensure_one()
        if self.type == "knowledge_article" and not self._is_folder():
            return self
        return super()._get_reindex_sources(source_filter)

    def action_reprocess_index(self):
        """Reprocess the index of the sources."""
        self.ensure_one()
        if not self.article_id:
            super().action_reprocess_index()
            return

        sources_to_reprocess = self._get_reindex_sources(
            source_filter=lambda s: s.article_id,
        )

        if not sources_to_reprocess:
            return

        sources_to_reprocess._sync_sources_name()
        sources_to_reprocess._reindex_sources()

    def _sync_sources_state(self):
        """
        Override to sync knowledge article sources state.

        :return: recordset of synced knowledge article sources
        :rtype: recordset of ai.agent.source
        """
        self.ensure_one()
        if self.type != 'knowledge_article':
            return super()._sync_sources_state()

        if not self.is_folder:
            return self

        articles = self.article_id._get_descendants() | self.article_id

        # Process the folder sources of the document folder across all agents
        folder_sources = self.search([('article_id', '=', self.article_id.id), ('is_folder', '=', True)])
        all_sources = folder_sources | folder_sources._get_descendants()

        # This loop to process the folder across agents to make sure all synchronized
        for folder_source in folder_sources:
            agent_id = folder_source.agent_id.id
            current_sources = folder_source._get_descendants() | folder_source
            existing_article_ids = set(current_sources.mapped('article_id').ids)

            missing_articles = articles.filtered(lambda a: a.id not in existing_article_ids)
            folder_articles_to_create = missing_articles.filtered(lambda a: a.child_ids)

            # Find folders missing their own "content" source child
            # (Where the folder's article_id is not represented in its children)
            missing_content_articles = current_sources.filtered(
                lambda s: s.is_folder and s.article_id not in s.child_ids.mapped('article_id')
            ).mapped('article_id')
            missing_articles |= missing_content_articles

            # Find file sources whose article has children but no corresponding folder source exists
            folder_article_ids = set(current_sources.filtered('is_folder').mapped('article_id').ids)
            folder_articles_to_create |= current_sources.filtered(
                lambda s: not s.is_folder
                        and s.article_id.child_ids
                        and s.article_id.id not in folder_article_ids
            ).mapped('article_id')

            sources_to_sync = current_sources
            if folder_articles_to_create:
                sources_to_sync |= self._create_folder_sources(folder_articles_to_create, agent_id)
                all_sources |= sources_to_sync

            if missing_articles:
                sources_to_sync |= self.create_from_articles(missing_articles, agent_id)
                all_sources |= sources_to_sync

            sources_to_sync._sync_sources_hierarchy(articles)

        # Remove sources linked to archived or trashed articles or articles that are not in the current hierarchy
        sources_to_unlink = all_sources.filtered(lambda s: not s.article_id.active or s.article_id.to_delete)
        sources_to_unlink |= all_sources.filtered(lambda s: s.article_id.id not in articles.ids)
        if sources_to_unlink:
            sources_to_unlink.unlink()
            all_sources -= sources_to_unlink

        # Collapse folder sources whose articles no longer have children.
        sources_to_collapse = all_sources._collapse_empty_folder_sources()
        if sources_to_collapse:
            all_sources = (all_sources - sources_to_collapse['unlinked']) | sources_to_collapse['reprocessed']

        return all_sources

    def _collapse_empty_folder_sources(self):
        """
        Collapse folder sources whose articles no longer have children:
        1. If a folder source still has a child (the article's own content source),
        we move that child to the parent (inherit folder's parent_id) and delete the now-redundant folder.
        2. If the folder source is empty (content source was deleted), we convert
        the folder itself into a content source by setting is_folder=False.
        (The actual attachment/content will be synced in the cron job later).

        :return: dictionary with 'unlinked' (folders that were deleted) and 'reprocessed'
                (sources that were converted or moved) keys, or None if nothing to collapse
        :rtype: dict or None
        """
        # Find all folder sources in self whose articles have no children
        folders_to_collapse = self.filtered(
            lambda s: s.is_folder and not s.article_id.child_ids
        )
        if not folders_to_collapse:
            return None

        folders_with_children = folders_to_collapse.filtered('child_ids')
        children_to_reprocess = folders_with_children.child_ids

        # Move children to inherit their folder's parent (not necessarily root)
        for folder in folders_with_children:
            folder.child_ids.write({'parent_id': folder.parent_id.id or False})

        folders_to_convert = folders_to_collapse - folders_with_children
        folders_to_convert.write({'is_folder': False})

        folders_with_children.unlink()

        return {
            'unlinked': folders_with_children,
            'reprocessed': children_to_reprocess | folders_to_convert,
        }

    def _sync_sources_hierarchy(self, target_records):
        """
        Override to sync the hierarchy of knowledge article sources.

        :param target_records: recordset of target articles
        :type target_records: recordset of knowledge.article
        """

        if any(source.type != 'knowledge_article' for source in self):
            return super()._sync_sources_hierarchy(target_records)

        article_sources = defaultdict(dict)
        for source in self:
            if source.is_folder:
                article_sources[source.article_id.id]['folder'] = source
            else:
                article_sources[source.article_id.id]['content'] = source

        parent_to_children_map = defaultdict(lambda: self.env['ai.agent.source'])

        for article in target_records:
            sources = article_sources.get(article.id)
            if not sources:
                continue

            folder_source = sources.get('folder')
            content_source = sources.get('content')

            if folder_source and content_source and content_source.parent_id.id != folder_source.id:
                parent_to_children_map[folder_source.id] |= content_source

            if article.parent_id:
                parent_folder = article_sources.get(article.parent_id.id, {}).get('folder')
                if parent_folder:
                    # link the source to the parent folder if it exists (folder source is a priority)
                    source_to_link = folder_source or content_source
                    if source_to_link and source_to_link.parent_id.id != parent_folder.id:
                        parent_to_children_map[parent_folder.id] |= source_to_link

        for parent_id, child_sources in parent_to_children_map.items():
            child_sources.write({'parent_id': parent_id})

    def _sync_sources_name(self):
        """Override to sync the name of knowledge article sources."""

        if any(source.type != 'knowledge_article' for source in self):
            return super()._sync_sources_name()

        article_names_map = defaultdict(list)
        for source in self:
            article_name = source.article_id.name
            if article_name and source.name != article_name:
                article_names_map[article_name].append(source.id)

        for name, ids in article_names_map.items():
            self.env['ai.agent.source'].browse(ids).write({'name': name})

    def _get_target_records(self):
        self.ensure_one()
        if self.article_id:
            return self.article_id
        return super()._get_target_records()

    @api.model
    def _get_target_models(self):
        return super()._get_target_models() + ["knowledge.article"]

    def _get_source_link(self, link_label=None):
        self.ensure_one()
        label = link_label if link_label else self.name
        if self.article_id:
            return Markup(
                "<a href='%s' target='_blank' rel='noopener noreferrer'>%s</a>",
            ) % (self.article_id.article_url, label)
        return super()._get_source_link(link_label)
