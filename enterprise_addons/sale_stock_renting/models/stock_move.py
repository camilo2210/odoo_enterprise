# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, models
from odoo.fields import Command, Domain


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _search_picking_for_assignation_domain(self):
        """Modify the picking search domain for rental moves.

        Modify the picking search domain to make sure that rental moves are on the
        same picking as sale moves in case of hybrid rental orders, while still making
        sure that modifying the SO line quantity is propagated to stock moves correctly.
        """
        domain = super()._search_picking_for_assignation_domain()
        rental_loc = self.company_id.rental_loc_id
        if (
            self.env['res.groups']._is_feature_enabled(
                'sale_stock_renting.group_rental_stock_picking'
            )
            and rental_loc
            and self.sale_line_id.order_id.is_rental_order
            and self.location_dest_id.id in (rental_loc.id, rental_loc.location_id.id)
        ):
            # optimize to make sure we have only to check the 'in' condition
            domain = (
                Domain(domain)
                .optimize(self.env['stock.picking'])
                .map_conditions(
                    lambda cond: (
                        Domain(
                            'location_dest_id',
                            'in',
                            {rental_loc.id, rental_loc.location_id.id}.union(cond.value),
                        )
                        if cond.field_expr == 'location_dest_id' and cond.operator == 'in'
                        else cond
                    )
                )
            )
        return domain

    def _prepare_procurement_values(self):
        res = super()._prepare_procurement_values()
        if (
            self.sale_line_id._are_rental_pickings_enabled()
            and self.sale_line_id.is_rental
            and self.sale_line_id.is_mto
        ):
            res['route_ids'] = self.rule_id.route_id
        return res

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        distinct_fields = super()._prepare_merge_moves_distinct_fields()
        if any(sale_order.is_rental_order for sale_order in self.reference_ids.sale_ids.sudo()):
            distinct_fields.remove('origin_returned_move_id')
            distinct_fields.remove('procure_method')
        return distinct_fields

    def _action_assign(self, force_qty=False):
        """Assign the lot_id present on the SO line to the stock move lines for rental orders."""
        super()._action_assign(force_qty=force_qty)

        for product in self.product_id:
            if product.tracking != 'serial':
                continue
            moves = self.filtered(lambda m: m.product_id == product)
            sale_lines = self.env['sale.order.line']
            for move in moves:
                sale_lines |= move._get_sale_order_lines()
            if sale_lines.sudo().reserved_lot_ids:
                free_reserved_lots = sale_lines.reserved_lot_ids.filtered(
                    lambda lot: lot not in moves.move_line_ids.lot_id
                )
                to_assign_move_lines = moves.move_line_ids.filtered(
                    lambda sml: sml.lot_id not in sale_lines.reserved_lot_ids
                )
                for line, lot in zip(to_assign_move_lines, free_reserved_lots):
                    quant = lot.quant_ids.filtered(
                        lambda q: (
                            q.location_id == line.location_id
                            and q.quantity == 1
                            and q.reserved_quantity == 0
                        )
                    )
                    if quant:
                        line.lot_id = lot

    def _action_done(self, cancel_backorder=False):
        """Correctly set the qty_delivered and qty_returned of rental order lines when using
        pickings."""
        res = super()._action_done(cancel_backorder=cancel_backorder)
        if (
            not self.env.context.get('rental_direct_stock_move')
            and self.env['res.groups']._is_feature_enabled(
                'sale_stock_renting.group_rental_stock_picking'
            )
        ):
            returned_lot_ids, pickedup_lot_ids = (defaultdict(set), defaultdict(set))
            for move in res:
                if move.state != "done":
                    continue
                if (
                    not move.sale_line_id.is_rental
                    or move.product_id != move.sale_line_id.product_id
                ):
                    continue
                if move.location_id == move.company_id.rental_loc_id:
                    current_qty_returned = move.uom_id._compute_quantity(
                        move.quantity, move.sale_line_id.product_uom_id, rounding_method='HALF-UP'
                    )
                    move.sale_line_id.qty_returned += current_qty_returned
                if move.picked and move.sale_line_id.tracking == 'serial':
                    # Synchronize the reserved lots with the picked lots.
                    # Ensure reserved lots include all picked lots and any extra reserved lots.
                    sol = move.sale_line_id
                    qty_to_keep_reserved = max(
                        int(sol.product_uom_qty), len(move.lot_ids), len(sol.reserved_lot_ids)
                    )
                    sol.reserved_lot_ids = (move.lot_ids | sol.reserved_lot_ids)[
                        :qty_to_keep_reserved
                    ]
                    if move.location_id == move.company_id.rental_loc_id:
                        returned_lot_ids[move.sale_line_id.id].update(move.lot_ids.ids)
                    elif move.location_dest_id == move.company_id.rental_loc_id:
                        pickedup_lot_ids[move.sale_line_id.id].update(move.lot_ids.ids)
            for sale_line_id, lot_ids in returned_lot_ids.items():
                self.env['sale.order.line'].browse(sale_line_id).returned_lot_ids = [Command.link(lot_id) for lot_id in lot_ids]
            for sale_line_id, lot_ids in pickedup_lot_ids.items():
                self.env['sale.order.line'].browse(sale_line_id).pickedup_lot_ids = [Command.link(lot_id) for lot_id in lot_ids]
        return res

    def _compute_location_dest_id(self):
        moves_to_super = self.env['stock.move']
        for move in self:
            if (
                move.location_dest_id
                and move.forecasted_location_id
                and move.sale_line_id
                and not move.sale_line_id.is_rental
                and move.sale_line_id.order_id.is_rental_order
                and move.picking_type_id.code == 'outgoing'
                and move.forecasted_location_id._child_of(move.location_dest_id)
            ):
                move.location_dest_id = move.forecasted_location_id
            else:
                moves_to_super |= move

        if moves_to_super:
            super(StockMove, moves_to_super)._compute_location_dest_id()

    @api.depends('sale_line_id.order_id.name')
    def _compute_reference(self):
        moves_with_reference = set()
        for move in self:
            if move.sale_line_id.is_rental and not move.picking_id:
                move.reference = self.env._(
                    "Rental move: %(order)s", order=move.sale_line_id.order_id.name
                )
                moves_with_reference.add(move.id)
        super(
            StockMove, self - self.env['stock.move'].browse(moves_with_reference)
        )._compute_reference()

    def _set_rental_sm_qty(self):
        self.ensure_one()
        return self

    def _is_incoming(self):
        if (
            self.company_id.rental_loc_id == self.location_id
            and self.location_dest_id.usage == 'internal'
        ):
            return True

        return super()._is_incoming()
