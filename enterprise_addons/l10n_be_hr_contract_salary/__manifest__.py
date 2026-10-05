# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Salary Configurator (Belgium)',
    'version': '1.1',
    'category': 'Human Resources',
    'summary': 'Salary Package Configurator',
    'depends': [
        'hr_contract_salary',
        'l10n_be_hr_payroll',
    ],
    'data': [
        'data/hr_contract_salary_benefit_data.xml',
        'data/hr_contract_salary_resume_data.xml',
        'data/hr_contract_salary_personal_info_data.xml',
        'views/hr_contract_salary_template.xml',
        'views/hr_contract_salary_offer_views.xml',
        'views/hr_fleet_state_views.xml',
        'views/hr_employee_views.xml',
    ],
    'demo': [
        'data/l10n_be_hr_contract_salary_demo.xml',
        # 'data/hr_contract_salary_benefit_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
    'assets': {
        'web.assets_frontend': [
            'l10n_be_hr_contract_salary/static/src/**/*',
        ],
        'web.assets_tests': [
            'l10n_be_hr_contract_salary/static/tests/**/*',
        ]
    },
    'other_files': [
        'data/hr_contract_salary_benefit_demo.xml',
    ],
}
