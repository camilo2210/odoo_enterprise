# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AIWebPage(models.Model):
    _inherit = 'ai.web.page'

    def _get_internal_domains(self):
        """
        OVERRIDE
        Extend the internal domains with every website's domain.
        Handles protocols, paths, and punycode fallback.
        :return: list of internal domains
        :rtype: list of str
        """
        websites = self.env['website'].search([])
        internal_domains = set(super()._get_internal_domains())
        for site in websites:
            if domain := self._get_url_domain(site.domain_punycode or site.domain):
                internal_domains.add(domain)
        return list(internal_domains)
