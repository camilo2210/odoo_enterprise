#  Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def split_uncompleted_moves(self):
        """ The new move is merged into the move it was split from.
        Nothing is received yet, so the subcontracting MO must be left as it is instead of
        being split in two, which would leave the merged move linked to two MOs.
        """
        subcontract_moves = self.filtered(lambda m: m.is_subcontract)
        if not subcontract_moves:
            return super().split_uncompleted_moves()
        new_moves = super(StockMove, self.with_context(keep_subcontract_production=True)).split_uncompleted_moves()
        # Gave both the scanned and the remaining quantity back to the origin move, so be resync MO.
        subcontract_moves.exists()._sync_subcontracting_productions()
        return new_moves

    def _clean_merged(self):
        if self.env.context.get('keep_subcontract_production'):
            # The merged away move shares the MO of the move it was merged into: drop the link
            # before it gets cancelled, otherwise it would cancel that MO too.
            self.filtered(lambda m: m.is_subcontract).move_orig_ids = False
        return super()._clean_merged()
