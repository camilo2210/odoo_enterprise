# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Expenses in Payslips',
    'category': 'Human Resources/Payroll',
    'sequence': 95,
    'summary': 'Submit, validate and reinvoice employee expenses',
    'description': """
Reimbursement of expenses in Payslips
=====================================

This application allows you to reimburse expenses in payslips.
    """,
    'depends': ['hr_expense', 'hr_payroll_account'],
    'data': [
        'views/hr_expense_views.xml',
        'views/hr_payslip_views.xml',
        'views/product_product_views.xml',
        'wizard/account_payment_register_views.xml',
    ],
    'demo': ['data/hr_payroll_expense_demo.xml'],
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'hr_payroll_expense/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
