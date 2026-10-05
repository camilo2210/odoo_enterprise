# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import html

from odoo import models
from odoo.addons.mail.tools.discuss import Store


PREVIEW_DATA_CLASS = 'o_ai_preview_data'
PREVIEW_HEADER_CLASS = 'o_ai_preview_header'


class MailMessage(models.Model):
    _inherit = 'mail.message'

    def _store_extra_fields(self, res: Store.FieldList, *, format_reply):
        super()._store_extra_fields(res, format_reply=format_reply)
        res.attr(
            'ai_record_previews',
            lambda message: message._ai_get_record_previews_data(),
            predicate=lambda message: PREVIEW_DATA_CLASS in (message.body or ''),
        )

    def _ai_get_record_previews_data(self):
        """ Scan message body for preview data and return record sets.

        :return: preview-set data for the message store, or False if none found.
        :rtype: dict | bool
        """
        self.ensure_one()
        body = self.body or ''
        tree = html.fragment_fromstring(body, create_parent='div')
        preview_blocks = tree.xpath(
            '//*[contains(concat(" ", normalize-space(@class), " "), " %s ")]' % PREVIEW_DATA_CLASS
        )
        # For single preview block, strip the header if added by the tool as it is useless.
        if len(preview_blocks) == 1:
            header = preview_blocks[0].xpath(
                './/*[contains(concat(" ", normalize-space(@class), " "), " %s ")]' % PREVIEW_HEADER_CLASS
            )
            if header:
                header[0].getparent().remove(header[0])

        preview_sets = [
            preview_set
            for preview_key, block in enumerate(preview_blocks)
            if (preview_set := self._ai_parse_record_preview_block(block, preview_key))
        ]
        return {'preview_sets': preview_sets} if preview_sets else False

    def _ai_parse_record_preview_block(self, block, preview_key):
        """Extract record links from a message's preview block and return a structured
        preview set dict."""
        links = block.xpath('.//a[@data-oe-model and @data-oe-id]')
        if not links:
            return None

        model = links[0].get('data-oe-model')
        if model not in self.env:
            return None
        records = []
        for link in links:
            records.append({
                'id': int(link.get('data-oe-id')),
                'url': link.get('href'),
                'name': link.text_content().strip(),
            })
        header_el = block.xpath(
            './/*[contains(concat(" ", normalize-space(@class), " "), " %s ")]'
            % PREVIEW_HEADER_CLASS
        )
        return {
            'preview_key': preview_key,
            'model': model,
            'header': header_el[0].text_content().strip() if header_el else '',
            'has_preview_cards': isinstance(self.env[model], self.env.registry['ai.preview.card.mixin']),
            'records': records,
        }
