from odoo import api, fields, models
from odoo.exceptions import UserError


class StockLot(models.Model):
    _inherit = 'stock.lot'

    slot_ids = fields.Many2many('planning.slot', string='Shifts')
    slots_count = fields.Integer(compute='_compute_slots_count', export_string_translation=False)
    is_equipment_enabled = fields.Boolean(compute='_compute_is_equipment_enabled', export_string_translation=False)
    delivery_date = fields.Datetime(string='Delivery Date', compute='_compute_delivery_date', inverse='_inverse_delivery_date')
    is_delivery_date_visible = fields.Boolean(compute='_compute_is_delivery_date_visible', export_string_translation=False)

    @api.depends('is_equipment_enabled', 'partner_ids')
    def _compute_is_delivery_date_visible(self):
        for lot in self:
            lot.is_delivery_date_visible = lot.is_equipment_enabled and len(lot._origin.sudo().partner_ids) == 1

    def _get_customer_quantities_by_lot(self):
        """ Quantities of each lot that reached a customer and that returned back in the product's unit.
            :return: a `{lot: (delivered quantity, returned quantity)}` mapping
        """
        lots = self._origin
        if not lots:
            return {}

        def quantities(usage_field):
            return dict(self.env['stock.move.line'].sudo()._read_group(
                [
                    ('lot_id', 'in', lots.ids),
                    ('state', '=', 'done'),
                    (usage_field, '=', 'customer'),
                ],
                groupby=['lot_id'],
                aggregates=['quantity_product_uom:sum'],
            ))

        delivered = quantities('location_dest_id.usage')
        returned = quantities('location_id.usage')
        return {lot: (delivered.get(lot, 0.0), returned.get(lot, 0.0)) for lot in lots}

    def _get_last_delivery(self):
        self.ensure_one()
        return self._origin.delivery_ids.filtered(
            lambda d: d.state == 'done' and d.date_done and d.location_dest_id.usage == 'customer'
        ).sorted('date_done')[-1:]

    @api.depends('delivery_ids')
    def _compute_delivery_date(self):
        quantities_by_lot = self._get_customer_quantities_by_lot()
        for lot in self:
            delivery_date = lot.sudo()._get_last_delivery().date_done
            delivered_qty, returned_qty = quantities_by_lot.get(lot._origin, (0.0, 0.0))

            if delivered_qty and lot.product_id.uom_id.compare(returned_qty, delivered_qty) >= 0:
                delivery_date = False

            lot.delivery_date = delivery_date

    def _inverse_delivery_date(self):
        for lot in self:
            delivery = lot._get_last_delivery()
            if not delivery:
                raise UserError(self.env._(
                    "%(lot)s has not been delivered to a customer yet, its delivery date cannot be set.",
                    lot=lot.display_name,
                ))
            if not lot.delivery_date:
                raise UserError(self.env._(
                    "The delivery date of %(lot)s is the date of transfer %(transfer)s, it cannot be emptied.",
                    lot=lot.display_name, transfer=delivery.name,
                ))
            delivery.date_done = lot.delivery_date

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # prevent creating a lot with an empty delivery date,
            # as it would be inconsistent with the delivery date computed from the last delivery
            if 'delivery_date' in vals and not vals['delivery_date']:
                del vals['delivery_date']
        return super().create(vals_list)

    @api.depends_context('uid')
    @api.depends('slot_ids', 'partner_ids')
    def _compute_is_equipment_enabled(self):
        is_equipment_enabled = self.env.user.has_group('planning.group_field_service_allow_equipment')
        for lot in self:
            lot.is_equipment_enabled = is_equipment_enabled

    @api.depends('slot_ids')
    def _compute_slots_count(self):
        for lot in self:
            lot.slots_count = len(lot.slot_ids)

    def action_view_slots(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('planning.planning_action_schedule_by_resource')
        action.update({
            'display_name': self.env._('Shifts'),
            'views': [(False, 'list'), (False, 'kanban'), (False, 'calendar'), (False, 'gantt'), (False, 'form')],
            'domain': [('id', 'in', self.slot_ids.ids)],
            'context': {'default_partner_id': self.partner_ids[:1].id},
        })
        if self.slots_count == 1:
            action['views'] = [(self.env.ref('planning.planning_view_form').id, 'form')]
            action['res_id'] = self.slot_ids[0].id
        return action
