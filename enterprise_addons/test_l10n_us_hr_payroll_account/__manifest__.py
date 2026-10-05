# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'United States - Test Payroll',
    'category': 'Human Resources',
    'summary': 'Test US Payroll',
    'depends': [
        'l10n_us_hr_payroll',
        'l10n_us_hr_payroll_account',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': 'generate_payslips',
}
