# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    ytd_balance_ids = fields.One2many("l10n_au.payslip.ytd", "employee_id", string="YTD Balances", groups="hr_payroll.group_hr_payroll_user")
    l10n_au_report_to_w3 = fields.Boolean(readonly=False, related="version_id.l10n_au_report_to_w3", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    def _get_fiscal_year_data(self, date_start: date, date_end: date, finalised=None):
        """ Returns the payslip ids and YTD balance ids for the employee
            in the given fiscal year (date_start to date_end).
            If finalised is True/False, only returns payslips/YTD balances
            that are finalised/not finalised. If finalised is None, returns all payslips/YTD balances.
        """
        self.ensure_one()
        finalised = [True, False] if finalised is None else [finalised]
        payslip_ids = self.slip_ids.filtered_domain([
            ('date_from', '>=', date_start),
            ('date_from', '<=', date_end),
            ('state', 'in', ('validated', 'paid')),
            ('l10n_au_finalised', 'in', finalised)
        ])

        ytd_balance_ids = self.env['l10n_au.payslip.ytd'].search([
            ('employee_id', '=', self.id),
            ('start_date', '=', date_start),  # Start date is always set to the start of fiscal year
            ('finalised', 'in', finalised)
        ])

        return payslip_ids.ids, ytd_balance_ids.ids
