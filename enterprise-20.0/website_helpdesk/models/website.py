# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _


class Website(models.Model):
    _inherit = "website"

    def get_suggested_controllers(self):
        suggested_controllers = super().get_suggested_controllers()
        suggested_controllers.append((_('Helpdesk Customer Satisfaction'), self.env['ir.http']._url_for('/helpdesk/rating'), 'helpdesk'))
        return suggested_controllers

    def configurator_get_footer_links(self):
        links = super().configurator_get_footer_links()
        links.append({'text': _("Help"), 'href': '/help'})
        return links

    def _search_get_details(self, search_type, order, options):
        if search_type == 'knowledge_and_forum':
            return (
                self._search_get_details('knowledge', order, options)
                + self._search_get_details('forums', order, options)
            )
        return super()._search_get_details(search_type, order, options)
