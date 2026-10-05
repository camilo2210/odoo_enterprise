from dateutil.relativedelta import relativedelta
from odoo.tools import float_round

from odoo import api, fields, models
from odoo.tools import SQL


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    billable_time_target = fields.Float("Billable Target", groups="hr_timesheet.group_hr_timesheet_user")
    show_billable_time_target = fields.Boolean(related="company_id.timesheet_show_rates")

    @api.model
    def get_all_billable_time_targets(self):
        if self.env.user.has_group("hr_timesheet.group_hr_timesheet_user") and self.env.company.timesheet_show_rates:
            return self.sudo().search_read([("company_id", "=", self.env.company.id)], ["billable_time_target"])
        return []

    _check_billable_time_target = models.Constraint(
        'CHECK(billable_time_target >= 0)',
        "The billable time target cannot be negative.",
    )

    def _get_timesheets_and_billable_working_hours_query(self, employee_ids, from_date, to_date):
        return SQL("""
            SELECT aal.employee_id AS employee_id, COALESCE(SUM(aal.unit_amount), 0) AS worked_hours
              FROM account_analytic_line aal
             WHERE aal.employee_id IN %s AND date >= %s AND date <= %s AND project_id IS NOT NULL
               AND aal.billable_type IN ('02_billable_fixed', '04_billable_time', '06_billable_milestones', '08_billable_manual')
          GROUP BY aal.employee_id
        """, tuple(employee_ids), from_date, to_date)

    @api.model
    def get_timesheet_target_show_rates_value(self):
        """
        Method called by the timesheet avatar widget on the frontend in gridview to get the
        timesheet target limit indicator value.

        :return: boolean indicating if the billing target is set or not
        """
        return self.env.company.timesheet_show_rates

    def get_timesheet_and_target_hours_for_employees(self, date_start, date_stop):
        """
        Method called by the timesheet avatar widget on the frontend in gridview to get information
        about the hours employees have billed and the billing target.

        :param date_start: date start of the interval to search (included)
        :param date_stop: date stop of the interval to search (included)
        :return: Dictionary of dictionary
                 for each employee id (integer) =>
                    {
                        units_to_work: number of target units to bill,
                        uom: what unit type are we using,
                        worked_hours: the number of billed units by the employees
                    }
        """

        if not self.get_timesheet_target_show_rates_value():
            return {}

        # make date_start and date_stop to always be at the start and end of the month
        date_start = fields.Date.to_date(date_start).replace(day=1)
        date_stop = fields.Date.to_date(date_stop) + relativedelta(day=31)
        month = date_start.strftime('%B')

        uom = self.env.company.timesheet_encode_uom_id
        result = {}
        query = self._get_timesheets_and_billable_working_hours_query(self.ids, date_start, date_stop)
        rows = self.env.execute_query_dict(query)
        for data_row in rows:
            worked_hours = data_row['worked_hours']
            employee = self.browse(data_row['employee_id'])
            billing_time_target = employee.billable_time_target

            if uom == self.env.ref('uom.product_uom_day'):
                calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
                rounding = self.env['decimal.precision'].precision_get('Product Unit')
                worked_hours = float_round(worked_hours / calendar.hours_per_day, precision_digits=rounding)
                billing_time_target = float_round(employee.billable_time_target / calendar.hours_per_day, precision_digits=rounding)

            result[employee.id] = {
                'units_to_work': billing_time_target,
                'uom': uom.name,
                'worked_hours': worked_hours,
                'month': month,
            }

        return result


class HREmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    billable_time_target = fields.Float(compute='_compute_billable_time_target')
    show_billable_time_target = fields.Boolean(compute='_compute_billable_time_target')

    def _compute_billable_time_target(self):
        self._compute_from_employee('billable_time_target')
        self._compute_from_employee('show_billable_time_target')
