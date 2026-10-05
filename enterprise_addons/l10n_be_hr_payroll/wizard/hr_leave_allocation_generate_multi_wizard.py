# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import fields, models
from odoo.fields import Domain
from odoo.tools import float_round


class HrLeaveAllocationGenerateMultiWizard(models.TransientModel):
    _inherit = 'hr.leave.allocation.generate.multi.wizard'

    public_holiday_id = fields.Many2one('resource.calendar.leaves', string='Public Holiday', readonly=True)

    def _get_employee_domain(self):
        domain = super()._get_employee_domain()
        if not self.public_holiday_id:
            return domain
        leave = self.public_holiday_id
        versions = self.env['hr.version'].search([
            ('l10n_be_worker_code_id', '!=', False),
            ('contract_date_start', '<=', leave.date_to.date()),
            '|',
            ('contract_date_end', '=', False),
            ('contract_date_end', '>=', leave.date_from.date()),
        ])
        return Domain.AND([domain, [
            ('active', '=', True),
            ('id', 'in', versions.employee_id.ids),
        ]])

    def _prepare_allocation_values(self, employees):
        self.ensure_one()
        if not self.public_holiday_id:
            return super()._prepare_allocation_values(employees)

        leave = self.public_holiday_id
        company = leave.company_id or self.env.company

        existing = self.env['hr.leave.allocation'].search([
            ('work_entry_type_id', '=', self.work_entry_type_id.id),
            ('public_holiday_id', '=', leave.id),
            ('employee_id', 'in', employees.ids),
        ])
        already_allocated_employees = existing.mapped('employee_id')
        employees = employees - already_allocated_employees

        result = []
        for employee in employees:
            days = 0
            for version in employee.version_ids:
                overlap_start = max(leave.date_from.date(), version.contract_date_start)
                overlap_end = min(
                    leave.date_to.date(),
                    version.contract_date_end or leave.date_to.date(),
                )
                if overlap_end < overlap_start:
                    continue
                current_date = overlap_start
                while current_date <= overlap_end:
                    if not company.resource_calendar_id._works_on_date(current_date):
                        days += 1
                    current_date += timedelta(days=1)

            if not days:
                continue

            self._adjust_allocation_name(days)
            result.append({
                'name': self.name,
                'work_entry_type_id': self.work_entry_type_id.id,
                'number_of_days': days,
                'employee_id': employee.id,
                'state': 'confirm',
                'date_from': self.date_from,
                'date_to': self.date_to,
                'accrual_plan_id': self.accrual_plan_id.id,
                'notes': self.notes,
                'public_holiday_id': leave.id,
            })
        return result

    def _adjust_allocation_name(self, days):
        if float_round(self.duration, precision_digits=2) != days:
            self.name = self.env._(
                '%(name)s (%(duration)s %(unit_of_measure)s(s))',
                name=self.work_entry_type_id.name,
                duration=float_round(days, precision_digits=2),
                unit_of_measure=self.unit_of_measure
            )
