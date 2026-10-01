from odoo.addons.portal.controllers import portal


class KnowledgePortal(portal.CustomerPortal):

    def _prepare_portal_counter_values(self, counter):
        if counter == 'knowledge_count':
            return 'knowledge.article', self._prepare_knowledge_article_domain(), 'read'
        return super()._prepare_portal_counter_values(counter)

    def _prepare_knowledge_article_domain(self):
        """Generate the domain for the portal's articles"""
        return []
