# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools import SQL


class ProductProduct(models.Model):
    _inherit = 'product.product'

    fsm_quantity = fields.Float('Material Quantity', compute="_compute_fsm_quantity", inverse="_inverse_fsm_quantity", search="_search_fsm_quantity")

    @api.depends_context('intervention_id')
    def _compute_fsm_quantity(self):
        slot = self._get_contextual_field_service_intervention()
        if slot:
            SaleOrderLine = self.env['sale.order.line']
            if self.env.user.has_group('planning.group_planning_user'):
                slot = slot.sudo()
                SaleOrderLine = SaleOrderLine.sudo()

            quantities_per_product = dict(
                SaleOrderLine._read_group(
                    [('order_id', '=', slot.sale_order_id.id), ('planning_slot_id', '=', slot.id), ('product_id', '!=', False)],
                    ['product_id'], ['product_uom_qty:sum'],
                )
            )
            for product in self:
                product.fsm_quantity = quantities_per_product.get(product, 0)
        else:
            self.fsm_quantity = False

    def _inverse_fsm_quantity(self):
        slot = self._get_contextual_field_service_intervention()
        if slot:
            sale_order_lines = slot.sale_order_id.order_line.filtered(
                lambda sol:
                    sol.product_id in self
                    and slot == sol.planning_slot_id
                    and sol._is_in_section()
            )
            sale_lines_per_product = defaultdict(lambda: self.env['sale.order.line'])
            for line in sale_order_lines:
                sale_lines_per_product[line.product_id.id] |= line
            for product in self:
                sale_lines = sale_lines_per_product.get(product.id, self.env['sale.order.line'])
                all_editable_lines = sale_lines.filtered(lambda sol: sol.qty_delivered == 0 or sol.qty_delivered_method == 'manual' or not sol.order_id.locked)
                diff_qty = product.fsm_quantity - sum(sale_lines.mapped('product_uom_qty'))
                if all_editable_lines:  # existing line: change ordered qty (and delivered, if delivered method)
                    if diff_qty > 0:
                        vals = {
                            'product_uom_qty': all_editable_lines[0].product_uom_qty + diff_qty,
                        }
                        if slot.under_warranty:
                            vals['price_unit'] = 0
                        if all_editable_lines[0].qty_delivered_method == 'manual':
                            vals['qty_delivered'] = all_editable_lines[0].product_uom_qty + diff_qty
                        all_editable_lines[0].with_context(fsm_no_message_post=True).write(vals)
                        continue
                    # diff_qty is negative, we remove the quantities from existing editable lines:
                    for line in all_editable_lines:
                        new_line_qty = max(0, line.product_uom_qty + diff_qty)
                        diff_qty += line.product_uom_qty - new_line_qty
                        if line.qty_delivered_method == 'manual':
                            line.with_context(fsm_no_message_post=True).qty_delivered = new_line_qty
                        line.with_context(fsm_no_message_post=True).product_uom_qty = new_line_qty
                        if slot.under_warranty:
                            line.price_unit = 0
                        if diff_qty == 0:
                            break
                elif diff_qty > 0:  # create new SOL
                    vals = {
                        **slot.sale_order_id._catalog_prepare_new_line_vals(
                            self.env.context.get('child_field', 'order_line'),
                            product,
                            diff_qty,
                            uom=product.uom_id,
                            section_id=self.env.context.get('section_id'),
                        ),
                        'planning_slot_id': slot.id,
                    }
                    if slot.under_warranty:
                        vals['price_unit'] = 0

                    sol_sudo = self.env['sale.order.line'].sudo().with_context(planning_slot_generation=False).create(vals)
                    if sol_sudo.qty_delivered_method == 'manual':
                        sol_sudo.qty_delivered = diff_qty

    @api.model
    def _search_fsm_quantity(self, operator, value):
        if operator == 'in':
            return Domain.OR(self._search_fsm_quantity('=', v) for v in value)
        if operator == 'not in':
            return NotImplemented
        if not (isinstance(value, int) or (isinstance(value, bool) and value is False)):
            return NotImplemented
        match operator:
            case '<=':
                operator_sql = SQL('<=')
            case '<':
                operator_sql = SQL('<')
            case '>':
                operator_sql = SQL('>')
            case '>=':
                operator_sql = SQL('>=')
            case _:
                return NotImplemented

        slot = self._get_contextual_field_service_intervention()
        if not slot:
            return []
        op = 'in'
        if value is False:
            value = 0
            operator = SQL('>=')
            op = 'not in'
        return [('id', op, SQL("""(
            SELECT sol.product_id
              FROM sale_order_line sol
         LEFT JOIN sale_order so
                ON sol.order_id = so.id
         LEFT JOIN planning_slot intervention
                ON so.id = intervention.sale_order_id
             WHERE intervention.id = %s
               AND sol.product_uom_qty %s %s
        )""", slot.id, operator_sql, value))]

    @api.model
    def _get_contextual_field_service_intervention(self):
        return self.env['planning.slot'].browse(self.env.context.get('intervention_id', False))

    def set_fsm_quantity(self, quantity):
        slot = self._get_contextual_field_service_intervention()
        # planning user with no sale rights should be able to change material quantities
        if not slot or slot.state in ['1_draft', '2_published'] or quantity and quantity < 0 or not self.env.user.has_group('planning.group_planning_user'):
            return

        # don't add material on read only SO (locked or cancelled)
        if slot.sale_order_id and slot.sale_order_id.sudo()._is_readonly():
            return False
        # ensure that the task is linked to a sale order
        slot._ensure_sale_order_set()
        wizard_product_lot = self.action_assign_serial(from_onchange=True)
        if wizard_product_lot:
            return wizard_product_lot
        self.sudo().fsm_quantity = self.uom_id.round(quantity or 0)
        return True

    # Is override by fsm_stock to manage lot
    def action_assign_serial(self, from_onchange=False):
        return False

    def fsm_add_quantity(self):
        return self.set_fsm_quantity(self.sudo().fsm_quantity + 1)

    def fsm_remove_quantity(self):
        fsm_product_qty = self.sudo().fsm_quantity
        fsm_product_qty = fsm_product_qty - 1 if fsm_product_qty > 1 else 0
        return self.set_fsm_quantity(fsm_product_qty)
