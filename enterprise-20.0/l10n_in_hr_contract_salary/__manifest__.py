# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Salary Configurator (India)',
    'category': 'Human Resources',
    'summary': 'Salary Configuration',
    'depends': [
        'hr_contract_salary',
        'l10n_in_hr_payroll',
    ],
    'data': [
        'data/l10n_in_hr_contract_salary_personal_info_data.xml',
        'data/l10n_in_hr_contract_salary_benefit_data.xml',
        'data/l10n_in_hr_contract_salary_resume_data.xml',
    ],
    'demo': [
        'data/l10n_in_hr_contract_salary_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
    'assets': {
        'web.assets_frontend': [
            'l10n_in_hr_contract_salary/static/src/js/hr_contract_salary.js',
        ],
    },
}
