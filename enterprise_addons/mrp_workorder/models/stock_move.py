# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    check_id = fields.One2many('quality.check', 'move_id')
    note = fields.Html('Note', related='check_id.note')
    worksheet_document = fields.Binary('Worksheet Image/PDF', compute='_compute_worksheet_document')
    product_barcode = fields.Char(related='product_id.barcode')
    move_line_ids_picked = fields.One2many('stock.move.line', 'move_id', domain=[('picked', '=', True)])
    picking_type_prefill_shop_floor_lots = fields.Boolean(related='picking_type_id.prefill_shop_floor_lots')

    @api.depends('check_id.worksheet_document')
    def _compute_worksheet_document(self):
        for record in self:
            if record.check_id:
                record.worksheet_document = record.check_id.worksheet_document
            else:
                record.worksheet_document = None

    @api.ondelete(at_uninstall=False)
    def _unlink_quality_check(self):
        self.env['quality.check'].search([('move_id', 'in', self.ids)]).unlink()

    def action_pass(self, keep_hidden_lines=False):
        if not keep_hidden_lines:
            for record in self:
                if record.has_tracking in ['lot', 'serial'] and not record.picking_type_id.prefill_shop_floor_lots:
                    # Remove any reserved smls that are hidden
                    record.move_line_ids.filtered(lambda ml: not ml.picked).unlink()
        for check in self.check_id:
            check.action_next()
        if not self.check_id:
            self.picked = True
        return True

    def action_undo(self):
        if self.check_id:
            self.check_id.write({'quality_state': 'none'})
        self.picked = False
        self.quantity = self.product_uom_qty

    def get_quant_from_barcode(self, barcode):
        self.ensure_one()
        if self.product_id.tracking not in ['lot', 'serial']:
            return False
        lot_id = self.env['stock.lot'].search([('name', '=', barcode), ('product_id', '=', self.product_id.id)], limit=1)
        if not lot_id:
            lot_id = self.env['stock.lot'].with_context(active_mo_id=self.raw_material_production_id.id).create([{
                'name': barcode,
                'product_id': self.product_id.id
            }])
            return self.env['stock.quant'].create([{
                'lot_id': lot_id.id,
                'product_id': self.product_id.id,
                'location_id': self.warehouse_id.lot_stock_id.id
            }]).id
        return self.env['stock.quant'].search([('lot_id', '=', lot_id.id), ('location_id', 'child_of', self.location_id.id)], limit=1).id

    def _visible_quantity(self):
        self.ensure_one()
        if self.env.context.get('hide_unpicked'):
            return sum(
                sml.uom_id._compute_quantity(sml.quantity, self.uom_id, rounding_method='HALF-UP')
                for sml in self.move_line_ids_picked
            )
        return super()._visible_quantity()

    def _add_from_quant(self, quant):
        hide_unpicked = self.product_id.tracking in ['lot', 'serial'] and not self.picking_type_prefill_shop_floor_lots
        if hide_unpicked:
            move_line = next((sml for sml in self.move_line_ids if sml._takes_from_quant(quant) and not sml.picked), False)
            if move_line:  # Quant already has hidden sml -> make visible
                move_line.picked = True
                return
        remaining_qty = self.product_qty - sum(sml.quantity_product_uom for sml in self.move_line_ids if not hide_unpicked or sml.picked)
        if min(remaining_qty, quant.available_quantity) > 0 and self.product_id.tracking != 'serial':
            qty_to_take = min(remaining_qty, quant.available_quantity)
        else:
            qty_to_take = 1
        move_line = next((sml for sml in self.move_line_ids if sml._takes_from_quant(quant)), False)
        if move_line:  # Quant already has visible sml -> increase existing sml's quantity
            move_line.quantity += self.product_id.uom_id._compute_quantity(qty_to_take, self.uom_id)
        else:  # No sml exists for quant -> make new sml
            move_line_vals = self._prepare_move_line_vals(
                quantity=qty_to_take,
                reserved_quant=quant)
            self.env['stock.move.line'].create([{**move_line_vals, 'picked': True}])

    def action_add_from_quant(self, quant_id):
        self._add_from_quant(self.env['stock.quant'].browse(quant_id))

        if self.product_id.tracking in ['lot', 'serial'] and (not self.picking_type_prefill_shop_floor_lots or self in self.production_id.move_byproduct_ids):
            self.move_line_ids.filtered(lambda ml: not ml.picked).unlink()

        if self.check_id:
            self.check_id.action_next()

    def _update_catalog_quantity(self, quantity, uom, *, from_shop_floor=False, **kwargs) -> float:
        res = super()._update_catalog_quantity(
            quantity, uom, from_shop_floor=from_shop_floor, **kwargs
        )

        if from_shop_floor:
            self.quantity = quantity

        return res


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _takes_from_quant(self, quant):
        self.ensure_one()
        fields_to_match = ('location_id', 'product_id', 'owner_id', 'package_id', 'lot_id')
        return all(self[field] == quant[field] for field in fields_to_match)
