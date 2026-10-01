# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.fields import Domain


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    leave_warning = fields.Char(compute='_compute_leave_warning', compute_sudo=True, export_string_translation=False)
    is_absent = fields.Boolean(
        compute='_compute_leave_warning', search='_search_is_absent',
        compute_sudo=True, readonly=True, export_string_translation=False)

    @api.depends_context('lang')
    @api.depends('start_datetime', 'end_datetime', 'employee_ids')
    def _compute_leave_warning(self):

        assigned_slots = self.filtered(lambda s: s.employee_ids and s.start_datetime and s.state != '4_completed')
        (self - assigned_slots).leave_warning = False
        (self - assigned_slots).is_absent = False

        if not assigned_slots:
            return

        min_date = min(assigned_slots.mapped('start_datetime'))
        date_from = min_date if min_date > fields.Datetime.today() else fields.Datetime.today()
        leaves = self.env['hr.leave']._get_leave_interval(
            date_from=date_from,
            date_to=max(assigned_slots.mapped('end_datetime')),
            employee_ids=assigned_slots.mapped('employee_ids')
        )

        for slot in assigned_slots:
            warnings = []
            for employee in slot.employee_ids:
                slot_leaves = leaves.get(employee.id)
                if slot_leaves:
                    warning = self.env['hr.leave']._get_leave_warning(
                        leaves=slot_leaves,
                        employee=employee,
                        date_from=slot.start_datetime,
                        date_to=slot.end_datetime
                    )
                    if warning:
                        warnings.append(warning)
            slot.leave_warning = '\n'.join(warnings) if warnings else False
            slot.is_absent = bool(warnings)

    @api.model
    def _search_is_absent(self, operator, value):
        if operator not in ('in', 'not in'):
            return NotImplemented

        today = fields.Datetime.today()
        slots = self.search([
            ('resource_ids.resource_type', '=', 'user'),
            ('end_datetime', '>', today),  # only fetch the slots containing today in their period or shifts in the future
            ('state', '!=', '4_completed'),
        ])
        if not slots:
            return Domain.FALSE if operator == 'in' else Domain.TRUE

        min_date = min(slots.mapped('start_datetime'))
        date_from = max(min_date, today)
        mapped_leaves = self.env['hr.leave']._get_leave_interval(
            date_from=date_from,
            date_to=max(slots.mapped('end_datetime')),
            employee_ids=slots.employee_ids,
        )

        slot_ids = []
        for slot in slots:
            employees = slot.employee_ids
            for employee in employees:
                if employee.id in mapped_leaves:
                    leaves = mapped_leaves[employee.id]
                    period = self.env['hr.leave']._group_leaves(leaves, employee, slot.start_datetime, slot.end_datetime)
                    if period:
                        slot_ids.append(slot.id)
                        break
        return [('id', operator, slot_ids)]

    def _get_needs_attention_domain(self):
        return super()._get_needs_attention_domain() | Domain('is_absent', '=', True)
