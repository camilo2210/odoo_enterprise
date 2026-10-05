# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.fields import Domain
from odoo.tools import float_utils, LazyTranslate, DEFAULT_SERVER_DATETIME_FORMAT

_lt = LazyTranslate(__name__)


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def _domain_sale_line_id(self):
        return Domain.AND([
            self.env['sale.order.line']._sellable_lines_domain(),
            self.env['sale.order.line']._domain_sale_line_service(),
        ])

    sale_line_id = fields.Many2one('sale.order.line', string='Sales Order Item',
        domain=lambda self: str(self._domain_sale_line_id()),
        index=True, ondelete='cascade', group_expand='_group_expand_sale_line_id',
        falsy_value_label=_lt('Non-Billable'),
        help="Sales order item for which this shift will be performed. When sales orders are automatically planned,"
             " the remaining hours of the sales order item, as well as the role defined on the service, are taken into account.")
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', related='sale_line_id.order_id', store=True, index=True, falsy_value_label=_lt('Non-Billable'))
    sale_order_state = fields.Selection(string="Sales Order State", related='sale_order_id.state')
    partner_id = fields.Many2one('res.partner', compute='_compute_partner_id', search='_search_partner_id')
    role_product_ids = fields.One2many('product.template', related='role_id.product_ids', export_string_translation=False)
    sale_line_plannable = fields.Boolean(related='sale_line_id.product_id.planning_enabled', export_string_translation=False)
    allocated_hours = fields.Float(compute_sudo=True)
    role_ids = fields.Many2many('planning.role', string="Roles", search="_search_role_ids", store=False)

    @api.depends('sale_line_id')
    def _compute_role_id(self):
        slot_with_sol = self.filtered('sale_line_plannable')
        for slot in slot_with_sol:
            if not slot.role_id:
                slot.role_id = slot.sale_line_id.product_id.planning_role_id
        super(PlanningSlot, self - slot_with_sol)._compute_role_id()

    @api.depends('start_datetime', 'sale_line_id.planning_hours_to_plan', 'sale_line_id.planning_hours_planned')
    def _compute_allocated_hours(self):
        planned_slots = self.filtered('start_datetime')
        unplanned_slots = self - planned_slots
        if self.env.context.get('sale_planning_prevent_recompute'):
            self.env.remove_to_compute(self._fields['allocated_percentage'], unplanned_slots)
        else:
            for slot in unplanned_slots:
                if slot.sale_line_plannable:
                    slot.allocated_hours = max(
                        slot.sale_line_id.planning_hours_to_plan - slot.sale_line_id.planning_hours_planned,
                        0.0
                    )
        super(PlanningSlot, planned_slots)._compute_allocated_hours()
        if planned_slots:
            self.env.add_to_compute(
                self.env['sale.order.line']._fields['planning_hours_planned'],
                self.sale_line_id
            )

    def _compute_allocated_percentage(self):
        planned_slots = self.filtered('start_datetime')
        super(PlanningSlot, planned_slots)._compute_allocated_percentage()

    @api.depends('start_datetime')
    def _compute_past_shift(self):
        planned_slots = self.filtered('start_datetime')
        (self - planned_slots).is_past = False
        super(PlanningSlot, planned_slots)._compute_past_shift()

    @api.depends('start_datetime')
    def _compute_unassign_deadline(self):
        planned_slots = self.filtered('start_datetime')
        (self - planned_slots).unassign_deadline = False
        super(PlanningSlot, planned_slots)._compute_unassign_deadline()

    @api.depends('start_datetime')
    def _compute_is_unassign_deadline_passed(self):
        planned_slots = self.filtered('start_datetime')
        (self - planned_slots).is_unassign_deadline_passed = False
        super(PlanningSlot, planned_slots)._compute_is_unassign_deadline_passed()

    @api.depends('start_datetime')
    def _compute_template_autocomplete_ids(self):
        planned_slots = self.filtered('start_datetime')
        (self - planned_slots).template_autocomplete_ids = self.template_id
        super(PlanningSlot, planned_slots)._compute_template_autocomplete_ids()

    def _search_role_ids(self, operator, value):
        return [('role_id', operator, value)]

    @api.depends('sale_order_id.partner_id')
    def _compute_partner_id(self):
        for slot in self:
            slot.partner_id = slot.sale_order_id.partner_id or slot.partner_id

    def _search_partner_id(self, operator, value):
        if self._fields['partner_id'].store:  # when field service is installed this search method is no longer needed
            return [('partner_id', operator, value)]
        if isinstance(value, (list, tuple)):
            value_is_null = any(val is False or val is None for val in value)
        else:
            value_is_null = value is False or value is None
        can_be_null = (  # (..., '=', False) or (..., 'not in', [truthy vals])
            (operator not in Domain.NEGATIVE_OPERATORS) == value_is_null
        )
        if operator in Domain.NEGATIVE_OPERATORS and not value_is_null:
            # we have a condition like 'not in' ['a']
            # let's call back with a positive operator
            return NotImplemented
        domain = Domain([('sale_order_id', 'any', [('partner_id', operator, value)])])
        if can_be_null:
            domain |= Domain('sale_order_id', '=', False)
        return domain

    def _group_expand_sale_line_id(self, sale_lines, domain):
        dom_tuples = [(dom[0], dom[1]) for dom in domain if isinstance(dom, (list, tuple)) and len(dom) == 3]
        sale_line_ids = self.env.context.get('filter_sale_line_ids', False)
        if sale_line_ids:
            # search method is used rather than browse since the order needs to be handled
            return sale_lines.search([('id', 'in', sale_line_ids)])
        elif self.env.context.get('planning_expand_sale_line_id') and ('start_datetime', '<=') in dom_tuples and ('end_datetime', '>=') in dom_tuples:
            if ('sale_line_id', '=') in dom_tuples or ('sale_line_id', 'ilike') in dom_tuples:
                filter_domain = self._expand_domain_m2o_groupby(domain, 'sale_line_id')
                return sale_lines.search(filter_domain)
            filters = self._expand_domain_dates(domain)
            sale_lines = self.env['planning.slot'].search(filters).mapped('sale_line_id')
            return sale_lines.search([('id', 'in', sale_lines.ids)])
        return sale_lines

    def action_plan_shift(self):
        action = super().action_plan_shift()
        if self.sale_line_id:
            action["context"]["default_sale_line_id"] = self.sale_line_id.id
        return action

    # -----------------------------------------------------------------
    # ORM Override
    # -----------------------------------------------------------------

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if res.get('sale_line_id'):
            sale_line_id = self.env['sale.order.line'].browse(res.get('sale_line_id'))
            if sale_line_id.product_id.planning_enabled and res.get('start_datetime') and res.get('end_datetime'):
                remaining_hours_to_plan = sale_line_id.planning_hours_to_plan - sale_line_id.planning_hours_planned
                if float_utils.float_compare(remaining_hours_to_plan, 0, precision_digits=2) < 1:
                    return res
                allocated_hours = (res['end_datetime'] - res['start_datetime']).total_seconds() / 3600.0
                if float_utils.float_compare(remaining_hours_to_plan, allocated_hours, precision_digits=2) < 1:
                    res['end_datetime'] = res['start_datetime'] + timedelta(hours=remaining_hours_to_plan)
        return res

    def _display_name_fields(self):
        """ List of fields that can be displayed in the display_name """
        return ['partner_id'] + super()._display_name_fields()

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if res.sale_line_id:
            res.sale_line_id.sudo()._compute_planning_hours_planned()  # ensure it is computed before doing postprocess
            res.sale_line_id.sudo()._post_process_planning_sale_line()
        return res

    def write(self, vals):
        res = super().write(vals)
        self.exists().sale_line_id.sudo()._post_process_planning_sale_line()
        return res

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------

    def action_view_sale_order(self):
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
        action['views'] = [(False, 'form')]
        action['res_id'] = self.sale_order_id.id
        return action

    # -----------------------------------------------------------------
    # Business methods
    # -----------------------------------------------------------------

    def _get_domain_template_slots(self):
        domain = super()._get_domain_template_slots()
        if self.sale_line_plannable:
            domain = Domain.AND([domain, ['|', ('role_id', '=', self.sale_line_id.product_id.planning_role_id.id), ('role_id', '=', False)]])
        return domain

    def _get_slot_to_allocate_value(self):
        self.ensure_one()
        if self.sale_line_plannable:
            return self.sale_line_id.planning_hours_to_plan - self.sale_line_id.planning_hours_planned
        return super()._get_slot_to_allocate_value()

    def _get_unplanned_slot_values(self):
        return {
            **super()._get_unplanned_slot_values(),
            'sale_line_id': self.sale_line_id.id,
        }

    def _get_ics_description_data(self):
        return {
            **super()._get_ics_description_data(),
            'sale_order': self.sale_line_id.sudo().order_id.name if self.sale_line_id else '',
            'sale_order_item': self.sale_line_id.sudo().name if self.sale_line_id else '',
            'partner': self.partner_id.name,
        }

    # -------------------------------------------
    # Slots Assignation
    # -------------------------------------------

    @api.model
    def _get_employee_to_assign_priority_list(self):
        return ['previous_slot', 'closest_so_line_slot', 'default_role', 'roles']

    def _get_employee_per_priority(self, priority, employee_ids_to_exclude, cache):
        """
            This method returns the id of an employee filling the priority criterias and
            not present in the employee_ids_to_exclude.
        """
        if priority in cache:
            return cache[priority].pop(0) if cache.get(priority) else None
        if priority == 'previous_slot':
            search = self._read_group([
                ('sale_line_id', '=', self.sale_line_id.id),
                ('resource_ids.resource_type', '=', 'user'),
                ('start_datetime', '!=', False),
                ('employee_ids', 'not in', employee_ids_to_exclude),
            ], ['resource_ids'], order='end_datetime:max desc, resource_ids')
            cache[priority] = [resource.employee_id.id for [resource] in search]
        elif priority == 'closest_so_line_slot':
            closest_slots = self.search([
                ('sale_line_id.product_id', '=', self.sale_line_id.product_id.id),
                ('sale_line_id.order_id.partner_id', '=', self.sale_line_id.order_id.partner_id.id),
                ('resource_ids.resource_type', '=', 'user'),
                ('start_datetime', '!=', False),
                ('employee_ids', 'not in', employee_ids_to_exclude),
            ])
            now = fields.Datetime.now()
            closest_slots = closest_slots.sorted(key=lambda s: abs(s.end_datetime - now))
            cache[priority] = closest_slots.employee_ids.ids
        elif priority == 'default_role':
            search = self.env['hr.employee'].sudo().search([
                ('default_planning_role_id', '=', self.role_id.id),
                ('id', 'not in', employee_ids_to_exclude),
            ])
            cache[priority] = search.ids
        elif priority == 'roles':
            domain = Domain([
                ('planning_role_ids', '!=', False),
                ('id', 'not in', employee_ids_to_exclude),
            ])
            if self.role_id.resource_ids:
                domain &= Domain('planning_role_ids', '=', self.role_id.id)
            search = self.env['hr.employee'].search(domain)
            cache[priority] = search.ids
        return cache[priority].pop(0) if cache.get(priority) else None

    def _get_employee_to_assign(self, default_priority, employee_ids_to_exclude, cache, employee_per_sol):
        """
            Returns the id of the employee to assign and its corresponding priority
        """
        self.ensure_one()
        if self.sale_line_id.id in employee_per_sol:
            employee_id = next(
                (employee_id
                 for employee_id in employee_per_sol[self.sale_line_id.id]
                 if employee_id not in employee_ids_to_exclude),
                None
            )
            return employee_id, default_priority
        # This method is written to be overridden, so as every module can keep the priority ordered as its required.
        priority_list = self._get_employee_to_assign_priority_list()
        for priority in priority_list:
            if not default_priority or priority == default_priority:
                # if default_priority is given, the search only starts with this priority.
                default_priority = None
                employee_id = self._get_employee_per_priority(priority, employee_ids_to_exclude, cache)
                if employee_id:
                    return employee_id, priority
        return None, None

    @api.model
    def _get_ordered_slots_to_assign(self, domain):
        """
            Returns an ordered list of slots (linked to sol) to plan while using the action_plan_sale_order.

            This method is meant to be easily overriden.
        """
        return self.search(domain, order='sale_line_id desc')

    @api.model
    def _get_employee_per_sol_within_period(self, slots, start, end):
        """ Gets the employees already assigned during this period.

            :returns: a dict with key : SOL id, and values : a list of employee ids
        """
        assert start and end
        if isinstance(end, str):
            end = datetime.strptime(end, DEFAULT_SERVER_DATETIME_FORMAT)

        employee_per_sol = self.env['planning.slot']._read_group([
            ('sale_line_id', 'in', slots.sale_line_id.ids),
            ('start_datetime', '<', end),
            ('end_datetime', '>', start),
            ('resource_ids.resource_type', '=', 'user'),
        ], ['sale_line_id'], ['id:recordset'])

        return {
            sale_line.id: slots.employee_ids.ids
            for sale_line, slots in employee_per_sol
        }

    def _get_shifts_to_plan_domain(self, view_domain=None):
        if view_domain:
            domain = Domain(view_domain).map_conditions(
                lambda cond: Domain(cond.field_expr, '=', False)
                if cond.field_expr in ('start_datetime', 'end_datetime')
                else cond
            )
        else:
            domain = Domain('start_datetime', '=', False)
        domain &= Domain('sale_line_id', '!=', False)
        if self.env.context.get('planning_gantt_active_sale_order_id'):
            domain &= Domain('sale_order_id', '=', self.env.context.get('planning_gantt_active_sale_order_id'))
        return domain

    def auto_plan_id(self):
        self.ensure_one()
        if self.sale_order_id.state == 'cancel':
            return self._get_notification_action("danger", _("You are attempting to create a slot for a cancelled sales order."))
        return super().auto_plan_id()

    @api.model
    def auto_plan_ids(self, view_domain):
        res = super().auto_plan_ids(view_domain)
        if self.env.context.get('planning_slot_id'):
            # It means we are looking to assign one shift in particular to an available resource, which we do in planning.
            res["sale_line_planned"] = []
            return res
        slots_to_assign = self._get_ordered_slots_to_assign(self._get_shifts_to_plan_domain(view_domain))
        start_datetime = max(datetime.strptime(self.env.context.get('default_start_datetime'), DEFAULT_SERVER_DATETIME_FORMAT), fields.Datetime.now())
        employee_per_sol = self._get_employee_per_sol_within_period(slots_to_assign, start_datetime, self.env.context.get('default_end_datetime'))
        PlanningShift = self.env['planning.slot']
        slots_assigned = PlanningShift
        employee_ids_to_exclude = []

        for slot in slots_to_assign:
            slot_assigned = PlanningShift
            previous_priority = None
            cache = {}
            while not slot_assigned:
                # Retrieve an employee_id that may be assigned to this slot, excluding the ones who have no time left.
                # The previous priority is given in order to get the second employee that respects the previous criterias
                employee_id, previous_priority = slot._get_employee_to_assign(previous_priority, employee_ids_to_exclude, cache, employee_per_sol)
                if not employee_id:
                    break
                # The browse is mandatory to access the resource calendar
                employee = self.env['hr.employee'].browse(employee_id)
                vals = {
                    'start_datetime': start_datetime,
                    'end_datetime': start_datetime + timedelta(days=1),
                    'resource_ids': employee.resource_id.ids
                }
                # With the context keys, the maximal date to assign the slot will be self.env.context.get('default_end_datetime')
                slot_assigned = PlanningShift.browse(slot.assign_slot(vals).get('slots_assigned_ids'))
                if not slot_assigned:
                    # if no slot was generated (it uses the write method), then the employee_id is excluded from the employees assignable on this slot.
                    employee_ids_to_exclude.append(employee_id)
            slots_assigned += slot_assigned

        res["sale_line_planned"] = slots_assigned.ids
        return res

    @api.model
    def action_rollback_auto_plan_ids(self, shifts_data):
        self.browse(shifts_data["sale_line_planned"]).action_unschedule()
        super().action_rollback_auto_plan_ids(shifts_data)

    # -------------------------------------------
    # Copy slots
    # -------------------------------------------

    def _init_remaining_hours_to_plan(self, remaining_hours_to_plan):
        """
            Fills the remaining_hours_to_plan dict for a given slot and returns wether
            there are enough remaining hours.

            :return a bool representing wether or not there are still hours remaining
        """
        self.ensure_one()
        res = super()._init_remaining_hours_to_plan(remaining_hours_to_plan)
        if self.sale_line_id.product_id.planning_enabled:
            # if the slot is linked to a slot, we only need to allocate the remaining hours to plan
            # we keep track of those hours in a dict and decrease it each time we create a slot.
            if self.sale_line_id not in remaining_hours_to_plan:
                self.sale_line_id._compute_planning_hours_planned()
                remaining_hours_to_plan[self.sale_line_id] = self.sale_line_id.planning_hours_to_plan - self.sale_line_id.planning_hours_planned
            if float_utils.float_compare(remaining_hours_to_plan[self.sale_line_id], 0.0, precision_digits=2) != 1:
                return False  # nothing left to allocate.
        return res

    def _update_remaining_hours_to_plan_and_values(self, remaining_hours_to_plan, values):
        """
            Update the remaining_hours_to_plan with the allocated hours of the slot in `values`
            and returns wether there are enough remaining hours.

            If remaining_hours is strictly positive, and the allocated hours of the slot in `values` is
            higher than remaining hours, than update the values in order to consume at most the
            number of remaining_hours still available.

            :return a bool representing wether or not there are still hours remaining
        """
        if self.allocated_percentage and self.sale_line_id.product_id.planning_enabled:
            if float_utils.float_compare(remaining_hours_to_plan[self.sale_line_id], 0.0, precision_digits=2) != 1:
                return False
            # The allocated hours of the slot can be computed as for a slot with allocation_type == 'planning'
            # since it is build from an employee work interval, thus will last less than 24hours.
            allocated_hours = (values['end_datetime'] - values['start_datetime']).total_seconds() / 3600
            # Allocated_hours is discounted from remaining hours with a maximum of : remaining_hours
            # So, the difference between the two values must be checked, if remaining_hours is less than the
            # allocated hours, than update the end_datetime.
            ratio = self.allocated_percentage / 100.00
            remaining_hours = min(remaining_hours_to_plan[self.sale_line_id] / ratio, allocated_hours)
            values['end_datetime'] = values['start_datetime'] + timedelta(hours=remaining_hours)
            values.pop('allocated_hours', None) # we want that to be computed again.
            remaining_hours_to_plan[self.sale_line_id] -= remaining_hours * ratio
        return True

    def action_unschedule(self):
        unfinished_slots = self.filtered(
            lambda slot:
                slot.sale_line_id.product_id.planning_enabled
                and (slot.sale_line_id.planning_hours_to_plan - slot.sale_line_id.planning_hours_planned > 0.0)
        )
        if unfinished_slots:
            unscheduled_slots = unfinished_slots.search([
                ('id', 'not in', unfinished_slots.ids),
                ('sale_line_id', 'in', unfinished_slots.sale_line_id.ids),
                ('start_datetime', '=', False),
            ])
            slots_to_unlink = self.env["planning.slot"]
            for slot in unscheduled_slots:
                slots_to_unlink += unfinished_slots.filtered(lambda shift: shift != slot and shift.sale_line_id == slot.sale_line_id)
            self = self - slots_to_unlink
            slots_to_unlink.unlink()
            if len(self) == 1:
                return {'type': 'ir.actions.act_window_close'}
        return super().action_unschedule()

    # -----------------------------------
    # Gantt Progress Bar
    # -----------------------------------
    def _gantt_progress_bar_sale_line_id(self, res_ids):
        if not self.env['sale.order.line'].has_access('read'):
            return {}
        return {
            sol.id: {
                'value': sol.planning_hours_planned,
                'max_value': sol.planning_hours_to_plan,
            }
            for sol in self.env['sale.order.line'].search([('id', 'in', res_ids)])
        }

    def _gantt_progress_bar(self, field, res_ids, start, stop):
        if field == 'sale_line_id':
            return dict(
                self._gantt_progress_bar_sale_line_id(res_ids),
                warning=_("This Sale Order Item doesn't have a target value of planned hours.")
            )
        return super()._gantt_progress_bar(field, res_ids, start, stop)

    def _prepare_shift_vals(self):
        return {
            **super()._prepare_shift_vals(),
            'sale_line_id': self.sale_line_id.id,
        }

    def _gantt_progress_bar_group_by_field(self, res_ids, start, stop, group_by_field):
        results = super()._gantt_progress_bar_group_by_field(res_ids, start, stop, group_by_field)
        if group_by_field != 'resource_ids':
            return results

        resource_per_id = {r.id: r for r in self.env['resource.resource'].browse(list(results.keys()))}
        for key, val in results.items():
            resource = resource_per_id[key]
            val['role_ids'] = resource.role_ids.ids
        return results

    def _print_planning_get_fields_to_copy(self):
        return super()._print_planning_get_fields_to_copy() + ['sale_line_id']

    def _print_planning_get_slot_title(self, slot_start, slot_end, tz_info, group_by):
        res = super()._print_planning_get_slot_title(slot_start, slot_end, tz_info, group_by)

        if group_by != 'sale_line_id' and self.sale_line_id:
            res += ' - ' + self.sale_line_id.display_name

        return res
