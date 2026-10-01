from odoo import models
from odoo.addons.mail.tools.discuss import Store


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _store_avatar_card_fields(self, res: Store.FieldList):
        super()._store_avatar_card_fields(res)
        res.attr("avatar_leave_summary", lambda employee: employee._get_avatar_leave_summary())
        res.attr("avatar_hours_per_week", lambda employee: employee.resource_calendar_id.hours_per_week)

    def _get_avatar_leave_summary(self):
        self.ensure_one()
        if not self.env.user.has_groups('hr.group_hr_user'):
            return []

        valid_work_entry_types = self.env['hr.work.entry.type'].search([
            '|',
                ('country_id', 'in', self.company_id.country_id.ids),
                ('country_id', '=', False),
        ])

        # _store_avatar_card_fields is called with sudo causing the time off data to be visible for all users
        # Use sudo=False to avoid showing leave data to unauthorized users
        consumed_leaves, _ = self.sudo(False)._get_consumed_leaves(valid_work_entry_types)

        leaves_summary = []
        for work_entry_type, allocations in consumed_leaves.get(self, {}).items():
            leaves_taken = 0
            remaining_leaves = 0
            max_leaves = 0
            primary_unit = 'hours' if work_entry_type.unit_of_measure == 'hour' else 'days'

            for allocation in allocations.values():
                leaves_taken += allocation[f'{primary_unit}_leaves_taken']
                remaining_leaves += allocation[f'{primary_unit}_remaining_leaves']
                max_leaves += allocation[f'{primary_unit}_max_leaves']

            if max_leaves > 0 or leaves_taken > 0:
                leaves_summary.append({
                    'display_name': work_entry_type.name,
                    'leaves_taken': leaves_taken,
                    'remaining_leaves': remaining_leaves,
                    'requires_allocation': work_entry_type.requires_allocation,
                    'max_leaves': max_leaves,
                    'unit': self.env._('days') if work_entry_type.unit_of_measure == 'day' else self.env._('hours'),
                })

        return sorted(leaves_summary, key=lambda x: x['remaining_leaves'])

    def get_employee_available_leave_types(self):
        '''
        Returns work entry types that are valid for the employee, all types that do not require allocation
        and all types that require allocation with available allocations.
        If no employee is passed, only return work entry types that do not require allocation, since those
        are valid for all employees.
        '''
        country_id = self.env.company.country_id.id

        def _create_leave_dict(work_entry_type, remaining=0.0, allocated=0.0, taken=0.0):
            return {
                'id': work_entry_type.id,
                'sequence': work_entry_type.sequence,
                'name': work_entry_type.name,
                'color': work_entry_type.color,
                'display_code': work_entry_type.display_code,
                'remaining_leaves': remaining,
                'allocated_leaves': allocated,
                'leaves_taken': taken,
                'requires_allocation': work_entry_type.requires_allocation,
                'unit': self.env._('days') if work_entry_type.unit_of_measure == 'day' else self.env._('hours'),
            }

        domain = ['&', ('country_id', '=', country_id), ('time_off_selectable', '=', True)]
        if not self:
            domain.append(('requires_allocation', '=', False))

        all_types = self.env['hr.work.entry.type']._read_group(domain, ['requires_allocation', 'code'], ['id:recordset'])
        no_allocation_types = {}
        allocation_work_entry_types = self.env['hr.work.entry.type']
        for requires_allocation, code, work_entry_types in all_types:
            if requires_allocation:
                allocation_work_entry_types |= work_entry_types
            else:
                no_allocation_types[code] = _create_leave_dict(work_entry_types[0])

        if not self:
            return sorted(no_allocation_types.values(), key=lambda x: x['sequence'])

        consumed_leaves, _ = self._get_consumed_leaves(allocation_work_entry_types)
        allocated_types = {}
        for work_entry_type, allocations in consumed_leaves.get(self, {}).items():
            primary_unit = 'hours' if work_entry_type.unit_of_measure == 'hour' else 'days'
            remaining = sum(a[f'{primary_unit}_virtual_remaining_leaves'] for a in allocations.values())
            allocated = sum(a[f'{primary_unit}_max_leaves'] for a in allocations.values())
            taken = sum(a[f'{primary_unit}_leaves_taken'] for a in allocations.values())

            if allocated > 0:
                allocated_types[work_entry_type.id] = _create_leave_dict(work_entry_type, remaining, allocated, taken)

        return sorted(list(allocated_types.values()) + list(no_allocation_types.values()), key=lambda x: x['sequence'])
