# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    ticket_id = fields.Many2one('helpdesk.ticket', export_string_translation=False, index='btree_not_null')

    def write(self, vals):
        previous_states = None
        if 'state' in vals:
            previous_states = {repair: repair.state for repair in self}
        res = super().write(vals)
        if 'state' in vals:
            tracked_repairs = self.filtered(
                lambda r: r.ticket_id.use_product_repairs and r.state in ('done', 'cancel') and previous_states[r] != r.state)
            for repair in tracked_repairs:
                subtype = self.env.ref('helpdesk.mt_ticket_repair_status', raise_if_not_found=False)
                if not subtype:
                    continue
                state_desc = dict(self._fields['state']._description_selection(self.env))[repair.state].lower()
                body = repair._get_html_link() + f" {_('Repair')} {state_desc}"
                repair.ticket_id.sudo().message_post(subtype_id=subtype.id, body=body)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        message = _('Repair Created')
        subtype_id = self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note')
        for order in orders.filtered('ticket_id'):
            order.message_post_with_source(
                'helpdesk.ticket_creation',
                render_values={'self': order, 'ticket': order.ticket_id},
                subtype_id=subtype_id
            )
            order.ticket_id.message_post_with_source(
                'helpdesk.ticket_conversion_link',
                render_values={'created_record': order, 'message': message},
                subtype_id=subtype_id,
            )
        return orders

    def action_create_sale_order(self):
        """
        Prevent `default_user_id` from propagating when creating a quotation
        so the quotation's salesperson is taken from the customer, unless a
        valid Sales user is explicitly provided in the context.
        """
        context = dict(self.env.context)
        default_user_id = context.get('default_user_id')
        if (
            not default_user_id
            or not self.env['res.users'].browse(default_user_id).has_group('sales_team.group_sale_salesman')
        ):
            context.pop('default_user_id', None)
        return super(RepairOrder, self.with_context(context)).action_create_sale_order()
