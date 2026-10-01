import re

from lxml import html

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools import html2plaintext, is_html_empty


class KnowledgeArticle(models.Model):
    _name = "knowledge.article"
    _inherit = ['knowledge.article', 'ai.embedding.mixin']

    ai_sources_ids = fields.One2many("ai.agent.source", "article_id", string="AI Agent Sources")

    def write(self, vals):
        result = super().write(vals)
        if not vals.get('cover_image_id'):
            return result
        cover_attachment = self.cover_image_id.attachment_id
        self.env['ai.attachment.vacuum'].mark_attachments_used(cover_attachment.ids)
        return result

    @api.ondelete(at_uninstall=False)
    def _unlink_sources(self):
        """Delete sources when an article is deleted."""
        source_linked_to_article = self.env['ai.agent.source'].search([('article_id', 'in', self.ids)])
        if source_linked_to_article:
            source_linked_to_article.unlink()

    def _get_embedding_content(self):
        self.ensure_one()
        result = self._extract_article_content()
        min_content_len = 10
        if result and (content := result.get("content")):
            # Check for reasonable content length
            if len(content) > min_content_len:
                return result["content"]
        raise ValueError(self.env._("Failed to extract content from the article's body. Content must be at least 10 characters long."))

    def _extract_article_content(self):
        """
        Extract plain text content from the article body.

        :return: dictionary with 'content' and 'error' keys
        :rtype: dict
        """
        self.ensure_one()
        body = self.body or ''
        if is_html_empty(body):
            return {'content': None, 'error': self.env._("Failed to extract content from the article's body.")}

        fragment = html.fragment_fromstring(body, create_parent=True)
        for element in fragment.xpath("//*[@data-embedded]"):
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)

        plain_text = html2plaintext(
            html.tostring(fragment, encoding='unicode'),
            include_references=False,
        )
        plain_text = re.sub(r'\n{3,}', '\n\n', plain_text).strip()

        if plain_text and self.name:
            plain_text = f"{self.name}\n\n{plain_text}"
        if plain_text:
            return {'content': plain_text, 'error': None}
        return {'content': None, 'error': self.env._("Failed to extract content from the article's body.")}

    @api.model
    def _get_records_to_embed_domain(self):
        return super()._get_records_to_embed_domain() & Domain("ai_sources_ids", "!=", False) & Domain("ai_sources_ids.status", "not in", ["failed", "skipped"])

    def _get_embedding_models(self):
        self.ensure_one()
        return {source.agent_id.embedding_model for source in self.ai_sources_ids}

    def _on_embedding_failure(self, error):
        super()._on_embedding_failure(error)
        self.ai_sources_ids.write({
            "status": "skipped",
            "error_details": str(error),
        })
