# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class ResourceResource(models.Model):
    _name = 'resource.resource'
    _inherit = 'resource.resource'

    def _get_unsearched_domain(self):
        domain = super()._get_unsearched_domain()
        domain = Domain.OR([domain, [('sale_line_id.rental_status', '=', 'returned')]])
        return domain

    def _get_not_invoiced_domain(self, config, partner_id=None, search=None, **kwargs):
        domain = super()._get_not_invoiced_domain(config, partner_id=partner_id, search=search, **kwargs)
        if rental_status := kwargs.get('rental_status'):
            domain = Domain.AND([domain, [('sale_line_id.rental_status', '=', rental_status)]])
        return domain
