# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import models

from .mail_message import ELEMENT_LABEL_CLASS


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    def message_post(self, **kwargs):
        labels = self.env.context.get('ai_website_element_labels')
        session = self.sudo().ai_session_ids[:1]
        if labels and session._is_website_builder_session():
            labels_markup = Markup('').join(
                Markup('<span class="%s d-none">%s</span>') % (ELEMENT_LABEL_CLASS, label)
                for label in labels
            )
            kwargs['body'] = Markup('%s%s') % (
                kwargs.get('body', ''),
                labels_markup,
            )
        return super().message_post(**kwargs)
