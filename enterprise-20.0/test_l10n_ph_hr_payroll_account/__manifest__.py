# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Test Philippines Payroll',
    'category': 'Human Resources',
    'summary': 'Test Philippines Payroll',
    'depends': [
        'l10n_ph_hr_payroll_account',
        'hr_holidays_attendance',
    ],
    'author': 'Odoo S.A.',
    'post_init_hook': '_generate_payslips',
    'license': 'OEEL-1',
}
