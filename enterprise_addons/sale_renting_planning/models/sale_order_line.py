# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import UTC
from random import shuffle

from odoo import models
from odoo.exceptions import ValidationError
from odoo.tools import float_round


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _compute_product_updatable(self):
        super()._compute_product_updatable()
        if line := self.filtered(lambda line: self.env.context.get("new_sale_line") == line.id):
            line.product_updatable = True

    def _compute_planning_hours_to_plan(self):
        planning_rental_sols = self.filtered(
            lambda sol:
                sol.is_rental
                and sol.state not in ['draft', 'sent']
                and sol.product_id.planning_enabled
        )

        for line in planning_rental_sols:
            if line.planning_slot_ids.resource_ids.calendar_id:
                days_per_week = line.company_id.resource_calendar_id.get_work_duration_data(line.start_date, line.return_date)['days']
            else:
                days_per_week = line.order_id.duration_days + (1 if line.order_id.remaining_hours else 0)
            line.planning_hours_to_plan = line.company_id.resource_calendar_id.hours_per_day * days_per_week
        super(SaleOrderLine, self - planning_rental_sols)._compute_planning_hours_to_plan()

    def _is_planning_rental_service(self):
        self.ensure_one()
        return bool(
            self.is_rental
            and self.product_id.planning_enabled
            and self.product_id.planning_role_id
        )

    def _get_planning_resources_available(self):
        self.ensure_one()
        if not self._is_planning_rental_service():
            return self.env['resource.resource']
        available_resources = self.product_id.planning_role_id.resource_ids
        if not available_resources:
            return available_resources

        unavailable_resource_slots = self.env['planning.slot'].search([
            ('resource_ids', 'in', available_resources.ids),
            ('start_datetime', '<=', self.return_date),
            ('end_datetime', '>=', self.start_date),
            ('sale_line_id', '!=', self.id),
        ])
        resource_leaves = self.env['resource.calendar.leaves'].search([
            ('resource_id', 'in', available_resources.ids + [False]),
            ('date_from', '<=', self.return_date),
            ('date_to', '>=', self.start_date),
            ('company_id', '=', self.company_id.id),
        ])
        removed_calendar_ids = self.env['resource.calendar']
        unavailable_resources = unavailable_resource_slots.resource_ids
        for leave in resource_leaves:
            if leave.resource_id:
                unavailable_resources += leave.resource_id
            # if no resource_id then leave applies to all resources with the same calendar_id.
            elif leave.calendar_id:
                removed_calendar_ids += leave.calendar_id
            # if no calendar_id then leave applies to all resources.
            else:
                return self.env['resource.resource']
        available_resources = available_resources.filtered(
            lambda r: r not in unavailable_resources and r.calendar_id not in removed_calendar_ids
        )
        if not available_resources:
            return available_resources

        date_from = self.start_date.replace(tzinfo=UTC)
        date_to = self.return_date.replace(tzinfo=UTC)
        work_intervals_per_resource, _dummy = available_resources._get_valid_work_intervals(
            date_from, date_to, available_resources.calendar_id
        )
        return available_resources.filtered(
            lambda r: not r.calendar_id or work_intervals_per_resource[r.id]
        )

    def _planning_slot_vals_list_per_sol(self):
        vals_list_per_sol = super()._planning_slot_vals_list_per_sol()
        assigned_resource_ids = []
        problematic_services = []
        unit_uom = self.env.ref('uom.product_uom_unit')
        for sol, vals_list in vals_list_per_sol.items():
            if not sol._is_planning_rental_service():
                continue
            sync_shift_rental = sol.product_id.planning_role_id.sync_shift_rental
            available_resources = sol._get_planning_resources_available().filtered(
                lambda r: r.id not in assigned_resource_ids
            )
            if not available_resources and sync_shift_rental:
                problematic_services.append(sol.product_id.name)
                continue

            free_resource_ids = available_resources.ids
            flexible_resource_ids = available_resources.filtered(lambda r: not r.calendar_id).ids

            shuffle(free_resource_ids)

            # FIXME: check why it is needed
            if free_resource_ids and free_resource_ids[0] not in flexible_resource_ids:
                days_per_week = sol.company_id.resource_calendar_id.get_work_duration_data(sol.start_date, sol.return_date)['days']
                sol.planning_hours_to_plan = sol.company_id.resource_calendar_id.hours_per_day * days_per_week

            if free_resource_ids and len(vals_list) <= len(free_resource_ids):
                for index, vals in enumerate(vals_list):
                    resource_id = free_resource_ids[index]
                    vals['resource_ids'] = [resource_id]
                    assigned_resource_ids.append(resource_id)
                if sol.product_uom_id == unit_uom and sol.product_uom_id.compare(sol.product_uom_qty, 1) > 0:
                    nb_shifts_to_generate = int(float_round(sol.product_uom_qty, 0, rounding_method="UP"))
                    if len(free_resource_ids) >= nb_shifts_to_generate:
                        vals_list.extend([
                            {**sol._planning_slot_values(), 'resource_ids': [free_resource_ids[i]]}
                            for i in range(1, nb_shifts_to_generate)
                        ])
                    elif sync_shift_rental:
                        raise ValidationError(
                            self.env._(
                                "This Sales Order can't be confirmed. No enough resources are available for the shifts in: %(product_name)s.",
                                product_name=sol.product_id.name,
                            )
                        )
            elif sync_shift_rental:
                problematic_services.append(sol.product_id.name)
        if problematic_services:
            raise ValidationError(
                self.env._(
                    "This Sales Order can't be confirmed. No resources are available for the shifts in: %(problematic_services)s.",
                    problematic_services=problematic_services,
                )
            )
        return vals_list_per_sol

    def _planning_slot_values(self):
        vals = super()._planning_slot_values()
        if self.is_rental:
            vals.update(
                start_datetime=self.start_date,
                end_datetime=self.return_date,
                state='2_published',
            )
        return vals

    def write(self, vals):
        if 'product_uom_qty' in vals and (rental_sols := self.filtered(lambda sol: sol.is_rental and sol._should_generate_planning_slot())):
            new_qty = int(vals['product_uom_qty'])
            uom_hour = self.env.ref('uom.product_uom_hour')
            for sol in rental_sols:
                # ignore slot update for hours unless all slots are being unlinked
                if new_qty > 0 and sol.product_id.uom_id == uom_hour:
                    continue
                slots = sol.planning_slot_ids
                slot_count = len(slots)
                if new_qty < slot_count and not self.env.context.get("unlink_qty", False):
                    slots[new_qty:].unlink()
                elif new_qty > slot_count:
                    self.env['planning.slot'].create([{
                        'sale_line_id': sol.id,
                        'start_datetime': sol.start_date,
                        'end_datetime': sol.return_date,
                    } for _ in range(new_qty - slot_count)])._set_slot_resource()
        return super().write(vals)

    def unlink(self):
        rental_order_lines = self.filtered('is_rental')
        if slots := self.env['planning.slot'].search([('sale_line_id', 'in', rental_order_lines.ids)]):
            slots.unlink()
        return super().unlink()

    def update_product_uom_qty(self, planning_slots):
        self.ensure_one()
        if not self.order_is_rental:
            return
        uom_hour = self.env.ref('uom.product_uom_hour')
        new_qty = 0
        if self.product_uom_id == uom_hour:
            for slot in planning_slots:
                new_qty += slot.allocated_hours
        else:
            new_qty = len(planning_slots)

        if self.product_uom_qty != new_qty:
            self.with_context(unlink_qty=True).write({'product_uom_qty': new_qty})
