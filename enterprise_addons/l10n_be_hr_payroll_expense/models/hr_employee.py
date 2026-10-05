# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import date

from odoo import api, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _get_mobility_expense_totals(self):
        """
        Get aggregated mobility expenses by employee and month.
        Returns a dict: {employee_id: {year_month: total_amount}}
        """
        if not self:
            return {}

        companies = self.mapped("company_id")
        all_product_ids = self.env["product.product"]
        for company in companies:
            all_product_ids |= company.l10n_be_mobility_expense_category_ids

        if not all_product_ids:
            return {}

        domain = [
            ("employee_id", "in", self.ids),
            ("product_id", "in", all_product_ids.ids),
            ("state", "in", ["approved", "posted", "in_payment", "paid"]),
        ]

        all_expenses_data = self.env['hr.expense'].search_read(
            domain, ["employee_id", "date", "total_amount"]
        )

        totals = defaultdict(lambda: defaultdict(float))
        for exp in all_expenses_data:
            emp_id = exp["employee_id"][0]
            year_month = exp["date"].strftime("%Y-%m")
            totals[emp_id][year_month] += exp["total_amount"]

        return totals

    def _get_l10n_be_paid_mobility_amounts(self, date_start, date_end):
        yearly_amounts, monthly_amounts = super()._get_l10n_be_paid_mobility_amounts(date_start, date_end)

        yearly_amounts = defaultdict(float, yearly_amounts)
        monthly_amounts = defaultdict(float, monthly_amounts)

        expense_totals = self._get_mobility_expense_totals()

        for employee in self:
            for year_month, amount in expense_totals.get(employee.id, {}).items():
                year, month = map(int, year_month.split('-'))
                expense_date = date(year, month, 1)

                if date_start <= expense_date <= date_end:
                    yearly_amounts[employee.id, year] += amount
                    monthly_amounts[employee.id, year, month] += amount

        return yearly_amounts, monthly_amounts
