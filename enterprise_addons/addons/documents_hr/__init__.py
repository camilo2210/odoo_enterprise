from . import models


def _documents_hr_post_init(env):
    active_companies = env['res.company'].search([])
    if employees_without_folder := env['hr.employee'].search(
        [('hr_employee_folder_id', '=', False), ('company_id', 'in', active_companies.ids)],
    ):
        employees_without_folder._generate_employee_documents_folders()
