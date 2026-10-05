import datetime
from ast import literal_eval
from collections import defaultdict
from random import shuffle

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.intervals import Intervals


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    role_sync_shift_rental = fields.Boolean(related='role_id.sync_shift_rental')

    def write(self, vals):
        res = super().write(vals)
        if (
            not self.env.context.get('rental_order_updated')
            and any(vals.get(k) for k in ['start_datetime', 'end_datetime'])
            and (rental_slots := self.exists().filtered('role_sync_shift_rental'))
        ):
            if rental_slots.filtered('overlap_slot_count'):
                raise ValidationError(self.env._('Shift not rescheduled due to conflicts'))
            rental_orders = rental_slots.sale_order_id.filtered('is_rental_order')
            if not rental_orders:
                return res
            order_vals = dict()
            if start_datetime := vals.get('start_datetime'):
                order_vals['rental_start_date'] = start_datetime
            if end_datetime := vals.get('end_datetime'):
                order_vals['rental_return_date'] = end_datetime
            update_sale_orders = rental_orders.filtered(lambda so:
                start_datetime and so.rental_start_date != start_datetime
                or end_datetime and so.rental_return_date != end_datetime
            )
            if update_sale_orders:
                update_sale_orders.write(order_vals)
                SaleOrderLine = self.env['sale.order.line']
                self.env.add_to_compute(
                    SaleOrderLine._fields['name'],
                    update_sale_orders.order_line.filtered('is_rental')
                )
        return res

    @api.ondelete(at_uninstall=False)
    def _update_order_line_count(self):
        for line, slots in self.grouped('sale_line_id').items():
            if line:
                line.update_product_uom_qty(line.planning_slot_ids - slots)

    def action_create_order(self):
        self.ensure_one()
        if self.overlap_slot_count:
            raise ValidationError(self.env._('Impossible to generate a rental order for a shift in conflict.'))
        action = self.env['ir.actions.actions']._for_xml_id('sale_renting.rental_order_action')
        context = literal_eval(action.get('context', '{}'))
        context.update(
            default_rental_start_date=self.start_datetime,
            default_rental_return_date=self.end_datetime,
        )
        if products := self.role_id.product_ids.filtered('rent_periodicity'):
            uom_hour = self.env.ref('uom.product_uom_hour')
            context['default_order_line'] = [
                Command.create({
                    'product_id': products[0].product_variant_id.id,
                    'product_uom_qty': self.allocated_hours if products[:1].uom_id == uom_hour else 1,
                    'planning_slot_ids': self.ids,
                }),
            ]
        context['new_sale_line'] = self.sale_line_id.id
        return {
            **action,
            'view_mode': 'form',
            'views': [(view_id, view_type) for view_id, view_type in action['views'] if view_type == 'form'],
            'target': 'current',
            'context': context,
        }

    def action_add_last_order(self):
        self.ensure_one()
        if self.overlap_slot_count:
            raise ValidationError(self.env._('The shift should not be in conflict to be able to correctly add it to an existing rental order.'))
        order = self.env['sale.order'].search([
            ('is_rental_order', '=', True),
            ('user_id', '=', self.env.uid),
            ('state', '=', 'sale'),
        ], limit=1)
        if not order:
            raise ValidationError(self.env._('No Rental Order is found.'))
        products = self.role_id.product_ids.filtered('rent_periodicity')
        for sol in order.order_line:
            if sol.product_template_id in products and sol.product_uom_id.is_zero(sol.planning_hours_to_plan):
                self.sale_line_id = sol
                break
        if self.role_sync_shift_rental:
            if order.rental_start_date != self.start_datetime or order.rental_return_date != self.end_datetime:
                try:
                    self.write({
                        'start_datetime': order.rental_start_date,
                        'end_datetime': order.rental_return_date,
                    })
                except ValidationError as err:
                    if self.env.context.get('is_rental_shift_new'):
                        self.unlink()
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'type': 'danger',
                                'message': str(err),
                            },
                        }
                    raise ValidationError(err)
        new_sale_line = False
        if not self.sale_line_id:
            sale_line = order.order_line.filtered(
                lambda l: l.is_rental and l.product_template_id in products
            )[:1]
            if sale_line:
                self.sale_line_id = sale_line
            else:
                uom_hour = self.env.ref('uom.product_uom_hour')
                product = products[:1]
                self.sale_line_id = self.env['sale.order.line'].with_context(planning_slot_generation=False).create({
                    'product_id': product.product_variant_id.id,
                    'product_uom_qty': self.allocated_hours if product.uom_id == uom_hour else 1,
                    'order_id': order.id,
                    'planning_slot_ids': self.ids,
                })
                new_sale_line = self.sale_line_id.id
        self.state = '2_published'
        if not self.resource_ids:
            self._set_slot_resource()
        self.sale_line_id.update_product_uom_qty(self.sale_line_id.planning_slot_ids)
        if not (order.rental_start_date == self.start_datetime and order.rental_return_date == self.end_datetime):
            min_start_datetime, max_end_datetime = self.env['planning.slot']._read_group(
                [('sale_order_id', '=', order.id)],
                [],
                ['start_datetime:min', 'end_datetime:max'],
            )[0]
            order.with_context(slots_rescheduled=True).write({'rental_start_date': min_start_datetime, 'rental_return_date': max_end_datetime})
            SaleOrderLine = self.env['sale.order.line']
            self.env.add_to_compute(
                SaleOrderLine._fields['name'],
                order.order_line.filtered('is_rental')
            )
        if not new_sale_line:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': self.env._('Shift added to last order'),
                },
            }
        else:
            action = self.env['ir.actions.actions']._for_xml_id('sale_renting.rental_order_action')
            context = literal_eval(action.get('context', '{}'))
            context['new_sale_line'] = new_sale_line
            return {
                **action,
                'view_mode': 'form',
                'views': [(view_id, view_type) for view_id, view_type in action['views'] if view_type == 'form'],
                'res_id': order.id,
                'target': 'current',
                'context': context,
            }

    def _set_slot_resource(self):
        # ensure role id is correctly set
        for slot in self:
            if not slot.role_id and slot.sale_line_id:
                slot.role_id = slot.sale_line_id.sudo().product_id.planning_role_id
        available_resources = self.role_id.resource_ids
        if not available_resources:
            return
        resources_per_role = dict(
            self.env['resource.resource']._read_group(
                [('role_ids', 'in', self.role_id.ids)],
                ['role_ids'],
                ['id:recordset'],
            )
        )

        def get_utc_timezone(utc_datetime):
            return utc_datetime.replace(tzinfo=datetime.UTC)

        min_start_datetime = min(self.mapped('start_datetime'))
        max_end_datetime = max(self.mapped('end_datetime'))
        slots_per_resource = self.env['planning.slot']._read_group([
            ('resource_ids', 'in', available_resources.ids),
            ('start_datetime', '<=', max_end_datetime),
            ('end_datetime', '>=', min_start_datetime),
        ], ['resource_ids'], ['id:recordset'])
        unavailable_intervals_per_resource = defaultdict(Intervals)
        for resource, slots in slots_per_resource:
            unavailable_intervals_per_resource[resource.id] |= Intervals([(get_utc_timezone(s.start_datetime), get_utc_timezone(s.end_datetime), s) for s in slots])
        work_intervals_per_resource, _dummy = available_resources._get_valid_work_intervals(get_utc_timezone(min_start_datetime), get_utc_timezone(max_end_datetime))
        problematic_shifts = self.env['planning.slot']
        for slot in self:
            slot_interval = Intervals([(get_utc_timezone(slot.start_datetime), get_utc_timezone(slot.end_datetime), slot)])
            resources = resources_per_role.get(slot.role_id, self.env['resource.resource'])
            shuffle(order := list(range(len(resources))))
            for i in order:
                resource = resources[i]
                work_intervals = work_intervals_per_resource[resource.id]
                unavailable_intervals = unavailable_intervals_per_resource.get(resource.id, Intervals())
                if not (unavailable_intervals & slot_interval) and (work_intervals & slot_interval):
                    slot.resource_ids = resource
                    unavailable_intervals_per_resource[resource.id] |= slot_interval
                    break

            if not slot.resource_ids:
                problematic_shifts += slot
        if problematic_shifts:
            raise ValidationError(
                self.env._(
                    "No resources are available for the shifts in: %s.",
                    ", ".join(problematic_shifts.sale_line_id.product_id.mapped('name'))
                )
            )
