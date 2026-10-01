# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, time, timedelta

from odoo import models
from odoo.fields import Domain


class HrEmployeeDeparture(models.Model):
    _inherit = 'hr.employee.departure'

    def action_register(self):
        departure_per_date = self.grouped(lambda d: datetime.combine(d.departure_date, time.max))
        departure_domain = Domain.OR([
            ('resource_ids', 'in', deps.employee_id.resource_id.ids),
            ('end_datetime', '>', d_date),
        ] for d_date, deps in departure_per_date.items())
        planning_slots_sudo = self.env['planning.slot'].sudo().search(departure_domain)
        res = super().action_register()
        for d_date, deps in departure_per_date.items():
            slots_sudo = planning_slots_sudo.filtered(lambda p_s: any(emp in deps.employee_id for emp in p_s.with_context(active_test=False).employee_ids))
            if slots_sudo:
                slots_sudo._manage_archived_resources(self.employee_id.resource_id, datetime.combine(d_date + timedelta(days=1), time.min))
        return res
