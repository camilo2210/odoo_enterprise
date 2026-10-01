# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Test Belgian Payroll',
    'category': 'Human Resources',
    'summary': 'Test Belgian Payroll',
    'data': [
        'wizard/test_l10n_be_dmfa_sandbox_answer_views.xml',
        'wizard/test_l10n_be_multiple_payruns_views.xml',
        'views/hr_dmfa_views.xml',
        'security/ir.access.csv',
    ],
    'depends': [
        'hr_contract_salary',
        'l10n_be_hr_contract_salary',
        'l10n_be_hr_payroll_account',
        'l10n_be',
        'account_accountant',
        'hr_payroll_account_iso20022',
        'documents_hr_payroll',
        'documents_hr_recruitment',
        'hr_payroll_attendance',
        'documents_hr',
        'hr_skills',
    ],
    'demo': [
        'data/test_l10n_be_hr_payroll_account_demo.xml',
        'data/be_payroll_demo_data.xml',
    ],
    'post_init_hook': 'generate_payslips',
    'assets': {
        'web.assets_tests': [
            'test_l10n_be_hr_payroll_account/static/tests/**/*',
        ],
        'web.assets_backend': [
            'test_l10n_be_hr_payroll_account/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
