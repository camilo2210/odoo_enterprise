# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard


def _documents_hr_payroll_post_init(env):
    companies = env['res.company'].with_context(active_test=False).search([])
    companies._init_generate_employee_documents_main_folders()
    companies = companies.filtered('active')
    if employees_without_folder := env['hr.employee'].search([('company_id', 'in', companies.ids)]):
        employees_without_folder._generate_employee_documents_folders(skip_subfolders=True)
        for company, employees in employees_without_folder.grouped('company_id').items():
            employees.hr_employee_folder_id.action_update_access_rights(
                groups={company.documents_hr_payroll_group_id: ('edit', False)},
                no_propagation=True
            )
