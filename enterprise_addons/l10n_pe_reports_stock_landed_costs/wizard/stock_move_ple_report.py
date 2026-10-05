# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class L10n_PeStockPleWizard(models.TransientModel):
    _inherit = 'l10n_pe.stock.ple.wizard'

    def _get_move_valuation_adjustments(self, moves):
        adjustments = defaultdict(list)
        adj_lines = self.env['stock.valuation.adjustment.lines'].sudo().search([
            ('move_id', 'in', moves.ids),
            ('cost_id.state', '=', 'done'),
        ])
        for adj in adj_lines:
            serie_folio = self._get_serie_folio(adj.cost_id.name or '')
            adjustments[adj.move_id.id].append({
                'cuo': f'{adj.id}LC'.zfill(6),
                'value': adj.additional_landed_cost,
                'operation_type': '26',
                'date': adj.cost_id.date.strftime('%d/%m/%Y'),
                'document_type': '00',
                'serie': serie_folio['serie'].replace(' ', '').replace('/', '') or '0',
                'folio': serie_folio['folio'].replace(' ', '') or '0',
            })
        return adjustments
