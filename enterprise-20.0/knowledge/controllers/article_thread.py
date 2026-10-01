# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.addons.portal.controllers.mail import MailController
from odoo.addons.knowledge.controllers.main import KnowledgeController
from odoo.http import request
from odoo.addons.mail.controllers.thread import ThreadController
from odoo.addons.mail.tools.discuss import Store


class ArticleThreadController(KnowledgeController):

    @http.route('/knowledge/thread/create', type='jsonrpc', auth='user')
    def create_thread(self, article_id, article_anchor_text="", fields=["id", "article_anchor_text"]):
        article_thread = request.env['knowledge.article.thread'].create({
            'article_id': article_id,
            'article_anchor_text': article_anchor_text,
        })
        return {field: article_thread[field] for field in fields}

    @http.route('/knowledge/thread/resolve', type='http', auth='user')
    def resolve_thread(self, res_id, token):
        _, thread, redirect = MailController._check_token_and_record_or_redirect('knowledge.article.thread', int(res_id), token)
        if not thread or not thread.article_id.user_can_write:
            return redirect
        if not thread.is_resolved:
            thread.is_resolved = True
        return self.redirect_to_article(thread.article_id.id, show_resolved_threads=True)
