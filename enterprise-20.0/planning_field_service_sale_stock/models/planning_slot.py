# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields
from odoo.fields import Domain


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    deliveries_total = fields.Integer(compute='_compute_deliveries_total')
    deliveries_done = fields.Integer(compute='_compute_deliveries_total')

    def _inverse_lot_ids(self):
        for slot in self:
            material_lots = slot.sale_order_id.order_line.filtered(
                lambda sol: sol.planning_slot_id == slot and sol.product_uom_qty > 0
            ).fsm_lot_id
            slot.lot_ids -= material_lots
            super(PlanningSlot, slot)._inverse_lot_ids()
            slot.lot_ids |= material_lots

    def _prepare_materials_delivery(self, timesheets):
        """ Prepare the materials delivery

            We validate the stock and generates/updates delivery order.
            This method is called at the end of the action_complete method in planning_field_service module.
        """
        for slot in self:
            if not slot.sale_order_id:
                continue
            exception = False
            sale_line = self.env['sale.order.line'].sudo().search([
                ('order_id', '=', slot.sale_order_id.id),
                ('planning_slot_id', '=', slot.id),
                ('display_type', 'not in', ['line_section', 'line_note'])
            ])
            for order_line in sale_line:
                to_log = {}
                total_qty = sum(order_line.move_ids.filtered(lambda m: m.state != 'cancel' and not m.move_dest_ids).mapped('product_uom_qty'))
                if (order_line.product_uom_id.compare(order_line.product_uom_qty, total_qty) < 0
                    and order_line.product_id in order_line.move_ids.product_id):
                    to_log[order_line] = (order_line.product_uom_qty, total_qty)

                if to_log:
                    exception = True
                    documents = self.env['stock.picking']._log_activity_get_documents(to_log, 'move_ids', 'UP')
                    documents = {k: v for k, v in documents.items() if k[0].state not in ['cancel', 'done']}
                    self.env['sale.order']._log_decrease_ordered_quantity(documents)
            if not exception:
                slot.sudo()._validate_stock()

    def _validate_stock(self, done_picking_ids=None):
        self.ensure_one()
        if not done_picking_ids:
            done_picking_ids = set()
        all_fsm_sn_moves = self.env['stock.move']
        ml_to_create = []
        for so_line in self.sale_order_id.order_line:
            if not (so_line.planning_slot_id or so_line.fsm_lot_id):
                continue
            qty = so_line.product_uom_qty - so_line.qty_delivered
            fsm_sn_moves = self.env['stock.move']
            if not qty:
                continue
            for move in so_line.move_ids:
                if move.state in ['done', 'cancel'] or (move.quantity >= qty and move.picked):
                    continue
                fsm_sn_moves |= move
                while move.move_orig_ids.filtered(lambda m: not m.picked or m.quantity < qty):
                    move = move.move_orig_ids
                    fsm_sn_moves |= move
            for fsm_sn_move in fsm_sn_moves:
                ml_vals = False
                if not fsm_sn_move.move_line_ids:
                    ml_vals = fsm_sn_move._prepare_move_line_vals(quantity=0)
                    ml_vals['quantity'] = fsm_sn_move.product_uom_qty
                    ml_vals['lot_id'] = so_line.fsm_lot_id.id
                    ml_to_create.append(ml_vals)
                else:
                    qty_done = 0
                    fsm_sn_move.move_line_ids.lot_id = so_line.fsm_lot_id
                    for move_line in fsm_sn_move.move_line_ids:
                        qty_done += move_line.quantity
                    missing_qty = fsm_sn_move.product_uom_qty - qty_done
                    if missing_qty > 0:
                        ml_vals = fsm_sn_move._prepare_move_line_vals(quantity=0)
                        ml_vals['quantity'] = missing_qty
                        ml_vals['lot_id'] = so_line.fsm_lot_id.id
                        ml_to_create.append(ml_vals)
                if ml_vals:
                    quants = self.env['stock.quant']._gather(fsm_sn_move.product_id, fsm_sn_move.location_id, lot_id=so_line.fsm_lot_id)
                    if fsm_sn_move.product_id.tracking == "serial":
                        quants = quants.filtered(lambda q: q.quantity == 1.0)
                    ml_vals['location_id'] = quants[:1].location_id.id or fsm_sn_move.location_id.id
            all_fsm_sn_moves |= fsm_sn_moves
        self.env['stock.move.line'].create(ml_to_create)
        for so_line in self.sale_order_id.order_line:
            # set the quantity delivered of the sol to the quantity ordered for the product linked to the intervention
            if so_line.planning_slot_id == self and so_line.product_id.service_policy not in ['delivered_timesheet', 'delivered_milestones']:
                so_line.qty_delivered = so_line.product_uom_qty

        def is_field_service_material_picking(picking, slot):
            """ this function returns if the picking is a picking ready to be validated. """
            accessed_moves = moves = picking.move_ids
            while moves:
                next_moves = moves.move_dest_ids - accessed_moves
                if not next_moves:
                    break
                accessed_moves |= next_moves
                moves = next_moves
            for move in moves:
                sol = move.sale_line_id
                if sol.fsm_lot_id:
                    continue
                if not (
                    sol.product_id != slot._get_timesheetable_project().timesheet_product_id
                    and sol != slot.sale_line_id
                    # On the last and, we check if the intervention is either done (and thus already done for the delivery) or the current one (and thus about to be validated)
                    # if not, we can not validate the delivery
                    and (sol.planning_slot_id == slot or sol.planning_slot_id.state == '4_completed')
                ):
                    return False
            return True

        pickings_to_do = self.sale_order_id.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'] and is_field_service_material_picking(p, self))
        # set the quantity done as the initial demand before validating the pickings
        for move in pickings_to_do.move_ids:
            if move.state in ('done', 'cancel') or move in all_fsm_sn_moves:
                continue
            if move.uom_id.compare(move.quantity, move.product_uom_qty) < 0:
                qty_to_do = move.uom_id.round(move.product_uom_qty - move.quantity)
                move.quantity = qty_to_do
        pickings_to_do.with_context(skip_sms=True, cancel_backorder=True).button_validate()

        # With new push rules, some pickings may not be created before previous picking validation, hence the need to go through the pickings again.
        done_picking_ids.update(pickings_to_do.ids)
        remaining_to_do = self.sale_order_id.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'] and is_field_service_material_picking(p, self))
        if any(remaining_id not in done_picking_ids for remaining_id in remaining_to_do.ids):
            self._validate_stock(done_picking_ids=done_picking_ids)

    def _get_customer_intervention_stock_move_lines(self):
        return self.env['stock.move'].search([
            ('sale_line_id.order_id', '=', self.sale_order_id.id),
            ('sale_line_id.planning_slot_id', '=', False),
            ('state', '!=', 'cancel'),
        ])

    def _compute_deliveries_total(self):
        for slot in self:
            customer_move_lines = slot.sudo()._get_customer_intervention_stock_move_lines()
            slot.deliveries_total = len(customer_move_lines)
            slot.deliveries_done = len(customer_move_lines.filtered(lambda d: d.state == 'done'))

    def action_fsm_pick_up(self):
        stock_move_ids = self.sudo()._get_customer_intervention_stock_move_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Deliveries'),
            'view_mode': 'list,kanban',
            'mobile_view_mode': 'kanban',
            'domain': [('id', 'in', stock_move_ids.ids)],
            'res_model': 'stock.move',
            'views': [
                (self.env.ref('planning_field_service_sale_stock.view_move_tree_picking_redirect').id, 'list'),
                (self.env.ref('planning_field_service_sale_stock.view_move_kanban_picking_redirect').id, 'kanban'),
            ],
        }

    def _update_equipment_from_materials(self, material_lots, removed_lots):
        self.ensure_one()
        if not self.env.user.has_group('planning.group_field_service_allow_equipment'):
            return

        if removed_lots:
            removed_lots -= self.env['stock.lot'].sudo().search([
                ('id', 'in', removed_lots.ids),
                ('partner_ids', 'child_of', self.partner_id.ids),
            ])
        lot_ids = (self.lot_ids | material_lots) - removed_lots
        if lot_ids != self.lot_ids:
            self.lot_ids = lot_ids

    def _ensure_sale_order_set(self):
        """Since we want to use the current user warehouse when using the field service product kanban view, the SO must
           be confirmed before adding any product trough the product kanban view.
           We cannot indeed wait that the user actually adds a product trough the field service product kanban view
           to do so as there would be a risk that all the existing SOL (possibly added in a (pre)sale phase)
           would get that user's default warehouse when the SO gets confirmed and the picking generated."""
        sale_order = super()._ensure_sale_order_set()
        if sale_order.state == 'draft':
            sale_order.action_confirm()
        return sale_order

    def _generate_sale_order(self):
        """Since we want to use the current user warehouse when using the field service product kanban view, the SO must
           be confirmed before adding any product trough the product kanban view.
           We cannot indeed wait that the user actually adds a product trough the field service product kanban view
           to do so as there would be a risk that all the existing SOL (possibly added in a (pre)sale phase)
           would get that user's default warehouse when the SO gets confirmed and the picking generated."""
        super()._generate_sale_order()
        sale_order = self.sale_order_id
        if self.env.user.has_group('planning.group_planning_user'):
            sale_order = self.sale_order_id.sudo()
        sale_order.with_context(intervention_create_sale_order=True).action_confirm()

    def _get_available_product_materials_domain(self):
        domain = super()._get_available_product_materials_domain()
        if not self.env.user.has_group('stock.group_stock_user'):
            domain = Domain.AND([
                domain,
                [('tracking', 'not in', ['lot', 'serial'])],
            ])
        return domain

    def action_view_material(self):
        action = super().action_view_material()
        action['context'].update({"warehouse_id": self.env.user._get_default_warehouse_id().id})
        return action

    def _action_complete(self, from_status_bar=False):
        """Since SOs for interventions are confirmed right after creation
           and this blocks the creation of pickings,
           we do not lock sales orders for interventions after confirmation.
           Instead, we lock the SOs when we mark the intervention as done."""
        super()._action_complete(from_status_bar)
        self.sudo().sale_order_id.filtered(lambda so: so._should_be_locked()).action_lock()
