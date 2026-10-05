# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup
from odoo import api, fields, models
from odoo.fields import Domain


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    ticket_id = fields.Many2one('helpdesk.ticket', string='Helpdesk Ticket', copy=False, index='btree_not_null')
    ticket_visibility = fields.Selection(related='ticket_id.team_id.privacy_visibility', export_string_translation=False)
    is_replacement = fields.Boolean(default=False, export_string_translation=False)

    def _compute_state(self):
        # Since `state` is a computed field, it does not go through the `write` function we usually use to track
        # those changes.
        previous_states = {picking: picking.state for picking in self}
        res = super()._compute_state()
        tracked_pickings = self.filtered(lambda m: m.state in ('done', 'cancel') and\
            m.state != previous_states[m])
        ticket_ids = self.env['helpdesk.ticket'].sudo().search([
            ('use_product_returns', '=', True), ('picking_ids', 'in', tracked_pickings.ids)])
        if ticket_ids:
            mapped_data = dict()
            for ticket in ticket_ids:
                if return_ids := ticket.picking_ids.filtered(lambda p: not p.is_replacement):
                    mapped_data[ticket] = (return_ids & self)
            for ticket, pickings in mapped_data.items():
                if not pickings:
                    continue
                subtype = self.env.ref('helpdesk.mt_ticket_return_status', raise_if_not_found=False)
                if not subtype:
                    continue
                state_desc = dict(self._fields['state']._description_selection(self.env))[pickings[0].state].lower()
                body = Markup('<br/>').join(
                    picking._get_html_link() + self.env._(' Return %(status)s', status=state_desc)
                    for picking in pickings
                )
                ticket.message_post(subtype_id=subtype.id, body=body)

        replacement_ticket_ids = self.env['helpdesk.ticket'].sudo().search([
            ('use_product_replacements', '=', True), ('picking_ids', 'in', tracked_pickings.ids)
        ])
        if replacement_ticket_ids:
            mapped_data = dict()
            for ticket in replacement_ticket_ids:
                if replacement_ids := ticket.picking_ids.filtered(lambda p: p.is_replacement):
                    mapped_data[ticket] = (replacement_ids & self)
            for ticket, replacements in mapped_data.items():
                if not replacements:
                    continue
                subtype = self.env.ref('helpdesk.mt_ticket_delivery_status', raise_if_not_found=False)
                if not subtype:
                    continue
                state_desc = dict(self._fields['state']._description_selection(self.env))[replacements[0].state].lower()
                body = Markup('<br/>').join(
                    replacement._get_html_link() + self.env._(' Delivery %(status)s', status=state_desc)
                    for replacement in replacements
                )
                ticket.message_post(subtype_id=subtype.id, body=body)

        return res

    def _create_empty_picking(self):
        picking_default_vals = {
            'move_ids': [],
            'state': 'draft',
            'return_id': False,
        }
        if self.env.context.get('default_ticket_id'):
            ticket_id = self.env['helpdesk.ticket'].browse(self.env.context['default_ticket_id'])
            # Take return picking type of outgoing type if found, else take the incoming type
            domain = Domain('company_id', '=', ticket_id.company_id.id)
            if ticket_id.sale_order_id:
                domain = Domain.AND([
                    domain,
                    [('warehouse_id', 'in', ticket_id.sale_order_id.warehouse_id.id)]
                ])

            picking_type = self.env['stock.picking.type'].search([
                Domain.AND([
                    domain,
                    [('code', '=', 'outgoing')],
                ])
            ], limit=1).return_picking_type_id

            if not picking_type:
                picking_type = self.env['stock.picking.type'].search([
                    Domain.AND([
                        domain,
                        [('code', '=', 'incoming')],
                    ])
                ], limit=1)

            picking_default_vals['origin'] = self.env._('Ticket: %(ticket_name)s', ticket_name=ticket_id.name)
            picking_default_vals['partner_id'] = ticket_id.partner_id.address_get(['delivery'])['delivery']
            picking_default_vals['ticket_id'] = ticket_id.id
            picking_default_vals['picking_type_id'] = picking_type.id

        new_picking = self.create(picking_default_vals)
        return new_picking

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        if self.env.context.get('replacement_create_trigger'):
            for picking in pickings:
                if not picking.ticket_id:
                    continue

                picking.ticket_id.picking_ids |= picking
                picking.message_post_with_source(
                    'helpdesk_stock.replacement_creation_picking',
                    render_values={'record': picking.ticket_id, 'message': self.env._('This transfer was created from the ticket')},
                    subtype_xmlid='mail.mt_note',
                )
                picking.ticket_id.message_post_with_source(
                    'helpdesk_stock.replacement_creation_ticket',
                    render_values={'created_record': picking, 'message': self.env._('Delivery created')},
                    subtype_xmlid='mail.mt_note',
                )
        return pickings

    def action_linked_ticket(self):
        """ Open the linked helpdesk ticket from the stock picking form view. """
        return {
            'type': 'ir.actions.act_window',
            'name': self.ticket_id.name,
            'res_model': 'helpdesk.ticket',
            'res_id': self.ticket_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
