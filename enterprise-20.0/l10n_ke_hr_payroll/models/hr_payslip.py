# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from dateutil.relativedelta import relativedelta

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _l10n_ke_is_employee_at_least_60(self):
        """The employee is at least 60 years old (and payslip should be in next month)"""
        self.ensure_one()
        employee = self.employee_id
        # The last day of the 1 month before the payslip's start date is the reference date for being 60 years old
        # Because if the employee becomes 60 at 20 Feb. 2026, the payslips start date should be at least 1st of March 2026 (next month)
        last_date_for_being_60 = self.date_from + relativedelta(day=1, days=-1)
        return employee._get_age(last_date_for_being_60) >= 60

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_ke_hr_payroll', [
                'data/hr_salary_rule_category_data.xml',
                'data/hr_payroll_structure_type_data.xml',
                'data/hr_payroll_structure_data.xml',
                'data/hr_rule_parameters_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]
