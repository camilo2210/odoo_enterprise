# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import html

from odoo import models
from odoo.addons.mail.tools.discuss import Store
from odoo.tools.mail import html_remove_xpath


ELEMENT_LABEL_CLASS = 'o-ai-website-element-label'


class MailMessage(models.Model):
    _inherit = 'mail.message'

    def _store_extra_fields(self, res: Store.FieldList, *, format_reply):
        super()._store_extra_fields(res, format_reply=format_reply)
        res.attr(
            'ai_website_element_labels',
            lambda message: message._ai_website_get_element_labels(),
            predicate=lambda message: ELEMENT_LABEL_CLASS in (message.body or ''),
        )

    def _ai_website_get_element_labels(self):
        self.ensure_one()
        tree = html.fragment_fromstring(self.body or '', create_parent='div')
        return [element.text_content() for element in tree.find_class(ELEMENT_LABEL_CLASS)]

    def _convert_to_parts(self):
        parts = super()._convert_to_parts()
        if ELEMENT_LABEL_CLASS in (self.body or ''):
            parts[0]['text'] = html_remove_xpath(
                parts[0]['text'],
                f"//*[hasclass('{ELEMENT_LABEL_CLASS}')]",
            )
        return parts
