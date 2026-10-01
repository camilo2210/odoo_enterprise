# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.fields import Domain, parse_field_expr


class HrLeaveReportCalendar(models.Model):
    _inherit = "hr.leave.report.calendar"

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        return self.env['hr.leave']._gantt_unavailability(field, res_ids, start, stop, scale)

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        """
        We override get_gantt_data to allow the display of emloyees that don't have any leaves
        when the view is grouped only by employee and no leave filters are applied.
        """
        domain = Domain(domain)
        # domain created from the user's filter input in the search bar
        user_domain = Domain(self.env.context.get('user_domain') or Domain.TRUE)

        def _is_entirely_employee_domain(domain):
            domain = Domain(domain)
            return all(c.field_expr == 'employee_id' for c in domain.optimize_full(self).iter_conditions())

        # This model uses a SQL view, so these fields are not stored here directly.
        # We map them when extracting the employee domain.
        field_map = {
            'job_id': 'employee_id.current_version_id.job_id',
            'company_id': 'employee_id.company_id',
        }

        def map_to_employee_field(condition):
            field_name, rest = parse_field_expr(condition.field_expr)
            field_name = field_map.get(field_name, field_name)
            field_expr = f'{field_name}.{rest}' if rest else field_name
            return Domain(field_expr, condition.operator, condition.value)

        user_domain = user_domain.map_conditions(map_to_employee_field)
        if groupby == ['employee_id'] and _is_entirely_employee_domain(user_domain):
            # search is only about employees, we can also display the employees
            # without any leaves in the gantt view
            return self._get_gantt_data_with_empty(
                super(HrLeaveReportCalendar, self.with_context(scale=scale)).get_gantt_data,
                domain.map_conditions(map_to_employee_field),
                groupby, read_specification, limit=limit,
                offset=offset, unavailability_fields=unavailability_fields,
                progress_bar_fields=progress_bar_fields, start_date=start_date,
                stop_date=stop_date, scale=scale,
            )
        return super(HrLeaveReportCalendar, self.with_context(scale=scale)).get_gantt_data(domain, groupby, read_specification, limit, offset, unavailability_fields, progress_bar_fields, start_date, stop_date, scale)
