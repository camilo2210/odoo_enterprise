# -*- coding: utf-8 -*-
# Part of Odoo. See ICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class StockReturnPicking(models.TransientModel):
    _name = 'stock.return.picking.helpdesk'
    _description = 'Return Picking in Helpdesk'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get('active_id') and self.env.context.get('active_model') == 'helpdesk.ticket':
            if len(self.env.context.get('active_ids', [])) > 1:
                raise UserError(self.env._("You may only return on one ticket at a time."))
            ticket_id = self.env['helpdesk.ticket'].browse(self.env.context.get('active_id'))
            if ticket_id.exists():
                res.update({'ticket_id': ticket_id.id})
        return res

    partner_id = fields.Many2one('res.partner', related="ticket_id.partner_id", string="Customer")
    ticket_id = fields.Many2one('helpdesk.ticket')
    sale_order_id = fields.Many2one('sale.order', string='Sales Order',
        domain="[('order_line.product_id.type', '!=', 'service'), ('picking_ids.state', '=', 'done'), ('id', 'in', suitable_sale_order_ids)]",
        compute='_compute_sale_order_id', readonly=False)
    picking_id = fields.Many2one('stock.picking', string='Delivery to Return', domain="[('id', 'in', suitable_picking_ids)]", compute='_compute_picking_id', precompute=True, readonly=False, store=True)
    suitable_picking_ids = fields.Many2many('stock.picking', compute='_compute_suitable_picking_ids')
    suitable_sale_order_ids = fields.Many2many('sale.order', compute='_compute_suitable_sale_orders')

    @api.depends('picking_id')
    def _compute_sale_order_id(self):
        for r in self:
            r.sale_order_id = r.picking_id.sale_id

    @api.depends('sale_order_id')
    def _compute_picking_id(self):
        for r in self:
            if not r.picking_id:
                domain = [
                    ('state', '=', 'done'),
                    ('partner_id.commercial_partner_id', '=', r.ticket_id.partner_id.commercial_partner_id.id),
                ]
                picking = self.env['stock.picking'].search(domain, limit=1, order='id desc')
                if picking:
                    r.picking_id = picking
            if r.sale_order_id:
                picking = r.sale_order_id.picking_ids.filtered(lambda p: p.id in r.suitable_picking_ids.ids) \
                    if r.sale_order_id.picking_ids \
                    else False
                if outgoing_picking := picking.filtered(lambda p: p.picking_type_code == 'outgoing'):
                    r.picking_id = outgoing_picking[0]
                else:
                    r.picking_id = picking[0] if picking else False

    @api.depends('ticket_id.partner_id.commercial_partner_id', 'sale_order_id')
    def _compute_suitable_picking_ids(self):
        for r in self:
            if not r.ticket_id and not r.sale_order_id:
                r.suitable_picking_ids = False
                continue

            domain = [('state', '=', 'done'), ('picking_type_id.code', '!=', 'incoming')]
            if r.sale_order_id:
                domain += [('id', 'in', r.sale_order_id.picking_ids._origin.ids)]
            elif r.partner_id:
                domain += [('partner_id', 'child_of', r.partner_id.commercial_partner_id._origin.id)]
            r.suitable_picking_ids = self.env['stock.picking'].with_context(active_test=False).search(domain)

    @api.depends('ticket_id.partner_id.commercial_partner_id')
    def _compute_suitable_sale_orders(self):
        for r in self:
            if not r.ticket_id:
                r.suitable_sale_order_ids = False
                continue
            domain = [('state', '=', 'sale')]
            if r.ticket_id.partner_id:
                domain += [
                    '|',
                        ('partner_id.commercial_partner_id', '=', r.ticket_id.partner_id.commercial_partner_id.id),
                        ('partner_shipping_id.commercial_partner_id', '=', r.ticket_id.partner_id.commercial_partner_id.id),
                ]
            r.suitable_sale_order_ids = self.env['sale.order'].search(domain)

    def action_return_picking(self):
        if self.picking_id:
            new_picking = self.picking_id._create_return()
        else:
            new_picking = self.picking_id._create_empty_picking()

        self.ticket_id.picking_ids |= new_picking

        return {
            'name': self.env._('Returned Picking'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': new_picking.id,
            'view_mode': 'form',
            'context': self.env.context,
        }
