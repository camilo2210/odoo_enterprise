# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class L10nBeEmployerCategory(models.Model):
    _name = 'l10n.be.employer.category'
    _description = 'BE: Employer Category'

    name = fields.Char(required=True, translate=True)
    sector = fields.Selection([
        ('private', 'Private'),
        ('public', 'Public'),
    ], default='private', required=True)
    egov3_code = fields.Char(required=True)
    dmfa_code = fields.Char(required=True)
    allowed_joint_committee_ids = fields.Many2many('l10n.be.joint.committee', string="Allowed Joint Committees", context={'active_test': False})
    allowed_worker_code_ids = fields.Many2many('l10n.be.worker.code', string="Worker Codes")

    @api.depends('dmfa_code')
    def _compute_display_name(self):
        for category in self:
            category.display_name = f'[{category.dmfa_code}] {category.name}'

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        result = []
        domain = Domain(domain or Domain.TRUE)
        # first search by code
        if not operator in Domain.NEGATIVE_OPERATORS and name:
            categories = self.search_fetch(domain & Domain('egov3_code', operator, name), ['display_name'], limit=limit)
            result.extend((category.id, category.display_name) for category in categories)
            domain &= Domain('id', 'not in', categories.ids)
            if limit is not None:
                limit -= len(categories)
                if limit <= 0:
                    return result
        # normal search
        result.extend(super().name_search(name, domain, operator, limit))
        return result
