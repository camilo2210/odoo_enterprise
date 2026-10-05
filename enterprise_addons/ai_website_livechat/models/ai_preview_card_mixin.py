# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from markupsafe import Markup

from odoo import models
from odoo.tools.urls import urljoin as url_join
from odoo.addons.base.models.ir_qweb import QWebError

_logger = logging.getLogger(__name__)


class AiPreviewCardMixin(models.AbstractModel):
    _name = 'ai.preview.card.mixin'
    _description = 'AI Preview Card Mixin'

    def _ai_get_preview_metadata(self):
        metadata = super()._ai_get_preview_metadata()
        for record, item in zip(self, metadata):
            item['preview_name'] = record.name
            if preview_url := record._ai_get_preview_url():
                item['preview_url'] = preview_url
        return metadata

    def _ai_get_preview_url(self):
        self.ensure_one()
        return url_join(self.get_base_url(), self.website_url) if self.website_url else False

    def _ai_get_preview_cards_render_context(self):
        """Return preview-card render data. To be overridden."""
        raise NotImplementedError()

    def _ai_render_preview_cards(self):
        """Render preview cards for the recordset.

        :return: tuple of (HTML string, card count) or ``False``
            if the recordset is empty, has no render context, or any card
            fails to render.
        :rtype: tuple(str, int) | bool
        """
        if not self:
            return False
        render_context = self._ai_get_preview_cards_render_context()
        if not render_context:
            return False
        cards = []
        template, records_render_context, extra_classes = render_context
        for record, card_context in zip(self, records_render_context):
            try:
                card_html = self.env['ir.ui.view']._render_template(template, card_context)
            except (QWebError, ValueError, RuntimeError):
                _logger.exception(
                    "Failed to render preview card for record %s (model: %s, template: %s)",
                    record.id, record._name, template,
                )
                return False
            url = record._ai_get_preview_url()
            href_attr = Markup(' data-href="%s"') % url if url else ''
            cards.append(
                Markup('<div class="o_ai_preview_card"%s>%s</div>')
                % (href_attr, card_html)
            )
        html = Markup('<div class="o_ai_preview_cards">%s</div>') % Markup('').join(cards)
        if extra_classes:
            html = Markup('<div class="%s">%s</div>') % (extra_classes, html)
        return html, len(cards)
