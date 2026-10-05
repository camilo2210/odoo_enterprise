# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from odoo import api, models
from odoo.tools.misc import ZoneInfo


class ResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    def action_open_multi_allocations_wizard(self):
        """
        Check if a public holiday falls outside the company's working schedule
        and open the allocation wizard pre-filled with the compensation data.
        """
        public_holiday_compensation_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_phc', raise_if_not_found=False)
        if not public_holiday_compensation_type:
            return False

        for leave in self.filtered(lambda leave: not leave.resource_id):
            company = leave.company_id or self.env.company
            if company.country_id.code != 'BE':
                continue

            user_tz = ZoneInfo(self.env.user.tz or 'UTC')
            leave_date_from = leave.date_from.astimezone(user_tz).date()
            leave_date_to = leave.date_to.astimezone(user_tz).date()

            non_working_days = 0
            current_date = leave_date_from
            while current_date <= leave_date_to:
                if not company.resource_calendar_id._works_on_date(current_date):
                    non_working_days += 1
                current_date += timedelta(days=1)

            if not non_working_days:
                continue

            allocation_date_from = leave.date_to.date().replace(day=1)
            allocation_date_to = leave.date_to.date().replace(month=12, day=31)

            view_id = self.env.ref('l10n_be_hr_payroll.hr_leave_allocation_generate_multi_wizard_view_form_inherit_l10n_be_hr_payroll').id
            return {
                'name': self.env._("Public Holiday Compensation"),
                'type': 'ir.actions.act_window',
                'res_model': 'hr.leave.allocation.generate.multi.wizard',
                'view_mode': 'form',
                'views': [(view_id, 'form')],
                'target': 'new',
                'context': {
                    'default_public_holiday_id': leave.id,
                    'default_work_entry_type_id': public_holiday_compensation_type.id,
                    'default_duration': non_working_days,
                    'default_company_id': company.id,
                    'default_date_from': allocation_date_from.isoformat(),
                    'default_date_to': allocation_date_to.isoformat(),
                },
            }
        return False

    @api.ondelete(at_uninstall=False)
    def _unlink_public_holiday_compensation_allocations(self):
        public_holiday_compensation_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_phc', raise_if_not_found=False)
        public_holiday_leaves = self.filtered(lambda rcl: not rcl.resource_id)
        if not (public_holiday_compensation_type and public_holiday_leaves):
            return

        allocations = self.env['hr.leave.allocation'].sudo().search([
            ('work_entry_type_id', '=', public_holiday_compensation_type.id),
            ('public_holiday_id', 'in', self.ids),
        ])
        allocations.action_refuse()
        allocations.unlink()
