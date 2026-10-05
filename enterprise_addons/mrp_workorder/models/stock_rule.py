# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _make_mo_get_domain(self, procurement, bom):
        domain = super()._make_mo_get_domain(procurement, bom)
        return tuple(
            Domain.AND([
                Domain(domain),
                Domain.OR([
                    [('check_ids', '=', False)],
                    [('check_ids', 'not any', [('quality_state', '!=', 'none')])]
                ]),
                Domain.OR([
                    [('workorder_ids', '=', False)],
                    [('workorder_ids', 'not any',
                        [
                            ('check_ids', '!=', False),
                            ('check_ids', 'any', [('quality_state', '!=', 'none')])
                        ]
                    )]
                ])
            ])
        )
