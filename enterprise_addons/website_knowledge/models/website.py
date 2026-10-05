# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class Website(models.Model):
    _inherit = "website"

    def _get_search_scopes(self):
        return {
            **super()._get_search_scopes(),
            'knowledge': {
                'label': self.env._("Knowledge articles"),
                'url': '/website/search/knowledge',
            },
        }

    def _search_get_details(self, search_type, order, options):
        result = super()._search_get_details(search_type, order, options)
        if search_type in ['knowledge', 'knowledge_article']:
            result.append(self.env['knowledge.article']._search_get_detail(self, order, options))
        return result
