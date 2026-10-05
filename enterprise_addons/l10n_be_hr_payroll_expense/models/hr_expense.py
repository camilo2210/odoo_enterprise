# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from collections import defaultdict
from datetime import date

from odoo import api, fields, models, _


class HrExpense(models.Model):
    _inherit = "hr.expense"

    l10n_be_is_mobility_expense = fields.Boolean(compute="_compute_l10n_be_is_mobility_expense")
    l10n_be_mobility_budget_remaining_month = fields.Monetary(compute="_compute_l10n_be_mobility_budget_info")
    l10n_be_mobility_budget_remaining_year = fields.Monetary(compute="_compute_l10n_be_mobility_budget_info")

    @api.depends("product_id", "company_id")
    def _compute_l10n_be_is_mobility_expense(self):
        for expense in self:
            if expense.product_id and expense.company_id.l10n_be_mobility_expense_category_ids:
                expense.l10n_be_is_mobility_expense = expense.product_id in expense.company_id.l10n_be_mobility_expense_category_ids
            else:
                expense.l10n_be_is_mobility_expense = False

    @api.depends("l10n_be_is_mobility_expense", "employee_id", "total_amount", "state")
    def _compute_l10n_be_mobility_budget_info(self):
        self.l10n_be_mobility_budget_remaining_month = 0.0
        self.l10n_be_mobility_budget_remaining_year = 0.0

        mobility_expenses = self.filtered(lambda e: e.l10n_be_is_mobility_expense and e.employee_id and e.date)
        if not mobility_expenses:
            return

        employees = mobility_expenses.employee_id
        dates = mobility_expenses.mapped('date')
        date_start = min(dates).replace(month=1, day=1)
        date_end = max(dates).replace(month=12, day=31)

        paid_by_year, paid_by_month = employees._get_l10n_be_paid_mobility_amounts(date_start=date_start, date_end=date_end)

        # Compute yearly entitlement once per year/reference date.
        employees_by_year = defaultdict(lambda: self.env['hr.employee'])

        for expense in mobility_expenses:
            employees_by_year[expense.date.year] |= expense.employee_id

        prorated_budgets = {}

        for year, employees in employees_by_year.items():
            amounts = employees.sudo()._get_l10n_be_mobility_budget_amount_prorated(reference_date=date(year, 12, 31), year=year)

            for employee_id, amount in amounts.items():
                prorated_budgets[employee_id, year] = amount

        for expense in mobility_expenses:
            employee = expense.employee_id
            version = employee.sudo()._get_version(date=expense.date)

            if not version or not version.l10n_be_mobility_budget:
                continue

            year = expense.date.year
            month = expense.date.month

            monthly_budget = version.l10n_be_mobility_budget_amount / 12
            yearly_budget = prorated_budgets.get((employee.id, year), 0.0)

            spent_month = paid_by_month.get((employee.id, year, month), 0.0)
            spent_year = paid_by_year.get((employee.id, year), 0.0)

            expense.l10n_be_mobility_budget_remaining_month = (monthly_budget - spent_month)
            expense.l10n_be_mobility_budget_remaining_year = (yearly_budget - spent_year)

    def action_open_monthly_expenses(self):
        self.ensure_one()
        if not self.employee_id or not self.date:
            return {}
        today = self.date
        month_start = today.replace(day=1)
        month_end = month_start + relativedelta(months=+1, days=-1)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Monthly Mobility Expenses"),
            "res_model": "hr.expense",
            "view_mode": "list,form",
            "domain": [
                ("employee_id", "=", self.employee_id.id),
                (
                    "product_id",
                    "in",
                    self.company_id.l10n_be_mobility_expense_category_ids.ids,
                ),
                ("state", "in", ["approved", "posted", "in_payment", "paid"]),
                ("date", ">=", month_start),
                ("date", "<=", month_end),
            ],
        }
        return action

    def action_open_yearly_expenses(self):
        self.ensure_one()
        if not self.employee_id or not self.date:
            return {}
        employee = self.employee_id
        version = employee.sudo().current_version_id
        if not version or not version.date_version:
            return {}
        period_start = max(self.date.replace(month=1, day=1), version.date_version)
        period_end = self.date.replace(month=12, day=31)

        action = {
            "type": "ir.actions.act_window",
            "name": _("Yearly Mobility Expenses"),
            "res_model": "hr.expense",
            "view_mode": "list,form",
            "domain": [
                ("employee_id", "=", employee.id),
                (
                    "product_id",
                    "in",
                    self.company_id.l10n_be_mobility_expense_category_ids.ids,
                ),
                ("state", "in", ["approved", "posted", "in_payment", "paid"]),
                ("date", ">=", period_start),
                ("date", "<=", period_end),
            ],
            "context": {"default_employee_id": employee.id},
        }
        return action
