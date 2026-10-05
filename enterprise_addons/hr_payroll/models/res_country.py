# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResCountry(models.Model):
    _inherit = 'res.country'

    def _get_work_entry_type_by_code_country(self):
        return {
            code: work_entry_types.grouped('country_id')
            for code, work_entry_types in self.env['hr.work.entry.type'].search([]).grouped('code').items()
        }

    def _adapt_work_entry_types_to_country(self):
        self.ensure_one()
        companies = self.env['res.company'].search([]).filtered(lambda c: c.country_id == self)
        work_entry_type_by_code_country = self._get_work_entry_type_by_code_country()

        # Update existing resource.calendar.attendance to use country specific work entry types
        company_calendars = self.env['resource.calendar'].search([('company_id', 'in', companies.ids)])
        generic_resource_attendances = company_calendars.attendance_ids.filtered(lambda a: a.work_entry_type_id and not a.work_entry_type_id.country_id)
        for attendance in generic_resource_attendances:
            attendance.work_entry_type_id = work_entry_type_by_code_country[attendance.work_entry_type_id.code].get(self, attendance.work_entry_type_id)

        # Update existing hr.leave.allocation to use country specific work entry types
        company_allocation = self.env['hr.leave.allocation'].search([('employee_company_id', 'in', companies.ids)])
        generic_allocation = company_allocation.filtered(lambda a: not a.work_entry_type_id.country_id)
        for allocation in generic_allocation:
            allocation.write({
                'work_entry_type_id': work_entry_type_by_code_country[allocation.work_entry_type_id.code].get(self, allocation.work_entry_type_id)
            })

        # Update existing hr.structure.type to use country specific work entry types
        structure_types = self.env['hr.payroll.structure.type'].search([('country_id', '=', self.id)])
        generic_structure_types = structure_types.filtered(lambda s: not s.default_work_entry_type_id.country_id)
        for structure_type in generic_structure_types:
            structure_type.write({
                'default_work_entry_type_id': work_entry_type_by_code_country[structure_type.default_work_entry_type_id.code].get(self, structure_type.default_work_entry_type_id)
            })

        # Update existing hr.leave to use country specific work entry types
        company_time_off = self.env['hr.leave'].search([('company_id', 'in', companies.ids)])
        generic_time_off = company_time_off.filtered(lambda t: not t.work_entry_type_id.country_id)
        for time_off in generic_time_off:
            time_off.with_context(leave_skip_state_check=True, skip_allocation_check=True).write({
                'work_entry_type_id': work_entry_type_by_code_country[time_off.work_entry_type_id.code].get(self, time_off.work_entry_type_id)
            })
