# Part of Odoo. See LICENSE file for full copyright and licensing details.

import itertools

from odoo import api, models, fields
from odoo.fields import Domain


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    product_id = fields.Many2one('product.product', string='Product', check_company=True,
        domain="[('sale_ok', '=', True), ('id', 'in', suitable_product_ids)]")
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number', domain="[('product_id', '=', product_id)]")
    tracking = fields.Selection(related='product_id.tracking')
    suitable_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_suitable_product_ids',
        export_string_translation=False,
        compute_sudo=True,
        groups="stock.group_stock_user",
    )

    @api.depends('helpdesk_ticket_id.partner_id')
    def _compute_suitable_product_ids(self):
        suitable_partner_ids = self.env['res.partner'].search([('commercial_partner_id', 'in', self.helpdesk_ticket_id.commercial_partner_id.ids)]).ids

        sale_data = self.env['sale.order.line']._read_group([
            ('product_id', '!=', False),
            ('order_id.state', '=', 'sale'),
            ('order_partner_id', 'in', suitable_partner_ids)
        ], ['order_partner_id'], ['product_id:array_agg'])
        order_data = {order_partner.id: product_ids for order_partner, product_ids in sale_data}

        picking_data = self.env['stock.picking']._read_group([
            ('state', '=', 'done'),
            ('partner_id', 'in', suitable_partner_ids),
            ('picking_type_code', '=', 'outgoing'),
        ], ['partner_id'], ['id:array_agg'])

        # it was not correct, it took only products of stock_move_line from the first partner_id of self
        picking_ids = [id_ for _dummy, ids in picking_data for id_ in ids]
        outgoing_product = {}
        if picking_ids:
            move_line_data = self.env['stock.move.line']._read_group([
                ('state', '=', 'done'),
                ('picking_id', 'in', picking_ids),
                ('picking_code', '=', 'outgoing'),
            ], ['picking_id'], ['product_id:array_agg'])
            move_lines = {picking.id: product_ids for picking, product_ids in move_line_data}
            if move_lines:
                for partner, picking_ids in picking_data:
                    product_lists = [move_lines[pick] for pick in picking_ids if pick in move_lines]
                    outgoing_product[partner.id] = list(itertools.chain(*product_lists))

        for move_reversal in self:
            product_ids = {item for partner_id in suitable_partner_ids for item in order_data.get(partner_id, []) + outgoing_product.get(partner_id, [])}
            move_reversal.suitable_product_ids = [fields.Command.set(product_ids)]

    def reverse_moves(self, is_modify=False):
        action = super().reverse_moves(is_modify=is_modify)
        if self.helpdesk_ticket_id:  # checking if the wizard was created from helpdesk
            if self.sudo().product_id and self.new_move_ids.invoice_line_ids.product_id != self.sudo().product_id:
                self.new_move_ids.invoice_line_ids = self.new_move_ids.invoice_line_ids.filtered(lambda line: line.product_id == self.sudo().product_id)
            for line in self.new_move_ids.invoice_line_ids:  # self.new_move_ids is the reverse of the moves passed to the wizard
                # the line could be a down payment, which has display_type == 'product'; we have to check if there is a product
                if not line.product_id or line.display_type != 'product' or line.product_id.type != 'consu' or line.product_id != self.product_id:
                    continue
                # for helpdesk, we are guaranteed to always have a single sale line
                line.quantity -= line.sale_line_ids.qty_delivered
        return action

    def _get_default_so_domain(self, ticket):
        domain = super()._get_default_so_domain(ticket)
        if self.product_id:
            domain = Domain.AND([
                domain,
                [('order_line.product_id', '=', self.product_id.id)]
            ])
        return domain

    def _get_default_moves_domain(self, ticket):
        domain = super()._get_default_moves_domain(ticket)
        if self.product_id:
            domain = Domain.AND([
                domain,
                [('line_ids.product_id', '=', self.product_id.id)]
            ])
        return domain

    def _get_suitable_move_domain(self):
        domain = super()._get_suitable_move_domain()
        if self.product_id:
            domain = Domain.AND([
                domain,
                [('invoice_line_ids.product_id', '=', self.product_id.id)]
            ])
        return domain

    def _get_suitable_so_domain(self):
        domain = super()._get_suitable_so_domain()
        if self.product_id:
            domain = Domain.AND([
                domain,
                [('order_line.product_id', '=', self.product_id.id)]
            ])
        return domain

    @api.depends('product_id')
    def _compute_suitable_moves(self):
        super()._compute_suitable_moves()

    @api.depends('product_id')
    def _compute_suitable_sale_orders(self):
        super()._compute_suitable_sale_orders()
