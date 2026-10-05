# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "SEPA Payments for Payroll",
    'summary': "Pay your employees with SEPA payment.",
    'category': 'Human Resources/Payroll',
    'depends': ['hr_payroll', 'account_iso20022'],
    'data': [
        'views/hr_payslip_run_views.xml',
        'data/hr_payroll_warning_data.xml',
        'wizard/hr_payroll_payment_report_wizard.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'uninstall_hook': '_hr_payroll_account_iso20022_uninstall_hook',
    'assets': {
        'web.assets_backend': [
            'hr_payroll_account_iso20022/static/src/**/*.scss',
        ],
    },
}
